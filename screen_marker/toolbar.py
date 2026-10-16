from __future__ import annotations

from PySide6.QtCore import QPoint, QSize, Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QToolButton,
    QWidget,
)

from . import icons
from .config import LOCAL_ACTIONS
from .shapes import TOOL_LABELS, TOOLS

STYLE = """
QWidget#panel {
    background: rgba(24, 26, 32, 235);
    border: 1px solid rgba(255, 255, 255, 40);
    border-radius: 10px;
}
QToolButton {
    background: transparent;
    border: 1px solid transparent;
    border-radius: 6px;
    padding: 3px;
}
QToolButton:hover { background: rgba(255, 255, 255, 28); }
QToolButton:checked {
    background: rgba(90, 150, 255, 90);
    border: 1px solid rgba(140, 190, 255, 160);
}
QLabel { color: #d8dbe2; font-size: 11px; }
QFrame#sep { background: rgba(255, 255, 255, 45); }
QLabel#width {
    background: rgba(255, 255, 255, 20);
    color: #eef0f4;
    border: 1px solid rgba(255, 255, 255, 45);
    border-radius: 5px;
    padding: 2px 0;
    font-size: 12px;
}
"""

ACTION_BUTTONS = (
    ("undo", "undo", "Desfazer"),
    ("redo", "redo", "Refazer"),
    ("erase_last", "erase_last", "Apagar último"),
    ("clear", "clear", "Apagar tudo"),
)

TOGGLE_BUTTONS = (
    ("toggle_freeze", "freeze", "Congelar a tela"),
    ("toggle_clickthrough", "clickthrough", "Passar cliques para o Windows"),
    ("toggle_smoothing", "smooth", "Suavizar traço (endireita linhas quase retas)"),
)

OUTPUT_BUTTONS = (
    ("save_png", "save", "Salvar PNG"),
    ("copy_clipboard", "copy", "Copiar imagem"),
)

COMPACT_TOOLS = ("pen", "highlighter", "arrow", "rectangle", "text", "eraser")
COMPACT_ACTIONS = ("undo", "clear")

COLOR_NAMES = {
    "#ff2d2d": "vermelho",
    "#ffd400": "amarelo",
    "#2dd45f": "verde",
    "#2f8fff": "azul",
    "#ff8a00": "laranja",
    "#c45cff": "roxo",
    "#ffffff": "branco",
    "#101010": "preto",
}


def describe(label: str, hotkey: str) -> str:
    return "%s  —  atalho: %s" % (label, hotkey) if hotkey else label


