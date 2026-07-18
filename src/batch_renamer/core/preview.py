from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from pathlib import Path

from .models import FileItem, RenamePlan, RuleSettings
from .rules import apply_rules
from .validator import validate_file_name, validate_target_path


def build_preview(items: list[FileItem], settings: RuleSettings) -> None:
    """计算预览并更新每一行状态；不触碰真实文件。"""

    selected_items = [item for item in items if item.selected]
    target_keys: list[str] = []

    for index, item in enumerate(selected_items):
        new_stem, new_suffix = apply_rules(item.stem, item.suffix, settings, index)
        item.new_name = f"{new_stem}{new_suffix}"
        item.target_path = item.folder / item.new_name
        item.status = "未变化" if item.new_name == item.original_name else "可改名"
        item.message = ""

        reason = validate_file_name(item.new_name) or validate_target_path(item.target_path)
        if reason:
            item.status = "错误"
            item.message = reason

        target_keys.append(normalize_path_key(item.target_path))

    conflicts = {key for key, count in Counter(target_keys).items() if count > 1}
    moving_source_keys = {
        normalize_path_key(item.source_path)
        for item in selected_items
        if item.target_path
        and item.status == "可改名"
        and normalize_path_key(item.target_path) != normalize_path_key(item.source_path)
    }
    existing_paths = _collect_existing_paths(item.folder for item in selected_items)

    for item in items:
        if not item.selected:
            item.new_name = item.original_name
            item.target_path = item.source_path
            item.status = "跳过"
            item.message = "未勾选"
            continue

        if item.target_path is None:
            item.status = "错误"
            item.message = "目标路径未生成"
            continue

        key = normalize_path_key(item.target_path)
        if key in conflicts:
            item.status = "冲突"
            item.message = "本批次内存在重名"
            continue

        source_key = normalize_path_key(item.source_path)
        if key in existing_paths and key != source_key and key not in moving_source_keys:
            item.status = "冲突"
            item.message = "目标文件已存在"


def build_plans(items: list[FileItem]) -> list[RenamePlan]:
    """生成可执行计划，只包含通过检查且确实变化的行。"""

    plans: list[RenamePlan] = []
    for item in items:
        if item.selected and item.status == "可改名" and item.target_path:
            plans.append(RenamePlan(source_path=item.source_path, target_path=item.target_path))
    return plans


def has_blocking_problem(items: list[FileItem]) -> bool:
    return any(item.status in {"冲突", "错误"} for item in items if item.selected)


def normalize_path_key(path: Path) -> str:
    """Windows 路径大小写不敏感，用小写绝对路径比较。"""

    return str(path.absolute()).replace("/", "\\").casefold()


def _collect_existing_paths(folders: Iterable[Path]) -> set[str]:
    """每个目录只枚举一次，避免大批量预览逐项执行磁盘 exists。"""

    unique_folders: dict[str, Path] = {}
    for folder in folders:
        unique_folders.setdefault(normalize_path_key(folder), folder)

    existing: set[str] = set()
    for folder in unique_folders.values():
        try:
            existing.update(normalize_path_key(path) for path in folder.iterdir())
        except OSError:
            continue
    return existing
