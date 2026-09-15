from __future__ import annotations

import os
import re
import sys
from math import ceil
from datetime import datetime
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QEvent, QPoint, QTimer, Qt
from PySide6.QtGui import QColor, QIcon, QPainter
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLayout,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .core.executor import RenameExecutor
from .core.models import FileItem, RuleSettings
from .core.preview import build_plans, build_preview, has_blocking_problem
from .core.scanner import scan_files
from .core.sorting import natural_sort_key
from . import __build_time__, __version__


def app_runtime_dir() -> Path:
    """源码运行用项目目录；打包后用 exe 所在目录保存日志和撤销记录。"""

    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


PROJECT_DIR = app_runtime_dir()


class IconSpinBox(QSpinBox):
    """统一绘制上下按钮，避免不同系统主题下出现黑块或不可见箭头。"""

    def __init__(self) -> None:
        super().__init__()
        self._ui_scale = 1.0
        self.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self._repeat_direction = 0
        self._repeat_delay_timer = QTimer(self)
        self._repeat_delay_timer.setSingleShot(True)
        self._repeat_delay_timer.setInterval(260)
        self._repeat_delay_timer.timeout.connect(self._start_repeat)
        self._repeat_timer = QTimer(self)
        self._repeat_timer.setInterval(70)
        self._repeat_timer.timeout.connect(self._step_once)
        self._up_button = self._make_arrow_button("▲")
        self._down_button = self._make_arrow_button("▼")
        self._up_button.pressed.connect(lambda: self._begin_step(1))
        self._up_button.released.connect(self._end_step)
        self._down_button.pressed.connect(lambda: self._begin_step(-1))
        self._down_button.released.connect(self._end_step)
        self._up_button.setAccessibleName("增加数值")
        self._down_button.setAccessibleName("减少数值")

    def set_ui_scale(self, scale: float) -> None:
        self._ui_scale = scale
        self._up_button.set_ui_scale(scale)
        self._down_button.set_ui_scale(scale)
        self.updateGeometry()
        self._layout_arrow_buttons()

    def _make_arrow_button(self, text: str) -> QToolButton:
        button = SpinArrowButton(text == "▲", self)
        button.setObjectName("spinArrowButton")
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setAutoRepeat(False)
        return button

    def _begin_step(self, direction: int) -> None:
        self._repeat_direction = direction
        self._step_once()
        self._repeat_delay_timer.start()

    def _start_repeat(self) -> None:
        if self._repeat_direction:
            self._repeat_timer.start()

    def _end_step(self) -> None:
        self._repeat_direction = 0
        self._repeat_delay_timer.stop()
        self._repeat_timer.stop()

    def _step_once(self) -> None:
        if not self._repeat_direction:
            return
        self.interpretText()
        self.stepBy(self._repeat_direction)

    def resizeEvent(self, event: QEvent) -> None:
        super().resizeEvent(event)
        self._layout_arrow_buttons()

    def _layout_arrow_buttons(self) -> None:
        button_width = max(8, ceil(18 * self._ui_scale))
        gap = max(1, ceil(2 * self._ui_scale))
        half_height = max((self.height() - gap * 2) // 2, max(5, ceil(10 * self._ui_scale)))
        x = self.width() - button_width - gap
        self._up_button.setGeometry(x, gap, button_width, half_height)
        self._down_button.setGeometry(x, gap + half_height, button_width, half_height)


class SpinArrowButton(QToolButton):
    def __init__(self, points_up: bool, parent: QWidget) -> None:
        super().__init__(parent)
        self.points_up = points_up
        self._ui_scale = 1.0

    def set_ui_scale(self, scale: float) -> None:
        self._ui_scale = scale
        self.update()

    def paintEvent(self, event: QEvent) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor("#64748b"))
        painter.setPen(Qt.PenStyle.NoPen)
        center_x = self.width() // 2
        center_y = self.height() // 2
        vertical = max(2, ceil(3 * self._ui_scale))
        horizontal = max(3, ceil(4 * self._ui_scale))
        lower = max(1, ceil(2 * self._ui_scale))
        if self.points_up:
            points = [QPoint(center_x, center_y - vertical), QPoint(center_x - horizontal, center_y + lower), QPoint(center_x + horizontal, center_y + lower)]
        else:
            points = [QPoint(center_x, center_y + vertical), QPoint(center_x - horizontal, center_y - lower), QPoint(center_x + horizontal, center_y - lower)]
        painter.drawPolygon(points)


class ComboArrowGlyph(QWidget):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self._ui_scale = 1.0

    def set_ui_scale(self, scale: float) -> None:
        self._ui_scale = scale
        self.update()

    def paintEvent(self, event: QEvent) -> None:
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(QColor("#64748b"))
        painter.setPen(Qt.PenStyle.NoPen)
        center_x = self.width() // 2
        center_y = self.height() // 2
        vertical = max(2, ceil(3 * self._ui_scale))
        horizontal = max(3, ceil(5 * self._ui_scale))
        points = [QPoint(center_x, center_y + vertical), QPoint(center_x - horizontal, center_y - vertical), QPoint(center_x + horizontal, center_y - vertical)]
        painter.drawPolygon(points)


class IconComboBox(QComboBox):
    """给下拉框叠加统一小箭头，避免系统原生黑色块。"""

    def __init__(self) -> None:
        super().__init__()
        self._ui_scale = 1.0
        self._arrow_label = ComboArrowGlyph(self)
        self._arrow_label.setObjectName("comboArrowGlyph")
        self._arrow_label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

    def set_ui_scale(self, scale: float) -> None:
        self._ui_scale = scale
        self._arrow_label.set_ui_scale(scale)
        self.updateGeometry()
        self._layout_arrow()

    def resizeEvent(self, event: QEvent) -> None:
        super().resizeEvent(event)
        self._layout_arrow()

    def _layout_arrow(self) -> None:
        inset = max(1, ceil(self._ui_scale))
        arrow_width = max(10, ceil(20 * self._ui_scale))
        drop_width = max(12, ceil(22 * self._ui_scale))
        self._arrow_label.setGeometry(self.width() - drop_width, inset, arrow_width, self.height() - inset * 2)


class ExtensionFilterPanel(QWidget):
    """Keep the filter row proportional when its available width is constrained."""

    def resizeEvent(self, event: QEvent) -> None:
        super().resizeEvent(event)
        self.fit_contents()

    def fit_contents(self) -> None:
        base_scale = getattr(self.window(), "_ui_scale", 1.0)
        scale = min(base_scale, max(0.3, self.width() / 1180))
        font_size = max(6, int(13 * scale))
        padding = max(1, int(8 * scale))
        self.setStyleSheet(
            f"#extensionFilter QPushButton, #extensionFilter QLabel, #extensionFilter QCheckBox {{ font-size: {font_size}px; }}"
            f"#extensionFilter QPushButton {{ min-width: {int(42 * scale)}px; padding: {max(1, int(3 * scale))}px {padding}px; }}"
        )
        if self.layout():
            self.layout().setSpacing(max(1, int(5 * scale)))


