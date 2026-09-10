"""Manual/dev runner — NOT the way the GUI starts the server (it imports
configure()+ServerController directly). This script exists only so the
server can be smoke-tested from the terminal with curl before/without the GUI.

Usage:
    .venv\\Scripts\\python.exe -m server.run_dev <dest_dir> [--profile-name "iPhone de prueba"] [--port 8787]

Prints the token of the (newly created, or first existing) profile so you
can use it directly with curl.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from server import app as app_module
from server.profiles import ProfileStore
from server.runner import ServerController


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("dest_dir")
    parser.add_argument("--profile-name", default="Perfil de prueba")
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()

    store = ProfileStore()
    profile = store.list()[0] if store.list() else store.add(args.profile_name)
    if not profile.destination_dir:
        store.set_destination(profile.id, args.dest_dir)
        profile = store.get(profile.id)

    app_module.configure(store)
    controller = ServerController(app_module.app, host="0.0.0.0", port=args.port)
    controller.start()
    print(f"Serving on 0.0.0.0:{args.port} -> {args.dest_dir}")
    print(f"Profile: {profile.name}  token={profile.token}")
    print("Press Ctrl+C to stop.")

    import time

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        controller.stop()


if __name__ == "__main__":
    main()
