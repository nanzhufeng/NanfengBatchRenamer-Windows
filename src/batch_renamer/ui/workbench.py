"""The approved gray/white workbench; business behavior stays in app/core."""
from __future__ import annotations

from math import ceil
from PySide6.QtCore import Qt, QByteArray, QSize, QSettings, QTimer, QEvent
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap, QRegion
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (QApplication, QWidget, QFrame, QLabel, QPushButton, QCheckBox,
    QLineEdit, QVBoxLayout, QHBoxLayout, QGridLayout, QTableWidget, QHeaderView,
    QDialog, QDialogButtonBox, QStyleOptionButton, QStyle, QGraphicsDropShadowEffect, QMessageBox)

from .. import __version__, __build_time__
from ..app import MainWindow as OriginalWindow, IconSpinBox, IconComboBox

IMAGE_FORMATS = ('jpg', 'png', 'exr', 'tif', 'dpx', 'psd')
VIDEO_FORMATS = ('mp4', 'mov', 'avi', 'mkv', 'ts', 'flv', 'wmv', 'm4v')
COLUMN_WEIGHTS = (45, 45, 65, 260, 300, 55, 170, 75, 130, 100)
RULE_ICON_COLORS = {'search':'#278575', 'text':'#AC7A24', 'trash':'#C16A43',
                    'number':'#7957AF', 'extension':'#AD507C'}

# Approved editable vector assets, matching the confirmed preview.
PATHS = {
 'folder':'<path d="M3 7h6l2 2h10v11H3zM3 7V5h6l2 2"/>',
 'file':'<path d="M6 3h8l4 4v14H6zM14 3v5h4M9 12h6M9 16h6"/>',
 'reset':'<path d="M20 7V3l-3 3a8 8 0 1 0 2 10M20 7h-5"/>',
 'eye':'<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
 'shield':'<path d="M12 3l8 3v6c0 5-8 9-8 9s-8-4-8-9V6zM8 12l3 3 5-6"/>',
 'play':'<path d="M7 4l13 8-13 8z"/>',
 'search':'<circle cx="10" cy="10" r="6"/><path d="M15 15l6 6"/>',
 'help':'<circle cx="12" cy="12" r="9"/><path d="M9.4 8.5a2.7 2.7 0 0 1 5.2 1c0 1.7-2.6 1.8-2.6 3.5"/><circle cx="12" cy="16.5" r=".7" fill="#526170" stroke="none"/>',
 'trash':'<path d="M4 6h16M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7M14 10v7"/>',
 'text':'<path d="M3 5h14M10 5v15M18 11h5M20 11v9"/>',
 'number':'<text x="12" y="18" text-anchor="middle" font-family="Arial" font-size="18" font-weight="700" fill="#526170" stroke="none">01</text>',
 'extension':'<text x="12" y="18" text-anchor="middle" font-family="Arial" font-size="17" font-weight="600" fill="#526170" stroke="none">Aa</text>',
 'settings':'<path d="M9.7 3h4.6l.6 2.5 2.1 1.2 2.5-.7 2.3 4-1.9 1.8v2.4l1.9 1.8-2.3 4-2.5-.7-2.1 1.2-.6 2.5H9.7l-.6-2.5L7 18.3l-2.5.7-2.3-4 1.9-1.8v-2.4L2.2 9l2.3-4L7 5.7l2.1-1.2z" transform="translate(1.2 0) scale(.9)"/><circle cx="12" cy="12" r="3.2"/>',
 'info':'<circle cx="12" cy="12" r="9"/><path d="M11 11h1v6h1"/><circle cx="12" cy="7.5" r=".65" fill="#526170" stroke="none"/>',
 'check':'<path d="M4 12l5 5L20 6"/>',
}

def icon(name, color='#526170'):
    artwork=PATHS[name].replace('#526170',color)
    svg=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><g fill="none" stroke="{color}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">{artwork}</g></svg>'
    pixmap=QPixmap(48,48); pixmap.fill(Qt.GlobalColor.transparent)
    painter=QPainter(pixmap); QSvgRenderer(QByteArray(svg.encode())).render(painter); painter.end()
    return QIcon(pixmap)

