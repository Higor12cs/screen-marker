from __future__ import annotations

import sys
import winreg

from PySide6.QtCore import QObject, Qt, QTimer
from PySide6.QtGui import QAction, QGuiApplication
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from . import icons, winutil
from .capture import grab_desktop
from .config import APP_NAME, GLOBAL_ACTIONS, LOCAL_ACTIONS, Config
from .hotkeys import GlobalHotkeyManager
from .overlay import OverlayWindow
from .settings_dialog import SettingsDialog
from .toolbar import Toolbar

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def apply_autostart(enabled: bool) -> None:
    target = sys.executable
    if not getattr(sys, "frozen", False):
        target = '"%s" -m screen_marker' % sys.executable
    else:
        target = '"%s"' % target
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_ALL_ACCESS) as key:
        if enabled:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, target)
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass


class ScreenMarker(QObject):
    def __init__(self, app: QApplication) -> None:
        super().__init__()
        self.app = app
        self.config = Config.load()
        self.overlay = OverlayWindow(self.config)
        self.toolbar = Toolbar(self.config)
        self.hotkeys = GlobalHotkeyManager(self)
        self.settings_dialog: SettingsDialog | None = None
        self._click_through_state = False

        self.overlay.state_changed.connect(self.sync_toolbar)
        self.overlay.closed.connect(self.toolbar.hide)
        self.overlay.action_requested.connect(self.handle_action)
        self.overlay.capture_prepare = self.toolbar.hide
        self.overlay.capture_restore = self.restore_toolbar
        self.overlay.raise_extras = self.raise_toolbar
        self.toolbar.action_triggered.connect(self.handle_action)
        self.hotkeys.triggered.connect(self.handle_global)

        self.tray = QSystemTrayIcon(icons.app_icon(), self)
        self.tray.setToolTip(APP_NAME)
        self.tray.activated.connect(self.on_tray_activated)
        self.build_tray_menu()
        self.tray.show()

        self.app.installNativeEventFilter(self.hotkeys)
        self.register_hotkeys()
        apply_autostart(bool(self.config["autostart"]))
        QTimer.singleShot(600, self.announce)

    def announce(self) -> None:
        toggle = self.config["global_hotkeys"].get("toggle_overlay", "")
        if self.hotkeys.failures:
            self.tray.showMessage(
                APP_NAME,
                "Não consegui registrar: %s. Outro programa já usa esse atalho."
                % ", ".join(self.hotkeys.failures),
                QSystemTrayIcon.MessageIcon.Warning,
                6000,
            )
        else:
            self.tray.showMessage(
                APP_NAME,
                "Pronto. Pressione %s para marcar a tela." % toggle,
                icons.app_icon(),
                4000,
            )

    def build_tray_menu(self) -> None:
        menu = QMenu()
        hotkeys = self.config["global_hotkeys"]

        draw_action = QAction("Marcar a tela\t%s" % hotkeys.get("toggle_overlay", ""), menu)
        draw_action.triggered.connect(lambda: self.handle_global("toggle_overlay"))
        menu.addAction(draw_action)

        freeze_action = QAction("Marcar com a tela congelada\t%s" % hotkeys.get("toggle_freeze", ""), menu)
        freeze_action.triggered.connect(lambda: self.handle_global("toggle_freeze"))
        menu.addAction(freeze_action)

        copy_action = QAction("Copiar a tela\t%s" % hotkeys.get("capture_clipboard", ""), menu)
        copy_action.triggered.connect(lambda: self.handle_global("capture_clipboard"))
        menu.addAction(copy_action)

        menu.addSeparator()

        settings_action = QAction("Configurações...", menu)
        settings_action.triggered.connect(self.open_settings)
        menu.addAction(settings_action)

        help_action = QAction("Lista de atalhos", menu)
        help_action.triggered.connect(self.show_shortcuts)
        menu.addAction(help_action)

        menu.addSeparator()

        quit_action = QAction("Sair", menu)
        quit_action.triggered.connect(self.quit)
        menu.addAction(quit_action)

        self.tray.setContextMenu(menu)

    def register_hotkeys(self) -> None:
        self.hotkeys.register(self.config["global_hotkeys"])

    def on_tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.handle_global("toggle_overlay")

    def show_toolbar(self) -> None:
        if not self.config["toolbar_visible"]:
            return
        self.toolbar.adjustSize()
        self.toolbar.place()
        self.toolbar.show()
        self.toolbar.raise_()
        self.raise_toolbar()
        self.sync_toolbar()

    def raise_toolbar(self) -> None:
        if self.toolbar.isVisible():
            winutil.keep_on_top(int(self.toolbar.winId()))

    def restore_toolbar(self) -> None:
        if self.config["toolbar_visible"] and self.overlay.isVisible():
            self.toolbar.show()
            self.toolbar.raise_()
            self.raise_toolbar()
            self.sync_toolbar()

    def sync_toolbar(self) -> None:
        if self.toolbar.isVisible():
            self.toolbar.sync(self.overlay)
        if self.overlay.click_through != self._click_through_state:
            self._click_through_state = self.overlay.click_through
            if self.overlay.click_through:
                self.tray.showMessage(
                    APP_NAME,
                    "Cliques liberados para o Windows. %s volta para a marcação."
                    % (self.config["global_hotkeys"].get("toggle_overlay", "") or "O atalho de marcação"),
                    icons.app_icon(),
                    3500,
                )

    def start_overlay(self, frozen: bool) -> None:
        self.overlay.start(frozen=frozen)
        self.show_toolbar()
        self.overlay.refocus()

    def is_locked_out(self) -> bool:
        return (
            self.overlay.click_through
            or not self.config["toolbar_visible"]
            or not self.overlay.isActiveWindow()
        )

    def ensure_interactive(self) -> None:
        if self.overlay.click_through:
            self.overlay.set_click_through(False)
        if not self.config["toolbar_visible"]:
            self.config["toolbar_visible"] = True
        self.show_toolbar()
        self.overlay.refocus()

    def handle_global(self, action: str) -> None:
        if action == "toggle_overlay":
            if not self.overlay.isVisible():
                self.start_overlay(bool(self.config["start_frozen"]))
            elif self.is_locked_out():
                self.ensure_interactive()
            else:
                self.overlay.stop()
        elif action == "toggle_freeze":
            if not self.overlay.isVisible():
                self.start_overlay(True)
            else:
                self.ensure_interactive()
                self.overlay.freeze(not self.overlay.frozen)
        elif action == "toggle_clickthrough":
            if self.overlay.isVisible():
                self.overlay.set_click_through(not self.overlay.click_through)
        elif action == "capture_clipboard":
            if self.overlay.isVisible():
                self.overlay.copy_to_clipboard()
            else:
                QGuiApplication.clipboard().setPixmap(grab_desktop())
            self.tray.showMessage(APP_NAME, "Imagem copiada.", icons.app_icon(), 2000)
        elif action == "toggle_toolbar":
            self.handle_action("toggle_toolbar")
        elif action == "open_settings":
            self.open_settings()
        elif action == "quit_app":
            self.quit()

    def handle_action(self, action: str) -> None:
        if action.startswith("set_width:"):
            self.overlay.set_pen_width(float(action.split(":")[1]))
            return
        if action == "open_settings":
            self.open_settings()
            return
        if action == "toggle_toolbar":
            self.config["toolbar_visible"] = not self.config["toolbar_visible"]
            if self.config["toolbar_visible"] and self.overlay.isVisible():
                self.show_toolbar()
            else:
                self.toolbar.hide()
            self.overlay.refocus()
            return
        if action == "save_png":
            path = self.overlay.save_png()
            self.tray.showMessage(
                APP_NAME,
                "Salvo em %s" % path if path else "Não consegui salvar a imagem.",
                icons.app_icon(),
                3000,
            )
            self.overlay.refocus()
            return
        if action == "copy_clipboard":
            self.overlay.copy_to_clipboard()
            self.tray.showMessage(APP_NAME, "Imagem copiada.", icons.app_icon(), 2000)
            self.overlay.refocus()
            return
        self.overlay.run_action(action)
        if action != "exit_overlay":
            self.overlay.refocus()

    def open_settings(self) -> None:
        if self.overlay.isVisible():
            self.overlay.stop()
        if self.settings_dialog is not None and self.settings_dialog.isVisible():
            self.settings_dialog.raise_()
            self.settings_dialog.activateWindow()
            return
        dialog = SettingsDialog(self.config)
        self.settings_dialog = dialog
        if dialog.exec():
            self.register_hotkeys()
            self.build_tray_menu()
            self.toolbar.refresh_tooltips()
            self.toolbar.set_orientation(self.config["toolbar_orientation"])
            self.overlay.tool = self.config["default_tool"]
            self.overlay.font_size = int(self.config["font_size"])
            self.overlay.set_pen_width(float(self.config["pen_width"]))
            apply_autostart(bool(self.config["autostart"]))
            if self.hotkeys.failures:
                QMessageBox.warning(
                    None,
                    APP_NAME,
                    "Estes atalhos globais já estão em uso por outro programa: %s"
                    % ", ".join(self.hotkeys.failures),
                )
        self.settings_dialog = None

    def show_shortcuts(self) -> None:
        lines = ["<b>Atalhos globais</b><table>"]
        for action, label in GLOBAL_ACTIONS.items():
            sequence = self.config["global_hotkeys"].get(action, "") or "—"
            lines.append("<tr><td>%s</td><td><b>%s</b></td></tr>" % (label, sequence))
        lines.append("</table><br><b>Durante a marcação</b><table>")
        for action, label in LOCAL_ACTIONS.items():
            sequence = self.config["local_hotkeys"].get(action, "") or "—"
            lines.append("<tr><td>%s</td><td><b>%s</b></td></tr>" % (label, sequence))
        lines.append("</table>")
        box = QMessageBox()
        box.setWindowTitle("%s — atalhos" % APP_NAME)
        box.setWindowIcon(icons.app_icon())
        box.setTextFormat(Qt.TextFormat.RichText)
        box.setText("".join(lines))
        box.exec()

    def quit(self) -> None:
        self.config.save()
        self.hotkeys.unregister_all()
        self.tray.hide()
        self.app.quit()


def main() -> int:
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeDialogs, False)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_NAME)
    app.setWindowIcon(icons.app_icon())
    app.setQuitOnLastWindowClosed(False)

    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.critical(None, APP_NAME, "A área de notificação do Windows não está disponível.")
        return 1

    marker = ScreenMarker(app)
    app.marker = marker
    return app.exec()
