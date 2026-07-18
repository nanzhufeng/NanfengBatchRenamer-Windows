from __future__ import annotations

import os
import sys
import tempfile
import unittest
from math import ceil
from pathlib import Path


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QScrollArea

from batch_renamer.app import IconSpinBox, MainWindow
from batch_renamer.core.models import FileItem


class UiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self) -> None:
        self.window = MainWindow()
        self.window.show()
        self.app.processEvents()

    def tearDown(self) -> None:
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    def test_final_workbench_identity_and_primary_layout_contract(self) -> None:
        self.assertEqual(self.window.windowTitle(), "南枫批量改名")
        self.assertEqual((self.window.minimumWidth(), self.window.minimumHeight()), (640, 360))
        self.assertEqual(
            self.window.table.horizontalScrollBarPolicy(),
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff,
        )
        self.assertGreater(self.window.table.columnWidth(4), self.window.table.columnWidth(3))
        self.assertEqual(self.window.findChildren(QScrollArea), [])
        self.assertTrue(self.window.number_separator.alignment() & Qt.AlignmentFlag.AlignLeft)

    def test_all_extensions_means_no_filter_restriction(self) -> None:
        self.window.extension_all_btn.setChecked(True)
        self.app.processEvents()

        self.assertEqual(self.window._selected_extension_filter(), "")
        self.assertFalse(any(button.isChecked() for button in self.window.extension_buttons.values()))

    def test_rapid_arrow_clicks_change_exactly_once_per_click(self) -> None:
        spin = IconSpinBox()
        spin.setRange(0, 1000)
        spin.resize(100, 34)
        spin.show()
        self.app.processEvents()

        for _ in range(25):
            QTest.mouseClick(spin._up_button, Qt.MouseButton.LeftButton)
        self.assertEqual(spin.value(), 25)

        for _ in range(7):
            QTest.mouseClick(spin._down_button, Qt.MouseButton.LeftButton)
        self.assertEqual(spin.value(), 18)

        spin.close()
        spin.deleteLater()

    def test_natural_sort_handles_different_digit_lengths_and_toggles_direction(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = [root / name for name in ("shot120.txt", "shot2.txt", "shot10.txt", "shot1.txt")]
            for path in paths:
                path.write_text(path.name, encoding="utf-8")
            self.window.items = [FileItem(path) for path in paths]
            self.window.refresh_table()

            self.window.sort_by_column(3)
            self.assertEqual(
                [item.original_name for item in self.window.items],
                ["shot1.txt", "shot2.txt", "shot10.txt", "shot120.txt"],
            )

            self.window.sort_by_column(3)
            self.assertEqual(
                [item.original_name for item in self.window.items],
                ["shot120.txt", "shot10.txt", "shot2.txt", "shot1.txt"],
            )

    def test_rule_change_updates_preview_after_coalesced_refresh(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            source = Path(temp_dir) / "plate001.exr"
            source.write_text("sample", encoding="utf-8")
            self.window.items = [FileItem(source)]
            self.window.refresh_table()

            self.window.prefix_enabled.setChecked(True)
            self.window.prefix_text.setText("shot_")
            QTest.qWait(self.window._live_preview_timer.interval() + 80)

            self.assertEqual(self.window.items[0].new_name, "shot_plate001.exr")
            self.assertEqual(self.window.items[0].status, "可改名")
            self.assertEqual(self.window.table.item(0, 4).text(), "shot_plate001.exr")

    def test_section_reset_and_status_timeout_contract(self) -> None:
        self.window.prefix_enabled.setChecked(True)
        self.window.prefix_text.setText("shot_")

        self.window.reset_add_rule()

        self.assertFalse(self.window.prefix_enabled.isChecked())
        self.assertEqual(self.window.prefix_text.text(), "")
        self.window.set_status("已复制新文件名", "copyNew")
        self.assertTrue(self.window._status_clear_timer.isActive())
        self.assertEqual(self.window._status_clear_timer.interval(), 7000)

    def test_supported_resolutions_scale_geometry_and_text_together_without_sidebar_clipping(self) -> None:
        self.window.apply_ui_scale(1.0)
        self.window.resize(self.window.BASE_WIDTH, self.window.BASE_HEIGHT)
        self.app.processEvents()
        sidebar = self.window.findChild(QLabel, "sidebarTitle").parentWidget()
        labels = [
            label
            for label in self.window.findChildren(QLabel)
            if label.objectName() in {"sidebarTitle", "sideSection", "stepLabel"}
        ]
        base_font_height = self.window.findChild(QLabel, "sidebarTitle").fontMetrics().height()

        for width, height in ((1280, 720), (1366, 768), (1600, 900), (1920, 1080), (2200, 1152)):
            with self.subTest(resolution=f"{width}x{height}"):
                scale = self.window.scale_for_available_size(width, height)
                self.window.apply_ui_scale(scale)
                self.window.resize(ceil(self.window.BASE_WIDTH * scale), ceil(self.window.BASE_HEIGHT * scale))
                self.app.processEvents()

                self.assertAlmostEqual(self.window._ui_scale, scale)
                self.assertEqual(sidebar.width(), ceil(196 * scale))
                for label in labels:
                    self.assertFalse(label.wordWrap())
                    text_width = label.fontMetrics().horizontalAdvance(label.text())
                    self.assertLessEqual(
                        text_width,
                        label.contentsRect().width(),
                        f"{width}x{height} 裁切：{label.text()}",
                    )

                if width < self.window.BASE_WIDTH:
                    self.assertLess(
                        self.window.findChild(QLabel, "sidebarTitle").fontMetrics().height(),
                        base_font_height,
                    )

    def test_scale_contract_uses_logical_available_geometry(self) -> None:
        self.assertAlmostEqual(self.window.scale_for_available_size(2200, 1152), 1.0)
        self.assertAlmostEqual(self.window.scale_for_available_size(1920, 1080), 1920 / 2200)
        self.assertAlmostEqual(self.window.scale_for_available_size(1280, 720), 1280 / 2200)

    def test_cross_monitor_rescaling_always_recomputes_from_baseline(self) -> None:
        sidebar = self.window.findChild(QLabel, "sidebarTitle").parentWidget()
        for width, height in ((1920, 1080), (1280, 720), (2200, 1152)):
            scale = self.window.scale_for_available_size(width, height)
            self.window.apply_ui_scale(scale)
            self.app.processEvents()
            self.assertEqual(sidebar.width(), ceil(196 * scale))

        self.assertEqual(sidebar.width(), 196)
        self.assertEqual(self.window.table.columnWidth(4), 430)

    def test_accessibility_names_cover_primary_and_custom_controls(self) -> None:
        self.assertEqual(self.window.path_edit.accessibleName(), "文件夹路径")
        self.assertEqual(self.window.table.accessibleName(), "文件改名预览表")
        self.assertEqual(self.window.status_label.accessibleName(), "操作状态")
        self.assertEqual(self.window.trim_count.accessibleName(), "中间删除字符数量")
        self.assertEqual(self.window.trim_count._up_button.accessibleName(), "增加数值")
        self.assertEqual(self.window.trim_count._down_button.accessibleName(), "减少数值")


if __name__ == "__main__":
    unittest.main()
