"""Capture the actual source application with isolated demonstration files."""
import sys
import tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QSettings
from batch_renamer.app import MainWindow, AboutDialog
from batch_renamer.ui.workbench import SettingsDialog

root=Path(__file__).resolve().parents[1]
out=root/'artifacts'/'workbench-acceptance'; out.mkdir(exist_ok=True)
app=QApplication([])
with tempfile.TemporaryDirectory() as temp:
    folder=Path(temp)
    for name in ('旅行记录01.mkv1','海边日记02.mkv1','城市夜景03.mp4','山间晨光04.ts','夏日片段05.mov','星光漫游06.mkv','归途记忆07.mp4'):
        (folder/name).write_text('demo',encoding='utf-8')
    w=MainWindow(QSettings(str(folder/'preferences.ini'),QSettings.Format.IniFormat)); w.show(); app.processEvents(); w.apply_ui_scale(1); w.resize(1820,1130); app.processEvents()
    w.path_edit.setText(str(folder)); w.set_file_type('全部'); w.load_files()
    w.include_extension.setChecked(True); w.find_enabled.setChecked(True); w.find_text.setText('mkv1'); w.replace_text.setText('mkv'); w.preview()
    # Display a sanitized path without reading it; the input/files above remain isolated.
    w.path_edit.setText(r'D:\影视素材')
    for item in w.items: item.source_path=Path(r'D:\影视素材')/item.original_name
    w.refresh_table(); app.processEvents(); w.grab().save(str(out/'main-window.png'))
    for kind,dialog in (('settings',SettingsDialog(w)),('about',AboutDialog(w))):
        dialog.show(); app.processEvents(); dialog.grab().save(str(out/f'{kind}.png')); dialog.close()
    w.close()
print(out)
