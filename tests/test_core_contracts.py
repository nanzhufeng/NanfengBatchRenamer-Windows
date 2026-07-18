from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from batch_renamer.core.executor import RenameExecutor
from batch_renamer.core.models import FileItem, RenamePlan, RuleSettings
from batch_renamer.core.preview import build_plans, build_preview
from batch_renamer.core.rules import apply_rules
from batch_renamer.core.scanner import scan_files


class RuleContractTests(unittest.TestCase):
    def test_combined_rules_follow_the_documented_order(self) -> None:
        settings = RuleSettings(
            find_enabled=True,
            find_text="clip",
            replace_text="shot",
            trim_enabled=True,
            trim_right=3,
            prefix_enabled=True,
            prefix_text="P_",
            suffix_enabled=True,
            suffix_text="_S",
            insert_enabled=True,
            insert_text="X",
            insert_position=2,
            number_enabled=True,
            number_start=10,
            number_step=5,
            number_digits=4,
            number_position="后缀",
            number_separator="-",
            extension_mode="统一小写",
        )

        stem, suffix = apply_rules("clip001", ".MP4", settings, index=2)

        self.assertEqual(stem, "P_Xshot_S-0020")
        self.assertEqual(suffix, ".mp4")

    def test_middle_delete_uses_one_based_position_and_quantity(self) -> None:
        settings = RuleSettings(trim_enabled=True, trim_start=2, trim_count=3)

        stem, _suffix = apply_rules("abcdef", ".txt", settings, index=0)

        self.assertEqual(stem, "aef")

    def test_case_insensitive_replace_preserves_unmatched_text(self) -> None:
        settings = RuleSettings(
            find_enabled=True,
            find_text="shot",
            replace_text="plate",
            find_case_sensitive=False,
        )

        stem, _suffix = apply_rules("SHOT_A_shot", ".exr", settings, index=0)

        self.assertEqual(stem, "plate_A_plate")


