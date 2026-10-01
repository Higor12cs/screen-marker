from __future__ import annotations

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtSvg import QSvgRenderer

from .lucide import GLYPHS

SIZE = 24
SVG_TEMPLATE = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" '
    'fill="none" stroke="%s" stroke-width="%s" stroke-linecap="round" '
    'stroke-linejoin="round">%s</svg>'
)


def render(name: str, color: str = "#f2f2f2", size: int = SIZE, stroke: float = 2.0) -> QPixmap:
    body = GLYPHS.get(name)
    pixmap = QPixmap(size * 2, size * 2)
    pixmap.fill(Qt.GlobalColor.transparent)
    if body is None:
        return pixmap
    markup = SVG_TEMPLATE % (color, stroke, body)
    renderer = QSvgRenderer(QByteArray(markup.encode("utf-8")))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(painter, QRectF(0, 0, size * 2, size * 2))
    painter.end()
    pixmap.setDevicePixelRatio(2)
    return pixmap


def glyph(name: str, color: str = "#f2f2f2") -> QIcon:
    return QIcon(render(name, color))


def color_swatch(color: str, size: int = 22) -> QIcon:
    pixmap = QPixmap(size * 2, size * 2)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(QPen(QColor("#9aa0ab"), 2))
    painter.setBrush(QColor(color))
    painter.drawEllipse(QRectF(3, 3, size * 2 - 6, size * 2 - 6))
    painter.end()
    pixmap.setDevicePixelRatio(2)
    return QIcon(pixmap)


def app_icon() -> QIcon:
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setBrush(QColor("#1f2430"))
        painter.setPen(Qt.PenStyle.NoPen)
        radius = size * 0.22
        painter.drawRoundedRect(QRectF(0.5, 0.5, size - 1, size - 1), radius, radius)
        inner = size * 0.60
        offset = (size - inner) / 2
        markup = SVG_TEMPLATE % ("#ff4d4d", 2.2, GLYPHS["pen"])
        renderer = QSvgRenderer(QByteArray(markup.encode("utf-8")))
        renderer.render(painter, QRectF(offset, offset, inner, inner))
        painter.end()
        icon.addPixmap(pixmap)
    return icon
