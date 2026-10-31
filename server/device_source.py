"""Read-only access to an iPhone/iPad connected by USB, through Windows
Portable Devices (WPD) — see PLAN.md section 26.

The device is only ever opened with GENERIC_READ and this module has no
code path that writes, moves or deletes anything on it (AGENTS.md's "never
touch the phone" invariant). `tests/test_cable_import.py` keeps that true.

server/cable_import.py only depends on the small DeviceSource shape below,
so tests and tools/ui_preview.py can hand it a simulated phone instead.

Every COM object here belongs to the thread that created it: a worker wraps
its whole job in `com_thread()` and opens its own source. Nothing is shared
between the "analyze" and "copy" steps except plain DeviceItem values — WPD
object ids stay valid across sessions (confirmed against a real iPhone).
"""
from __future__ import annotations

import ctypes
import gc
import struct
import threading
from contextlib import contextmanager
from ctypes import POINTER, byref, c_ulong, c_void_p, c_wchar_p
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Iterator, Optional, Protocol

GENERIC_READ = 0x80000000
VT_DATE = 7
_ENUM_BATCH = 200

_OBJECT_PROPS = "{EF6B490D-5CD8-437A-AFFC-DA8B60EE4A3C}"
_DEVICE_PROPS = "{26D4979A-E643-4626-9E2B-736DC0C92FDC}"
_CLIENT_INFO = "{204E9F0C-2292-4080-9F42-40664E70F859}"
_RESOURCE_DEFAULT = "{E81E79BE-34F0-41BF-B53F-F1A06AE87842}"
# WPD_CONTENT_TYPE_FOLDER and WPD_CONTENT_TYPE_FUNCTIONAL_OBJECT
_CONTAINER_TYPES = {"{27E2E392-A111-48E0-AB0C-E17705A05F85}", "{99ED0160-17FF-4C44-9D98-1D7A6F941921}"}


class DeviceReadError(Exception):
    """The phone failed a read (locked, unplugged, or a transient WPD error).
    Deliberately NOT an OSError: server/cable_import.py treats OSError as a
    failure of the DESTINATION drive, which needs a different response."""


@dataclass(frozen=True)
class DeviceInfo:
    device_id: str
    name: str
    serial: Optional[str]
    ready: bool  # False: connected, but locked or "Trust this PC" not accepted yet


@dataclass(frozen=True)
class DeviceItem:
    object_id: str
    name: str
    size: int
    taken_at: Optional[str]  # naive local ISO date, same shape the Shortcut sends


class DeviceReader(Protocol):
    def read(self, n: int) -> bytes: ...
    def close(self) -> None: ...


class DeviceSource(Protocol):
    def list_items(
        self, on_progress: Optional[Callable[[int], None]] = None, cancel: Optional[threading.Event] = None,
    ) -> list[DeviceItem]: ...
    def open_reader(self, item: DeviceItem) -> DeviceReader: ...
    def reopen(self) -> None: ...
    def close(self) -> None: ...


def _comtypes():
    # Imported lazily: importing it starts COM on the calling thread, and
    # anyone who never presses the cable button should never pay for that.
    import comtypes
    import comtypes.client as client

    return comtypes, client, client.GetModule("portabledeviceapi.dll"), client.GetModule("portabledevicetypes.dll")


@contextmanager
def com_thread() -> Iterator[None]:
    comtypes, *_ = _comtypes()
    comtypes.CoInitialize()
    try:
        yield
    finally:
        gc.collect()  # release this thread's COM pointers while COM is still up
        comtypes.CoUninitialize()


def _key(fmtid: str, pid: int, key_type):
    from comtypes import GUID

    key = key_type()
    key.fmtid = GUID(fmtid)
    key.pid = pid
    return key


def _as_key(fn, key):
    # The two WPD type libraries each generate their own PROPERTYKEY class;
    # these raw methods only accept the one from their own library.
    return ctypes.pointer(fn.argtypes[0]._type_.from_buffer_copy(key))


def _take_string(pointer: c_wchar_p) -> Optional[str]:
    value = pointer.value
    if value is not None:
        ctypes.windll.ole32.CoTaskMemFree(ctypes.cast(pointer, c_void_p))
    return value


def _get_string(values, key) -> Optional[str]:
    fn = values._IPortableDeviceValues__com_GetStringValue
    pointer = c_wchar_p()
    fn(_as_key(fn, key), byref(pointer))
    return _take_string(pointer)


def _get_date(values, key) -> Optional[str]:
    fn = values._IPortableDeviceValues__com_GetValue
    variant = fn.argtypes[1]._type_()
    fn(_as_key(fn, key), byref(variant))
    raw = bytes(variant)
    if struct.unpack_from("<H", raw, 0)[0] != VT_DATE:
        return None
    days = struct.unpack_from("<d", raw, 8)[0]
    return (datetime(1899, 12, 30) + timedelta(days=days)).isoformat(timespec="seconds")


