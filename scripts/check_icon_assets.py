from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QIcon, QImageReader
from PySide6.QtWidgets import QApplication


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PNG_PATH = PROJECT_ROOT / "build_assets" / "app_icon.png"
ICO_PATH = PROJECT_ROOT / "build_assets" / "app_icon.ico"
REQUIRED_ICO_SIZES = {16, 20, 24, 32, 40, 48, 64, 96, 128, 256}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="检查软件图标原图保真与 Windows 多尺寸资源。")
    parser.add_argument("--original", type=Path, help="可选：用户确认的原始 PNG，用于逐字节摘要核对。")
    args = parser.parse_args()

    for path in (PNG_PATH, ICO_PATH):
        if not path.is_file():
            raise SystemExit(f"缺少图标资源：{path}")

    reader = QImageReader(str(PNG_PATH))
    png_size = reader.size()
    if not png_size.isValid() or png_size.width() != png_size.height():
        raise SystemExit(f"PNG 必须是有效正方形：{png_size.width()}x{png_size.height()}")

    app = QApplication.instance() or QApplication([])
    icon = QIcon(str(ICO_PATH))
    if icon.isNull():
        raise SystemExit("ICO 无法被 Qt 读取。")
    actual_sizes = {size.width() for size in icon.availableSizes() if size.width() == size.height()}
    missing_sizes = sorted(REQUIRED_ICO_SIZES - actual_sizes)
    if missing_sizes:
        raise SystemExit(f"ICO 缺少尺寸：{missing_sizes}；实际：{sorted(actual_sizes)}")

    png_hash = sha256(PNG_PATH)
    if args.original:
        original = args.original.resolve()
        if not original.is_file():
            raise SystemExit(f"原图不存在：{original}")
        original_hash = sha256(original)
        if png_hash != original_hash:
            raise SystemExit(f"仓库 PNG 与原图不一致：{png_hash} != {original_hash}")
        print(f"原图 SHA-256 一致：{png_hash}")

    print(f"PNG：{png_size.width()}x{png_size.height()}，SHA-256={png_hash}")
    print(f"ICO 尺寸：{sorted(actual_sizes)}")
    app.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
