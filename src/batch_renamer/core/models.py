from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


RenameStatus = Literal["未预览", "可改名", "未变化", "冲突", "错误", "跳过", "已完成", "已撤销", "失败"]


@dataclass
class FileItem:
    """表格中的一行文件数据。"""

    source_path: Path
    selected: bool = True
    status: RenameStatus = "未预览"
    new_name: str = ""
    target_path: Path | None = None
    message: str = ""

    @property
    def folder(self) -> Path:
        return self.source_path.parent

    @property
    def original_name(self) -> str:
        return self.source_path.name

    @property
    def stem(self) -> str:
        return self.source_path.stem

    @property
    def suffix(self) -> str:
        return self.source_path.suffix


@dataclass
class RenamePlan:
    """一次执行改名前的最终计划。"""

    source_path: Path
    target_path: Path


@dataclass
class RenameResult:
    """执行结果，用于更新界面和写日志。"""

    source_path: Path
    target_path: Path
    ok: bool
    message: str


@dataclass
class RuleSettings:
    """第一版可用的规则设置。"""

    find_enabled: bool = False
    find_text: str = ""
    replace_text: str = ""
    find_case_sensitive: bool = False

    prefix_enabled: bool = False
    prefix_text: str = ""
    suffix_enabled: bool = False
    suffix_text: str = ""
    insert_enabled: bool = False
    insert_text: str = ""
    insert_position: int = 0

    trim_enabled: bool = False
    trim_left: int = 0
    trim_right: int = 0
    trim_start: int = 0
    trim_count: int = 0

    number_enabled: bool = False
    number_start: int = 1
    number_step: int = 1
    number_digits: int = 4
    number_position: Literal["前缀", "后缀"] = "前缀"
    number_separator: str = "_"

    extension_mode: Literal["保持不变", "统一小写", "统一大写"] = "保持不变"

    notes: list[str] = field(default_factory=list)
