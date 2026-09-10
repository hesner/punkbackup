"""Entry point launched by the Desktop shortcut. Opens the dashboard GUI.
The backup server itself stays off until the user clicks "Iniciar backup"."""
import io
import sys

# Running via pythonw.exe (no console window, by design — see PLAN.md
# section 7) leaves sys.stdout/stderr as None. Several libraries (uvicorn's
# logging setup among them) assume a real stream and crash on that. Give
# them a harmless no-op stream instead of patching every call site.
if sys.stdout is None:
    sys.stdout = io.StringIO()
if sys.stderr is None:
    sys.stderr = io.StringIO()

from gui.main_window import main

if __name__ == "__main__":
    main()
