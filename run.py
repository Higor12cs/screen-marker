from __future__ import annotations

import ctypes
import sys

from screen_marker.app import main

ERROR_ALREADY_EXISTS = 183


def single_instance() -> bool:
    handle = ctypes.windll.kernel32.CreateMutexW(None, False, "ScreenMarkerSingleInstanceMutex")
    return not (handle and ctypes.windll.kernel32.GetLastError() == ERROR_ALREADY_EXISTS)


if __name__ == "__main__":
    if not single_instance():
        ctypes.windll.user32.MessageBoxW(
            None,
            "O ScreenMarker já está em execução. Procure o ícone na área de notificação.",
            "ScreenMarker",
            0x40,
        )
        sys.exit(0)
    sys.exit(main())
