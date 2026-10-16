from __future__ import annotations

import ctypes
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter, QObject, Signal

WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

user32 = ctypes.windll.user32

NAMED_KEYS = {
    "ESC": 0x1B,
    "ESCAPE": 0x1B,
    "SPACE": 0x20,
    "TAB": 0x09,
    "RETURN": 0x0D,
    "ENTER": 0x0D,
    "BACKSPACE": 0x08,
    "DEL": 0x2E,
    "DELETE": 0x2E,
    "INS": 0x2D,
    "INSERT": 0x2D,
    "HOME": 0x24,
    "END": 0x23,
    "PGUP": 0x21,
    "PGDOWN": 0x22,
    "LEFT": 0x25,
    "UP": 0x26,
    "RIGHT": 0x27,
    "DOWN": 0x28,
    "PRINT": 0x2C,
    "PRINTSCREEN": 0x2C,
    "PAUSE": 0x13,
    "+": 0xBB,
    "PLUS": 0xBB,
    "-": 0xBD,
    "MINUS": 0xBD,
    ",": 0xBC,
    ".": 0xBE,
    "/": 0xBF,
    ";": 0xBA,
    "[": 0xDB,
    "]": 0xDD,
    "\\": 0xDC,
    "'": 0xDE,
    "`": 0xC0,
}


def parse_sequence(sequence: str) -> tuple[int, int] | None:
    if not sequence:
        return None
    parts: list[str] = []
    buffer = ""
    for character in sequence.strip():
        if character == "+":
            if buffer:
                parts.append(buffer)
                buffer = ""
            else:
                buffer = "+"
        else:
            buffer += character
    if buffer:
        parts.append(buffer)
    if not parts:
        return None
    modifiers = 0
    key_token = None
    for part in parts:
        upper = part.upper()
        if upper in ("CTRL", "CONTROL"):
            modifiers |= MOD_CONTROL
        elif upper == "ALT":
            modifiers |= MOD_ALT
        elif upper == "SHIFT":
            modifiers |= MOD_SHIFT
        elif upper in ("META", "WIN", "SUPER"):
            modifiers |= MOD_WIN
        else:
            key_token = upper
    if key_token is None:
        return None
    if key_token in NAMED_KEYS:
        vk = NAMED_KEYS[key_token]
    elif len(key_token) == 1 and (key_token.isalnum()):
        vk = ord(key_token)
    elif key_token.startswith("F") and key_token[1:].isdigit():
        number = int(key_token[1:])
        if not 1 <= number <= 24:
            return None
        vk = 0x6F + number
    else:
        return None
    return modifiers | MOD_NOREPEAT, vk


class GlobalHotkeyManager(QObject, QAbstractNativeEventFilter):
    triggered = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        QObject.__init__(self, parent)
        QAbstractNativeEventFilter.__init__(self)
        self._registered: dict[int, str] = {}
        self._next_id = 0xB000
        self.failures: list[str] = []

    def nativeEventFilter(self, event_type, message):
        if event_type in (b"windows_generic_MSG", "windows_generic_MSG"):
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY:
                action = self._registered.get(int(msg.wParam))
                if action:
                    self.triggered.emit(action)
                    return True, 0
        return False, 0

    def unregister_all(self) -> None:
        for hotkey_id in list(self._registered):
            user32.UnregisterHotKey(None, hotkey_id)
        self._registered.clear()
        self._next_id = 0xB000
        self.failures.clear()

    def register(self, bindings: dict[str, str]) -> None:
        self.unregister_all()
        for action, sequence in bindings.items():
            parsed = parse_sequence(sequence)
            if parsed is None:
                continue
            modifiers, vk = parsed
            if not modifiers & (MOD_CONTROL | MOD_ALT | MOD_WIN) and not 0x70 <= vk <= 0x87:
                self.failures.append(sequence)
                continue
            hotkey_id = self._next_id
            self._next_id += 1
            if user32.RegisterHotKey(None, hotkey_id, modifiers, vk):
                self._registered[hotkey_id] = action
            else:
                self.failures.append(sequence)
