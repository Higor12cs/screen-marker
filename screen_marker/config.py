from __future__ import annotations

import json
import os
from pathlib import Path

APP_NAME = "ScreenMarker"
APP_TITLE = "ScreenMarker"
ORG_NAME = "ScreenMarker"

CONFIG_DIR = Path(os.environ.get("APPDATA") or Path.home()) / APP_NAME
CONFIG_PATH = CONFIG_DIR / "config.json"

GLOBAL_ACTIONS = {
    "toggle_overlay": "Ligar/desligar marcação",
    "toggle_freeze": "Marcar com a tela congelada",
    "toggle_clickthrough": "Passar cliques para o Windows",
    "toggle_toolbar": "Mostrar / ocultar a barra de ferramentas",
    "capture_clipboard": "Copiar a tela para a área de transferência",
    "open_settings": "Abrir configurações",
    "quit_app": "Sair do aplicativo",
}

LOCAL_ACTIONS = {
    "tool_pen": "Caneta (desenho livre)",
    "tool_highlighter": "Marca-texto",
    "tool_line": "Linha",
    "tool_arrow": "Seta",
    "tool_rectangle": "Retângulo",
    "tool_ellipse": "Círculo / elipse",
    "tool_triangle": "Triângulo",
    "tool_text": "Texto",
    "tool_eraser": "Borracha",
    "undo": "Desfazer",
    "redo": "Refazer",
    "erase_last": "Apagar último desenho",
    "clear": "Apagar tudo",
    "toggle_freeze": "Congelar / descongelar a tela",
    "toggle_clickthrough": "Passar cliques para o Windows",
    "toggle_toolbar": "Mostrar / ocultar a barra",
    "toggle_smoothing": "Suavizar traço (liga/desliga)",
    "save_png": "Salvar imagem em PNG",
    "copy_clipboard": "Copiar imagem",
    "width_up": "Traço mais grosso",
    "width_down": "Traço mais fino",
    "next_color": "Próxima cor",
    "exit_overlay": "Sair da marcação",
    "color_1": "Cor 1",
    "color_2": "Cor 2",
    "color_3": "Cor 3",
    "color_4": "Cor 4",
    "color_5": "Cor 5",
    "color_6": "Cor 6",
    "color_7": "Cor 7",
    "color_8": "Cor 8",
}

DEFAULTS = {
    "global_hotkeys": {
        "toggle_overlay": "Ctrl+Alt+D",
        "toggle_freeze": "Ctrl+Alt+F",
        "toggle_clickthrough": "Ctrl+Alt+P",
        "toggle_toolbar": "Ctrl+Alt+B",
        "capture_clipboard": "Ctrl+Alt+C",
        "open_settings": "Ctrl+Alt+O",
        "quit_app": "",
    },
    "local_hotkeys": {
        "tool_pen": "P",
        "tool_highlighter": "H",
        "tool_line": "L",
        "tool_arrow": "A",
        "tool_rectangle": "R",
        "tool_ellipse": "C",
        "tool_triangle": "T",
        "tool_text": "X",
        "tool_eraser": "E",
        "undo": "Ctrl+Z",
        "redo": "Ctrl+Y",
        "erase_last": "Backspace",
        "clear": "Del",
        "toggle_freeze": "F",
        "toggle_clickthrough": "Space",
        "toggle_toolbar": "Tab",
        "toggle_smoothing": "S",
        "save_png": "Ctrl+S",
        "copy_clipboard": "Ctrl+C",
        "width_up": "+",
        "width_down": "-",
        "next_color": "N",
        "exit_overlay": "Esc",
        "color_1": "1",
        "color_2": "2",
        "color_3": "3",
        "color_4": "4",
        "color_5": "5",
        "color_6": "6",
        "color_7": "7",
        "color_8": "8",
    },
    "palette": [
        "#ff2d2d",
        "#ffd400",
        "#2dd45f",
        "#2f8fff",
        "#ff8a00",
        "#c45cff",
        "#ffffff",
        "#101010",
    ],
    "color_index": 0,
    "pen_width": 4,
    "font_size": 28,
    "highlighter_opacity": 0.35,
    "smoothing": 0.5,
    "smoothing_enabled": True,
    "straighten": True,
    "straighten_tolerance": 0.04,
    "default_tool": "pen",
    "start_frozen": False,
    "toolbar_visible": True,
    "toolbar_position": None,
    "toolbar_orientation": "horizontal",
    "toolbar_scale": 1.0,
    "autostart": False,
    "save_directory": "",
    "dim_background": 0.0,
}


class Config:
    def __init__(self, data: dict | None = None) -> None:
        self.data = json.loads(json.dumps(DEFAULTS))
        if data:
            self.merge(data)

    def merge(self, data: dict) -> None:
        for key, value in data.items():
            if key not in self.data:
                continue
            if isinstance(self.data[key], dict) and isinstance(value, dict):
                self.data[key].update(value)
            else:
                self.data[key] = value
        for key, value in DEFAULTS["global_hotkeys"].items():
            self.data["global_hotkeys"].setdefault(key, value)
        for key, value in DEFAULTS["local_hotkeys"].items():
            self.data["local_hotkeys"].setdefault(key, value)

    def __getitem__(self, key: str):
        return self.data[key]

    def __setitem__(self, key: str, value) -> None:
        self.data[key] = value

    def get(self, key: str, fallback=None):
        return self.data.get(key, fallback)

    @property
    def save_directory(self) -> Path:
        raw = self.data.get("save_directory") or ""
        if raw:
            return Path(raw)
        return Path.home() / "Pictures" / APP_NAME

    @classmethod
    def load(cls) -> "Config":
        try:
            with CONFIG_PATH.open("r", encoding="utf-8") as handle:
                return cls(json.load(handle))
        except (OSError, ValueError):
            return cls()

    def save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with CONFIG_PATH.open("w", encoding="utf-8") as handle:
            json.dump(self.data, handle, indent=2, ensure_ascii=False)

    def reset(self) -> None:
        self.data = json.loads(json.dumps(DEFAULTS))
