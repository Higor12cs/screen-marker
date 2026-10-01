from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QEvent, QPoint, QPointF, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QCursor,
    QGuiApplication,
    QKeySequence,
    QPainter,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QLineEdit, QWidget

from . import winutil
from .capture import grab_desktop, virtual_geometry
from .config import Config
from .shapes import (
    Shape,
    constrain_angle,
    constrain_square,
    ema_point,
    hit_test,
    is_nearly_straight,
    paint_shape,
    simplify,
)

DRAG_TOOLS = ("line", "arrow", "rectangle", "ellipse", "triangle")


def event_sequence(event) -> str:
    return QKeySequence(event.keyCombination()).toString(QKeySequence.SequenceFormat.PortableText)


def matches(event, sequence: str) -> bool:
    if not sequence:
        return False
    normalized = QKeySequence(sequence).toString(QKeySequence.SequenceFormat.PortableText).lower()
    if event_sequence(event).lower() == (normalized or sequence.lower()):
        return True
    modifiers = event.modifiers()
    allowed = (
        Qt.KeyboardModifier.NoModifier,
        Qt.KeyboardModifier.ShiftModifier,
        Qt.KeyboardModifier.KeypadModifier,
        Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.KeypadModifier,
    )
    if len(sequence) == 1 and modifiers in allowed and event.text():
        return event.text().lower() == sequence.lower()
    return False