class Toolbar(QWidget):
    action_triggered = Signal(str)

    def __init__(self, config) -> None:
        super().__init__()
        self.config = config
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_AlwaysShowToolTips, True)
        self.setStyleSheet(STYLE)
        self._drag_origin: QPoint | None = None
        self._syncing = False
        self._palette_open = False

        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        panel = QWidget(self)
        panel.setObjectName("panel")
        outer.addWidget(panel)

        self._grid = QGridLayout(panel)
        self._grid.setSpacing(3)
        self._separators: list[QFrame] = []

        self.tool_buttons: dict[str, QToolButton] = {}
        self.tool_group = QButtonGroup(self)
        self.tool_group.setExclusive(True)
        for tool in TOOLS:
            button = self._button(tool, TOOL_LABELS[tool], "tool_" + tool, checkable=True)
            button.clicked.connect(lambda _=False, name=tool: self.action_triggered.emit("tool_" + name))
            self.tool_group.addButton(button)
            self.tool_buttons[tool] = button

        self.color_buttons: list[QToolButton] = []
        self.color_group = QButtonGroup(self)
        self.color_group.setExclusive(True)
        for index, color in enumerate(config["palette"]):
            button = self._swatch(color)
            button.setCheckable(True)
            button.setToolTip(self._color_tooltip(index))
            button.clicked.connect(lambda _=False, i=index: self._pick_color(i))
            self.color_group.addButton(button)
            self.color_buttons.append(button)

        self.current_color = self._swatch(config["palette"][0])
        self.current_color.setCheckable(True)
        self.current_color.setToolTip(
            describe("Escolher cor", self.config["local_hotkeys"].get("next_color", ""))
        )
        self.current_color.clicked.connect(self._toggle_palette)

        self._minus = self._button("minus", "Traço mais fino", "width_down")
        self._minus.clicked.connect(lambda: self.action_triggered.emit("width_down"))

        self.width_label = QLabel("4", self)
        self.width_label.setObjectName("width")
        self.width_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.width_label.setFixedWidth(30)
        self.width_label.setToolTip("Espessura do traço (roda do mouse tambem ajusta)")

        self._plus = self._button("plus", "Traço mais grosso", "width_up")
        self._plus.clicked.connect(lambda: self.action_triggered.emit("width_up"))

        self.toggle_buttons: dict[str, QToolButton] = {}
        for action, glyph, label in TOGGLE_BUTTONS:
            button = self._button(glyph, label, action, checkable=True)
            button.clicked.connect(lambda _=False, name=action: self.action_triggered.emit(name))
            self.toggle_buttons[action] = button

        self.action_buttons: dict[str, QToolButton] = {}
        for action, glyph, label in ACTION_BUTTONS + OUTPUT_BUTTONS:
            button = self._button(glyph, label, action)
            button.clicked.connect(lambda _=False, name=action: self.action_triggered.emit(name))
            self.action_buttons[action] = button

        self._settings_button = self._button("settings", "Configurações", "open_settings")
        self._settings_button.clicked.connect(lambda: self.action_triggered.emit("open_settings"))

        self._hide_button = self._button(
            "hide", "Ocultar esta barra (as marcações continuam na tela)", "toggle_toolbar"
        )
        self._hide_button.clicked.connect(lambda: self.action_triggered.emit("toggle_toolbar"))

        self._more_button = self._button("more", "Mostrar todas as ferramentas", "", checkable=True)
        self._more_button.clicked.connect(lambda: self.set_compact(not self.compact))

        self._close_button = self._button("close", "Sair da marcação", "exit_overlay")
        self._close_button.clicked.connect(lambda: self.action_triggered.emit("exit_overlay"))

        self.orientation = "vertical" if config.get("toolbar_orientation") == "vertical" else "horizontal"
        self.compact = bool(config.get("toolbar_compact", True))
        self._relayout()

    def _button(self, glyph: str, label: str, action: str, checkable: bool = False) -> QToolButton:
        button = QToolButton(self)
        button.setIcon(icons.glyph(glyph))
        button.setIconSize(QSize(20, 20))
        button.setCheckable(checkable)
        button.setAutoRaise(True)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.setAttribute(Qt.WidgetAttribute.WA_AlwaysShowToolTips, True)
        button.setToolTip(describe(label, self.config["local_hotkeys"].get(action, "")))
        return button

    def _swatch(self, color: str) -> QToolButton:
        button = QToolButton(self)
        button.setIcon(icons.color_swatch(color))
        button.setIconSize(QSize(20, 20))
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.setAttribute(Qt.WidgetAttribute.WA_AlwaysShowToolTips, True)
        return button

    def _color_tooltip(self, index: int) -> str:
        color = self.config["palette"][index]
        name = COLOR_NAMES.get(color.lower())
        label = "Cor %d — %s" % (index + 1, name or color)
        return describe(label, self.config["local_hotkeys"].get("color_%d" % (index + 1), ""))

    def _pick_color(self, index: int) -> None:
        self.action_triggered.emit("color_%d" % (index + 1))
        if self.compact and self._palette_open:
            self._palette_open = False
            self._relayout()

    def _toggle_palette(self) -> None:
        self._palette_open = not self._palette_open
        self._relayout()

    def _separator(self, vertical: bool) -> QFrame:
        line = QFrame(self)
        line.setObjectName("sep")
        if vertical:
            line.setFixedHeight(1)
            line.setFrameShape(QFrame.Shape.HLine)
        else:
            line.setFixedWidth(1)
            line.setFrameShape(QFrame.Shape.VLine)
        self._separators.append(line)
        return line

    def _all_widgets(self) -> list[QWidget]:
        return (
            list(self.tool_buttons.values())
            + self.color_buttons
            + [self.current_color, self._minus, self.width_label, self._plus]
            + list(self.toggle_buttons.values())
            + list(self.action_buttons.values())
            + [self._settings_button, self._hide_button, self._more_button, self._close_button]
        )

    def _groups(self) -> list[list[QWidget]]:
        if self.compact:
            colors = [self.current_color] + (self.color_buttons if self._palette_open else [])
            return [
                [self.tool_buttons[tool] for tool in COMPACT_TOOLS],
                colors,
                [self.action_buttons[action] for action in COMPACT_ACTIONS],
                [self._more_button, self._close_button],
            ]
        return [
            list(self.tool_buttons.values()),
            list(self.color_buttons),
            [self._minus, self.width_label, self._plus],
            list(self.toggle_buttons.values()) + list(self.action_buttons.values()),
            [self._settings_button, self._hide_button, self._more_button, self._close_button],
        ]

    def set_orientation(self, orientation: str) -> None:
        orientation = "vertical" if orientation == "vertical" else "horizontal"
        if orientation == self.orientation:
            return
        self.orientation = orientation
        self._relayout()

    def set_compact(self, compact: bool) -> None:
        self.compact = bool(compact)
        self.config["toolbar_compact"] = self.compact
        self._palette_open = False
        self._relayout()

    def _available_height(self) -> int:
        from PySide6.QtGui import QGuiApplication

        screen = QGuiApplication.screenAt(self.frameGeometry().center()) or QGuiApplication.primaryScreen()
        return screen.availableGeometry().height() if screen is not None else 100000

    def _relayout(self) -> None:
        self._more_button.setChecked(not self.compact)
        self.current_color.setChecked(self._palette_open)
        self._more_button.setToolTip("Mostrar menos ferramentas" if not self.compact else "Mostrar todas as ferramentas")
        if self.orientation == "vertical":
            self._fill(columns=1)
            if self.sizeHint().height() > self._available_height() - 16:
                self._fill(columns=2)
        else:
            self._fill(columns=0)
        self.resize(self.sizeHint())
        if self.isVisible():
            self._keep_on_screen()

    def _fill(self, columns: int) -> None:
        grid = self._grid
        while grid.count():
            grid.takeAt(0)
        for line in self._separators:
            line.hide()
            line.deleteLater()
        self._separators = []
        for widget in self._all_widgets():
            widget.hide()

        groups = self._groups()
        center = Qt.AlignmentFlag.AlignCenter
        vertical = columns > 0
        if vertical:
            grid.setContentsMargins(6, 8, 6, 8)
        else:
            grid.setContentsMargins(8, 6, 8, 6)

        row = 0
        column = 0
        for index, group in enumerate(groups):
            if index:
                if vertical:
                    grid.addWidget(self._separator(True), row, 0, 1, columns)
                    row += 1
                else:
                    grid.addWidget(self._separator(False), 0, column)
                    column += 1
            if vertical and columns == 2 and group and group[0] is self._minus:
                grid.addWidget(self._minus, row, 0)
                grid.addWidget(self._plus, row, 1)
                grid.addWidget(self.width_label, row + 1, 0, 1, 2, center)
                row += 2
            elif vertical:
                for position, widget in enumerate(group):
                    grid.addWidget(widget, row + position // columns, position % columns, center)
                row += (len(group) + columns - 1) // columns
            else:
                for widget in group:
                    grid.addWidget(widget, 0, column)
                    column += 1
            for widget in group:
                widget.show()

        grid.invalidate()
        grid.activate()
        self.layout().invalidate()
        self.layout().activate()

    def refresh_tooltips(self) -> None:
        for tool, button in self.tool_buttons.items():
            button.setToolTip(
                describe(TOOL_LABELS[tool], self.config["local_hotkeys"].get("tool_" + tool, ""))
            )
        for index, button in enumerate(self.color_buttons):
            button.setIcon(icons.color_swatch(self.config["palette"][index]))
            button.setToolTip(self._color_tooltip(index))
        self.current_color.setToolTip(
            describe("Escolher cor", self.config["local_hotkeys"].get("next_color", ""))
        )

    def sync(self, overlay) -> None:
        self._syncing = True
        button = self.tool_buttons.get(overlay.tool)
        if button is not None:
            button.setChecked(True)
        for index, swatch in enumerate(self.color_buttons):
            swatch.setChecked(index == overlay.color_index)
        self.current_color.setIcon(icons.color_swatch(overlay.color))
        self.width_label.setText(str(int(overlay.pen_width)))
        self.toggle_buttons["toggle_freeze"].setChecked(overlay.frozen)
        self.toggle_buttons["toggle_clickthrough"].setChecked(overlay.click_through)
        self.toggle_buttons["toggle_smoothing"].setChecked(
            bool(self.config.get("smoothing_enabled", True))
        )
        self._syncing = False

    def _keep_on_screen(self) -> None:
        from PySide6.QtGui import QGuiApplication

        screen = QGuiApplication.screenAt(self.frameGeometry().center()) or QGuiApplication.screenAt(
            self.pos()
        ) or QGuiApplication.primaryScreen()
        geometry = screen.availableGeometry()
        x = max(geometry.left(), min(self.x(), geometry.right() - self.width() + 1))
        y = max(geometry.top(), min(self.y(), geometry.bottom() - self.height() + 1))
        if (x, y) != (self.x(), self.y()):
            self.move(x, y)

    def place(self) -> None:
        from PySide6.QtGui import QCursor, QGuiApplication

        position = self.config.get("toolbar_position")
        if position and len(position) == 2:
            x, y = int(position[0]), int(position[1])
            screen = QGuiApplication.screenAt(QPoint(x, y)) or QGuiApplication.primaryScreen()
            geometry = screen.availableGeometry()
            x = max(geometry.left(), min(x, geometry.right() - self.width() + 1))
            y = max(geometry.top(), min(y, geometry.bottom() - self.height() + 1))
            self.move(x, y)
            return

        screen = QGuiApplication.screenAt(QCursor.pos()) or QGuiApplication.primaryScreen()
        geometry = screen.availableGeometry()
        if self.orientation == "vertical":
            self.move(geometry.left() + 24, geometry.center().y() - self.height() // 2)
        else:
            self.move(geometry.center().x() - self.width() // 2, geometry.top() + 24)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_origin = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_origin is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_origin)
            event.accept()

    def mouseReleaseEvent(self, event) -> None:
        if self._drag_origin is not None:
            self._drag_origin = None
            self._keep_on_screen()
            self.config["toolbar_position"] = [self.x(), self.y()]
            event.accept()


LOCAL_ACTION_LABELS = LOCAL_ACTIONS