STYLE = '''
QWidget {font-family:"Microsoft YaHei";font-size:13px;color:#233342;background:transparent;}
QMainWindow,QWidget#canvas {background:#EEEEEE;}
QFrame#card,QFrame#sidebar,QFrame#rulesPanel,QFrame#aboutCard {background:#FFFFFF;border:0;border-radius:18px;}
QFrame#managementActions,QFrame#processingActions {background:#F7F7F7;border:0;border-radius:24px;}
QFrame#rule {background:#F4F4F4;border:0;border-radius:12px;}
QFrame#aboutSection {background:#F4F4F4;border:0;border-radius:12px;}
QLabel#title {font-size:19px;font-weight:600;}
QLabel#sidebarTitle {font-size:18px;font-weight:600;}
QLabel#sub {font-size:12px;color:#82909B;}
QLabel#ruleTitle {font-size:14px;font-weight:600;}
QLabel#popupTitle {font-size:17px;font-weight:600;}
QLabel#badge {background:#E8E8E8;border-radius:8px;}
QLabel#numberBadge {background:#E8E8EC;border-radius:13px;}
QLabel#brandIcon {font-size:25px;font-weight:600;background:#EEEEEE;border-radius:10px;}
QPushButton {border:0;background:#EEEEEE;border-radius:18px;padding:0 12px;font-size:13px;font-weight:400;}
QPushButton:hover {background:#E5E5E5;}
QPushButton:pressed {background:#DCDCDC;}
QPushButton:focus {background:#E6EAF1;}
QPushButton:disabled {background:#F4F4F4;color:#9AA3AD;}
QPushButton#primary {background:#6075C8;color:#FFFFFF;}
QPushButton#primary:hover {background:#566AB5;}
QPushButton#primary:pressed {background:#4D5FA4;}
QPushButton#primary:disabled {background:#CDD3E5;color:#FFFFFF;}
QPushButton#apricot {background:#FFF0E3;color:#A9744D;}
QPushButton#apricot:hover {background:#F6E6D8;}
QPushButton#lavender {background:#F1EBFC;color:#8066AA;}
QPushButton#pale {background:#EDF2FF;color:#5269AC;}
QPushButton#green {background:#E7EFE9;color:#557562;}
QPushButton#type:checked {background:#E7EFE9;color:#557562;}
QPushButton#format {border-radius:14px;}
QPushButton#format:checked {background:#EDF2FF;color:#5269AC;}
QPushButton#nav {background:transparent;text-align:left;padding-left:10px;}
QPushButton#nav:hover {background:#F4F4F4;}
QPushButton#reset {background:#EAEAEA;border-radius:8px;font-size:11px;padding:0 6px;}
QPushButton#reset:hover {background:#DEDEDE;}
QPushButton#popupClose {background:#EEEEEE;border:0;border-radius:8px;padding:0;}
QPushButton#popupClose:hover {background:#E5E5E5;}
QPushButton#popupClose:pressed {background:#DCDCDC;}
QPushButton#popupClose:focus {background:#E6EAF1;}
QLineEdit,QSpinBox,QComboBox {border:0;background:#EEEEEE;border-radius:8px;padding:0 9px;}
QLineEdit:focus,QSpinBox:focus,QComboBox:focus {background:#E8ECF2;}
QFrame#rule QLineEdit,QFrame#rule QSpinBox,QFrame#rule QComboBox {background:#FFFFFF;}
QFrame#rule QLineEdit:focus,QFrame#rule QSpinBox:focus,QFrame#rule QComboBox:focus {background:#EDF2FF;}
QSpinBox {padding-right:25px;}
QComboBox {padding-right:28px;}
QComboBox::drop-down {border:0;width:28px;background:transparent;}
QComboBox::down-arrow {image:none;border:0;}
QToolButton#spinArrowButton {border:0;background:transparent;padding:0;border-radius:4px;}
QToolButton#spinArrowButton:hover {background:#EEEEEE;}
QCheckBox {spacing:7px;}
QCheckBox::indicator {width:16px;height:16px;border:0;border-radius:3px;background:#D3D7DC;}
QCheckBox::indicator:checked {background:#6075C8;}
QCheckBox:disabled {color:#9AA3AD;}
QTableWidget {border:0;background:#FFFFFF;alternate-background-color:#FAFAFA;selection-background-color:#EDF2FF;gridline-color:transparent;}
QHeaderView {background:#FAFAFA;border:0;padding:0;}
QHeaderView::section {background:#FAFAFA;border:0;padding:8px 2px;font-size:12px;}
QScrollBar:vertical {background:#F4F4F4;width:8px;border:0;}
QScrollBar::handle:vertical {background:#CDD1D3;border-radius:4px;min-height:24px;}
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {height:0;}
'''

class CheckBox(QCheckBox):
    def paintEvent(self,event):
        super().paintEvent(event)
        if self.isChecked():
            option=QStyleOptionButton(); self.initStyleOption(option)
            box=self.style().subElementRect(QStyle.SubElement.SE_CheckBoxIndicator,option,self)
            painter=QPainter(self); icon('check','#FFFFFF').paint(painter,box.adjusted(1,1,-1,-1)); painter.end()