class OverlayWindow(QWidget):
    state_changed = Signal()
    closed = Signal()
    action_requested = Signal(str)

    def __init__(self, config: Config) -> None:
        super().__init__()
        self.config = config
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setWindowTitle("ScreenMarker")

        self.shapes: list[Shape] = []
        self._undo: list[list[Shape]] = []
        self._redo: list[list[Shape]] = []
        self.tool = config["default_tool"]
        self.color_index = int(config["color_index"])
        self.pen_width = float(config["pen_width"])
        self.font_size = int(config["font_size"])
        self.frozen = False
        self.click_through = False
        self.background: QPixmap | None = None
        self._draft: Shape | None = None
        self._drawing = False
        self._erasing = False
        self._editor: QLineEdit | None = None
        self._editor_origin = QPointF()
        self.capture_prepare = None
        self.capture_restore = None
        self.raise_extras = None

    @property
    def palette_colors(self) -> list[str]:
        return list(self.config["palette"])

    @property
    def color(self) -> str:
        colors = self.palette_colors
        return colors[self.color_index % len(colors)]

    def start(self, frozen: bool = False) -> None:
        self.setGeometry(virtual_geometry())
        if frozen:
            self.freeze(True, refresh=False)
        else:
            self.frozen = False
            self.background = None
        self.click_through = False
        self.show()
        winutil.set_click_through(int(self.winId()), False)
        self.raise_()
        winutil.force_foreground(int(self.winId()))
        self.activateWindow()
        self.setFocus()
        self.apply_cursor()
        self.update()
        if self.raise_extras is not None:
            self.raise_extras()
        self.state_changed.emit()

    def stop(self) -> None:
        self.cancel_editor()
        self.hide()
        self.background = None
        self.frozen = False
        self.closed.emit()
        self.state_changed.emit()

    def refocus(self) -> None:
        if not self.isVisible() or self.click_through:
            return
        self.raise_()
        winutil.force_foreground(int(self.winId()))
        self.activateWindow()
        self.setFocus()
        if self.raise_extras is not None:
            self.raise_extras()

    def freeze(self, enabled: bool, refresh: bool = True) -> None:
        if enabled:
            was_visible = self.isVisible()
            if was_visible:
                if self.capture_prepare is not None:
                    self.capture_prepare()
                self.hide()
                QGuiApplication.processEvents()
            self.background = grab_desktop()
            self.frozen = True
            if was_visible:
                self.show()
                self.refocus()
                if self.capture_restore is not None:
                    self.capture_restore()
        else:
            self.frozen = False
            self.background = None
        if refresh:
            self.update()
        self.state_changed.emit()

    def set_tool(self, tool: str) -> None:
        self.commit_editor()
        self.tool = tool
        self.apply_cursor()
        self.state_changed.emit()

    def set_color_index(self, index: int) -> None:
        colors = self.palette_colors
        self.color_index = index % len(colors)
        self.config["color_index"] = self.color_index
        self.apply_cursor()
        self.state_changed.emit()

    def set_pen_width(self, width: float) -> None:
        self.pen_width = max(1.0, min(60.0, float(width)))
        self.config["pen_width"] = self.pen_width
        self.apply_cursor()
        self.state_changed.emit()

    def set_click_through(self, enabled: bool) -> None:
        self.click_through = enabled
        winutil.set_click_through(int(self.winId()), enabled)
        if not enabled:
            self.refocus()
        self.state_changed.emit()

    def apply_cursor(self) -> None:
        if self.tool == "eraser":
            size = int(max(16.0, self.pen_width * 4))
            pixmap = QPixmap(size + 4, size + 4)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setPen(QPen(QColor("#ffffff"), 2))
            painter.setBrush(QBrush(QColor(0, 0, 0, 60)))
            painter.drawEllipse(2, 2, size, size)
            painter.end()
            self.setCursor(QCursor(pixmap))
        elif self.tool == "text":
            self.setCursor(Qt.CursorShape.IBeamCursor)
        else:
            self.setCursor(Qt.CursorShape.CrossCursor)

    def snapshot(self) -> None:
        self._undo.append(list(self.shapes))
        if len(self._undo) > 200:
            self._undo.pop(0)
        self._redo.clear()

    def undo(self) -> None:
        if not self._undo:
            return
        self._redo.append(list(self.shapes))
        self.shapes = self._undo.pop()
        self.update()
        self.state_changed.emit()

    def redo(self) -> None:
        if not self._redo:
            return
        self._undo.append(list(self.shapes))
        self.shapes = self._redo.pop()
        self.update()
        self.state_changed.emit()

    def erase_last(self) -> None:
        if not self.shapes:
            return
        self.snapshot()
        self.shapes = self.shapes[:-1]
        self.update()
        self.state_changed.emit()

    def clear(self) -> None:
        if not self.shapes:
            return
        self.snapshot()
        self.shapes = []
        self.update()
        self.state_changed.emit()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        if self.background is not None:
            painter.drawPixmap(self.rect(), self.background)
            dim = float(self.config.get("dim_background", 0.0) or 0.0)
            if dim > 0:
                painter.fillRect(self.rect(), QColor(0, 0, 0, int(dim * 255)))
        else:
            painter.fillRect(self.rect(), QColor(0, 0, 0, 1))
        for shape in self.shapes:
            paint_shape(painter, shape)
        if self._draft is not None:
            paint_shape(painter, self._draft)
        painter.end()

    def new_shape(self, origin: QPointF) -> Shape:
        opacity = 1.0
        width = self.pen_width
        if self.tool == "highlighter":
            opacity = float(self.config["highlighter_opacity"])
            width = self.pen_width * 4
        return Shape(
            kind=self.tool,
            color=self.color,
            width=width,
            points=[origin],
            opacity=opacity,
        )

    def mousePressEvent(self, event) -> None:
        position = QPointF(event.position())
        if event.button() == Qt.MouseButton.RightButton:
            self.erase_last()
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return
        if self._editor is not None:
            self.commit_editor()
            return
        if self.tool == "eraser":
            self._erasing = True
            self.snapshot()
            self.erase_at(position)
            return
        if self.tool == "text":
            self.open_editor(position)
            return
        self._drawing = True
        self._draft = self.new_shape(position)
        self.update()

    def mouseMoveEvent(self, event) -> None:
        position = QPointF(event.position())
        if self._erasing:
            self.erase_at(position)
            return
        if not self._drawing or self._draft is None:
            return
        shift = bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        if self._draft.kind in ("pen", "highlighter"):
            strength = self.smoothing_strength()
            last = self._draft.points[-1]
            point = ema_point(last, position, strength) if strength > 0 else position
            if abs(point.x() - last.x()) + abs(point.y() - last.y()) >= 0.8:
                self._draft.points.append(point)
        else:
            origin = self._draft.points[0]
            if shift:
                if self._draft.kind in ("line", "arrow"):
                    position = constrain_angle(origin, position)
                else:
                    position = constrain_square(origin, position)
            self._draft.points = [origin, position]
        self.update()

    def mouseReleaseEvent(self, event) -> None:
        if self._erasing:
            self._erasing = False
            return
        if not self._drawing or self._draft is None:
            return
        self._drawing = False
        draft = self._draft
        self._draft = None
        if draft.kind in DRAG_TOOLS and len(draft.points) >= 2:
            delta = draft.points[-1] - draft.points[0]
            if abs(delta.x()) < 3 and abs(delta.y()) < 3:
                self.update()
                return
        if draft.kind in ("pen", "highlighter"):
            draft.points = self.refine_stroke(draft.points)
        self.snapshot()
        self.shapes.append(draft)
        self.update()
        self.state_changed.emit()

    def smoothing_strength(self) -> float:
        if not self.config.get("smoothing_enabled", True):
            return 0.0
        return float(self.config.get("smoothing", 0.5) or 0.0)

    def refine_stroke(self, points: list[QPointF]) -> list[QPointF]:
        strength = self.smoothing_strength()
        if len(points) < 4 or strength <= 0:
            return points
        refined = simplify(points, 0.8 + strength * 2.4)
        if self.config.get("straighten", True) and is_nearly_straight(
            refined, float(self.config.get("straighten_tolerance", 0.04))
        ):
            return [refined[0], refined[-1]]
        return refined

    def wheelEvent(self, event) -> None:
        step = 1 if event.angleDelta().y() > 0 else -1
        self.set_pen_width(self.pen_width + step)
        self.update()

    def erase_at(self, position: QPointF) -> None:
        tolerance = max(6.0, self.pen_width * 2)
        for index in range(len(self.shapes) - 1, -1, -1):
            if hit_test(self.shapes[index], position, tolerance):
                del self.shapes[index]
                self.update()
                self.state_changed.emit()
                return

    def open_editor(self, position: QPointF) -> None:
        editor = QLineEdit(self)
        editor.setStyleSheet(
            "QLineEdit { color: %s; background: rgba(0,0,0,120);"
            " border: 1px dashed %s; padding: 2px; }" % (self.color, self.color)
        )
        font = editor.font()
        font.setFamily("Segoe UI")
        font.setPointSize(self.font_size)
        font.setBold(True)
        editor.setFont(font)
        editor.move(QPoint(int(position.x()), int(position.y())))
        editor.setMinimumWidth(260)
        editor.returnPressed.connect(self.commit_editor)
        editor.show()
        editor.setFocus()
        self._editor = editor
        self._editor_origin = position

    def commit_editor(self) -> None:
        if self._editor is None:
            return
        text = self._editor.text().strip()
        origin = self._editor_origin
        self._editor.deleteLater()
        self._editor = None
        if text:
            self.snapshot()
            self.shapes.append(
                Shape(
                    kind="text",
                    color=self.color,
                    width=self.pen_width,
                    points=[origin],
                    text=text,
                    font_size=self.font_size,
                )
            )
        self.setFocus()
        self.update()
        self.state_changed.emit()

    def cancel_editor(self) -> None:
        if self._editor is None:
            return
        self._editor.deleteLater()
        self._editor = None
        self.setFocus()

    def composed_image(self) -> QPixmap:
        if self.frozen and self.background is not None:
            canvas = QPixmap(self.background)
        else:
            if self.capture_prepare is not None:
                self.capture_prepare()
            self.hide()
            QGuiApplication.processEvents()
            canvas = grab_desktop()
            self.show()
            self.refocus()
            if self.capture_restore is not None:
                self.capture_restore()
        painter = QPainter(canvas)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        for shape in self.shapes:
            paint_shape(painter, shape)
        painter.end()
        return canvas

    def save_png(self) -> str | None:
        directory = self.config.save_directory
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / ("marcacao-%s.png" % datetime.now().strftime("%Y%m%d-%H%M%S"))
        if self.composed_image().save(str(path), "PNG"):
            return str(path)
        return None

    def copy_to_clipboard(self) -> None:
        QGuiApplication.clipboard().setPixmap(self.composed_image())

    def event(self, incoming):
        if incoming.type() == QEvent.Type.KeyPress and incoming.key() in (
            Qt.Key.Key_Tab,
            Qt.Key.Key_Backtab,
        ):
            self.keyPressEvent(incoming)
            return True
        return super().event(incoming)

    def toggle_smoothing(self) -> None:
        self.config["smoothing_enabled"] = not self.config.get("smoothing_enabled", True)
        self.state_changed.emit()

    def keyPressEvent(self, event) -> None:
        for action, sequence in self.config["local_hotkeys"].items():
            if matches(event, sequence):
                self.run_action(action)
                event.accept()
                return
        super().keyPressEvent(event)

    def run_action(self, action: str) -> None:
        if action.startswith("tool_"):
            self.set_tool(action[5:])
            return
        if action.startswith("color_"):
            self.set_color_index(int(action.split("_")[1]) - 1)
            return
        handlers = {
            "undo": self.undo,
            "redo": self.redo,
            "erase_last": self.erase_last,
            "clear": self.clear,
            "exit_overlay": self.stop,
            "toggle_freeze": lambda: self.freeze(not self.frozen),
            "toggle_clickthrough": lambda: self.set_click_through(not self.click_through),
            "width_up": lambda: self.set_pen_width(self.pen_width + 1),
            "width_down": lambda: self.set_pen_width(self.pen_width - 1),
            "next_color": lambda: self.set_color_index(self.color_index + 1),
            "toggle_smoothing": self.toggle_smoothing,
        }
        handler = handlers.get(action)
        if handler is not None:
            handler()
            return
        self.action_requested.emit(action)
