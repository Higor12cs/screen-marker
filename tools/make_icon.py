from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtGui import QGuiApplication

from screen_marker import icons


def main() -> int:
    app = QGuiApplication(sys.argv)
    icon = icons.app_icon()
    frames = []
    from PIL import Image

    for size in (16, 24, 32, 48, 64, 128, 256):
        pixmap = icon.pixmap(size, size)
        buffer = QBuffer()
        buffer.open(QIODevice.OpenModeFlag.WriteOnly)
        pixmap.save(buffer, "PNG")
        from io import BytesIO

        frames.append(Image.open(BytesIO(buffer.data().data())).convert("RGBA"))

    target = ROOT / "screen_marker" / "resources" / "icon.ico"
    target.parent.mkdir(parents=True, exist_ok=True)
    frames[-1].save(target, format="ICO", sizes=[(f.width, f.height) for f in frames])
    print("icone gerado em", target)
    del app
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