class Switch(CheckBox):
    def __init__(self,name):
        super().__init__(); self.setAccessibleName(name); self.setFixedSize(42,24)
    def hitButton(self,point):
        return self.rect().contains(point)
    def paintEvent(self,event):
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing); p.setPen(Qt.PenStyle.NoPen)
        track = '#6B8879' if self.hasFocus() and self.isChecked() else '#769483' if self.isChecked() else '#C8CED3' if self.hasFocus() else '#D8DCE0'
        p.setBrush(QColor(track))
        p.drawRoundedRect(self.rect(),self.height()/2,self.height()/2)
        radius=self.height()-6; x=self.width()-radius-3 if self.isChecked() else 3
        p.setBrush(QColor('#FFFFFF')); p.drawEllipse(x,3,radius,radius)
        p.end()

class WorkbenchTable(QTableWidget):
    def resizeEvent(self,event):
        super().resizeEvent(event); self.fit_columns()
    def fit_columns(self):
        available=self.viewport().width(); total=sum(COLUMN_WEIGHTS)
        widths=[round(available*w/total) for w in COLUMN_WEIGHTS]; widths[-1]=available-sum(widths[:-1])
        for i,w in enumerate(widths): self.setColumnWidth(i,w)
        r=18*getattr(self.window(),'_ui_scale',1)
        path=QPainterPath(); path.moveTo(0,r); path.quadTo(0,0,r,0)
        path.lineTo(self.width()-r,0); path.quadTo(self.width(),0,self.width(),r)
        path.lineTo(self.width(),self.height()); path.lineTo(0,self.height()); path.closeSubpath()
        self.setMask(QRegion(path.toFillPolygon().toPolygon()))

def label(text,name=''):
    w=QLabel(text); w.setObjectName(name); return w

def field(text='',placeholder=''):
    w=QLineEdit(text); w.setPlaceholderText(placeholder); w.setFixedHeight(32); return w

def button(text,name='neutral',glyph=None,width=None):
    w=QPushButton(text); w.setObjectName(name); w.setFixedHeight(38)
    if glyph: w.setIcon(icon(glyph,'#FFFFFF' if name=='primary' else '#526170')); w.setIconSize(QSize(18,18))
    if width: w.setFixedWidth(width)
    return w

def row(parent,*widgets):
    l=QHBoxLayout(); l.setSpacing(10)
    for w in widgets: l.addWidget(w)
    parent.addLayout(l); return l

def spin(value=0,maximum=9999,minimum=0):
    w=IconSpinBox(); w.setRange(minimum,maximum); w.setValue(value); w.setFixedHeight(32)
    w.setMinimumWidth(48); return w

def combo(values):
    w=IconComboBox(); w.addItems(values); w.setFixedHeight(32); return w

