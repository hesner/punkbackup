"""One version number, one build (AGENTS.md section 3): the app and its installer
must always state the same number.

Run with: .venv\\Scripts\\python.exe -m pytest tests -v
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from server.version import APP_VERSION


def test_the_app_and_the_installer_state_the_same_version():
    installer = (ROOT / "installer" / "PunkBackup.iss").read_text(encoding="utf-8")
    assert re.search(r'#define MyAppVersion "([^"]+)"', installer).group(1) == APP_VERSION
