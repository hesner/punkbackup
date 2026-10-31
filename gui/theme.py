"""The two looks of the app. Dark is WiFi mode; "Xerox" is cable mode, after
the black-and-white photocopied punk zines (approved design, PLAN.md section
26). Seeing a different app is what tells you which path is active.

gui/main_window.py and gui/dialogs.py read these names as module globals, and
MainWindow rebuilds its widgets after switching, so every color has to go
through this table to change with the mode.
"""
from __future__ import annotations

DARK = {
    "BG": "#0c0c0e",            # near-black window background
    "CARD_BG": "#19191d",       # card/panel background
    "CARD_BG_ALT": "#221418",   # subtle warm-dark variant for the log panel
    "BORDER": "#2c2c32",
    "BORDER_WIDTH": 1,
    "TEXT_MAIN": "#f2f2f5",
    "TEXT_MUTED": "#9a9aa3",
    "ACCENT": "#ff2d55",        # punk pink/red — headers, selected nav, highlights
    "ACCENT_HOVER": "#c81d4a",
    "ACCENT_INK": "#1a0308",    # text color used ON TOP of the accent color
    "GREEN": "#2ecc71",
    "GREEN_HOVER": "#1e9e58",
    "AMBER": "#ffb020",
    "RED": "#ff3b30",
    "RED_HOVER": "#c62828",
    "RED_INK": "#f2f2f5",       # text color used ON TOP of RED
    "HEADER_BG": "transparent",
    "HEADER_TITLE": "#ff2d55",
    "HEADER_TEXT": "#9a9aa3",
    "CONTROL_BG": "#19191d",    # the bar holding the main button and the status
    "CONTROL_TEXT": "#9a9aa3",
    "NAV_BG": "#19191d",
    "NAV_TEXT": "#f2f2f5",
    "NAV_HOVER": "#221418",
    "ACTION": "#ff2d55",        # a profile's own "start" button
    "ACTION_HOVER": "#c81d4a",
    "ACTION_INK": "#1a0308",
    "MODE_BUTTON": "#d9d9d6",   # already previews the other mode's color
    "MODE_BUTTON_HOVER": "#bdbdb9",
    "MODE_BUTTON_INK": "#141416",
    "MODE_BUTTON_BORDER": 0,
    "PROGRESS_TRACK": "#2c2c32",
    "APPEARANCE": "dark",
}

XEROX = {
    **DARK,
    "BG": "#f2f2ee",
    "CARD_BG": "#ffffff",
    "CARD_BG_ALT": "#e4e4df",
    "BORDER": "#8a8a86",        # softer than the bands' black, as asked after real use
    "BORDER_WIDTH": 2,
    "TEXT_MAIN": "#000000",
    "TEXT_MUTED": "#454545",
    "ACCENT": "#d90000",        # a single red to act, as on a two-ink flyer
    "ACCENT_HOVER": "#a80000",
    "ACCENT_INK": "#ffffff",
    "GREEN": "#0b6b35",         # the dark mode's greens can't be read on paper
    "GREEN_HOVER": "#085228",
    "AMBER": "#b30000",
    "RED": "#d90000",
    "RED_HOVER": "#a80000",
    "RED_INK": "#ffffff",
    "HEADER_BG": "#000000",
    "HEADER_TITLE": "#ffffff",
    "HEADER_TEXT": "#d0d0d0",
    "CONTROL_BG": "#000000",
    "CONTROL_TEXT": "#d0d0d0",
    "NAV_BG": "#000000",
    "NAV_TEXT": "#ffffff",
    "NAV_HOVER": "#333333",
    "ACTION": "#d90000",
    "ACTION_HOVER": "#a80000",
    "ACTION_INK": "#ffffff",
    "MODE_BUTTON": "#ff3b30",   # same red as the dark mode's stop button
    "MODE_BUTTON_HOVER": "#ff6259",
    "MODE_BUTTON_INK": "#1a0308",
    "MODE_BUTTON_BORDER": 2,
    "PROGRESS_TRACK": "#d8d8d4",
    "APPEARANCE": "light",
}

# Fixed in both modes: the log stays a black terminal and the selected nav item
# stays the brand pink. Both sit on black, so neither depends on the mode.
LOG_BG = "#050505"
TERMINAL_GREEN = "#39d353"
NAV_SELECTED = "#ff2d55"
NAV_SELECTED_HOVER = "#c81d4a"
NAV_SELECTED_INK = "#1a0308"
MODE_CHIP_BG = "#ffffff"
MODE_CHIP_INK = "#000000"
