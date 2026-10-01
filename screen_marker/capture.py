from __future__ import annotations

from PySide6.QtCore import QRect, QRectF
from PySide6.QtGui import QGuiApplication, QPixmap


def virtual_geometry() -> QRect:
    rect = QRect()
    for screen in QGuiApplication.screens():
        rect = rect.united(screen.geometry())
    return rect


def grab_desktop() -> QPixmap:
    geometry = virtual_geometry()
    ratio = max((screen.devicePixelRatio() for screen in QGuiApplication.screens()), default=1.0)
    canvas = QPixmap(int(geometry.width() * ratio), int(geometry.height() * ratio))
    canvas.setDevicePixelRatio(ratio)
    canvas.fill()

    from PySide6.QtGui import QPainter

    painter = QPainter(canvas)
    for screen in QGuiApplication.screens():
        shot = screen.grabWindow(0)
        if shot.isNull():
            continue
        target = QRectF(screen.geometry().translated(-geometry.topLeft()))
        painter.drawPixmap(target, shot, QRectF(shot.rect()))
    painter.end()
    return canvas