class PopupSurface(QDialog):
    """One opaque rounded surface for all application-owned dialogs."""
    def __init__(self,parent=None):
        super().__init__(parent,Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setModal(True); self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet(STYLE+'QDialog {background:transparent;}')
        outer=QVBoxLayout(self); outer.setContentsMargins(16,16,16,16)
        self.surface=QFrame(); self.surface.setObjectName('card'); outer.addWidget(self.surface)
        shadow=QGraphicsDropShadowEffect(self.surface); shadow.setBlurRadius(24); shadow.setOffset(0,2); shadow.setColor(QColor(0,0,0,30)); self.surface.setGraphicsEffect(shadow)
        self.content=QVBoxLayout(self.surface); self.content.setContentsMargins(24,24,24,24); self.content.setSpacing(16)

    def title_row(self,title,glyph='info'):
        line=QHBoxLayout(); line.setSpacing(10)
        badge=QLabel(); badge.setPixmap(icon(glyph).pixmap(20,20)); line.addWidget(badge)
        line.addWidget(label(title,'popupTitle'),1)
        close=button('×','popupClose',width=28); close.setFixedHeight(28); close.setAccessibleName('关闭窗口'); close.clicked.connect(self.reject)
        line.addWidget(close); self.content.addLayout(line)

class MessageDialog(PopupSurface):
    def __init__(self,parent,kind,title,text):
        super().__init__(parent); self.setWindowTitle(title); self.resize(472,260)
        self.setMinimumWidth(400); self.title_row(title,'shield' if kind=='question' else 'info')
        self.body=QLabel(text); self.body.setTextFormat(Qt.TextFormat.PlainText); self.body.setWordWrap(True)
        self.body.setStyleSheet('font-size:14px;color:#405362;background:transparent;'); self.content.addWidget(self.body)
        self.content.addSpacing(8); controls=QHBoxLayout(); controls.addStretch()
        self.cancel_btn=None
        if kind=='question':
            self.cancel_btn=button('取消'); self.cancel_btn.clicked.connect(self.reject); controls.addWidget(self.cancel_btn)
        self.confirm_btn=button('确认' if kind=='question' else '知道了','primary')
        self.confirm_btn.setAutoDefault(False); self.confirm_btn.clicked.connect(self.accept); controls.addWidget(self.confirm_btn)
        self.content.addLayout(controls)
        if self.cancel_btn:
            self.cancel_btn.setDefault(True); self.cancel_btn.setFocus()
        else: self.confirm_btn.setFocus()
        self.content.setSizeConstraint(QVBoxLayout.SizeConstraint.SetMinimumSize)

class AboutDialog(PopupSurface):
    def __init__(self,parent=None):
        super().__init__(parent); self.setWindowTitle('关于 南枫批量改名'); self.setModal(True)
        self.setMinimumSize(620,490); self.resize(660,560)
        l=self.content; l.setContentsMargins(30,24,30,24); l.setSpacing(24)
        title=label('关于','title'); title.setAlignment(Qt.AlignmentFlag.AlignCenter); l.addWidget(title)
        card=QFrame(); card.setObjectName('aboutCard')
        cl=QVBoxLayout(card); cl.setContentsMargins(0,0,0,0); cl.setSpacing(12)
        sections=[]
        for heading in ('南枫批量改名 Windows','版本信息','开发者信息'):
            section=QFrame(); section.setObjectName('aboutSection'); section_layout=QVBoxLayout(section)
            section_layout.setContentsMargins(20,18,20,18); section_layout.setSpacing(8)
            section_layout.addWidget(label(heading,'ruleTitle')); cl.addWidget(section); sections.append(section_layout)
        sections[0].addWidget(label('本地文件批量改名与安全预览工作台。'))
        sections[1].addWidget(label(f'Desktop 版 {__version__}'))
        sections[1].addWidget(label(f'开发时间  {__build_time__}'))
        sections[2].addWidget(label('开发者：席瑞'))
        sections[2].addWidget(label('联系邮箱：nanzhufeng.studio@gmail.com'))
        link=QLabel('源码与更新：<a href="https://github.com/nanzhufeng/NanfengBatchRenamer-Windows">GitHub · nanzhufeng/NanfengBatchRenamer-Windows</a>')
        link.setOpenExternalLinks(True); link.setWordWrap(True); sections[2].addWidget(link)
        sections[2].addWidget(label('版权所有 © 2026 席瑞')); l.addWidget(card,1)
        close=button('关闭','primary',width=140); close.clicked.connect(self.accept)
        bottom=QHBoxLayout(); bottom.addStretch(); bottom.addWidget(close); bottom.addStretch(); l.addLayout(bottom)

class SettingsDialog(PopupSurface):
    def __init__(self,parent):
        super().__init__(parent); self.owner=parent; self.setModal(True); self.setWindowTitle('设置')
        self.resize(640,540)
        l=self.content; l.setSpacing(14); self.title_row('设置','settings')
        card=QFrame(); card.setObjectName('rule'); c=QVBoxLayout(card); c.setContentsMargins(18,18,18,18); c.setSpacing(14)
        heading=QHBoxLayout(); glyph=QLabel(); glyph.setPixmap(icon('folder').pixmap(20,20)); heading.addWidget(glyph)
        heading.addWidget(label('文件与启动','ruleTitle'),1); c.addLayout(heading)
        self.remember=CheckBox('启动时恢复上次来源文件夹'); self.remember.setChecked(parent.preferences.value('remember_folder',False,type=bool)); c.addWidget(self.remember)
        self.default_type=combo(['全部','图片','视频']); self.default_type.setCurrentText(parent.preferences.value('default_type','全部'))
        row(c,label('启动文件类型'),self.default_type); c.addWidget(label('仅保存界面偏好；不会移动、删除或改名文件。','sub')); l.addWidget(card)
        review=button('功能审阅  ▾'); review.setCheckable(True); l.addWidget(review)
        self.review=label('类型筛选：保留，位于来源卡；减少格式干扰。\n包含扩展名：保留，位于规则标题；明确改名范围。\n五组规则：保留并默认展开；可直接预览与独立重置。\n撤销：保留在动作条；恢复最近一次成功批次。\n包含子文件夹：保留，勾选后重新读取；包含所有层级，仍在原目录改名。')
        self.review.setText(self.review.text()+'\n窗口大小记忆：保留，关闭时自动保存；下次恢复大小与最大化状态，无需额外按键。')
        self.review.setObjectName('sub'); self.review.setWordWrap(True); self.review.hide(); l.addWidget(self.review)
        review.toggled.connect(self.review.setVisible); l.addStretch()
        controls=QHBoxLayout(); controls.addStretch(); cancel=button('取消'); save=button('保存','primary')
        cancel.clicked.connect(self.reject); save.clicked.connect(self.accept); controls.addWidget(cancel); controls.addWidget(save); l.addLayout(controls)
    def accept(self):
        prefs=self.owner.preferences; prefs.setValue('remember_folder',self.remember.isChecked())
        prefs.setValue('default_type',self.default_type.currentText())
        if self.remember.isChecked(): prefs.setValue('last_folder',self.owner.path_edit.text())
        else: prefs.remove('last_folder')
        prefs.sync(); super().accept()

class WorkbenchWindow(OriginalWindow):
    BASE_WIDTH=1820
    BASE_HEIGHT=1130
    SIDEBAR_WIDTH=206
    def __init__(self, preferences=None):
        self.preferences=preferences if preferences is not None else QSettings('Nanzhufeng','NanfengBatchRenamer')
        self._window_restore_done=False
        self._resize_reflow_pending=False
        self._resize_reflow_generation=0
        self._applying_ui_scale=False
        super().__init__()
        if self.preferences.value('remember_folder',False,type=bool): self.path_edit.setText(self.preferences.value('last_folder',''))
        self.set_file_type(self.preferences.value('default_type','全部'))

    def _fit_to_current_screen(self):
        self._screen_fit_pending=False
        first=not self._window_restore_done
        saved=self.preferences.value('window_size') if first else self.normalGeometry().size()
        self._window_restore_done=True
        if not isinstance(saved,QSize) or saved.width()<=0 or saved.height()<=0:
            return super()._fit_to_current_screen()
        handle=self.windowHandle()
        screen=handle.screen() if handle and handle.screen() else QApplication.primaryScreen()
        if screen is None: return
        available=screen.availableGeometry()
        width=max(self.MINIMUM_WIDTH,min(saved.width(),available.width()-16))
        height=max(self.MINIMUM_HEIGHT,min(saved.height(),available.height()-48))
        self.apply_ui_scale(self.scale_for_available_size(width,height))
        self.resize(width,height)
        self.move(available.left()+max(0,(available.width()-self.frameGeometry().width())//2),
                  available.top()+max(0,(available.height()-self.frameGeometry().height())//2))
        if first and self.preferences.value('window_maximized',False,type=bool): self.showMaximized()

    def closeEvent(self,event):
        maximized=self.isMaximized() or bool(self.windowState() & Qt.WindowState.WindowMaximized)
        size=self.normalGeometry().size() if maximized or self.isMinimized() else self.size()
        if size.isValid(): self.preferences.setValue('window_size',size)
        self.preferences.setValue('window_maximized',maximized)
        self.preferences.sync()
        super().closeEvent(event)

    def _build_ui(self):
        root=QWidget(); root.setObjectName('canvas'); layout=QHBoxLayout(root)
        layout.setContentsMargins(24,24,24,24); layout.setSpacing(18)
        layout.addWidget(self._build_sidebar()); main=QVBoxLayout(); main.setSpacing(14)
        main.addWidget(self._build_source_panel()); main.addWidget(self._build_action_bar())
        card=QFrame(); card.setObjectName('card'); table_layout=QVBoxLayout(card); table_layout.setContentsMargins(0,0,0,16); table_layout.setSpacing(12)
        self.table=WorkbenchTable(0,10); self.table.setObjectName('fileTable')
        self.table.setHorizontalHeaderLabels(['序号','选择','状态','原文件名','新文件名','扩展名','所在目录','大小','修改时间','问题提示'])
        self.table.verticalHeader().hide(); self.table.setAlternatingRowColors(True); self.table.setShowGrid(False)
        self.table.setWordWrap(False); self.table.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows); self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.table.horizontalHeader().setSectionsClickable(True); self.table.horizontalHeader().setSortIndicatorShown(True)
        self.table.horizontalHeader().setFixedHeight(38); self.table.verticalHeader().setDefaultSectionSize(38)
        self.table.viewport().installEventFilter(self); self.table.cellClicked.connect(self.copy_table_cell)
        self.table.horizontalHeader().sectionClicked.connect(self.sort_by_column); table_layout.addWidget(self.table,1)
        status=QHBoxLayout(); status.setContentsMargins(12,0,12,0)
        self.status_label=label('未读取文件。','sub'); self.count_label=label('','sub')
        status.addWidget(self.status_label,1); status.addWidget(self.count_label); table_layout.addLayout(status)
        main.addWidget(card,1); layout.addLayout(main,1); layout.addWidget(self._build_rules_panel())
        self.setCentralWidget(root)

    def _build_sidebar(self):
        card=QFrame(); card.setObjectName('sidebar'); card.setFixedWidth(self.SIDEBAR_WIDTH)
        l=QVBoxLayout(card); l.setContentsMargins(18,24,18,20); l.setSpacing(12)
        brand=QHBoxLayout(); brand.setSpacing(6); mark=label('南','brandIcon'); mark.setFixedSize(40,42); mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        brand.addWidget(mark); brand.addWidget(label('南枫批量改名','sidebarTitle')); l.addLayout(brand)
        l.addSpacing(26); self.open_folder_btn=button('打开当前目录','nav','folder'); self.open_logs_btn=button('打开日志','nav','file')
        self.open_folder_btn.clicked.connect(self.open_current_folder); self.open_logs_btn.clicked.connect(self.open_logs)
        l.addWidget(self.open_folder_btn); l.addWidget(self.open_logs_btn); l.addStretch()
        self.settings_btn=button('设置','neutral','settings'); self.about_btn=button('关于软件','neutral','info')
        self.settings_btn.clicked.connect(lambda:SettingsDialog(self).exec()); self.about_btn.clicked.connect(self.show_about)
        l.addWidget(self.settings_btn); l.addWidget(self.about_btn); return card

    def show_about(self):
        AboutDialog(self).exec()

    def _message(self,kind,title,text):
        dialog=MessageDialog(self,kind,title,text)
        result=dialog.exec()
        return QMessageBox.StandardButton.Yes if result==QDialog.DialogCode.Accepted else QMessageBox.StandardButton.No

    def _build_source_panel(self):
        card=QFrame(); card.setObjectName('card'); self.source_panel=card
        l=QVBoxLayout(card); l.setContentsMargins(24,22,24,16); l.setSpacing(16)
        l.addWidget(label('选择源文件夹','title')); self.path_edit=field(placeholder='选择要处理的文件夹')
        self.browse_btn=button('选择','pale',width=88); self.read_btn=button('读取文件','apricot','folder',126)
        r=row(l,self.path_edit,self.browse_btn,self.read_btn); r.setStretch(0,1)
        self.browse_btn.clicked.connect(self.choose_folder); self.read_btn.clicked.connect(self.load_files); self.path_edit.returnPressed.connect(self.load_files)
        types=QHBoxLayout(); types.setSpacing(12); types.addWidget(label('文件类型'))
        self.type_buttons={}
        for name in ('全部','图片','视频'):
            b=button(name,'type',width=82); b.setCheckable(True); b.clicked.connect(lambda checked=False,n=name:self.set_file_type(n)); types.addWidget(b); self.type_buttons[name]=b
        self.extension_all_btn=self.type_buttons['全部']; types.addStretch()
        subfolder_help='包含子文件夹\n勾选后，点击“读取文件”，读取所选文件夹及所有层级子文件夹中的文件。\n不勾选时，只读取当前文件夹。\n文件类型和扩展名筛选仍然有效；改名与撤销都在各文件原目录进行。\n不会对文件夹改名，也不会进入目录链接。'
        self.include_subfolders=CheckBox('包含子文件夹'); self.include_subfolders.setToolTip(subfolder_help)
        types.addWidget(self.include_subfolders)
        self.subfolder_help_icon=QLabel(); self.subfolder_help_icon.setPixmap(icon('help','#697986').pixmap(20,20))
        self.subfolder_help_icon.setFixedSize(24,24); self.subfolder_help_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subfolder_help_icon.setAccessibleName('包含子文件夹功能说明'); self.subfolder_help_icon.setAccessibleDescription(subfolder_help)
        self.subfolder_help_icon.setToolTip(subfolder_help); self.subfolder_help_icon.setCursor(Qt.CursorShape.WhatsThisCursor)
        types.addWidget(self.subfolder_help_icon); l.addLayout(types)
        # Stable reserved slot; changing type never moves the action bar or table.
        self.filter_slot=QWidget(); self.filter_slot.setFixedHeight(32); slot=QHBoxLayout(self.filter_slot); slot.setContentsMargins(0,0,0,0)
        self.filter_contents=QWidget(); fl=QHBoxLayout(self.filter_contents); fl.setContentsMargins(0,0,0,0); fl.setSpacing(6); fl.addWidget(label('扩展名筛选'))
        self.extension_buttons={}
        for ext in IMAGE_FORMATS+VIDEO_FORMATS:
            b=button(ext,'format',width=52); b.setFixedHeight(28); b.setCheckable(True); b.setChecked(True); self.extension_buttons[ext]=b; fl.addWidget(b)
        fl.addStretch(); slot.addWidget(self.filter_contents); l.addWidget(self.filter_slot)
        self._file_type='全部'; self.set_file_type('全部'); return card

    def set_file_type(self,name):
        if name not in self.type_buttons: name='全部'
        self._file_type=name
        for key,b in self.type_buttons.items(): b.setChecked(key==name)
        visible=IMAGE_FORMATS if name=='图片' else VIDEO_FORMATS if name=='视频' else ()
        for ext,b in self.extension_buttons.items(): b.setVisible(ext in visible)
        self.filter_contents.setVisible(name!='全部')

    def _selected_extension_filter(self):
        if self._file_type=='全部': return ''
        group=IMAGE_FORMATS if self._file_type=='图片' else VIDEO_FORMATS
        selected=[ext for ext in group if self.extension_buttons[ext].isChecked()]
        # Empty selection must not accidentally mean unrestricted scanning.
        return ','.join(selected) if selected else '__no_format_selected__'

    def _build_action_bar(self):
        card=QFrame(); card.setObjectName('card'); l=QHBoxLayout(card); l.setContentsMargins(14,6,14,6); l.setSpacing(24)
        self.processing_actions=QFrame(); self.processing_actions.setObjectName('processingActions'); self.processing_actions.setAccessibleName('文件处理操作')
        self.management_actions=QFrame(); self.management_actions.setObjectName('managementActions'); self.management_actions.setAccessibleName('列表与规则操作')
        groups=[]
        for group in (self.processing_actions,self.management_actions):
            layout=QHBoxLayout(group); layout.setContentsMargins(6,6,6,6); layout.setSpacing(10); groups.append(layout)
        l.addWidget(self.management_actions); l.addWidget(self.processing_actions)
        specs=[('preview_btn','预览','pale','eye',84,self.preview),('check_btn','检查冲突','neutral','shield',112,self.preview),
            ('execute_btn','执行改名','primary','play',112,self.execute_rename),('undo_btn','撤销','apricot','reset',82,self.undo_last),
            ('select_all_btn','全选','pale','check',78,lambda:self.set_all_selected(True)),('invert_btn','反选','lavender','check',78,self.invert_selected),
            ('reset_btn','重置规则','neutral','reset',108,self.reset_rules),('clear_btn','清空列表','neutral','trash',108,self.clear_items)]
        for i,(attr,text,name,glyph,width,callback) in enumerate(specs):
            b=button(text,name,glyph,width); setattr(self,attr,b); b.clicked.connect(callback); groups[i//4].addWidget(b)
        l.addStretch(); return card

    def _rule(self,title,glyph,switch,reset):
        card=QFrame(); card.setObjectName('rule'); l=QVBoxLayout(card); l.setContentsMargins(14,14,14,14); l.setSpacing(10)
        h=QHBoxLayout(); h.setSpacing(8); badge=QLabel(); badge.setPixmap(icon(glyph,RULE_ICON_COLORS[glyph]).pixmap(18,18)); badge.setFixedSize(26,26)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter); badge.setObjectName('numberBadge' if glyph in ('number','extension') else 'badge')
        h.addWidget(badge); h.addWidget(label(title,'ruleTitle')); h.addStretch(); h.addWidget(switch)
        b=button('重置','reset','reset',62); b.setFixedHeight(26); b.setAccessibleName(f'重置{title}'); b.clicked.connect(lambda:reset()); h.addWidget(b); l.addLayout(h)
        self.rule_cards.append(card); return card,l

    def _build_rules_panel(self):
        card=QFrame(); card.setObjectName('rulesPanel'); card.setFixedWidth(320); l=QVBoxLayout(card); l.setContentsMargins(14,22,14,18); l.setSpacing(12)
        self.rule_cards=[]; h=QHBoxLayout(); h.addWidget(label('重命名规则','title')); h.addStretch()
        self.include_extension=CheckBox('包含扩展名'); self.include_extension.setAccessibleName('改名范围：包含扩展名'); self.include_extension.setToolTip('对完整文件名应用规则，含点号与扩展名。')
        h.addWidget(self.include_extension); l.addLayout(h); l.addSpacing(6)
        self.find_enabled=Switch('启用查找替换'); c,r=self._rule('查找替换','search',self.find_enabled,self.reset_find_rule)
        self.find_text=field(placeholder='查找内容'); self.replace_text=field(placeholder='替换为'); self.case_sensitive=CheckBox('区分大小写')
        r.addWidget(self.find_text); r.addWidget(self.replace_text); r.addWidget(self.case_sensitive); l.addWidget(c)
        self.add_enabled=Switch('启用添加文字'); c,r=self._rule('添加文字','text',self.add_enabled,self.reset_add_rule)
        self.prefix_enabled=CheckBox('前缀'); self.prefix_text=field(placeholder='例如：shot_')
        self.suffix_enabled=CheckBox('后缀'); self.suffix_text=field(placeholder='例如：_v001')
        for check,edit in ((self.prefix_enabled,self.prefix_text),(self.suffix_enabled,self.suffix_text)):
            check.setFixedWidth(58); layout=row(r,check,edit); layout.setStretch(1,1)
        self.insert_enabled=CheckBox('指定位置'); self.insert_position=spin(maximum=999); self.insert_text=field(placeholder='插入内容')
        layout=row(r,self.insert_enabled,label('位置'),self.insert_position); layout.setStretch(0,1); r.addWidget(self.insert_text); l.addWidget(c)
        self.trim_enabled=Switch('启用删除字符'); c,r=self._rule('删除字符','trash',self.trim_enabled,self.reset_trim_rule)
        self.trim_left=spin(maximum=999); self.trim_right=spin(maximum=999); self.trim_start=spin(maximum=999); self.trim_count=spin(maximum=999)
        grid=QGridLayout(); grid.setHorizontalSpacing(7); grid.setVerticalSpacing(10)
        for i,(a,sa,b,sb) in enumerate((('开头',self.trim_left,'结尾',self.trim_right),('位置',self.trim_start,'删除数量',self.trim_count))):
            for j,w in enumerate((label(a),sa,label(b),sb)): grid.addWidget(w,i,j)
        r.addLayout(grid); l.addWidget(c)
        self.number_enabled=Switch('启用自动编号'); c,r=self._rule('自动编号','number',self.number_enabled,self.reset_number_rule)
        self.number_position=combo(['前缀','后缀']); self.number_digits=spin(4,12,1); self.number_start=spin(1,999999); self.number_step=spin(1,9999,1); self.number_separator=field('_')
        grid=QGridLayout(); grid.setHorizontalSpacing(7); grid.setVerticalSpacing(10)
        for i,widgets in enumerate(((label('位置'),self.number_position,label('位数'),self.number_digits),(label('起始'),self.number_start,label('递增'),self.number_step))):
            for j,w in enumerate(widgets): grid.addWidget(w,i,j)
        r.addLayout(grid); row(r,label('分隔符'),self.number_separator); l.addWidget(c)
        self.extension_enabled=Switch('启用扩展名大小写'); c,r=self._rule('扩展名','extension',self.extension_enabled,self.reset_extension_rule)
        self.extension_mode=combo(['保持不变','统一小写','统一大写']); r.addWidget(self.extension_mode); l.addWidget(c); l.addStretch(); return card

    def _connect_rule_live_preview(self):
        super()._connect_rule_live_preview()
        self.add_enabled.toggled.connect(self.live_preview); self.extension_enabled.toggled.connect(self.live_preview)
        for check in (self.prefix_enabled,self.suffix_enabled,self.insert_enabled):
            check.toggled.connect(lambda checked: self.add_enabled.setChecked(True) if checked else None)
        self.extension_mode.currentTextChanged.connect(lambda text:self.extension_enabled.setChecked(text!='保持不变'))

    def collect_settings(self):
        settings=super().collect_settings()
        if not self.add_enabled.isChecked(): settings.prefix_enabled=settings.suffix_enabled=settings.insert_enabled=False
        if not self.extension_enabled.isChecked(): settings.extension_mode='保持不变'
        return settings

    def reset_add_rule(self,update_status=True):
        super().reset_add_rule(update_status); self.add_enabled.setChecked(False)

    def reset_extension_rule(self,update_status=True):
        super().reset_extension_rule(update_status); self.extension_enabled.setChecked(False)

    def load_files(self):
        super().load_files()
        if self.preferences.value('remember_folder',False,type=bool): self.preferences.setValue('last_folder',self.path_edit.text())

    def refresh_table(self):
        super().refresh_table()
        self.table.fit_columns()

    def _apply_style(self):
        self.setStyleSheet(STYLE)

    def _apply_current_status_style(self):
        if not hasattr(self,'status_label'): return
        color='#976148' if self._status_variant in ('warning','error') else '#557562' if self._status_variant=='success' else '#82909B'
        self.status_label.setStyleSheet(f'color:{color};background:transparent;border:0;font-weight:400;')

    def _status_color(self,status):
        return QColor('#FFFFFF')

    def apply_ui_scale(self,scale):
        self._resize_reflow_generation+=1
        self._resize_reflow_pending=False
        self._applying_ui_scale=True
        try:
            super().apply_ui_scale(scale)
        finally:
            self._applying_ui_scale=False
        self.table.horizontalHeader().setFixedHeight(ceil(38*self._ui_scale)); self.table.fit_columns()
        for b in self.findChildren(QPushButton): b.setIconSize(QSize(ceil(18*self._ui_scale),ceil(18*self._ui_scale)))
        for b in self.extension_buttons.values(): b.setStyleSheet(f'border-radius:{b.height()//2}px;')

    def resizeEvent(self,event):
        super().resizeEvent(event)
        if hasattr(self,'table'):
            QTimer.singleShot(0,self.table.fit_columns)
            if not self._resize_reflow_pending and not self._applying_ui_scale:
                self._resize_reflow_pending=True
                generation=self._resize_reflow_generation
                QTimer.singleShot(0,lambda:self._reflow_resized_window(generation))

    def _reflow_resized_window(self,generation):
        if generation!=self._resize_reflow_generation: return
        self._resize_reflow_pending=False
        if not self._window_restore_done: return
        scale=self.scale_for_available_size(self.width(),self.height())
        if abs(scale-self._ui_scale)>0.001: self.apply_ui_scale(scale)

    def _apply_accessibility(self):
        super()._apply_accessibility()
        self.settings_btn.setAccessibleName('打开设置'); self.browse_btn.setAccessibleName('选择来源文件夹'); self.read_btn.setAccessibleName('读取文件')

