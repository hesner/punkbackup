"""Runs the FastAPI app with uvicorn inside a background thread so the GUI's
own event loop / mainloop is never blocked, and so the server can be
started and stopped on demand (it must be 100% off until the user clicks
"Start" — see PLAN.md section 8)."""
from __future__ import annotations

import logging
import socket
import threading
import time

import uvicorn

# Same logger the GUI's queue handler listens to — a bind failure inside
# the background thread below used to be totally invisible: under
# pythonw.exe, sys.stderr is redirected to an in-memory buffer nobody
# ever reads (see main.py), so a silently-dead server thread left the GUI
# showing "Escuchando..." while nothing was actually listening at all
# (confirmed on a real device: "Could not connect to the server", with
# netstat showing nothing bound to the port). Routing it through this
# logger instead means it shows up in the activity log for free.
logger = logging.getLogger("backup_engine")


class ServerController:
    def __init__(self, app, host: str = "0.0.0.0", port: int = 8787):
        self.host = host
        self.port = port
        self._app = app
        self._config: uvicorn.Config | None = None
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None
        self.start_error: str | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def actually_listening(self) -> bool:
        """Whether uvicorn has really finished binding the socket — as
        opposed to `running`, which is only "the thread hasn't died yet"
        and stays True for a while even during/just-after a failed bind."""
        return bool(self._server is not None and getattr(self._server, "started", False))

    def _run(self) -> None:
        try:
            self._server.run()
        except BaseException as exc:
            # BaseException, not Exception: uvicorn's own bind-failure path
            # calls sys.exit(1) on a port conflict/permission error, which
            # raises SystemExit — a plain `except Exception` would miss it
            # entirely, letting the thread die silently (confirmed: this is
            # exactly what happened on a real device, port never bound, GUI
            # never found out). A non-main thread's uncaught exception
            # doesn't crash the process either way, so catching broadly
            # here is safe and only used to surface *why* it failed.
            self.start_error = str(exc) or type(exc).__name__
            logger.error("ERROR: the backup server failed to start (port %s): %s", self.port, self.start_error)

    def _preflight_bind_error(self) -> str | None:
        """Tries a plain socket bind first, synchronously, so a port
        conflict gets a real, specific message (e.g. "[WinError 10048]
        Only one usage of each socket address...") instead of just "1" —
        which is all `str(SystemExit(1))` gives, since that's the generic
        way uvicorn's own bind-failure path exits (see _run() above).
        Closed immediately either way; uvicorn does the real bind after
        this — a tiny race is possible but harmless, wait_until_listening()
        is still the ultimate source of truth."""
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            probe.bind((self.host, self.port))
        except OSError as exc:
            return str(exc)
        finally:
            probe.close()
        return None

    def start(self) -> None:
        if self.running:
            return
        self.start_error = self._preflight_bind_error()
        if self.start_error:
            logger.error("ERROR: the backup server failed to start (port %s): %s", self.port, self.start_error)
            return
        self._config = uvicorn.Config(
            self._app, host=self.host, port=self.port, log_level="warning",
            log_config=None,  # skip uvicorn's own logging setup — it assumes a real
            # console (calls sys.stdout.isatty()) and crashes under pythonw.exe,
            # where sys.stdout is None. The app has its own logger anyway.
        )
        self._server = uvicorn.Server(self._config)
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def wait_until_listening(self, timeout: float = 5.0) -> bool:
        """Blocks briefly after start() to confirm the socket actually
        bound, instead of the GUI just assuming success. Returns False on
        a real failure (port in use, permission denied, etc.) — check
        `start_error` for why."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.actually_listening:
                return True
            if not self.running:  # the thread already died — no point waiting out the timeout
                return False
            time.sleep(0.05)
        return self.actually_listening

    def stop(self, timeout: float = 5.0) -> None:
        if not self.running or self._server is None:
            return
        self._server.should_exit = True
        self._thread.join(timeout=timeout)

    def start_with_retry(self, attempts: int = 4, retry_delay: float = 2.0) -> bool:
        """Like start() + wait_until_listening(), but retries a few times
        on a transient bind failure before giving up.

        Covers a real, recurring case (confirmed on a real device,
        2026-09-18): some antivirus products — Avast in particular, see
        PLAN.md's "not code-signed" notes — intercept a freshly-launched
        unsigned exe, kill it, and relaunch it moments later. During that
        brief window Windows can still refuse to rebind the just-released
        port ([WinError 10048]) even though nothing is genuinely holding
        it anymore — confirmed the exact same port was free again just
        seconds later. A few short retries paper over that window instead
        of surfacing an error for something that resolves itself almost
        immediately.

        Blocking — call this from a background thread, not the GUI's own
        event-loop thread, and marshal the boolean result back via
        `after(0, ...)`."""
        for attempt in range(attempts):
            self.start()
            if self.wait_until_listening(timeout=5.0):
                return True
            self.stop()
            if attempt < attempts - 1:
                time.sleep(retry_delay)
        return False
