from __future__ import annotations

import os
import sys
from pathlib import Path


os.environ.setdefault("QT_QPA_PLATFORM", "windows")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
OUTPUT_PATH = PROJECT_ROOT / "docs" / "images" / "app-preview.png"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from PySide6.QtWidgets import QApplication

from batch_renamer.app import MainWindow
from batch_renamer.core.models import FileItem


DEMO_FOLDER = Path(r"D:\影视项目\镜头序列")
DEMO_NAMES = (
    "镜头_001_城市晨景.exr",
    "镜头_002_城市晨景.exr",
    "镜头_003_城市晨景.exr",
    "镜头_010_城市晨景.exr",
    "镜头_011_角色近景.exr",
    "镜头_012_角色近景.exr",
    "镜头_020_动作预演.mp4",
    "镜头_021_动作预演.mp4",
    "镜头_022_动作预演.mp4",
    "镜头_030_合成预览.mp4",
    "镜头_031_合成预览.mp4",
    "镜头_032_合成预览.mp4",
    "镜头_040_天空素材.png",
    "镜头_041_天空素材.png",
    "镜头_042_天空素材.png",
    "镜头_050_场景参考.jpg",
    "镜头_051_场景参考.jpg",
    "镜头_052_场景参考.jpg",
    "镜头_100_终版输出.exr",
    "镜头_101_终版输出.exr",
    "镜头_102_终版输出.exr",
    "镜头_110_客户预览.mp4",
    "镜头_111_客户预览.mp4",
    "镜头_120_交付版本.mp4",
)


def main() -> int:
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    window = MainWindow()
    window.show()
    app.processEvents()

    scale = window.scale_for_available_size(1920, 1080)
    window.apply_ui_scale(scale)
    window.resize(round(window.BASE_WIDTH * scale), round(window.BASE_HEIGHT * scale))
    window.path_edit.setText(str(DEMO_FOLDER))
    window.items = [FileItem(DEMO_FOLDER / name) for name in DEMO_NAMES]

    # 发布预览只使用固定脱敏数据，不读取或展示本机用户文件。
    window._format_size = lambda path: f"{24 + sum(map(ord, path.name)) % 380 / 10:.1f} MB"  # type: ignore[method-assign]
    window._format_mtime = lambda path: "2026-07-21 14:30"  # type: ignore[method-assign]
    window.prefix_enabled.setChecked(True)
    window.prefix_text.setText("交付_")
    window.number_enabled.setChecked(True)
    window.number_digits.setValue(3)
    window.number_start.setValue(1)
    window.number_step.setValue(1)
    window.number_separator.setText("_")
    window.preview()
    app.processEvents()

    image = window.grab().toImage()
    if image.isNull() or image.width() != 1920 or image.height() > 1080:
        raise SystemExit(f"发布预览尺寸异常：{image.width()}x{image.height()}")
    sampled_colors = {
        image.pixelColor(x, y).rgba()
        for x in range(0, image.width(), max(1, image.width() // 50))
        for y in range(0, image.height(), max(1, image.height() // 30))
    }
    if len(sampled_colors) < 12:
        raise SystemExit("发布预览疑似空白或颜色层级不足。")
    if not image.save(str(OUTPUT_PATH), "PNG"):
        raise SystemExit(f"无法保存发布预览：{OUTPUT_PATH}")

    window.close()
    app.quit()
    print(f"GitHub 界面预览：{OUTPUT_PATH}")
    print(f"尺寸：{image.width()}x{image.height()}，演示文件：{len(DEMO_NAMES)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
