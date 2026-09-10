"""Runs the FastAPI app with uvicorn inside a background thread so the GUI's
own event loop / mainloop is never blocked, and so the server can be
started and stopped on demand (it must be 100% off until the user clicks
"Start" — see PLAN.md section 8)."""
from __future__ import annotations

import threading

import uvicorn


class ServerController:
    def __init__(self, app, host: str = "0.0.0.0", port: int = 8787):
        self.host = host
        self.port = port
        self._app = app
        self._config: uvicorn.Config | None = None
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.running:
            return
        self._config = uvicorn.Config(
            self._app, host=self.host, port=self.port, log_level="warning",
            log_config=None,  # skip uvicorn's own logging setup — it assumes a real
            # console (calls sys.stdout.isatty()) and crashes under pythonw.exe,
            # where sys.stdout is None. The app has its own logger anyway.
        )
        self._server = uvicorn.Server(self._config)
        self._thread = threading.Thread(target=self._server.run, daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        if not self.running or self._server is None:
            return
        self._server.should_exit = True
        self._thread.join(timeout=timeout)
