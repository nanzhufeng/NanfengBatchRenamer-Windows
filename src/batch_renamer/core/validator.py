from __future__ import annotations

import os
from pathlib import Path


INVALID_CHARS = set('<>:"/\\|?*')
RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def validate_file_name(file_name: str) -> str:
    """返回空字符串表示通过；否则返回用户能看懂的原因。"""

    if not file_name:
        return "文件名为空"
    if file_name.strip() != file_name:
        return "文件名前后不能有空格"
    if file_name.endswith("."):
        return "文件名不能以点结尾"
    bad = sorted(ch for ch in file_name if ch in INVALID_CHARS)
    if bad:
        return f"包含 Windows 不允许的字符：{' '.join(bad)}"

    stem = Path(file_name).stem.upper()
    if stem in RESERVED_NAMES:
        return f"Windows 保留名称不可用：{stem}"
    return ""


def validate_target_path(target_path: Path) -> str:
    """检查目标路径基础合法性。"""

    target_text = str(target_path)
    if len(target_text) >= 240:
        return "路径过长，可能导致 Windows 改名失败"
    try:
        os.fspath(target_path)
    except TypeError:
        return "目标路径无效"
    return ""