def _device_ids(manager) -> list[str]:
    fn = manager._IPortableDeviceManager__com_GetDevices
    count = c_ulong(0)
    fn(POINTER(c_wchar_p)(), byref(count))
    if not count.value:
        return []
    ids = (c_void_p * count.value)()
    fn(ctypes.cast(ids, POINTER(c_wchar_p)), byref(count))
    return [_take_string(ctypes.cast(ids[i], c_wchar_p)) for i in range(count.value)]


def _friendly_name(manager, device_id: str) -> str:
    fn = manager._IPortableDeviceManager__com_GetDeviceFriendlyName
    length = c_ulong(0)
    fn(device_id, POINTER(ctypes.c_ushort)(), byref(length))
    buffer = ctypes.create_unicode_buffer(length.value)
    fn(device_id, ctypes.cast(buffer, POINTER(ctypes.c_ushort)), byref(length))
    return buffer.value


class WpdSource:
    def __init__(self, device_id: str):
        self.device_id = device_id
        self._device = None
        self.unreadable = 0  # see list_items
        self._open()

    def _open(self) -> None:
        comtypes, client, api, types = _comtypes()
        self._api = api
        self._types = types
        info = client.CreateObject(
            types.PortableDeviceValues, clsctx=comtypes.CLSCTX_INPROC_SERVER, interface=types.IPortableDeviceValues,
        )
        self._key_type = (types if hasattr(types, "_tagpropertykey") else api)._tagpropertykey
        access_key = _key(_CLIENT_INFO, 4, self._key_type)  # WPD_CLIENT_DESIRED_ACCESS
        info.SetUnsignedIntegerValue(access_key, GENERIC_READ)
        device = client.CreateObject(
            api.PortableDevice, clsctx=comtypes.CLSCTX_INPROC_SERVER, interface=api.IPortableDevice,
        )
        device.Open(self.device_id, info)
        self._device = device
        self._content = device.Content()
        self._properties = self._content.Properties()
        self._resources = self._content.Transfer()
        self._keys = {
            name: _key(_OBJECT_PROPS, pid, self._key_type)
            for name, pid in {"content_type": 7, "size": 11, "name": 12, "created": 18, "modified": 19}.items()
        }
        self._key_collection = client.CreateObject(
            types.PortableDeviceKeyCollection, clsctx=comtypes.CLSCTX_INPROC_SERVER,
            interface=types.IPortableDeviceKeyCollection,
        )
        for key in self._keys.values():
            self._key_collection.Add(key)

    def _children(self, object_id: str) -> list[str]:
        enumerator = self._content.EnumObjects(0, object_id, None)
        fn = enumerator._IEnumPortableDeviceObjectIDs__com_Next
        out: list[str] = []
        while True:
            batch = (c_void_p * _ENUM_BATCH)()
            fetched = c_ulong(0)
            fn(_ENUM_BATCH, ctypes.cast(batch, POINTER(c_wchar_p)), byref(fetched))
            if not fetched.value:
                return out
            out += [_take_string(ctypes.cast(batch[i], c_wchar_p)) for i in range(fetched.value)]

    def _describe(self, object_id: str) -> Optional[tuple[bool, DeviceItem]]:
        values = self._properties.GetValues(object_id, self._key_collection)
        try:
            guid_fn = values._IPortableDeviceValues__com_GetGuidValue
            from comtypes import GUID

            content_type = GUID()
            guid_fn(_as_key(guid_fn, self._keys["content_type"]), byref(content_type))
        except Exception:
            return None
        if str(content_type).upper() in _CONTAINER_TYPES:
            # Checked before asking for a name: the phone's storage has none,
            # and skipping it would hide every file inside it.
            return True, DeviceItem(object_id, object_id, 0, None)
        try:
            name = _get_string(values, self._keys["name"]) or object_id
        except Exception:
            return None
        size = ctypes.c_ulonglong()
        try:
            size_fn = values._IPortableDeviceValues__com_GetUnsignedLargeIntegerValue
            size_fn(_as_key(size_fn, self._keys["size"]), byref(size))
        except Exception:
            return None
        taken_at = None
        for date_key in ("created", "modified"):
            try:
                taken_at = _get_date(values, self._keys[date_key])
            except Exception:
                taken_at = None
            if taken_at:
                break
        return False, DeviceItem(object_id, name, size.value, taken_at)

    def serial(self) -> Optional[str]:
        values = self._properties.GetValues("DEVICE", None)
        try:
            return _get_string(values, _key(_DEVICE_PROPS, 9, self._key_type))
        except Exception:
            return None

    def is_ready(self) -> bool:
        """A locked or not-yet-trusted iPhone shows up with no readable
        storage content at all."""
        try:
            return any(self._children(storage) for storage in self._children("DEVICE"))
        except Exception:
            return False

    def list_items(self, on_progress=None, cancel=None) -> list[DeviceItem]:
        """`unreadable` counts what the phone wouldn't describe (say, it locked
        midway), since a file left out silently would look like nothing missing."""
        self.unreadable = 0
        items: list[DeviceItem] = []
        stack = ["DEVICE"]
        try:
            while stack:
                for child in self._children(stack.pop()):
                    if cancel is not None and cancel.is_set():
                        return items
                    described = self._describe(child)
                    if described is None:
                        self.unreadable += 1
                        continue
                    is_container, item = described
                    if is_container:
                        stack.append(child)
                    else:
                        items.append(item)
                        if on_progress is not None:
                            on_progress(len(items))
        except Exception as exc:
            raise DeviceReadError(str(exc)) from exc
        return items

    def open_reader(self, item: DeviceItem) -> "_WpdReader":
        from comtypes import COMError

        if self._device is None:
            # A previous reopen failed (the phone was asleep, locked, or the PC
            # just woke up). This read is the next chance to reconnect.
            self.reopen()
        fn = self._resources._IPortableDeviceResources__com_GetStream
        key = ctypes.pointer(fn.argtypes[1]._type_.from_buffer_copy(_key(_RESOURCE_DEFAULT, 0, self._key_type)))
        optimal = c_ulong(0)
        stream = POINTER(self._api.IStream)()
        try:
            fn(item.object_id, key, 0, byref(optimal), byref(stream))  # 0: STGM_READ
        except COMError as exc:
            raise DeviceReadError(str(exc)) from exc
        return _WpdReader(stream)

    def reopen(self) -> None:
        self.close()
        try:
            self._open()
        except Exception as exc:
            raise DeviceReadError(str(exc)) from exc

    def close(self) -> None:
        device, self._device = self._device, None
        self._content = self._properties = self._resources = self._key_collection = None
        if device is not None:
            try:
                device.Close()
            except Exception:
                pass
        del device
        gc.collect()


