from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QScrollArea

from batch_renamer.app import MainWindow


RESOLUTIONS = [(1280, 720), (1366, 768), (1600, 900), (1920, 1080), (2200, 1152)]
DPI_CASES = [(1920, 1080, 100), (1536, 864, 125), (1280, 720, 150), (1097, 617, 175)]


def _sample_color_count(window: MainWindow) -> int:
    image = window.grab().toImage()
    step_x = max(1, image.width() // 40)
    step_y = max(1, image.height() // 24)
    colors = {
        image.pixelColor(x, y).rgba()
        for x in range(0, image.width(), step_x)
        for y in range(0, image.height(), step_y)
    }
    return len(colors)


def _label_checks(window: MainWindow) -> list[dict[str, object]]:
    checks: list[dict[str, object]] = []
    for label in window.findChildren(QLabel):
        if label.objectName() not in {"sidebarTitle", "sideSection", "stepLabel"}:
            continue
        text_width = label.fontMetrics().horizontalAdvance(label.text())
        available_width = label.contentsRect().width()
        checks.append(
            {
                "text": label.text(),
                "text_width": text_width,
                "available_width": available_width,
                "single_line": not label.wordWrap(),
                "fits": text_width <= available_width,
            }
        )
    return checks


def main() -> int:
    output_dir = PROJECT_ROOT / "artifacts" / "ui-resolution"
    output_dir.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    window = MainWindow()
    window.show()
    app.processEvents()

    cases: list[dict[str, object]] = []
    failures: list[str] = []
    for width, height in RESOLUTIONS:
        scale = window.scale_for_available_size(width, height)
        render_width = round(window.BASE_WIDTH * scale)
        render_height = round(window.BASE_HEIGHT * scale)
        window.apply_ui_scale(scale)
        window.resize(render_width, render_height)
        app.processEvents()

        image_name = f"workbench-{width}x{height}.png"
        image_path = output_dir / image_name
        window.grab().save(str(image_path), "PNG")
        labels = _label_checks(window)
        color_count = _sample_color_count(window)
        case = {
            "target_resolution": [width, height],
            "scale": round(scale, 6),
            "rendered_window": [window.width(), window.height()],
            "image": image_name,
            "fits_target": window.width() <= width and window.height() <= height,
            "horizontal_scroll_disabled": window.table.horizontalScrollBarPolicy()
            == Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
            "rule_scroll_area_count": len(window.findChildren(QScrollArea)),
            "sampled_color_count": color_count,
            "labels": labels,
        }
        cases.append(case)
        if not case["fits_target"]:
            failures.append(f"{width}x{height} 窗口超出目标")
        if any(not label["fits"] or not label["single_line"] for label in labels):
            failures.append(f"{width}x{height} 左侧文字裁切或换行")
        if color_count < 8:
            failures.append(f"{width}x{height} 截图疑似空白")

    dpi_cases = [
        {
            "physical_reference": [1920, 1080],
            "windows_scale_percent": dpi,
            "logical_available": [width, height],
            "application_scale": round(window.scale_for_available_size(width, height), 6),
        }
        for width, height, dpi in DPI_CASES
    ]
    manifest = {
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "cases": cases,
        "dpi_logic_cases": dpi_cases,
        "failures": failures,
        "notes": [
            "截图为 Qt offscreen 离屏渲染，不等同于真实多显示器或辅助技术验收。",
            "DPI 用 Qt 逻辑可用尺寸模拟，验证应用不会再次使用物理分辨率重复缩放。",
        ],
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    window.close()
    print(f"分辨率截图：{len(cases)}，失败：{len(failures)}")
    print(f"清单：{output_dir / 'manifest.json'}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
