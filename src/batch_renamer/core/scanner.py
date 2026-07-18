from __future__ import annotations

from pathlib import Path

from .models import FileItem


def parse_extensions(text: str) -> set[str]:
    """把 jpg,png 这类输入整理成后缀集合。"""

    result: set[str] = set()
    for part in text.replace(";", ",").split(","):
        cleaned = part.strip().lower().lstrip(".")
        if cleaned:
            result.add(cleaned)
    return result


def scan_files(folder: Path, extension_filter: str = "") -> list[FileItem]:
    """读取当前目录文件；第一版不递归、不处理文件夹。"""

    if not folder.exists():
        raise FileNotFoundError(f"路径不存在：{folder}")
    if not folder.is_dir():
        raise NotADirectoryError(f"不是文件夹：{folder}")

    allowed = parse_extensions(extension_filter)
    items: list[FileItem] = []

    for path in sorted(folder.iterdir(), key=lambda p: p.name.lower()):
        if not path.is_file():
            continue
        if allowed and path.suffix.lower().lstrip(".") not in allowed:
            continue
        items.append(FileItem(source_path=path))

    return items

