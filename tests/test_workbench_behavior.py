from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from PySide6.QtCore import Qt, QSettings, QSize
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from batch_renamer.app import MainWindow
from batch_renamer.core.executor import RenameExecutor
from batch_renamer.ui.workbench import SettingsDialog, MessageDialog, IMAGE_FORMATS, VIDEO_FORMATS, COLUMN_WEIGHTS


class WorkbenchBehaviorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.window=MainWindow(QSettings(str(Path(self.temp.name)/'preferences.ini'),QSettings.Format.IniFormat))
        self.window.show(); self.app.processEvents()

    def tearDown(self):
        self.window.close(); self.window.deleteLater(); self.app.processEvents(); self.temp.cleanup()

    def test_type_switch_preserves_layout_and_scans_only_visible_group(self):
        folder=Path(self.temp.name)/'files'; folder.mkdir()
        for name in ('shot.jpg','shot.png','shot.ts','shot.mkv','unknown.xyz'):
            (folder/name).write_text('sample',encoding='utf-8')
        self.window.path_edit.setText(str(folder))
        before=(self.window.source_panel.height(),self.window.table.mapTo(self.window,self.window.table.rect().topLeft()).y())
        for name,extensions in (('图片',IMAGE_FORMATS),('视频',VIDEO_FORMATS),('全部',())):
            QTest.mouseClick(self.window.type_buttons[name],Qt.MouseButton.LeftButton)
            self.app.processEvents()
            after=(self.window.source_panel.height(),self.window.table.mapTo(self.window,self.window.table.rect().topLeft()).y())
            self.assertEqual(before,after)
            self.assertEqual({ext for ext,b in self.window.extension_buttons.items() if b.isVisible()},set(extensions))
            self.window.load_files()
            expected={'shot.jpg','shot.png'} if name=='图片' else {'shot.ts','shot.mkv'} if name=='视频' else {'shot.jpg','shot.png','shot.ts','shot.mkv','unknown.xyz'}
            self.assertEqual({item.original_name for item in self.window.items},expected)
        self.window.set_file_type('视频')
        for ext in VIDEO_FORMATS: self.window.extension_buttons[ext].setChecked(False)
        self.window.load_files(); self.assertEqual(self.window.items,[])

    def test_rule_switches_gate_parameters_without_losing_values(self):
        QTest.mouseClick(self.window.find_enabled,Qt.MouseButton.LeftButton)
        self.assertTrue(self.window.find_enabled.isChecked())
        QTest.mouseClick(self.window.find_enabled,Qt.MouseButton.LeftButton)
        self.assertFalse(self.window.find_enabled.isChecked())
        self.window.prefix_text.setText('P_'); self.window.prefix_enabled.setChecked(True)
        self.assertTrue(self.window.collect_settings().prefix_enabled)
        self.window.add_enabled.setChecked(False)
        self.assertFalse(self.window.collect_settings().prefix_enabled)
        self.assertEqual(self.window.prefix_text.text(),'P_')
        self.window.add_enabled.setChecked(True)
        self.assertTrue(self.window.collect_settings().prefix_enabled)
        self.window.extension_mode.setCurrentText('统一小写')
        self.assertEqual(self.window.collect_settings().extension_mode,'统一小写')
        self.window.extension_enabled.setChecked(False)
        self.assertEqual(self.window.collect_settings().extension_mode,'保持不变')
        self.window.reset_rules()
        self.assertFalse(self.window.add_enabled.isChecked()); self.assertFalse(self.window.extension_enabled.isChecked())

    def test_public_ui_preview_execute_undo_on_temporary_files(self):
        folder=Path(self.temp.name)/'rename'; folder.mkdir()
        source=folder/'film.mkv1'; source.write_text('original',encoding='utf-8')
        self.window.executor=RenameExecutor(folder/'logs')
        self.window.path_edit.setText(str(folder)); self.window.load_files()
        self.window.include_extension.setChecked(True); self.window.find_enabled.setChecked(True)
        self.window.find_text.setText('mkv1'); self.window.replace_text.setText('mkv')
        QTest.qWait(160)
        self.assertTrue(self.window.execute_btn.isEnabled())
        from PySide6.QtWidgets import QMessageBox
        with patch.object(self.window,'_message',return_value=QMessageBox.StandardButton.Yes):
            QTest.mouseClick(self.window.execute_btn,Qt.MouseButton.LeftButton)
            self.assertTrue((folder/'film.mkv').exists()); self.assertFalse(source.exists())
            QTest.mouseClick(self.window.undo_btn,Qt.MouseButton.LeftButton)
        self.assertEqual(source.read_text(encoding='utf-8'),'original')
        self.assertFalse((folder/'film.mkv').exists())

    def test_settings_cancel_and_save_only_ui_preferences(self):
        self.window.path_edit.setText(str(Path(self.temp.name)/'chosen'))
        dialog=SettingsDialog(self.window); dialog.remember.setChecked(True); dialog.default_type.setCurrentText('视频'); dialog.reject()
        self.assertFalse(self.window.preferences.contains('remember_folder'))
        dialog=SettingsDialog(self.window); dialog.remember.setChecked(True); dialog.default_type.setCurrentText('视频'); dialog.accept()
        self.assertTrue(self.window.preferences.value('remember_folder',False,type=bool))
        self.assertEqual(self.window.preferences.value('default_type'),'视频')
        self.assertEqual(self.window.preferences.value('last_folder'),self.window.path_edit.text())

    def test_window_size_survives_close_and_next_launch(self):
        self.window.resize(740,470); self.app.processEvents()
        expected=self.window.size()
        self.window.close()
        self.assertEqual(self.window.preferences.value('window_size'),expected)
        reopened=MainWindow(self.window.preferences)
        try:
            reopened.show(); self.app.processEvents()
            self.assertEqual(reopened.size(),expected)
        finally:
            reopened.close(); reopened.deleteLater(); self.app.processEvents()

    def test_execute_uses_latest_rule_before_debounced_preview(self):
        folder=Path(self.temp.name)/'latest'; folder.mkdir()
        source=folder/'film.txt'; source.write_text('original',encoding='utf-8')
        self.window.executor=RenameExecutor(Path(self.temp.name)/'transaction')
        self.window.path_edit.setText(str(folder)); self.window.load_files()
        self.window.prefix_enabled.setChecked(True); self.window.prefix_text.setText('old_'); self.window.preview()
        self.window.prefix_text.setText('new_')
        from PySide6.QtWidgets import QMessageBox
        with patch.object(self.window,'_message',return_value=QMessageBox.StandardButton.Yes):
            self.window.execute_rename()
        self.assertTrue((folder/'new_film.txt').exists())
        self.assertFalse((folder/'old_film.txt').exists())

    def test_selection_and_sort_recalculate_numbering(self):
        folder=Path(self.temp.name)/'numbering'; folder.mkdir()
        for name in ('a.txt','b.txt'): (folder/name).write_text(name,encoding='utf-8')
        self.window.path_edit.setText(str(folder)); self.window.load_files()
        self.window.number_enabled.setChecked(True); self.window.preview()
        self.window.sort_by_column(3); self.window.sort_by_column(3); QTest.qWait(160)
        self.assertEqual([item.new_name for item in self.window.items],['0001_b.txt','0002_a.txt'])
        self.window.set_all_selected(False); QTest.qWait(160)
        self.assertTrue(all(item.status=='跳过' for item in self.window.items))

    def test_manual_resize_rescales_controls(self):
        self.window.resize(740,470); self.app.processEvents(); self.app.processEvents()
        expected=self.window.scale_for_available_size(self.window.width(),self.window.height())
        self.assertAlmostEqual(self.window._ui_scale,expected,places=3)

    def test_empty_source_path_does_not_scan_working_directory(self):
        self.window.path_edit.clear()
        from PySide6.QtWidgets import QMessageBox
        with patch.object(self.window,'_message',return_value=QMessageBox.StandardButton.No) as message:
            self.window.load_files()
        self.assertEqual(self.window.items,[])
        self.assertTrue(message.called)

    def test_saved_size_is_clamped_to_current_screen(self):
        self.window.preferences.setValue('window_size',QSize(99999,99999))
        reopened=MainWindow(self.window.preferences)
        try:
            reopened.show(); self.app.processEvents()
            available=reopened.screen().availableGeometry()
            self.assertLessEqual(reopened.width(),available.width())
            self.assertLessEqual(reopened.height(),available.height())
            self.assertTrue(available.contains(reopened.frameGeometry().center()))
        finally:
            reopened.close(); reopened.deleteLater(); self.app.processEvents()

    def test_maximized_window_restores_maximized_state_and_normal_size(self):
        self.window.resize(740,470); self.app.processEvents()
        expected=self.window.size()
        self.window.showMaximized(); self.app.processEvents(); self.window.close()
        self.assertEqual(self.window.preferences.value('window_size'),expected)
        reopened=MainWindow(self.window.preferences)
        try:
            reopened.show(); self.app.processEvents()
            self.assertTrue(reopened.isMaximized())
            reopened.showNormal(); self.app.processEvents()
            self.assertEqual(reopened.size(),expected)
        finally:
            reopened.close(); reopened.deleteLater(); self.app.processEvents()

    def test_subfolder_checkbox_reads_nested_files_and_execute_undo_keeps_directories(self):
        folder=Path(self.temp.name)/'tree'; nested=folder/'子目录'/'深层'; nested.mkdir(parents=True)
        sources=[folder/'film.mkv1',nested/'film.mkv1']
        for source in sources: source.write_text(str(source.parent),encoding='utf-8')
        (nested/'ignore.txt').write_text('skip',encoding='utf-8')
        self.window.executor=RenameExecutor(Path(self.temp.name)/'transaction')
        self.window.path_edit.setText(str(folder)); self.window.load_files()
        self.assertEqual([item.source_path for item in self.window.items],[sources[0]])
        QTest.mouseClick(self.window.include_subfolders,Qt.MouseButton.LeftButton)
        self.assertTrue(self.window.include_subfolders.isChecked())
        self.window.load_files()
        self.assertEqual({item.source_path for item in self.window.items},set(sources+[nested/'ignore.txt']))
        self.window.include_extension.setChecked(True); self.window.find_enabled.setChecked(True)
        self.window.find_text.setText('mkv1'); self.window.replace_text.setText('mkv')
        self.window.preview()
        self.assertEqual([item.status for item in self.window.items if item.original_name=='film.mkv1'],['可改名','可改名'])
        from PySide6.QtWidgets import QMessageBox
        with patch.object(self.window,'_message',return_value=QMessageBox.StandardButton.Yes):
            QTest.mouseClick(self.window.execute_btn,Qt.MouseButton.LeftButton)
            for source in sources:
                self.assertFalse(source.exists()); self.assertEqual(source.with_suffix('.mkv').read_text(encoding='utf-8'),str(source.parent))
            QTest.mouseClick(self.window.undo_btn,Qt.MouseButton.LeftButton)
        for source in sources:
            self.assertEqual(source.read_text(encoding='utf-8'),str(source.parent)); self.assertFalse(source.with_suffix('.mkv').exists())
        self.assertEqual((nested/'ignore.txt').read_text(encoding='utf-8'),'skip')

    def test_switch_focus_has_no_dark_outline_and_keeps_keyboard_control(self):
        switch=self.window.find_enabled
        switch.setChecked(False); switch.setFocus(); self.app.processEvents()
        image=switch.grab().toImage()
        edge=image.pixelColor(1,switch.height()//2)
        self.assertGreater(min(edge.red(),edge.green(),edge.blue()),150)
        QTest.keyClick(switch,Qt.Key.Key_Space)
        self.assertTrue(switch.isChecked())
        QTest.keyClick(switch,Qt.Key.Key_Space)
        self.assertFalse(switch.isChecked())

    def test_confirmation_has_readable_white_surface_and_safe_cancel(self):
        dialog=MessageDialog(self.window,'question','确认执行改名','将改名 251 个文件。\n\n任一步失败将尝试恢复整批原文件。')
        dialog.show(); self.app.processEvents()
        self.assertEqual(dialog.confirm_btn.text(),'确认')
        self.assertEqual(dialog.cancel_btn.text(),'取消')
        self.assertTrue(dialog.cancel_btn.isDefault())
        point=dialog.surface.grab().toImage().pixelColor(24,dialog.surface.height()-20)
        self.assertEqual((point.red(),point.green(),point.blue()),(255,255,255))
        QTest.keyClick(dialog,Qt.Key.Key_Escape)
        self.assertEqual(dialog.result(),0)

    def test_columns_fit_viewport_and_keep_ratios_with_scrollbar(self):
        self.window.table.setRowCount(100)
        self.app.processEvents(); self.window.table.fit_columns()
        widths=[self.window.table.columnWidth(i) for i in range(10)]
        self.assertEqual(sum(widths),self.window.table.viewport().width())
        for i in range(9):
            self.assertAlmostEqual(widths[i]/sum(widths),COLUMN_WEIGHTS[i]/sum(COLUMN_WEIGHTS),delta=0.002)
        self.assertTrue(self.window.table.mask().contains(self.window.table.rect().center()))
        self.assertFalse(self.window.table.mask().contains(self.window.table.rect().topLeft()))
        self.assertEqual(len(self.window.rule_cards),5)
        self.assertTrue(all(card.isVisible() for card in self.window.rule_cards))

if __name__=='__main__': unittest.main()