class _WpdReader:
    """Must be closed before the next read. A stream left open made the real
    iPhone answer "resource in use" and then hand back the PREVIOUS file's
    bytes for the next request (confirmed 2026-10-30, PLAN.md section 26)."""

    def __init__(self, stream):
        self._stream = stream

    def read(self, n: int) -> bytes:
        from comtypes import COMError

        buffer = ctypes.create_string_buffer(n)
        got = c_ulong(0)
        fn = self._stream._ISequentialStream__com_RemoteRead
        try:
            fn(ctypes.cast(buffer, fn.argtypes[0]), n, byref(got))
        except COMError as exc:
            raise DeviceReadError(str(exc)) from exc
        return ctypes.string_at(buffer, got.value)

    def close(self) -> None:
        self._stream = None
        gc.collect()


def _looks_like_apple_device(name: str) -> bool:
    lowered = name.lower()
    return any(word in lowered for word in ("iphone", "ipad", "ipod"))


def find_devices() -> list[DeviceInfo]:
    """Blocking — call it from a background thread inside com_thread().
    Reports an unreadable device as not ready instead of raising, because
    "locked" is a normal state here, not an error."""
    comtypes, client, api, _types = _comtypes()
    manager = client.CreateObject(api.PortableDeviceManager, interface=api.IPortableDeviceManager)
    found: list[DeviceInfo] = []
    for device_id in _device_ids(manager):
        name = _friendly_name(manager, device_id)
        if not _looks_like_apple_device(name):
            continue
        serial, ready = None, False
        try:
            source = WpdSource(device_id)
            try:
                serial = source.serial()
                ready = source.is_ready()
            finally:
                source.close()
        except comtypes.COMError:
            pass
        found.append(DeviceInfo(device_id, name, serial, ready))
    return found


def open_source(device: DeviceInfo) -> WpdSource:
    return WpdSource(device.device_id)


if __name__ == "__main__":
    # Packaging probe: proves WPD works from a frozen build. Lists metadata only.
    with com_thread():
        devices = find_devices()
        print("devices:", [(d.name, bool(d.serial), d.ready) for d in devices])
        if devices and devices[0].ready:
            source = open_source(devices[0])
            found: list[DeviceItem] = []
            cancel = threading.Event()

            def _stop_early(count: int) -> None:
                if count >= 20:
                    cancel.set()

            found = source.list_items(_stop_early, cancel)
            reader = source.open_reader(found[0])
            data = b""
            while chunk := reader.read(1024 * 1024):
                data += chunk
            reader.close()
            print("first item bytes ok:", len(data) == found[0].size, "items sampled:", len(found))
            source.close()
