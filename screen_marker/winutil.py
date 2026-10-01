from __future__ import annotations

import ctypes
from ctypes import wintypes

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_LAYERED = 0x00080000
WS_EX_NOACTIVATE = 0x08000000

user32.GetWindowLongW.restype = ctypes.c_long
user32.SetWindowLongW.restype = ctypes.c_long


def set_click_through(hwnd: int, enabled: bool) -> None:
    if not hwnd:
        return
    style = user32.GetWindowLongW(wintypes.HWND(hwnd), GWL_EXSTYLE)
    if enabled:
        style |= WS_EX_TRANSPARENT | WS_EX_LAYERED
    else:
        style &= ~WS_EX_TRANSPARENT
    user32.SetWindowLongW(wintypes.HWND(hwnd), GWL_EXSTYLE, style)


def set_no_activate(hwnd: int, enabled: bool) -> None:
    if not hwnd:
        return
    style = user32.GetWindowLongW(wintypes.HWND(hwnd), GWL_EXSTYLE)
    if enabled:
        style |= WS_EX_NOACTIVATE
    else:
        style &= ~WS_EX_NOACTIVATE
    user32.SetWindowLongW(wintypes.HWND(hwnd), GWL_EXSTYLE, style)


def force_foreground(hwnd: int) -> None:
    if not hwnd:
        return
    handle = wintypes.HWND(hwnd)
    foreground = user32.GetForegroundWindow()
    target_thread = kernel32.GetCurrentThreadId()
    source_thread = user32.GetWindowThreadProcessId(foreground, None)
    attached = False
    if source_thread and source_thread != target_thread:
        attached = bool(user32.AttachThreadInput(source_thread, target_thread, True))
    user32.BringWindowToTop(handle)
    user32.SetForegroundWindow(handle)
    user32.SetActiveWindow(handle)
    if attached:
        user32.AttachThreadInput(source_thread, target_thread, False)


HWND_TOPMOST = -1
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040


def keep_on_top(hwnd: int) -> None:
    if not hwnd:
        return
    user32.SetWindowPos(
        wintypes.HWND(hwnd),
        wintypes.HWND(HWND_TOPMOST),
        0,
        0,
        0,
        0,
        SWP_NOSIZE | SWP_NOMOVE | SWP_NOACTIVATE | SWP_SHOWWINDOW,
    )
