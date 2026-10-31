"""Cable mode's interface logic and palette: pure functions, no window needed.

Run with: .venv\\Scripts\\python.exe -m pytest tests -v
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from gui import theme
from gui.i18n import TRANSLATIONS
from gui.main_window import _cable_view_for
from server.cable_import import CableImportResult, CablePlan
from server.device_source import DeviceInfo, DeviceItem
from server.profiles import Profile

READY = DeviceInfo("id", "Apple iPhone", "SERIAL", True)
LOCKED = DeviceInfo("id", "Apple iPhone", "SERIAL", False)


def _profile(pid="a", destination="E:/x", enabled=True):
    return Profile(id=pid, name=pid, slug=pid, token="t", created_at="2026", enabled=enabled, destination_dir=destination)


def _flow(state, **extra):
    return {
        "profile_id": "a", "state": state, "scanned": 0, "plan": None, "device": READY, "done": 0, "total": 0,
        "failed": 0, "bytes": 0, "elapsed": 0, "result": None, "message": "", **extra,
    }


def _plan(pending=1, already=2, free=10**12):
    items = [DeviceItem(str(i), f"{i}.JPG", 1000, None) for i in range(pending)]
    return CablePlan(pending=items, already=already, total_on_device=pending + already, pending_bytes=1000 * pending, free_bytes=free)


def _actions(view):
    return [action for _label, action in view["actions"]]


def test_start_needs_a_ready_phone():
    assert _cable_view_for(_profile(), None, READY, "es")["start_enabled"] is True
    assert _cable_view_for(_profile(), None, LOCKED, "es")["start_enabled"] is False
    assert _cable_view_for(_profile(), None, None, "es")["start_enabled"] is False


def test_a_paused_profile_can_still_use_the_cable():
    assert _cable_view_for(_profile(enabled=False), None, READY, "es")["start_enabled"] is True


def test_a_profile_without_a_folder_says_why_it_cant_start():
    view = _cable_view_for(_profile(destination=None), None, READY, "es")
    assert view["start_enabled"] is False and "carpeta destino" in view["text"]


def test_only_one_copy_at_a_time():
    view = _cable_view_for(_profile("b"), _flow("copying", plan=_plan()), READY, "es")
    assert view["start_enabled"] is False and "otro perfil" in view["text"]


def test_another_profiles_finished_copy_doesnt_block():
    view = _cable_view_for(_profile("b"), _flow("done", result=CableImportResult()), READY, "es")
    assert view["start_enabled"] is True


def test_summary_offers_copy_and_nothing_is_copied_before_it():
    view = _cable_view_for(_profile(), _flow("summary", plan=_plan(pending=3)), READY, "es")
    assert _actions(view) == ["copy", "close"] and view["show_start"] is False
    assert "Por revisar: 3" in view["text"] and "3" in view["actions"][0][0]


def test_summary_with_nothing_pending_only_closes():
    view = _cable_view_for(_profile(), _flow("summary", plan=_plan(pending=0)), READY, "es")
    assert _actions(view) == ["close"] and view["tone"] == "ok"


def test_summary_warns_when_it_may_not_fit():
    view = _cable_view_for(_profile(), _flow("summary", plan=_plan(pending=2, free=10)), READY, "es")
    assert view["tone"] == "warn" and "libres" in view["text"]


def test_an_incomplete_analysis_never_says_all_backed_up():
    plan = _plan(pending=0)
    plan.unreadable = 2
    view = _cable_view_for(_profile(), _flow("summary", plan=plan), READY, "es")
    assert view["tone"] == "warn" and "incompleto" in view["text"]
    assert _actions(view) == ["start", "close"]


def test_copying_shows_confirmed_failed_and_can_stop():
    view = _cable_view_for(
        _profile(), _flow("copying", plan=_plan(pending=4), done=3, total=6, failed=1, bytes=2000, elapsed=2), READY, "es",
    )
    assert view["progress"] == 0.5 and _actions(view) == ["cancel"]
    assert "3 de 6 confirmados" in view["text"] and "1 fallidos" in view["text"]


def test_finished_with_failures_is_not_shown_as_a_clean_success():
    assert _cable_view_for(_profile(), _flow("done", result=CableImportResult(copied=5)), READY, "es")["tone"] == "ok"
    assert _cable_view_for(_profile(), _flow("done", result=CableImportResult(failed=1)), READY, "es")["tone"] == "warn"


def test_finished_message_points_to_wifi_for_icloud_originals():
    view = _cable_view_for(_profile(), _flow("done", result=CableImportResult()), READY, "es")
    assert "iCloud" in view["text"] and "Atajo" in view["text"]


def test_stopped_can_resume_or_close():
    view = _cable_view_for(_profile(), _flow("stopped", message="x"), READY, "es")
    assert _actions(view) == ["start", "close"] and view["text"] == "x"


def test_every_cable_text_exists_in_both_languages_and_renders():
    for key, texts in TRANSLATIONS.items():
        if "cable" in key or key.startswith("btn_mode") or key == "status_cable":
            assert set(texts) >= {"es", "en"}, key


def _luminance(color):
    channels = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    channels = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def _contrast(a, b):
    high, low = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


@pytest.mark.parametrize("text,background", [
    ("TEXT_MAIN", "BG"), ("TEXT_MAIN", "CARD_BG"), ("TEXT_MUTED", "CARD_BG"), ("TEXT_MUTED", "BG"),
    ("GREEN", "CARD_BG"), ("AMBER", "CARD_BG"), ("ACTION_INK", "ACTION"), ("ACCENT_INK", "ACCENT"), ("RED_INK", "RED"),
    ("HEADER_TITLE", "HEADER_BG"), ("HEADER_TEXT", "HEADER_BG"), ("CONTROL_TEXT", "CONTROL_BG"),
    ("MODE_BUTTON_INK", "MODE_BUTTON"), ("NAV_TEXT", "NAV_BG"),
])
def test_cable_palette_meets_the_contrast_minimum_for_text(text, background):
    assert _contrast(theme.XEROX[text], theme.XEROX[background]) >= 4.5


def test_cable_borders_stay_visible_against_paper():
    assert _contrast(theme.XEROX["BORDER"], theme.XEROX["BG"]) >= 3


def test_both_palettes_define_the_same_colors():
    assert set(theme.DARK) == set(theme.XEROX)