class ScannerAndPreviewContractTests(unittest.TestCase):
    def test_empty_filter_means_true_all_file_formats(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for name in ("a.jpg", "b.custom", "c.MP4"):
                (root / name).write_text(name, encoding="utf-8")
            (root / "folder.jpg").mkdir()

            all_names = {item.original_name for item in scan_files(root, "")}
            selected_names = {item.original_name for item in scan_files(root, "jpg,mp4")}

        self.assertEqual(all_names, {"a.jpg", "b.custom", "c.MP4"})
        self.assertEqual(selected_names, {"a.jpg", "c.MP4"})

    def test_preview_blocks_batch_conflicts_and_skips_unselected_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = root / "a1.txt"
            second = root / "a2.txt"
            skipped = root / "keep.txt"
            for path in (first, second, skipped):
                path.write_text(path.name, encoding="utf-8")

            items = [FileItem(first), FileItem(second), FileItem(skipped, selected=False)]
            build_preview(items, RuleSettings(trim_enabled=True, trim_right=1))

            self.assertEqual(items[0].status, "冲突")
            self.assertEqual(items[1].status, "冲突")
            self.assertEqual(items[2].status, "跳过")
            self.assertEqual(build_plans(items), [])

    def test_preview_blocks_existing_target_and_invalid_windows_name(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "a1.txt"
            source.write_text("source", encoding="utf-8")
            (root / "a.txt").write_text("occupied", encoding="utf-8")

            existing_item = FileItem(source)
            build_preview([existing_item], RuleSettings(trim_enabled=True, trim_right=1))
            self.assertEqual(existing_item.status, "冲突")

            invalid_item = FileItem(source)
            build_preview([invalid_item], RuleSettings(prefix_enabled=True, prefix_text="<"))
            self.assertEqual(invalid_item.status, "错误")
            self.assertIn("Windows 不允许", invalid_item.message)

class ExecutorIntegrationTests(unittest.TestCase):
    def test_execute_and_single_level_undo_use_only_temporary_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_a = root / "a.txt"
            source_b = root / "b.txt"
            target_a = root / "renamed_a.txt"
            target_b = root / "renamed_b.txt"
            source_a.write_text("A", encoding="utf-8")
            source_b.write_text("B", encoding="utf-8")
            executor = RenameExecutor(root)

            results = executor.execute(
                [
                    RenamePlan(source_a, target_a),
                    RenamePlan(source_b, target_b),
                ]
            )

            self.assertTrue(all(result.ok for result in results))
            self.assertFalse(source_a.exists())
            self.assertFalse(source_b.exists())
            self.assertTrue(target_a.exists())
            self.assertTrue(target_b.exists())
            self.assertTrue(executor.undo_file.exists())

            undo_results = executor.undo_last()

            self.assertTrue(all(result.ok for result in undo_results))
            self.assertTrue(source_a.exists())
            self.assertTrue(source_b.exists())
            self.assertFalse(target_a.exists())
            self.assertFalse(target_b.exists())

    def test_case_only_rename_uses_transaction_staging(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "clip.mp4"
            target = root / "CLIP.MP4"
            source.write_text("video", encoding="utf-8")
            moves: list[tuple[Path, Path]] = []

            def tracked_rename(current: Path, next_path: Path) -> None:
                moves.append((current, next_path))
                current.rename(next_path)

            executor = RenameExecutor(root, tracked_rename)
            results = executor.execute([RenamePlan(source, target)])

            self.assertTrue(all(result.ok for result in results))
            self.assertEqual(len(moves), 2)
            self.assertIn(".nfbatch-", moves[0][1].name)
            self.assertTrue(target.exists())
            self.assertEqual(target.read_text(encoding="utf-8"), "video")

    def test_transaction_supports_name_swaps_and_transactional_undo(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = root / "a.txt"
            second = root / "b.txt"
            first.write_text("A", encoding="utf-8")
            second.write_text("B", encoding="utf-8")
            executor = RenameExecutor(root)

            results = executor.execute([RenamePlan(first, second), RenamePlan(second, first)])

            self.assertTrue(all(result.ok for result in results))
            self.assertEqual(first.read_text(encoding="utf-8"), "B")
            self.assertEqual(second.read_text(encoding="utf-8"), "A")

            undo_results = executor.undo_last()

            self.assertTrue(all(result.ok for result in undo_results))
            self.assertEqual(first.read_text(encoding="utf-8"), "A")
            self.assertEqual(second.read_text(encoding="utf-8"), "B")

    def test_commit_failure_rolls_back_whole_batch_and_preserves_previous_undo(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source_a = root / "a.txt"
            source_b = root / "b.txt"
            target_a = root / "renamed_a.txt"
            target_b = root / "renamed_b.txt"
            source_a.write_text("A", encoding="utf-8")
            source_b.write_text("B", encoding="utf-8")
            calls = 0

            def fail_once_on_second_commit(current: Path, next_path: Path) -> None:
                nonlocal calls
                calls += 1
                if calls == 4:
                    raise OSError("模拟最终阶段失败")
                current.rename(next_path)

            executor = RenameExecutor(root, fail_once_on_second_commit)
            previous_undo = '{"items": [{"source": "old", "target": "new"}]}'
            executor.undo_file.write_text(previous_undo, encoding="utf-8")

            results = executor.execute(
                [RenamePlan(source_a, target_a), RenamePlan(source_b, target_b)]
            )

            self.assertTrue(all(not result.ok for result in results))
            self.assertTrue(all("已恢复全部原文件" in result.message for result in results))
            self.assertEqual(source_a.read_text(encoding="utf-8"), "A")
            self.assertEqual(source_b.read_text(encoding="utf-8"), "B")
            self.assertFalse(target_a.exists())
            self.assertFalse(target_b.exists())
            self.assertEqual(executor.undo_file.read_text(encoding="utf-8"), previous_undo)
            self.assertIsNone(executor.last_recovery_file)

    def test_incomplete_rollback_writes_recovery_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "a.txt"
            target = root / "renamed_a.txt"
            source.write_text("A", encoding="utf-8")
            calls = 0

            def fail_commit_and_rollback(current: Path, next_path: Path) -> None:
                nonlocal calls
                calls += 1
                if calls in {2, 3}:
                    raise OSError("模拟提交或回滚失败")
                current.rename(next_path)

            executor = RenameExecutor(root, fail_commit_and_rollback)
            results = executor.execute([RenamePlan(source, target)])

            self.assertFalse(results[0].ok)
            self.assertIn("恢复清单", results[0].message)
            self.assertIsNotNone(executor.last_recovery_file)
            assert executor.last_recovery_file is not None
            self.assertTrue(executor.last_recovery_file.exists())
            manifest = executor.last_recovery_file.read_text(encoding="utf-8")
            self.assertIn('"restored": false', manifest)


if __name__ == "__main__":
    unittest.main()
