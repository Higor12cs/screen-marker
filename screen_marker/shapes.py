from __future__ import annotations

import math
from dataclasses import dataclass, field

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QFontMetricsF,
    QPainter,
    QPainterPath,
    QPainterPathStroker,
    QPen,
    QPolygonF,
)

TOOLS = (
    "pen",
    "highlighter",
    "line",
    "arrow",
    "rectangle",
    "ellipse",
    "triangle",
    "text",
    "eraser",
)

TOOL_LABELS = {
    "pen": "Caneta",
    "highlighter": "Marca-texto",
    "line": "Linha",
    "arrow": "Seta",
    "rectangle": "Retângulo",
    "ellipse": "Círculo",
    "triangle": "Triângulo",
    "text": "Texto",
    "eraser": "Borracha",
}


@dataclass
class Shape:
    kind: str
    color: str
    width: float
    points: list[QPointF] = field(default_factory=list)
    opacity: float = 1.0
    filled: bool = False
    text: str = ""
    font_size: int = 28

    def clone(self) -> "Shape":
        return Shape(
            kind=self.kind,
            color=self.color,
            width=self.width,
            points=[QPointF(point) for point in self.points],
            opacity=self.opacity,
            filled=self.filled,
            text=self.text,
            font_size=self.font_size,
        )


def ema_point(previous: QPointF, target: QPointF, strength: float) -> QPointF:
    factor = 1.0 - max(0.0, min(0.95, strength)) * 0.8
    return QPointF(
        previous.x() + (target.x() - previous.x()) * factor,
        previous.y() + (target.y() - previous.y()) * factor,
    )


def perpendicular_distance(point: QPointF, start: QPointF, end: QPointF) -> float:
    dx = end.x() - start.x()
    dy = end.y() - start.y()
    length = math.hypot(dx, dy)
    if length == 0:
        return math.hypot(point.x() - start.x(), point.y() - start.y())
    area = abs(dx * (start.y() - point.y()) - (start.x() - point.x()) * dy)
    return area / length


def simplify(points: list[QPointF], epsilon: float) -> list[QPointF]:
    if len(points) < 3:
        return list(points)
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        first, last = stack.pop()
        if last <= first + 1:
            continue
        farthest = -1.0
        index = first
        for position in range(first + 1, last):
            distance = perpendicular_distance(points[position], points[first], points[last])
            if distance > farthest:
                farthest = distance
                index = position
        if farthest > epsilon:
            keep[index] = True
            stack.append((first, index))
            stack.append((index, last))
    return [point for point, flag in zip(points, keep) if flag]


def is_nearly_straight(points: list[QPointF], tolerance: float) -> bool:
    if len(points) < 3:
        return False
    start, end = points[0], points[-1]
    length = math.hypot(end.x() - start.x(), end.y() - start.y())
    if length < 24:
        return False
    travelled = sum(
        math.hypot(points[i + 1].x() - points[i].x(), points[i + 1].y() - points[i].y())
        for i in range(len(points) - 1)
    )
    if travelled > length * 1.35:
        return False
    deviation = max(perpendicular_distance(point, start, end) for point in points)
    return deviation <= max(2.5, length * tolerance)


def smooth_path(points: list[QPointF]) -> QPainterPath:
    path = QPainterPath(points[0])
    total = len(points)
    for index in range(total - 1):
        previous = points[max(index - 1, 0)]
        current = points[index]
        following = points[index + 1]
        after = points[min(index + 2, total - 1)]
        control_one = QPointF(
            current.x() + (following.x() - previous.x()) / 6.0,
            current.y() + (following.y() - previous.y()) / 6.0,
        )
        control_two = QPointF(
            following.x() - (after.x() - current.x()) / 6.0,
            following.y() - (after.y() - current.y()) / 6.0,
        )
        path.cubicTo(control_one, control_two, following)
    return path


def normalized_rect(start: QPointF, end: QPointF) -> QRectF:
    return QRectF(start, end).normalized()


def constrain_square(start: QPointF, end: QPointF) -> QPointF:
    dx = end.x() - start.x()
    dy = end.y() - start.y()
    size = max(abs(dx), abs(dy))
    return QPointF(
        start.x() + math.copysign(size, dx or 1.0),
        start.y() + math.copysign(size, dy or 1.0),
    )


