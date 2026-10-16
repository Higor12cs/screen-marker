from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QKeySequenceEdit,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from . import icons
from .config import GLOBAL_ACTIONS, LOCAL_ACTIONS, Config
from .hotkeys import MOD_ALT, MOD_CONTROL, MOD_WIN, parse_sequence
from .shapes import TOOL_LABELS, TOOLS


class HotkeyRow(QWidget):
    def __init__(self, sequence: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.editor = QKeySequenceEdit(QKeySequence(sequence), self)
        self.editor.setMaximumSequenceLength(1)
        clear = QPushButton("Limpar", self)
        clear.setFixedWidth(70)
        clear.clicked.connect(self.editor.clear)
        layout.addWidget(self.editor)
        layout.addWidget(clear)

    def value(self) -> str:
        return self.editor.keySequence().toString(QKeySequence.SequenceFormat.PortableText)

    def set_value(self, sequence: str) -> None:
        self.editor.setKeySequence(QKeySequence(sequence))


def _scrollable(widget: QWidget) -> QScrollArea:
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setWidget(widget)
    return area


class SettingsDialog(QDialog):
    def __init__(self, config: Config, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("ScreenMarker — Configurações")
        self.setWindowIcon(icons.app_icon())
        self.setMinimumSize(620, 620)

        self.global_rows: dict[str, HotkeyRow] = {}
        self.local_rows: dict[str, HotkeyRow] = {}
        self.color_buttons: list[QPushButton] = []
        self.palette = list(config["palette"])

        tabs = QTabWidget(self)
        tabs.addTab(_scrollable(self._build_hotkeys(GLOBAL_ACTIONS, config["global_hotkeys"], self.global_rows)), "Atalhos globais")
        tabs.addTab(_scrollable(self._build_hotkeys(LOCAL_ACTIONS, config["local_hotkeys"], self.local_rows)), "Atalhos da marcação")
        tabs.addTab(_scrollable(self._build_general()), "Aparência e geral")

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.RestoreDefaults,
            self,
        )
        buttons.button(QDialogButtonBox.StandardButton.Save).setText("Salvar")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        buttons.button(QDialogButtonBox.StandardButton.RestoreDefaults).setText("Restaurar padrões")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.RestoreDefaults).clicked.connect(self.restore_defaults)

        layout = QVBoxLayout(self)
        layout.addWidget(tabs)
        layout.addWidget(buttons)

    def _build_hotkeys(self, actions: dict[str, str], values: dict[str, str], store: dict[str, HotkeyRow]) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        hint = QLabel(
            "Clique no campo e pressione a combinação desejada. "
            "Deixe vazio para desativar o atalho."
        )
        hint.setWordWrap(True)
        form.addRow(hint)
        for action, label in actions.items():
            row = HotkeyRow(values.get(action, ""), page)
            store[action] = row
            form.addRow(label, row)
        return page

    def _build_general(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        colors_box = QGroupBox("Cores da paleta", page)
        grid = QGridLayout(colors_box)
        for index, color in enumerate(self.palette):
            button = QPushButton(colors_box)
            button.setFixedSize(70, 28)
            button.clicked.connect(lambda _=False, i=index: self.pick_color(i))
            self.color_buttons.append(button)
            grid.addWidget(QLabel("Cor %d" % (index + 1), colors_box), index // 4, (index % 4) * 2)
            grid.addWidget(button, index // 4, (index % 4) * 2 + 1)
        self._refresh_color_buttons()
        layout.addWidget(colors_box)

        drawing_box = QGroupBox("Desenho", page)
        form = QFormLayout(drawing_box)

        self.tool_combo = QComboBox(drawing_box)
        for tool in TOOLS:
            self.tool_combo.addItem(TOOL_LABELS[tool], tool)
        index = self.tool_combo.findData(self.config["default_tool"])
        self.tool_combo.setCurrentIndex(max(0, index))
        form.addRow("Ferramenta inicial", self.tool_combo)

        self.width_spin = QSpinBox(drawing_box)
        self.width_spin.setRange(1, 60)
        self.width_spin.setValue(int(self.config["pen_width"]))
        form.addRow("Espessura do traço", self.width_spin)

        self.font_spin = QSpinBox(drawing_box)
        self.font_spin.setRange(8, 96)
        self.font_spin.setValue(int(self.config["font_size"]))
        form.addRow("Tamanho do texto", self.font_spin)

        self.opacity_spin = QDoubleSpinBox(drawing_box)
        self.opacity_spin.setRange(0.05, 1.0)
        self.opacity_spin.setSingleStep(0.05)
        self.opacity_spin.setValue(float(self.config["highlighter_opacity"]))
        form.addRow("Opacidade do marca-texto", self.opacity_spin)

        self.smoothing_check = QCheckBox("Suavizar o traço livre", drawing_box)
        self.smoothing_check.setChecked(bool(self.config.get("smoothing_enabled", True)))
        form.addRow(self.smoothing_check)

        self.smoothing_spin = QDoubleSpinBox(drawing_box)
        self.smoothing_spin.setRange(0.0, 1.0)
        self.smoothing_spin.setSingleStep(0.05)
        self.smoothing_spin.setValue(float(self.config.get("smoothing", 0.5)))
        form.addRow("Intensidade da suavização", self.smoothing_spin)

        self.straighten_check = QCheckBox(
            "Endireitar automaticamente traços quase retos", drawing_box
        )
        self.straighten_check.setChecked(bool(self.config.get("straighten", True)))
        form.addRow(self.straighten_check)

        self.dim_spin = QDoubleSpinBox(drawing_box)
        self.dim_spin.setRange(0.0, 0.8)
        self.dim_spin.setSingleStep(0.05)
        self.dim_spin.setValue(float(self.config.get("dim_background", 0.0)))
        form.addRow("Escurecer tela congelada", self.dim_spin)

        layout.addWidget(drawing_box)

        general_box = QGroupBox("Geral", page)
        general_form = QFormLayout(general_box)

        self.frozen_check = QCheckBox("Iniciar a marcação com a tela congelada", general_box)
        self.frozen_check.setChecked(bool(self.config["start_frozen"]))
        general_form.addRow(self.frozen_check)

        self.toolbar_check = QCheckBox("Mostrar a barra de ferramentas", general_box)
        self.toolbar_check.setChecked(bool(self.config["toolbar_visible"]))
        general_form.addRow(self.toolbar_check)

        self.orientation_combo = QComboBox(general_box)
        self.orientation_combo.addItem("Horizontal", "horizontal")
        self.orientation_combo.addItem("Vertical", "vertical")
        index = self.orientation_combo.findData(self.config.get("toolbar_orientation", "horizontal"))
        self.orientation_combo.setCurrentIndex(max(0, index))
        general_form.addRow("Orientação da barra", self.orientation_combo)

        self.compact_check = QCheckBox("Barra resumida (só as ferramentas principais)", general_box)
        self.compact_check.setChecked(bool(self.config.get("toolbar_compact", True)))
        general_form.addRow(self.compact_check)

        self.autostart_check = QCheckBox("Iniciar junto com o Windows", general_box)
        self.autostart_check.setChecked(bool(self.config["autostart"]))
        general_form.addRow(self.autostart_check)

        directory_row = QWidget(general_box)
        directory_layout = QHBoxLayout(directory_row)
        directory_layout.setContentsMargins(0, 0, 0, 0)
        self.directory_edit = QLineEdit(str(self.config.save_directory), directory_row)
        browse = QPushButton("Escolher...", directory_row)
        browse.clicked.connect(self.pick_directory)
        directory_layout.addWidget(self.directory_edit)
        directory_layout.addWidget(browse)
        general_form.addRow("Pasta das imagens", directory_row)

        reset_position = QPushButton("Recentralizar barra de ferramentas", general_box)
        reset_position.clicked.connect(lambda: self.config.__setitem__("toolbar_position", None))
        general_form.addRow(reset_position)

        layout.addWidget(general_box)
        layout.addStretch(1)
        return page

    def _refresh_color_buttons(self) -> None:
        for index, button in enumerate(self.color_buttons):
            color = self.palette[index]
            button.setText(color)
            text_color = "#000000" if QColor(color).lightnessF() > 0.6 else "#ffffff"
            button.setStyleSheet(
                "background: %s; color: %s; border: 1px solid #888; border-radius: 4px;"
                % (color, text_color)
            )

    def pick_color(self, index: int) -> None:
        color = QColorDialog.getColor(QColor(self.palette[index]), self, "Escolha a cor %d" % (index + 1))
        if color.isValid():
            self.palette[index] = color.name()
            self._refresh_color_buttons()

    def pick_directory(self) -> None:
        directory = QFileDialog.getExistingDirectory(self, "Pasta das imagens", self.directory_edit.text())
        if directory:
            self.directory_edit.setText(directory)

    def restore_defaults(self) -> None:
        if QMessageBox.question(self, "Restaurar padrões", "Voltar todas as configurações para o padrão?") != QMessageBox.StandardButton.Yes:
            return
        from .config import DEFAULTS

        for action, row in self.global_rows.items():
            row.set_value(DEFAULTS["global_hotkeys"].get(action, ""))
        for action, row in self.local_rows.items():
            row.set_value(DEFAULTS["local_hotkeys"].get(action, ""))
        self.palette = list(DEFAULTS["palette"])
        self._refresh_color_buttons()
        self.width_spin.setValue(DEFAULTS["pen_width"])
        self.font_spin.setValue(DEFAULTS["font_size"])
        self.opacity_spin.setValue(DEFAULTS["highlighter_opacity"])
        self.dim_spin.setValue(DEFAULTS["dim_background"])
        self.smoothing_check.setChecked(DEFAULTS["smoothing_enabled"])
        self.smoothing_spin.setValue(DEFAULTS["smoothing"])
        self.straighten_check.setChecked(DEFAULTS["straighten"])
        self.frozen_check.setChecked(DEFAULTS["start_frozen"])
        self.toolbar_check.setChecked(DEFAULTS["toolbar_visible"])
        self.orientation_combo.setCurrentIndex(
            max(0, self.orientation_combo.findData(DEFAULTS["toolbar_orientation"]))
        )
        self.compact_check.setChecked(DEFAULTS["toolbar_compact"])
        self.tool_combo.setCurrentIndex(max(0, self.tool_combo.findData(DEFAULTS["default_tool"])))

    def _duplicates(self, rows: dict[str, HotkeyRow], labels: dict[str, str]) -> str | None:
        seen: dict[str, str] = {}
        for action, row in rows.items():
            value = row.value()
            if not value:
                continue
            key = value.lower()
            if key in seen:
                return "%s está em %s e %s." % (value, seen[key], labels[action])
            seen[key] = labels[action]
        return None

    def _unsafe_global(self) -> str | None:
        for action, row in self.global_rows.items():
            value = row.value()
            if not value:
                continue
            parsed = parse_sequence(value)
            if parsed is None:
                return "%s não pode ser usado como atalho global (%s)." % (value, GLOBAL_ACTIONS[action])
            modifiers, vk = parsed
            if not modifiers & (MOD_CONTROL | MOD_ALT | MOD_WIN) and not 0x70 <= vk <= 0x87:
                return (
                    "%s sozinho bloquearia essa tecla em todo o Windows (%s). "
                    "Use Ctrl, Alt ou Win junto." % (value, GLOBAL_ACTIONS[action])
                )
        return None

    def _shadowed_local(self) -> str | None:
        globals_in_use = {row.value().lower(): action for action, row in self.global_rows.items() if row.value()}
        for action, row in self.local_rows.items():
            value = row.value()
            if value and value.lower() in globals_in_use:
                return "%s já é atalho global (%s) e nunca chegaria em %s." % (
                    value,
                    GLOBAL_ACTIONS[globals_in_use[value.lower()]],
                    LOCAL_ACTIONS[action],
                )
        return None

    def accept(self) -> None:
        conflict = (
            self._duplicates(self.global_rows, GLOBAL_ACTIONS)
            or self._duplicates(self.local_rows, LOCAL_ACTIONS)
            or self._unsafe_global()
            or self._shadowed_local()
        )
        if conflict:
            QMessageBox.warning(self, "Atalho inválido", conflict)
            return
        for action, row in self.global_rows.items():
            self.config["global_hotkeys"][action] = row.value()
        for action, row in self.local_rows.items():
            self.config["local_hotkeys"][action] = row.value()
        self.config["palette"] = list(self.palette)
        self.config["default_tool"] = self.tool_combo.currentData()
        self.config["pen_width"] = self.width_spin.value()
        self.config["font_size"] = self.font_spin.value()
        self.config["highlighter_opacity"] = self.opacity_spin.value()
        self.config["smoothing_enabled"] = self.smoothing_check.isChecked()
        self.config["smoothing"] = self.smoothing_spin.value()
        self.config["straighten"] = self.straighten_check.isChecked()
        self.config["dim_background"] = self.dim_spin.value()
        self.config["start_frozen"] = self.frozen_check.isChecked()
        self.config["toolbar_visible"] = self.toolbar_check.isChecked()
        self.config["toolbar_orientation"] = self.orientation_combo.currentData()
        self.config["toolbar_compact"] = self.compact_check.isChecked()
        self.config["autostart"] = self.autostart_check.isChecked()
        self.config["save_directory"] = self.directory_edit.text().strip()
        self.config.save()
        super().accept()
