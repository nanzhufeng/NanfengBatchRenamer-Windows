from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QIcon, QImage, QImageReader
from PySide6.QtWidgets import QApplication


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = PROJECT_ROOT / "build_assets" / "app_icon_source.png"
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
    parser.add_argument("--original", type=Path, help="可选：覆盖仓库内置的原始 PNG 校验基准。")
    args = parser.parse_args()

    for path in (SOURCE_PATH, PNG_PATH, ICO_PATH):
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

    original = (args.original or SOURCE_PATH).resolve()
    if not original.is_file():
        raise SystemExit(f"原图不存在：{original}")

    source_image = QImage(str(original)).convertToFormat(QImage.Format.Format_RGBA8888)
    rounded_image = QImage(str(PNG_PATH)).convertToFormat(QImage.Format.Format_RGBA8888)
    if source_image.size() != rounded_image.size():
        raise SystemExit("圆角图标尺寸与原图不一致。")

    source_bytes = bytes(source_image.constBits())
    rounded_bytes = bytes(rounded_image.constBits())
    neutralized_pixels = 0
    for offset in range(0, len(rounded_bytes), 4):
        red, green, blue = source_bytes[offset : offset + 3]
        expected = (red, green, blue)
        if max(expected) >= 95 and red >= green >= blue and red - blue <= 45:
            neutral = (54 * red + 183 * green + 19 * blue + 128) // 256
            expected = (neutral, neutral, neutral)
            if expected != (red, green, blue):
                neutralized_pixels += 1
        if rounded_bytes[offset + 3] and tuple(rounded_bytes[offset : offset + 3]) != expected:
            raise SystemExit(f"图标存在规则外 RGB 改动：offset={offset}")

    width = rounded_image.width()
    height = rounded_image.height()
    corner_alphas = [
        rounded_image.pixelColor(0, 0).alpha(),
        rounded_image.pixelColor(width - 1, 0).alpha(),
        rounded_image.pixelColor(0, height - 1).alpha(),
        rounded_image.pixelColor(width - 1, height - 1).alpha(),
    ]
    if any(corner_alphas) or rounded_image.pixelColor(width // 2, height // 2).alpha() != 255:
        raise SystemExit("透明圆角遮罩不符合预期。")
    expected_radius = round(width * 0.12)
    if rounded_image.pixelColor(0, expected_radius // 2).alpha() != 0:
        raise SystemExit("圆角半径过小，小尺寸下可能不可见。")
    if rounded_image.pixelColor(0, expected_radius).alpha() < 250:
        raise SystemExit("圆角半径或边缘位置异常。")

    png_hash = sha256(PNG_PATH)
    print(f"原图 SHA-256：{sha256(original)}")
    print(f"色彩校验：仅 {neutralized_pixels} 个低饱和暖白像素转为中性灰")
    print(f"圆角校验：四角透明，半径约 {expected_radius}px（12%）")
    print(f"PNG：{png_size.width()}x{png_size.height()}，SHA-256={png_hash}")
    print(f"ICO 尺寸：{sorted(actual_sizes)}")
    app.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