def constrain_angle(start: QPointF, end: QPointF) -> QPointF:
    dx = end.x() - start.x()
    dy = end.y() - start.y()
    length = math.hypot(dx, dy)
    if length == 0:
        return end
    angle = math.degrees(math.atan2(dy, dx))
    snapped = math.radians(round(angle / 15.0) * 15.0)
    return QPointF(start.x() + math.cos(snapped) * length, start.y() + math.sin(snapped) * length)


def arrow_head(start: QPointF, end: QPointF, width: float) -> QPolygonF:
    dx = end.x() - start.x()
    dy = end.y() - start.y()
    length = math.hypot(dx, dy)
    if length < 1:
        return QPolygonF()
    size = max(12.0, width * 4.5)
    angle = math.atan2(dy, dx)
    spread = math.radians(24)
    left = QPointF(
        end.x() - math.cos(angle - spread) * size,
        end.y() - math.sin(angle - spread) * size,
    )
    right = QPointF(
        end.x() - math.cos(angle + spread) * size,
        end.y() - math.sin(angle + spread) * size,
    )
    return QPolygonF([QPointF(end), left, right])


def triangle_polygon(rect: QRectF) -> QPolygonF:
    return QPolygonF(
        [
            QPointF(rect.center().x(), rect.top()),
            QPointF(rect.left(), rect.bottom()),
            QPointF(rect.right(), rect.bottom()),
        ]
    )


def shape_path(shape: Shape) -> QPainterPath:
    path = QPainterPath()
    points = shape.points
    if not points:
        return path
    if shape.kind in ("pen", "highlighter"):
        if len(points) == 1:
            path.moveTo(points[0])
            path.lineTo(points[0].x() + 0.1, points[0].y() + 0.1)
            return path
        if len(points) >= 3:
            return smooth_path(points)
        path.moveTo(points[0])
        for point in points[1:]:
            path.lineTo(point)
        return path
    if len(points) < 2:
        return path
    start, end = points[0], points[-1]
    if shape.kind in ("line", "arrow"):
        path.moveTo(start)
        path.lineTo(end)
        if shape.kind == "arrow":
            path.addPolygon(arrow_head(start, end, shape.width))
        return path
    rect = normalized_rect(start, end)
    if shape.kind == "rectangle":
        path.addRect(rect)
    elif shape.kind == "ellipse":
        path.addEllipse(rect)
    elif shape.kind == "triangle":
        polygon = triangle_polygon(rect)
        path.addPolygon(polygon)
        path.closeSubpath()
    return path


def text_rect(shape: Shape) -> QRectF:
    font = QFont("Segoe UI", shape.font_size)
    font.setBold(True)
    metrics = QFontMetricsF(font)
    lines = shape.text.split("\n") or [""]
    width = max((metrics.horizontalAdvance(line) for line in lines), default=0.0)
    height = metrics.height() * max(1, len(lines))
    origin = shape.points[0]
    return QRectF(origin.x(), origin.y(), width + 8, height + 4)


def paint_shape(painter: QPainter, shape: Shape) -> None:
    color = QColor(shape.color)
    painter.save()
    painter.setOpacity(shape.opacity)
    if shape.kind == "text":
        font = QFont("Segoe UI", shape.font_size)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QPen(color))
        rect = text_rect(shape)
        painter.drawText(rect, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop), shape.text)
        painter.restore()
        return

    pen = QPen(color)
    pen.setWidthF(shape.width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    if shape.kind == "arrow" and len(shape.points) >= 2:
        start, end = shape.points[0], shape.points[-1]
        painter.drawLine(start, end)
        head = arrow_head(start, end, shape.width)
        if not head.isEmpty():
            painter.setBrush(color)
            painter.drawPolygon(head)
        painter.restore()
        return

    if shape.filled and shape.kind in ("rectangle", "ellipse", "triangle"):
        fill = QColor(color)
        fill.setAlphaF(0.30)
        painter.setBrush(fill)

    painter.drawPath(shape_path(shape))
    painter.restore()


def hit_test(shape: Shape, point: QPointF, tolerance: float) -> bool:
    if shape.kind == "text":
        return text_rect(shape).adjusted(-tolerance, -tolerance, tolerance, tolerance).contains(point)
    path = shape_path(shape)
    if path.isEmpty():
        return False
    stroker = QPainterPathStroker()
    stroker.setWidth(max(shape.width, 2.0) + tolerance * 2)
    stroker.setCapStyle(Qt.PenCapStyle.RoundCap)
    stroker.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    if stroker.createStroke(path).contains(point):
        return True
    if shape.filled and shape.kind in ("rectangle", "ellipse", "triangle"):
        return path.contains(point)
    return False
