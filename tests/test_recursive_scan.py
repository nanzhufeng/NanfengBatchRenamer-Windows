from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from batch_renamer.core.scanner import scan_files
from batch_renamer.core.models import RuleSettings
from batch_renamer.core.preview import build_preview, build_plans, has_blocking_problem


class RecursiveScanTests(unittest.TestCase):
    def test_recursive_filter_and_default_current_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); child=root/'素材'/'深层'; child.mkdir(parents=True)
            for path in (root/'root.MKV',child/'clip.mkv',child/'still.JPG',child/'note.txt'):
                path.write_text('sample',encoding='utf-8')
            self.assertEqual([item.source_path for item in scan_files(root)],[root/'root.MKV'])
            self.assertEqual([item.source_path for item in scan_files(root,'MKV',include_subfolders=True)],
                             [root/'root.MKV',child/'clip.mkv'])
            self.assertEqual([item.source_path for item in scan_files(root,'jpg',include_subfolders=True)],
                             [child/'still.JPG'])
            self.assertEqual(scan_files(root,'png',include_subfolders=True),[])

    def test_subtree_conflict_blocks_batch_and_unselected_file_is_skipped(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); child=root/'nested'; child.mkdir()
            for path in (root/'film.mkv1',child/'film.mkv1',child/'film.mkv'):
                path.write_text('original',encoding='utf-8')
            items=scan_files(root,'mkv1',include_subfolders=True)
            settings=RuleSettings(find_enabled=True,find_text='mkv1',replace_text='mkv',include_extension=True)
            build_preview(items,settings)
            self.assertTrue(has_blocking_problem(items))
            nested_item=next(item for item in items if item.folder==child)
            self.assertEqual(nested_item.status,'冲突')
            self.assertEqual(nested_item.message,'目标文件已存在')
            nested_item.selected=False
            build_preview(items,settings)
            self.assertFalse(has_blocking_problem(items))
            self.assertEqual(nested_item.status,'跳过')
            plans=build_plans(items)
            self.assertEqual([(plan.source_path,plan.target_path) for plan in plans],
                             [(root/'film.mkv1',root/'film.mkv')])


if __name__=='__main__': unittest.main()
