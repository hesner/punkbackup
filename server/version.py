"""Single source of truth for the app's own version string, shown in the
GUI (window title + "⚙ Settings") so a user can tell what they actually
have installed — e.g. to compare against a manual/release note, or when
reporting a bug.

NOT read by the installer script (Inno Setup's preprocessor can't easily
parse Python) — installer/PunkBackup.iss's `MyAppVersion` is a SEPARATE
value that must be bumped by hand alongside this one. Keep both in sync
whenever either changes.
"""
APP_VERSION = "1.7.6"