class AboutDialog(QDialog):
    """显示产品、版本和维护入口，不承载任何文件操作。"""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("关于 南枫批量改名")
        self.setObjectName("aboutDialog")
        self.setModal(True)
        self.setMinimumSize(720, 470)
        self.resize(920, 560)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(46, 32, 46, 38)
        layout.setSpacing(24)

        title = QLabel("关于")
        title.setObjectName("aboutPageTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        card = QFrame()
        card.setObjectName("aboutCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(28, 26, 28, 24)
        card_layout.setSpacing(0)

        product_name = QLabel("南枫批量改名")
        product_name.setObjectName("aboutProductName")
        card_layout.addWidget(product_name)
        product_summary = QLabel("批量文件改名与安全预览工作台。")
        product_summary.setObjectName("aboutSummary")
        card_layout.addWidget(product_summary)

        card_layout.addWidget(self._divider())
        card_layout.addWidget(self._section("版本信息", [
            f"Desktop 版 {__version__}",
            f"开发时间  {__build_time__}",
        ]))
        card_layout.addWidget(self._divider())
        card_layout.addWidget(self._section("开发者信息", [
            "开发者：席瑞",
            "联系邮箱：nanzhufeng.studio@gmail.com",
            "源码与更新：GitHub · nanzhufeng/NanfengBatchRenamer-Windows",
            "版权所有 © 2026 席瑞",
        ]))
        layout.addWidget(card)
        layout.addStretch(1)

        self.setStyleSheet(
            """
            QDialog#aboutDialog { background: #f8fafc; color: #172033; font-family: \"Microsoft YaHei\"; }
            #aboutPageTitle { font-size: 26px; font-weight: 700; background: transparent; }
            #aboutCard { background: #ffffff; border: 1px solid #e5e7eb; border-radius: 20px; }
            #aboutProductName { font-size: 18px; font-weight: 700; background: transparent; }
            #aboutSummary { color: #6b7280; font-size: 14px; background: transparent; padding-top: 4px; }
            #aboutDivider { background: #e5e7eb; border: none; min-height: 1px; max-height: 1px; margin: 24px -28px; }
            #aboutSectionTitle { font-size: 17px; font-weight: 700; background: transparent; }
            #aboutSectionLine { font-size: 15px; background: transparent; padding-top: 5px; }
            """
        )

    @staticmethod
    def _divider() -> QFrame:
        divider = QFrame()
        divider.setObjectName("aboutDivider")
        divider.setFrameShape(QFrame.Shape.HLine)
        return divider

    @staticmethod
    def _section(title_text: str, lines: list[str]) -> QWidget:
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        title = QLabel(title_text)
        title.setObjectName("aboutSectionTitle")
        layout.addWidget(title)
        for line in lines:
            label = QLabel(line)
            label.setObjectName("aboutSectionLine")
            layout.addWidget(label)
        return section


class MainWindow(QMainWindow):
    BASE_WIDTH = 2200
    BASE_HEIGHT = 1152
    MINIMUM_WIDTH = 640
    MINIMUM_HEIGHT = 360

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("南枫批量改名")
        self.setWindowIcon(self._make_app_icon())
        self.resize(self.BASE_WIDTH, self.BASE_HEIGHT)
        self.setMinimumSize(self.MINIMUM_WIDTH, self.MINIMUM_HEIGHT)
        self._ui_scale = 1.0
        self._base_stylesheet = ""
        self._widget_base_metrics: list[tuple[QWidget, int, int, int, int]] = []
        self._layout_base_metrics: list[tuple[QLayout, tuple[int, int, int, int], int, int, int]] = []
        self._base_table_column_widths: list[int] = []
        self._base_table_row_height = 0
        self._screen_signal_connected = False
        self._screen_fit_pending = False
        self._status_variant = "normal"
        self.items: list[FileItem] = []
        self.executor = RenameExecutor(PROJECT_DIR)
        self._updating_table = False
        self._drag_selecting = False
        self._drag_select_state = Qt.CheckState.Checked
        self._sort_column: int | None = None
        self._sort_ascending = True
        self._live_preview_timer = QTimer(self)
        self._live_preview_timer.setSingleShot(True)
        self._live_preview_timer.setInterval(80)
        self._live_preview_timer.timeout.connect(self._apply_live_preview)
        self._status_clear_timer = QTimer(self)
        self._status_clear_timer.setSingleShot(True)
        self._status_clear_timer.timeout.connect(self.clear_status)

        self._build_ui()
        self._apply_style()
        self._base_stylesheet = self.styleSheet()
        self._capture_scalable_metrics()
        self._apply_accessibility()
        self._connect_rule_live_preview()
        self._update_buttons()

    def _make_app_icon(self) -> QIcon:
        resource_root = Path(getattr(sys, "_MEIPASS", PROJECT_DIR))
        icon = QIcon(str(resource_root / "build_assets" / "app_icon.png"))
        if icon.isNull() and getattr(sys, "frozen", False):
            icon = QIcon(sys.executable)
        return icon

    def _build_ui(self) -> None:
        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(12)

        root_layout.addWidget(self._build_sidebar(), 0)

        main_area = QVBoxLayout()
        main_area.setSpacing(8)
        main_area.addWidget(self._build_header())
        main_area.addWidget(self._build_source_panel())
        main_area.addWidget(self._build_action_bar())
        main_area.addLayout(self._build_work_area(), 1)
        main_area.addWidget(self._build_status_bar())
        root_layout.addLayout(main_area, 1)

        self.setCentralWidget(root)

    def _capture_scalable_metrics(self) -> None:
        """记录基准像素，后续始终从基准重算，避免跨屏反复缩放累积误差。"""

        if self.centralWidget() and self.centralWidget().layout():
            self.centralWidget().layout().activate()

        self._widget_base_metrics.clear()
        for widget in self.findChildren(QWidget):
            minimum = widget.minimumSize()
            maximum = widget.maximumSize()
            self._widget_base_metrics.append(
                (widget, minimum.width(), minimum.height(), maximum.width(), maximum.height())
            )

        self._layout_base_metrics.clear()
        for layout in self.findChildren(QLayout):
            margins = layout.contentsMargins()
            horizontal_spacing = layout.horizontalSpacing() if hasattr(layout, "horizontalSpacing") else -1
            vertical_spacing = layout.verticalSpacing() if hasattr(layout, "verticalSpacing") else -1
            self._layout_base_metrics.append(
                (
                    layout,
                    (margins.left(), margins.top(), margins.right(), margins.bottom()),
                    layout.spacing(),
                    horizontal_spacing,
                    vertical_spacing,
                )
            )

        self._base_table_column_widths = [self.table.columnWidth(index) for index in range(self.table.columnCount())]
        self._base_table_row_height = self.table.verticalHeader().defaultSectionSize()

    @staticmethod
    def scale_for_available_size(width: int, height: int) -> float:
        if width <= 0 or height <= 0:
            return 1.0
        return min(1.0, width / MainWindow.BASE_WIDTH, height / MainWindow.BASE_HEIGHT)

    @staticmethod
    def _scaled_value(value: int, scale: float) -> int:
        if value <= 0:
            return value
        return max(1, ceil(value * scale))

    def _scaled_stylesheet(self, stylesheet: str, scale: float) -> str:
        def replace(match: re.Match[str]) -> str:
            return f"{self._scaled_value(int(match.group(1)), scale)}px"

        return re.sub(r"(\d+)px", replace, stylesheet)

    def apply_ui_scale(self, scale: float) -> None:
        """公开给离屏回归使用；字号、几何和间距严格使用同一比例。"""

        scale = max(0.3, min(1.0, scale))
        self._ui_scale = scale

        for widget, min_width, min_height, max_width, max_height in self._widget_base_metrics:
            widget.setMinimumSize(0, 0)
            widget.setMaximumSize(16777215, 16777215)
            next_max_width = self._scaled_value(max_width, scale) if max_width < 16777215 else 16777215
            next_max_height = self._scaled_value(max_height, scale) if max_height < 16777215 else 16777215
            widget.setMaximumSize(next_max_width, next_max_height)
            widget.setMinimumSize(
                self._scaled_value(min_width, scale),
                self._scaled_value(min_height, scale),
            )

        for layout, margins, spacing, horizontal_spacing, vertical_spacing in self._layout_base_metrics:
            layout.setContentsMargins(*(self._scaled_value(value, scale) for value in margins))
            if horizontal_spacing >= 0 and hasattr(layout, "setHorizontalSpacing"):
                layout.setHorizontalSpacing(self._scaled_value(horizontal_spacing, scale))
            if vertical_spacing >= 0 and hasattr(layout, "setVerticalSpacing"):
                layout.setVerticalSpacing(self._scaled_value(vertical_spacing, scale))
            elif spacing >= 0:
                layout.setSpacing(self._scaled_value(spacing, scale))

        for index, width in enumerate(self._base_table_column_widths):
            self.table.setColumnWidth(index, self._scaled_value(width, scale))
        self.table.verticalHeader().setDefaultSectionSize(self._scaled_value(self._base_table_row_height, scale))

        self.setStyleSheet(self._scaled_stylesheet(self._base_stylesheet, scale))
        for spinbox in self.findChildren(IconSpinBox):
            spinbox.set_ui_scale(scale)
        for combo in self.findChildren(IconComboBox):
            combo.set_ui_scale(scale)
        for label in self.findChildren(QLabel):
            label.setWordWrap(False)

        for panel in self.findChildren(ExtensionFilterPanel):
            panel.fit_contents()
        self._apply_current_status_style()
        if self.centralWidget() and self.centralWidget().layout():
            self.centralWidget().layout().activate()

    def _fit_to_current_screen(self) -> None:
        self._screen_fit_pending = False
        handle = self.windowHandle()
        screen = handle.screen() if handle and handle.screen() else QApplication.primaryScreen()
        if screen is None:
            return

        available = screen.availableGeometry()
        usable_width = max(self.MINIMUM_WIDTH, available.width() - 16)
        usable_height = max(self.MINIMUM_HEIGHT, available.height() - 48)
        scale = self.scale_for_available_size(usable_width, usable_height)
        self.apply_ui_scale(scale)

        target_width = min(self.BASE_WIDTH, usable_width, ceil(self.BASE_WIDTH * scale))
        target_height = min(self.BASE_HEIGHT, usable_height, ceil(self.BASE_HEIGHT * scale))
        self.resize(target_width, target_height)

        left = available.left() + max(0, (available.width() - self.frameGeometry().width()) // 2)
        top = available.top() + max(0, (available.height() - self.frameGeometry().height()) // 2)
        self.move(left, top)

    def _schedule_screen_fit(self) -> None:
        if self._screen_fit_pending:
            return
        self._screen_fit_pending = True
        QTimer.singleShot(0, self._fit_to_current_screen)

    def showEvent(self, event: QEvent) -> None:
        super().showEvent(event)
        handle = self.windowHandle()
        if handle and not self._screen_signal_connected:
            handle.screenChanged.connect(lambda _screen: self._schedule_screen_fit())
            self._screen_signal_connected = True
        self._schedule_screen_fit()

    def _apply_accessibility(self) -> None:
        self.path_edit.setAccessibleName("文件夹路径")
        self.path_edit.setAccessibleDescription("输入待处理文件夹路径，按回车读取文件")
        self.table.setAccessibleName("文件改名预览表")
        self.table.setAccessibleDescription("逐行比较原文件名、新文件名、状态和问题提示")
        self.status_label.setAccessibleName("操作状态")
        self.count_label.setAccessibleName("文件数量统计")
        self.extension_all_btn.setAccessibleName("读取全部文件格式")
        self.about_btn.setAccessibleName("打开关于软件信息")

        for extension, button in self.extension_buttons.items():
            button.setAccessibleName(f"筛选 {extension} 扩展名")

        controls = {
            self.find_enabled: "启用查找替换",
            self.find_text: "查找内容",
            self.replace_text: "替换内容",
            self.case_sensitive: "查找时区分大小写",
            self.prefix_enabled: "启用前缀",
            self.prefix_text: "前缀文字",
            self.suffix_enabled: "启用后缀",
            self.suffix_text: "后缀文字",
            self.insert_enabled: "启用指定位置插入",
            self.insert_text: "插入文字",
            self.insert_position: "插入位置",
            self.trim_enabled: "启用删除字符",
            self.trim_left: "删除开头字符数量",
            self.trim_right: "删除结尾字符数量",
            self.trim_start: "中间删除起始位置",
            self.trim_count: "中间删除字符数量",
            self.number_enabled: "启用自动编号",
            self.number_position: "编号位置",
            self.number_digits: "编号位数",
            self.number_start: "编号起始值",
            self.number_step: "编号递增值",
            self.number_separator: "编号分隔符",
            self.extension_mode: "扩展名大小写规则",
        }
        for widget, name in controls.items():
            widget.setAccessibleName(name)

    def _build_sidebar(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("sidebar")
        panel.setFixedWidth(196)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(9)

        mark = QLabel("南")
        mark.setObjectName("brandMark")
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mark.setFixedSize(38, 38)
        layout.addWidget(mark)

        title = QLabel("南枫批量改名")
        title.setObjectName("sidebarTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        sub = QLabel("素材与文件序列整理工作台")
        sub.setObjectName("muted")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(sub)

        layout.addSpacing(6)
        layout.addWidget(self._side_section("快捷入口"))
        self.choose_folder_side_btn = QPushButton("选择文件夹")
        self.open_folder_btn = QPushButton("打开当前目录")
        self.open_logs_btn = QPushButton("打开日志")
        self.about_btn = QPushButton("关于软件")
        self.choose_folder_side_btn.setObjectName("sideChooseButton")
        self.open_folder_btn.setObjectName("sideOpenButton")
        self.open_logs_btn.setObjectName("sideLogButton")
        self.about_btn.setObjectName("sideAboutButton")
        for btn in (self.choose_folder_side_btn, self.open_folder_btn, self.open_logs_btn, self.about_btn):
            layout.addWidget(btn)

        layout.addSpacing(6)
        layout.addWidget(self._side_section("操作流程"))
        for text in ("01  导入文件", "02  设置规则", "03  预览检查", "04  执行改名"):
            step = QLabel(text)
            step.setObjectName("stepLabel")
            step.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            layout.addWidget(step)

        layout.addStretch(1)
        self.undo_btn = QPushButton("撤销上次改名")
        self.undo_btn.setObjectName("dangerOutline")
        layout.addWidget(self.undo_btn)

        self.choose_folder_side_btn.clicked.connect(self.choose_folder)
        self.open_folder_btn.clicked.connect(self.open_current_folder)
        self.open_logs_btn.clicked.connect(self.open_logs)
        self.about_btn.clicked.connect(self.show_about)
        self.undo_btn.clicked.connect(self.undo_last)
        return panel

    def show_about(self) -> None:
        AboutDialog(self).exec()

    def _side_section(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("sideSection")
        label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        return label

    def _build_header(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        title = QLabel("改名控制台")
        title.setObjectName("pageTitle")
        desc = QLabel("先读取文件，设置规则，再预览检查；确认无冲突后才执行改名。")
        desc.setObjectName("muted")
        layout.addWidget(title)
        layout.addWidget(desc)
        return panel

    def _build_source_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("panel")
        panel.setFixedHeight(106)
        layout = QGridLayout(panel)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setHorizontalSpacing(10)
        layout.setVerticalSpacing(8)

        self.path_edit = QLineEdit()
        self.path_edit.setPlaceholderText("选择要处理的文件夹")
        browse_btn = QPushButton("选择")
        browse_btn.setObjectName("greenButton")
        read_btn = QPushButton("读取文件")
        read_btn.setObjectName("orangeButton")

        self.include_subfolders = QCheckBox("包含子文件夹")
        self.include_subfolders.setEnabled(False)
        self.include_subfolders.setToolTip("第一版先只读取当前目录文件。")

        layout.addWidget(self._source_label("文件夹"), 0, 0)
        layout.addWidget(self.path_edit, 0, 1, 1, 4)
        layout.addWidget(browse_btn, 0, 5)
        layout.addWidget(self._source_label("扩展名筛选"), 1, 0)
        layout.addWidget(self._build_extension_filter(), 1, 1, 1, 4)
        layout.addWidget(read_btn, 1, 5)

        browse_btn.clicked.connect(self.choose_folder)
        read_btn.clicked.connect(self.load_files)
        self.path_edit.returnPressed.connect(self.load_files)
        return panel

    def _source_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("sourceLabel")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return label

    def _build_extension_filter(self) -> QWidget:
        panel = ExtensionFilterPanel()
        panel.setObjectName("extensionFilter")
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(6, 3, 6, 3)
        layout.setSpacing(5)

        self.extension_all_btn = QPushButton("全部")
        self.extension_all_btn.setObjectName("extensionAllChip")
        self.extension_all_btn.setCheckable(True)
        self.extension_all_btn.setToolTip("读取真实全部格式，不限制扩展名")
        self.extension_all_btn.toggled.connect(self._toggle_all_extensions)
        layout.addWidget(self.extension_all_btn)

        default_extensions = {"jpg", "png", "exr", "mp4"}
        self.extension_buttons: dict[str, QPushButton] = {}

        layout.addWidget(self._extension_group_label("序列/图片"))
        for ext in ("jpg", "png", "exr", "tif", "dpx", "psd"):
            btn = QPushButton(ext)
            btn.setObjectName("extensionSequenceChip")
            btn.setCheckable(True)
            btn.setChecked(ext in default_extensions)
            btn.toggled.connect(lambda _checked: self._sync_extension_all())
            self.extension_buttons[ext] = btn
            layout.addWidget(btn)

        layout.addSpacing(6)
        layout.addWidget(self._extension_group_label("视频"))
        for ext in ("mp4", "mov", "avi", "mkv", "ts", "flv", "wmv", "m4v"):
            btn = QPushButton(ext)
            btn.setObjectName("extensionVideoChip")
            btn.setCheckable(True)
            btn.setChecked(ext in default_extensions)
            btn.toggled.connect(lambda _checked: self._sync_extension_all())
            self.extension_buttons[ext] = btn
            layout.addWidget(btn)

        layout.addStretch(1)
        layout.addWidget(self.include_subfolders, 0, Qt.AlignmentFlag.AlignVCenter)
        return panel

    def _extension_group_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("extensionGroupLabel")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        return label

    def _toggle_all_extensions(self, checked: bool) -> None:
        if not checked:
            if not any(btn.isChecked() for btn in self.extension_buttons.values()):
                self.extension_all_btn.blockSignals(True)
                self.extension_all_btn.setChecked(True)
                self.extension_all_btn.blockSignals(False)
            return
        for btn in self.extension_buttons.values():
            btn.blockSignals(True)
            btn.setChecked(False)
            btn.blockSignals(False)

    def _sync_extension_all(self) -> None:
        has_selected = any(btn.isChecked() for btn in self.extension_buttons.values())
        self.extension_all_btn.blockSignals(True)
        self.extension_all_btn.setChecked(not has_selected)
        self.extension_all_btn.blockSignals(False)

    def _selected_extension_filter(self) -> str:
        if self.extension_all_btn.isChecked():
            # 空筛选代表不限制扩展名，也就是真实读取所有文件格式。
            return ""
        selected = [ext for ext, btn in self.extension_buttons.items() if btn.isChecked()]
        return ",".join(selected)

    def _build_action_bar(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("panel")
        panel.setFixedHeight(54)
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)

        self.preview_btn = QPushButton("预览")
        self.preview_btn.setObjectName("primaryButton")
        self.check_btn = QPushButton("检查冲突")
        self.check_btn.setObjectName("purpleButton")
        self.select_all_btn = QPushButton("全选")
        self.select_all_btn.setObjectName("greenSoftButton")
        self.invert_btn = QPushButton("反选")
        self.invert_btn.setObjectName("pinkSoftButton")
        self.reset_btn = QPushButton("重置规则")
        self.clear_btn = QPushButton("清空列表")
        self.execute_btn = QPushButton("执行改名")
        self.execute_btn.setObjectName("dangerButton")

        for btn in (
            self.preview_btn,
            self.check_btn,
            self.select_all_btn,
            self.invert_btn,
            self.reset_btn,
            self.clear_btn,
            self.execute_btn,
        ):
            layout.addWidget(btn)
        layout.addStretch(1)

        self.preview_btn.clicked.connect(self.preview)
        self.check_btn.clicked.connect(self.preview)
        self.select_all_btn.clicked.connect(lambda: self.set_all_selected(True))
        self.invert_btn.clicked.connect(self.invert_selected)
        self.reset_btn.clicked.connect(self.reset_rules)
        self.clear_btn.clicked.connect(self.clear_items)
        self.execute_btn.clicked.connect(self.execute_rename)
        return panel

    def _build_work_area(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(10)

        self.table = QTableWidget(0, 10)
        self.table.setObjectName("fileTable")
        self.table.setHorizontalHeaderLabels(
            ["序号", "选择", "状态", "原文件名", "新文件名", "扩展名", "所在目录", "大小", "修改时间", "问题提示"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.table.viewport().installEventFilter(self)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionsClickable(True)
        self.table.horizontalHeader().setSortIndicatorShown(True)
        self.table.setColumnWidth(0, 54)
        self.table.setColumnWidth(1, 54)
        self.table.setColumnWidth(2, 76)
        self.table.setColumnWidth(3, 370)
        self.table.setColumnWidth(4, 430)
        self.table.setColumnWidth(5, 66)
        self.table.setColumnWidth(6, 220)
        self.table.setColumnWidth(7, 82)
        self.table.setColumnWidth(8, 132)
        self.table.setColumnWidth(9, 120)
        self.table.cellClicked.connect(self.copy_table_cell)
        self.table.horizontalHeader().sectionClicked.connect(self.sort_by_column)
        layout.addWidget(self.table, 1)

        layout.addWidget(self._build_rules_panel(), 0)
        return layout

    def _build_rules_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("rulesPanel")
        panel.setFixedWidth(304)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        title = QLabel("规则链")
        title.setObjectName("sectionTitle")
        heading = QHBoxLayout()
        heading.addWidget(title)
        heading.addStretch()
        self.include_extension = QCheckBox("包含扩展名")
        self.include_extension.setAccessibleName("改名范围：包含扩展名")
        self.include_extension.setToolTip("勾选后，查找替换、添加、删除和编号统一作用于完整文件名（含点号和扩展名）；扩展名大小写最后处理。")
        heading.addWidget(self.include_extension)
        layout.addLayout(heading)

        self.find_enabled = QCheckBox("查找替换")
        self.find_text = QLineEdit()
        self.find_text.setPlaceholderText("查找内容")
        self.replace_text = QLineEdit()
        self.replace_text.setPlaceholderText("替换为")
        self.case_sensitive = QCheckBox("区分大小写")
        layout.addWidget(
            self._rule_box(
                self.find_enabled,
                [self.find_text, self.replace_text, self.case_sensitive],
                "findRuleBox",
                "findRuleTitle",
                self.reset_find_rule,
            )
        )

        add_title = QLabel("添加文本")
        add_title.setObjectName("addRuleTitle")
        self.prefix_enabled = QCheckBox("前缀")
        self.prefix_text = QLineEdit()
        self.prefix_text.setPlaceholderText("例如：shot_")
        self.suffix_enabled = QCheckBox("后缀")
        self.suffix_text = QLineEdit()
        self.suffix_text.setPlaceholderText("例如：_v001")
        self.insert_enabled = QCheckBox("指定位置")
        self.insert_text = QLineEdit()
        self.insert_text.setPlaceholderText("插入内容")
        self.insert_position = IconSpinBox()
        self.insert_position.setRange(0, 999)
        layout.addWidget(
            self._panel_box(
                [
                    add_title,
                    self._inline_row([self.prefix_enabled, self.prefix_text], [0, 1]),
                    self._inline_row([self.suffix_enabled, self.suffix_text], [0, 1]),
                    self._insert_row(),
                ],
                "addRuleBox",
                self.reset_add_rule,
            )
        )

        self.trim_enabled = QCheckBox("删除字符")
        self.trim_left = IconSpinBox()
        self.trim_left.setRange(0, 999)
        self.trim_right = IconSpinBox()
        self.trim_right.setRange(0, 999)
        self.trim_start = IconSpinBox()
        self.trim_start.setRange(0, 999)
        self.trim_count = IconSpinBox()
        self.trim_count.setRange(0, 999)
        layout.addWidget(
            self._rule_box(
                self.trim_enabled,
                [
                    self._number_pair_row("开头", self.trim_left, "结尾", self.trim_right, "trimEdgeRow"),
                    self._number_pair_row("位置", self.trim_start, "删除数量", self.trim_count, "trimMiddleRow"),
                ],
                "trimRuleBox",
                "trimRuleTitle",
                self.reset_trim_rule,
            )
        )

        self.number_enabled = QCheckBox("自动编号")
        self.number_start = IconSpinBox()
        self.number_start.setRange(0, 999999)
        self.number_start.setValue(1)
        self.number_step = IconSpinBox()
        self.number_step.setRange(1, 9999)
        self.number_digits = IconSpinBox()
        self.number_digits.setRange(1, 12)
        self.number_digits.setValue(4)
        self.number_position = IconComboBox()
        self.number_position.addItems(["前缀", "后缀"])
        self.number_separator = QLineEdit("_")
        self.number_separator.setPlaceholderText("分隔符")
        layout.addWidget(
            self._rule_box(
                self.number_enabled,
                [
                    self._control_number_pair_row("位置", self.number_position, "位数", self.number_digits, "numberPositionDigitsRow"),
                    self._number_pair_row("起始", self.number_start, "递增", self.number_step, "numberRangeRow"),
                    self._single_control_row("分隔符", self.number_separator, "numberSeparatorRow", wide=True),
                ],
                "numberRuleBox",
                "numberRuleTitle",
                self.reset_number_rule,
            )
        )

        ext_label = QLabel("扩展名")
        ext_label.setObjectName("extensionRuleTitle")
        self.extension_mode = IconComboBox()
        self.extension_mode.addItems(["保持不变", "统一小写", "统一大写"])
        box = QFrame()
        box.setObjectName("extensionRuleBox")
        box_layout = QVBoxLayout(box)
        box_layout.setContentsMargins(8, 8, 8, 8)
        box_layout.setSpacing(6)
        box_layout.addWidget(self._header_row(ext_label, self.reset_extension_rule))
        box_layout.addWidget(self.extension_mode)
        layout.addWidget(box)

        layout.addStretch(1)
        return panel

    def _rule_box(
        self,
        checkbox: QCheckBox,
        widgets: list[QWidget],
        box_name: str = "ruleBox",
        title_name: str = "ruleTitle",
        reset_callback: Callable[[], None] | None = None,
    ) -> QWidget:
        box = QFrame()
        box.setObjectName(box_name)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        checkbox.setObjectName(title_name)
        layout.addWidget(self._header_row(checkbox, reset_callback))
        for widget in widgets:
            layout.addWidget(widget)
        return box

    def _panel_box(
        self,
        widgets: list[QWidget],
        box_name: str = "ruleBox",
        reset_callback: Callable[[], None] | None = None,
    ) -> QWidget:
        box = QFrame()
        box.setObjectName(box_name)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        for index, widget in enumerate(widgets):
            if index == 0:
                layout.addWidget(self._header_row(widget, reset_callback))
                continue
            layout.addWidget(widget)
        return box

    def _header_row(self, title_widget: QWidget, reset_callback: Callable[[], None] | None = None) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(title_widget, 1)
        if reset_callback:
            reset_btn = QPushButton("重置")
            reset_btn.setObjectName("ruleResetButton")
            reset_btn.setToolTip("只重置当前区域")
            reset_btn.setFixedSize(44, 22)
            reset_btn.clicked.connect(lambda _checked=False: reset_callback())
            layout.addWidget(reset_btn, 0)
        return row

    def _inline_row(self, widgets: list[QWidget], stretches: list[int] | None = None) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        for index, widget in enumerate(widgets):
            stretch = stretches[index] if stretches and index < len(stretches) else 1
            layout.addWidget(widget, stretch)
        return row

    def _insert_row(self) -> QWidget:
        row = QWidget()
        layout = QVBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        top_row = QWidget()
        top_layout = QHBoxLayout(top_row)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(6)
        label = QLabel("位置")
        label.setObjectName("miniLabel")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setFixedWidth(36)
        self.insert_position.setFixedWidth(58)
        self.insert_position.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.insert_text.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        top_layout.addWidget(self.insert_enabled, 0)
        top_layout.addStretch(1)
        top_layout.addWidget(label, 0)
        top_layout.addWidget(self.insert_position, 0)
        layout.addWidget(top_row)
        layout.addWidget(self.insert_text)
        return row

    def _single_number_row(self, label_text: str, spin: QSpinBox, row_name: str | None = None) -> QWidget:
        row = QWidget()
        if row_name:
            row.setObjectName(row_name)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(5, 3, 5, 3)
        layout.setSpacing(6)
        label = QLabel(label_text)
        label.setObjectName("miniLabel")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setFixedWidth(38)
        spin.setFixedWidth(76)
        spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label, 0)
        layout.addWidget(spin, 0)
        layout.addStretch(1)
        return row

    def _single_control_row(
        self,
        label_text: str,
        widget: QWidget,
        row_name: str | None = None,
        wide: bool = False,
    ) -> QWidget:
        row = QWidget()
        if row_name:
            row.setObjectName(row_name)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(5, 3, 5, 3)
        layout.setSpacing(6)
        label = QLabel(label_text)
        label.setObjectName("miniLabel")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setFixedWidth(42)
        if wide:
            widget.setMinimumWidth(120)
        else:
            widget.setFixedWidth(88)
        if isinstance(widget, QLineEdit):
            widget.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        elif hasattr(widget, "setAlignment"):
            widget.setAlignment(Qt.AlignmentFlag.AlignCenter)  # type: ignore[attr-defined]
        layout.addWidget(label, 0)
        layout.addWidget(widget, 1 if wide else 0)
        if not wide:
            layout.addStretch(1)
        return row

    def _control_number_pair_row(
        self,
        left_text: str,
        left_widget: QWidget,
        right_text: str,
        right_spin: QSpinBox,
        row_name: str | None = None,
    ) -> QWidget:
        row = QWidget()
        if row_name:
            row.setObjectName(row_name)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(4, 3, 4, 3)
        layout.setSpacing(3)
        left_label = QLabel(left_text)
        right_label = QLabel(right_text)
        for label in (left_label, right_label):
            label.setObjectName("miniLabel")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_label.setFixedWidth(34)
        right_label.setFixedWidth(56)
        left_widget.setFixedWidth(76)
        right_spin.setFixedWidth(76)
        if hasattr(left_widget, "setAlignment"):
            left_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)  # type: ignore[attr-defined]
        right_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(left_label, 0)
        layout.addWidget(left_widget, 0)
        layout.addWidget(right_label, 0)
        layout.addWidget(right_spin, 0)
        layout.addStretch(1)
        return row

    def _control_pair_row(
        self,
        left_text: str,
        left_widget: QWidget,
        right_text: str,
        right_widget: QWidget,
        row_name: str | None = None,
    ) -> QWidget:
        row = QWidget()
        if row_name:
            row.setObjectName(row_name)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(5, 3, 5, 3)
        layout.setSpacing(4)
        left_label = QLabel(left_text)
        right_label = QLabel(right_text)
        for label in (left_label, right_label):
            label.setObjectName("miniLabel")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_label.setFixedWidth(38)
        right_label.setFixedWidth(44)
        left_widget.setFixedWidth(76)
        right_widget.setFixedWidth(76)
        if hasattr(left_widget, "setAlignment"):
            left_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)  # type: ignore[attr-defined]
        if hasattr(right_widget, "setAlignment"):
            right_widget.setAlignment(Qt.AlignmentFlag.AlignCenter)  # type: ignore[attr-defined]
        layout.addWidget(left_label, 0)
        layout.addWidget(left_widget, 0)
        layout.addWidget(right_label, 0)
        layout.addWidget(right_widget, 0)
        layout.addStretch(1)
        return row

    def _number_pair_row(
        self,
        left_text: str,
        left_spin: QSpinBox,
        right_text: str,
        right_spin: QSpinBox,
        row_name: str | None = None,
    ) -> QWidget:
        row = QWidget()
        if row_name:
            row.setObjectName(row_name)
        layout = QHBoxLayout(row)
        layout.setContentsMargins(4, 3, 4, 3)
        layout.setSpacing(3)
        left_label = QLabel(left_text)
        right_label = QLabel(right_text)
        for label in (left_label, right_label):
            label.setObjectName("miniLabel")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        left_label.setFixedWidth(34)
        right_label.setFixedWidth(56)
        left_spin.setFixedWidth(76)
        right_spin.setFixedWidth(76)
        left_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(left_label, 0)
        layout.addWidget(left_spin, 0)
        layout.addWidget(right_label, 0)
        layout.addWidget(right_spin, 0)
        layout.addStretch(1)
        return row

    def _build_status_bar(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("statusPanel")
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(10, 6, 10, 6)
        self.status_label = QLabel("未读取文件。")
        self.status_label.setObjectName("muted")
        self.count_label = QLabel("已读取 0 | 已选择 0 | 可改名 0 | 冲突 0")
        self.count_label.setObjectName("muted")
        layout.addWidget(self.status_label, 1)
        layout.addWidget(self.count_label)
        return panel

    def choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "选择文件夹", self.path_edit.text() or str(Path.home()))
        if folder:
            self.path_edit.setText(folder)

    def load_files(self) -> None:
        folder = Path(self.path_edit.text().strip())
        try:
            self.items = scan_files(folder, self._selected_extension_filter())
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "读取失败", str(exc))
            return
        self.refresh_table()
        self.set_status(f"已读取 {len(self.items)} 个文件。")
        self._update_buttons()

    def collect_settings(self) -> RuleSettings:
        return RuleSettings(
            include_extension=self.include_extension.isChecked(),
            find_enabled=self.find_enabled.isChecked(),
            find_text=self.find_text.text(),
            replace_text=self.replace_text.text(),
            find_case_sensitive=self.case_sensitive.isChecked(),
            prefix_enabled=self.prefix_enabled.isChecked(),
            prefix_text=self.prefix_text.text(),
            suffix_enabled=self.suffix_enabled.isChecked(),
            suffix_text=self.suffix_text.text(),
            insert_enabled=self.insert_enabled.isChecked(),
            insert_text=self.insert_text.text(),
            insert_position=self.insert_position.value(),
            trim_enabled=self.trim_enabled.isChecked(),
            trim_left=self.trim_left.value(),
            trim_right=self.trim_right.value(),
            trim_start=self.trim_start.value(),
            trim_count=self.trim_count.value(),
            number_enabled=self.number_enabled.isChecked(),
            number_start=self.number_start.value(),
            number_step=self.number_step.value(),
            number_digits=self.number_digits.value(),
            number_position=self.number_position.currentText(),  # type: ignore[arg-type]
            number_separator=self.number_separator.text(),
            extension_mode=self.extension_mode.currentText(),  # type: ignore[arg-type]
        )

    def preview(self) -> None:
        if not self.items:
            self.set_status("请先读取文件。", "warning")
            return
        build_preview(self.items, self.collect_settings())
        self.refresh_table()
        plans = build_plans(self.items)
        conflicts = sum(1 for item in self.items if item.status == "冲突")
        errors = sum(1 for item in self.items if item.status == "错误")
        self.set_status(f"预览完成：可改名 {len(plans)} 个，冲突 {conflicts} 个，错误 {errors} 个。", "success")
        self._update_buttons()

    def execute_rename(self) -> None:
        plans = build_plans(self.items)
        if not plans:
            self.set_status("没有可执行的改名项。", "warning")
            return
        if has_blocking_problem(self.items):
            self.set_status("存在冲突或错误，不能执行。", "error")
            return

        reply = QMessageBox.question(
            self,
            "确认执行改名",
            f"将改名 {len(plans)} 个文件。\n\n目标路径为当前文件所在目录。"
            "\n任一步失败将尝试恢复整批原文件。\n完整成功后才写入撤销记录。",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        results = self.executor.execute(plans)
        success_map = {str(result.target_path): result for result in results if result.ok}
        failed_map = {str(result.source_path): result for result in results if not result.ok}

        for item in self.items:
            if item.target_path and str(item.target_path) in success_map:
                item.source_path = item.target_path
                item.new_name = item.original_name
                item.status = "已完成"
                item.message = "已完成"
            elif str(item.source_path) in failed_map:
                item.status = "失败"
                item.message = failed_map[str(item.source_path)].message

        ok_count = sum(1 for result in results if result.ok)
        fail_count = len(results) - ok_count
        self.refresh_table()
        if self.executor.last_recovery_file:
            self.set_status(f"执行失败且回滚不完整；恢复清单：{self.executor.last_recovery_file}", "error")
            QMessageBox.critical(
                self,
                "需要恢复文件",
                f"批次执行失败，部分文件未能自动恢复。\n\n恢复清单：\n{self.executor.last_recovery_file}",
            )
        elif fail_count:
            self.set_status(f"执行失败：已恢复整批原文件，失败 {fail_count} 个。", "warning")
            QMessageBox.warning(self, "执行失败", "改名没有完整完成，已恢复整批原文件。")
        else:
            self.set_status(f"执行完成：成功 {ok_count} 个。", "success")
            QMessageBox.information(self, "执行完成", f"成功改名 {ok_count} 个文件。")
        self._update_buttons()

    def undo_last(self) -> None:
        reply = QMessageBox.question(self, "确认撤销", "将尝试撤销最近一次成功改名。是否继续？")
        if reply != QMessageBox.StandardButton.Yes:
            return
        results = self.executor.undo_last()
        ok_map = {str(result.source_path): result for result in results if result.ok}
        for item in self.items:
            result = ok_map.get(str(item.source_path))
            if result:
                item.source_path = result.target_path
                item.new_name = item.original_name
                item.target_path = item.source_path
                item.status = "已撤销"
                item.message = "已撤销"

        ok_count = sum(1 for result in results if result.ok)
        fail_count = len(results) - ok_count
        self.refresh_table()
        if self.executor.last_recovery_file:
            self.set_status(f"撤销失败且回滚不完整；恢复清单：{self.executor.last_recovery_file}", "error")
            QMessageBox.critical(self, "撤销需要恢复", f"恢复清单：\n{self.executor.last_recovery_file}")
        elif fail_count:
            self.set_status("撤销失败：已恢复到撤销前状态。", "warning")
            QMessageBox.warning(self, "撤销失败", "撤销没有完整完成，已恢复到撤销前状态。")
        else:
            self.set_status(f"撤销完成：成功 {ok_count} 个。", "success")
            QMessageBox.information(self, "撤销结果", f"成功撤销 {ok_count} 个文件。")
        self._update_buttons()

    def set_all_selected(self, selected: bool) -> None:
        for item in self.items:
            item.selected = selected
        self.refresh_table()
        self._update_buttons()

    def invert_selected(self) -> None:
        for item in self.items:
            item.selected = not item.selected
        self.refresh_table()
        self._update_buttons()

    def reset_find_rule(self, update_status: bool = True) -> None:
        self.find_enabled.setChecked(False)
        self.case_sensitive.setChecked(False)
        self.find_text.clear()
        self.replace_text.clear()
        if update_status:
            self.set_status("查找替换已重置。", "reset")
            self.live_preview()

    def reset_add_rule(self, update_status: bool = True) -> None:
        self.prefix_enabled.setChecked(False)
        self.suffix_enabled.setChecked(False)
        self.insert_enabled.setChecked(False)
        self.prefix_text.clear()
        self.suffix_text.clear()
        self.insert_text.clear()
        self.insert_position.setValue(0)
        if update_status:
            self.set_status("添加文本已重置。", "reset")
            self.live_preview()

    def reset_trim_rule(self, update_status: bool = True) -> None:
        self.trim_enabled.setChecked(False)
        self.trim_left.setValue(0)
        self.trim_right.setValue(0)
        self.trim_start.setValue(0)
        self.trim_count.setValue(0)
        if update_status:
            self.set_status("删除字符已重置。", "reset")
            self.live_preview()

    def reset_number_rule(self, update_status: bool = True) -> None:
        self.number_enabled.setChecked(False)
        self.number_start.setValue(1)
        self.number_step.setValue(1)
        self.number_digits.setValue(4)
        self.number_position.setCurrentText("前缀")
        self.number_separator.setText("_")
        if update_status:
            self.set_status("自动编号已重置。", "reset")
            self.live_preview()

    def reset_extension_rule(self, update_status: bool = True) -> None:
        self.extension_mode.setCurrentText("保持不变")
        if update_status:
            self.set_status("扩展名规则已重置。", "reset")
            self.live_preview()

    def reset_rules(self) -> None:
        self.include_extension.setChecked(False)
        self.reset_find_rule(update_status=False)
        self.reset_add_rule(update_status=False)
        self.reset_trim_rule(update_status=False)
        self.reset_number_rule(update_status=False)
        self.reset_extension_rule(update_status=False)
        self.set_status("规则已重置。", "reset")
        self.live_preview()

    def _connect_rule_live_preview(self) -> None:
        checkboxes = (
            self.include_extension,
            self.find_enabled,
            self.case_sensitive,
            self.prefix_enabled,
            self.suffix_enabled,
            self.insert_enabled,
            self.trim_enabled,
            self.number_enabled,
        )
        for checkbox in checkboxes:
            checkbox.toggled.connect(self.live_preview)

        edits = (
            self.find_text,
            self.replace_text,
            self.prefix_text,
            self.suffix_text,
            self.insert_text,
            self.number_separator,
        )
        for edit in edits:
            edit.textChanged.connect(self.live_preview)

        spinboxes = (
            self.insert_position,
            self.trim_left,
            self.trim_right,
            self.trim_start,
            self.trim_count,
            self.number_start,
            self.number_step,
            self.number_digits,
        )
        for spinbox in spinboxes:
            spinbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
            spinbox.valueChanged.connect(self.live_preview)

        self.number_position.currentTextChanged.connect(self.live_preview)
        self.extension_mode.currentTextChanged.connect(self.live_preview)

    def live_preview(self, *_args: object) -> None:
        if self._updating_table or not self.items:
            return
        self._live_preview_timer.start()

    def _apply_live_preview(self) -> None:
        if self._updating_table or not self.items:
            return
        build_preview(self.items, self.collect_settings())
        self.refresh_table()
        self._update_buttons()

    def clear_items(self) -> None:
        self.items = []
        self.refresh_table()
        self.set_status("列表已清空。")
        self._update_buttons()

    def open_current_folder(self) -> None:
        folder = Path(self.path_edit.text().strip())
        if folder.exists():
            os.startfile(folder)
        else:
            self.set_status("当前文件夹不存在。", "error")

    def open_logs(self) -> None:
        os.startfile(self.executor.logs_dir)

    def refresh_table(self) -> None:
        self._updating_table = True
        self.table.setRowCount(len(self.items))
        for row, item in enumerate(self.items):
            values = [
                str(row + 1),
                "☑" if item.selected else "☐",
                item.status,
                item.original_name,
                item.new_name or item.original_name,
                item.suffix.lstrip("."),
                str(item.folder),
                self._format_size(item.source_path),
                self._format_mtime(item.source_path),
                item.message,
            ]
            for col, value in enumerate(values):
                cell = QTableWidgetItem(value)
                if col == 1:
                    cell.setFlags(cell.flags() & ~Qt.ItemFlag.ItemIsEditable)
                cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                cell.setToolTip(value)
                if col == 2:
                    cell.setBackground(self._status_color(item.status))
                if col == 4 and item.new_name and item.new_name != item.original_name:
                    cell.setBackground(QColor("#edf8f6"))
                self.table.setItem(row, col, cell)
        self._updating_table = False
        self._update_counts()

    def copy_table_cell(self, row: int, column: int) -> None:
        if row < 0 or row >= self.table.rowCount():
            return
        if column == 1:
            state = Qt.CheckState.Unchecked if self.items[row].selected else Qt.CheckState.Checked
            self._set_row_checked(row, state)
            return
        if column not in {3, 4, 5, 6}:
            return
        cell = self.table.item(row, column)
        if not cell:
            return
        text = cell.text()
        QApplication.clipboard().setText(text)
        column_names = {3: "原文件名", 4: "新文件名", 5: "扩展名", 6: "所在目录"}
        variants = {3: "copySource", 4: "copyNew", 5: "copyExt", 6: "copyPath"}
        self.set_status(f"已复制 {column_names[column]}：{text}", variants[column])

    def sort_by_column(self, column: int) -> None:
        sortable_columns = {3, 4, 5, 6, 7, 8}
        if column not in sortable_columns or not self.items:
            return

        if self._sort_column == column:
            self._sort_ascending = not self._sort_ascending
        else:
            self._sort_column = column
            self._sort_ascending = True

        self.items.sort(key=lambda item: self._sort_key(item, column), reverse=not self._sort_ascending)
        order = Qt.SortOrder.AscendingOrder if self._sort_ascending else Qt.SortOrder.DescendingOrder
        self.table.horizontalHeader().setSortIndicator(column, order)
        self.refresh_table()
        direction = "正序" if self._sort_ascending else "倒序"
        column_name = self.table.horizontalHeaderItem(column).text()
        self.set_status(f"已按 {column_name} {direction}排序。")
        self._update_buttons()

    def _sort_key(self, item: FileItem, column: int) -> tuple[object, ...]:
        if column == 3:
            return self._natural_key(item.original_name)
        if column == 4:
            return self._natural_key(item.new_name or item.original_name)
        if column == 5:
            return self._natural_key(item.suffix.lstrip("."))
        if column == 6:
            return self._natural_key(str(item.folder))
        if column == 7:
            return (self._file_size(item.source_path),)
        if column == 8:
            return (self._file_mtime(item.source_path),)
        return self._natural_key(item.original_name)

    def _natural_key(self, text: str) -> tuple[object, ...]:
        return natural_sort_key(text)

    def eventFilter(self, watched: object, event: QEvent) -> bool:
        if watched is self.table.viewport():
            if event.type() == QEvent.Type.MouseButtonPress and getattr(event, "button", lambda: None)() == Qt.MouseButton.LeftButton:
                index = self.table.indexAt(event.position().toPoint())
                if index.isValid() and index.column() == 1:
                    current = self.items[index.row()].selected
                    self._drag_select_state = Qt.CheckState.Unchecked if current else Qt.CheckState.Checked
                    self._drag_selecting = True
                    self._set_row_checked(index.row(), self._drag_select_state)
                    return True

            if event.type() == QEvent.Type.MouseMove and self._drag_selecting:
                index = self.table.indexAt(event.position().toPoint())
                if index.isValid() and index.column() == 1:
                    self._set_row_checked(index.row(), self._drag_select_state)
                    return True

            if event.type() == QEvent.Type.MouseButtonRelease and self._drag_selecting:
                self._drag_selecting = False
                return True

        return super().eventFilter(watched, event)

    def _set_row_checked(self, row: int, state: Qt.CheckState) -> None:
        if row < 0 or row >= len(self.items):
            return
        self.items[row].selected = state == Qt.CheckState.Checked
        cell = self.table.item(row, 1)
        next_text = "☑" if state == Qt.CheckState.Checked else "☐"
        if cell and cell.text() != next_text:
            self._updating_table = True
            cell.setText(next_text)
            self._updating_table = False
        self._update_counts()
        self._update_buttons()

    def _update_counts(self) -> None:
        selected = sum(1 for item in self.items if item.selected)
        ready = len(build_plans(self.items))
        conflicts = sum(1 for item in self.items if item.status == "冲突")
        self.count_label.setText(f"已读取 {len(self.items)} | 已选择 {selected} | 可改名 {ready} | 冲突 {conflicts}")

    def _update_buttons(self) -> None:
        has_items = bool(self.items)
        has_plan = bool(build_plans(self.items))
        blocked = has_blocking_problem(self.items)
        self.preview_btn.setEnabled(has_items)
        self.check_btn.setEnabled(has_items)
        self.select_all_btn.setEnabled(has_items)
        self.invert_btn.setEnabled(has_items)
        self.clear_btn.setEnabled(has_items)
        self.execute_btn.setEnabled(has_plan and not blocked)

    def set_status(self, text: str, variant: str = "normal") -> None:
        self._status_variant = variant
        self._status_clear_timer.stop()
        self.status_label.setText(text)
        self._apply_current_status_style()
        self._status_clear_timer.start(7000)

    def _apply_current_status_style(self) -> None:
        if not hasattr(self, "status_label"):
            return
        styles = {
            "normal": ("#f8fafc", "#475569", "#dbe4f0"),
            "success": ("#d1fae5", "#047857", "#34d399"),
            "warning": ("#ffedd5", "#c2410c", "#fb923c"),
            "error": ("#fee2e2", "#dc2626", "#f87171"),
            "reset": ("#fef3c7", "#b45309", "#f59e0b"),
            "copySource": ("#dbeafe", "#1d4ed8", "#60a5fa"),
            "copyNew": ("#d1fae5", "#047857", "#34d399"),
            "copyExt": ("#ede9fe", "#6d28d9", "#a78bfa"),
            "copyPath": ("#ffedd5", "#c2410c", "#fb923c"),
        }
        bg, fg, border = styles.get(self._status_variant, styles["normal"])
        radius = self._scaled_value(6, self._ui_scale)
        vertical_padding = self._scaled_value(4, self._ui_scale)
        horizontal_padding = self._scaled_value(10, self._ui_scale)
        border_width = self._scaled_value(1, self._ui_scale)
        self.status_label.setStyleSheet(
            f"background:{bg}; color:{fg}; border:{border_width}px solid {border}; "
            f"border-radius:{radius}px; padding:{vertical_padding}px {horizontal_padding}px; font-weight:800;"
        )

    def clear_status(self) -> None:
        self.status_label.clear()
        self._status_variant = "normal"
        self._apply_current_status_style()

    def _format_size(self, path: Path) -> str:
        size = self._file_size(path)
        if size < 0:
            return "-"
        if size < 1024:
            return f"{size} B"
        if size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        return f"{size / 1024 / 1024:.1f} MB"

    def _format_mtime(self, path: Path) -> str:
        timestamp = self._file_mtime(path)
        if timestamp < 0:
            return "-"
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")

    def _file_size(self, path: Path) -> int:
        try:
            return path.stat().st_size
        except OSError:
            return -1

    def _file_mtime(self, path: Path) -> float:
        try:
            return path.stat().st_mtime
        except OSError:
            return -1.0

    def _status_color(self, status: str) -> QColor:
        colors = {
            "未预览": QColor("#eef2f7"),
            "可改名": QColor("#dcfce7"),
            "未变化": QColor("#f1f5f9"),
            "冲突": QColor("#fee2e2"),
            "错误": QColor("#fee2e2"),
            "跳过": QColor("#fef3c7"),
            "已完成": QColor("#bbf7d0"),
            "已撤销": QColor("#dbeafe"),
            "失败": QColor("#fecaca"),
        }
        return colors.get(status, QColor("#f8fafc"))

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: #eef5f6;
                color: #0f172a;
                font-family: "Microsoft YaHei";
                font-size: 13px;
            }
            #sidebar, #panel, #rulesPanel, #statusPanel {
                background: #ffffff;
                border: 1px solid #c9dce0;
                border-radius: 8px;
            }
            #brandMark {
                background: #0f766e;
                color: #ffffff;
                border: 1px solid #0f766e;
                border-radius: 8px;
                font-weight: 700;
                font-size: 18px;
            }
            #sidebarTitle, #pageTitle {
                font-weight: 700;
                font-size: 20px;
            }
            #sidebarTitle {
                font-size: 15px;
            }
            #sectionTitle {
                font-weight: 700;
                font-size: 15px;
            }
            #miniLabel {
                color: #0f172a;
                font-weight: 700;
                background: transparent;
            }
            #sideSection, #muted, #hint {
                color: #64748b;
            }
            #sourceLabel {
                background: #e0f2f1;
                color: #0f4f4a;
                font-weight: 600;
                border-radius: 0px;
                padding: 6px 8px;
            }
            #sideSection {
                background: transparent;
                padding: 4px 0px 4px 8px;
                font-weight: 600;
            }
            #stepLabel {
                background: #f0fdfa;
                border: 1px solid #99d8d0;
                border-radius: 6px;
                padding: 7px 9px 7px 16px;
                font-weight: 600;
                color: #0f766e;
            }
            QFrame#rulesPanel QLabel,
            QFrame#rulesPanel QCheckBox,
            QFrame#rulesPanel QLineEdit,
            QFrame#rulesPanel QSpinBox,
            QFrame#rulesPanel QComboBox {
                font-weight: 800;
            }
            #ruleBox, #findRuleBox, #addRuleBox, #trimRuleBox, #numberRuleBox, #extensionRuleBox {
                background: #fbfdff;
                border: 1px solid #d6e0ec;
                border-radius: 8px;
            }
            #ruleTitle {
                font-weight: 700;
            }
            #findRuleBox { background: #dff0ff; border-color: #60a5fa; }
            #addRuleBox { background: #dcfce7; border-color: #22c55e; }
            #trimRuleBox { background: #ffedd5; border-color: #fb923c; }
            #numberRuleBox { background: #ede9fe; border-color: #8b5cf6; }
            #extensionRuleBox { background: #e2e8f0; border-color: #94a3b8; }
            #findRuleTitle { color: #075985; font-weight: 800; }
            #addRuleTitle { color: #047857; font-weight: 800; }
            #trimRuleTitle { color: #c2410c; font-weight: 800; }
            #numberRuleTitle { color: #5b21b6; font-weight: 800; }
            #extensionRuleTitle { color: #334155; font-weight: 800; }
            QPushButton {
                background: #f8fafc;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 6px 14px;
                font-weight: 600;
                outline: none;
                text-align: center;
            }
            QPushButton:focus {
                border: 1px solid #93c5fd;
            }
            QPushButton:disabled {
                color: #94a3b8;
                background: #eef2f7;
            }
            #primaryButton { background: #0f766e; color: white; border-color: #0f766e; }
            #purpleButton { background: #eef2ff; color: #4338ca; border-color: #c7d2fe; }
            #greenButton, #greenSoftButton { background: #d1fae5; color: #047857; border-color: #34d399; }
            #orangeButton { background: #fff7ed; color: #c2410c; border-color: #fdba74; }
            #pinkSoftButton { background: #fdf2f8; color: #be185d; border-color: #fbcfe8; }
            #dangerButton { background: #ef4444; color: white; border-color: #ef4444; }
            #dangerOutline { background: #ef4444; color: #ffffff; border-color: #ef4444; }
            #dangerOutline:hover { background: #dc2626; border-color: #dc2626; }
            #sideChooseButton {
                text-align: left;
                padding-left: 18px;
                background: #d1fae5;
                color: #047857;
                border-color: #34d399;
            }
            #sideOpenButton {
                text-align: left;
                padding-left: 18px;
                background: #e0f2fe;
                color: #0369a1;
                border-color: #7dd3fc;
            }
            #sideLogButton {
                text-align: left;
                padding-left: 18px;
                background: #ede9fe;
                color: #5b21b6;
                border-color: #a78bfa;
            }
            #sideAboutButton {
                text-align: left;
                padding-left: 18px;
                background: #f8fafc;
                color: #334155;
                border-color: #cbd5e1;
            }
            #extensionFilter {
                background: #e0f2f1;
                border: 1px solid #99d8d0;
                border-radius: 6px;
            }
            #extensionGroupLabel {
                background: transparent;
                color: #0f4f4a;
                font-weight: 700;
                padding: 0px 3px;
            }
            QPushButton#extensionSequenceChip,
            QPushButton#extensionVideoChip,
            QPushButton#extensionAllChip {
                min-height: 20px;
                min-width: 42px;
                padding: 3px 8px;
                border-radius: 5px;
                text-align: center;
            }
            QPushButton#extensionSequenceChip {
                background: #ffffff;
                color: #0f766e;
                border: 1px solid #7ccdc3;
            }
            QPushButton#extensionSequenceChip:checked {
                background: #0f766e;
                color: #ffffff;
                border-color: #0f766e;
            }
            QPushButton#extensionVideoChip {
                background: #eff6ff;
                color: #1d4ed8;
                border: 1px solid #93c5fd;
            }
            QPushButton#extensionVideoChip:checked {
                background: #2563eb;
                color: #ffffff;
                border-color: #2563eb;
            }
            QPushButton#extensionAllChip {
                background: #fff7ed;
                color: #c2410c;
                border: 1px solid #fdba74;
            }
            QPushButton#extensionAllChip:checked {
                background: #ea580c;
                color: #ffffff;
                border-color: #ea580c;
            }
            QPushButton#ruleResetButton {
                background: rgba(255, 255, 255, 0.72);
                color: #475569;
                border: 1px solid #b6c5d4;
                border-radius: 5px;
                padding: 0px;
                font-size: 12px;
                font-weight: 800;
            }
            QPushButton#ruleResetButton:hover {
                background: #ffffff;
                color: #0f766e;
                border-color: #5eead4;
            }
            QLineEdit, QSpinBox, QComboBox {
                background: #ffffff;
                border: 1px solid #b9cbd2;
                border-radius: 6px;
                padding: 5px 8px;
                min-height: 20px;
            }
            QSpinBox {
                padding: 4px 24px 4px 8px;
                min-height: 22px;
            }
            QToolButton#spinArrowButton {
                background: #edf5f8;
                border: 0px;
                border-left: 1px solid #cbd5e1;
                padding: 0px;
            }
            QToolButton#spinArrowButton:hover {
                background: #e0f2fe;
            }
            QComboBox::drop-down {
                border: 0px;
                width: 22px;
            }
            QComboBox::down-arrow {
                image: none;
                border: 0px;
                width: 0px;
                height: 0px;
            }
            QWidget#comboArrowGlyph {
                background: transparent;
            }
            QTableWidget {
                background: #ffffff;
                alternate-background-color: #f5faf9;
                border: 1px solid #c9dce0;
                border-radius: 8px;
                gridline-color: #d7e4e7;
            }
            QTableWidget::item {
                padding: 4px 6px;
            }
            QTableWidget::item:selected {
                background: #dbeafe;
                color: #0f172a;
            }
            QHeaderView::section {
                background: #e0edf0;
                border: 0px;
                border-right: 1px solid #c9dce0;
                border-bottom: 1px solid #c9dce0;
                padding: 7px;
                font-weight: 700;
            }
            QScrollArea#rulesScroll {
                background: transparent;
                border: 0px;
            }
            QWidget#trimEdgeRow {
                background: #fff7ed;
                border: 1px solid #fdba74;
                border-radius: 6px;
            }
            QWidget#trimMiddleRow {
                background: #fff7ed;
                border: 1px solid #fdba74;
                border-radius: 6px;
            }
            QWidget#trimEdgeRow QLabel#miniLabel {
                color: #c2410c;
            }
            QWidget#trimMiddleRow QLabel#miniLabel {
                color: #92400e;
            }
            QWidget#numberPositionRow,
            QWidget#numberPositionDigitsRow,
            QWidget#numberDigitsRow,
            QWidget#numberRangeRow,
            QWidget#numberSeparatorRow {
                background: #f1f5ff;
                border: 1px solid #a5b4fc;
                border-radius: 6px;
            }
            QScrollBar:vertical {
                background: #edf2f8;
                width: 10px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #cbd5e1;
                border-radius: 5px;
                min-height: 32px;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
            }
            """
        )


def run() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()
