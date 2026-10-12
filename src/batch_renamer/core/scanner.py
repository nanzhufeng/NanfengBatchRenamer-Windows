from __future__ import annotations

import os
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


def scan_files(folder: Path, extension_filter: str = "", *, include_subfolders: bool = False) -> list[FileItem]:
    """读取普通文件；可包含子目录，但不沿目录链接跳出所选目录。"""

    if not folder.exists():
        raise FileNotFoundError(f"路径不存在：{folder}")
    if not folder.is_dir():
        raise NotADirectoryError(f"不是文件夹：{folder}")

    allowed = parse_extensions(extension_filter)
    items: list[FileItem] = []

    if include_subfolders:
        paths: list[Path] = []

        def report_error(error: OSError) -> None:
            raise OSError(f"无法读取子文件夹：{error.filename}（{error.strerror}）") from error

        for current, directories, filenames in os.walk(folder, followlinks=False, onerror=report_error):
            parent = Path(current)
            directories[:] = [name for name in directories
                              if not (parent / name).is_symlink() and not (parent / name).is_junction()]
            paths.extend(parent / name for name in filenames if not (parent / name).is_symlink())
    else:
        paths = list(folder.iterdir())

    for path in sorted(paths, key=lambda p: (str(p.relative_to(folder)).casefold(), str(p.relative_to(folder)))):
        if not path.is_file():
            continue
        if allowed and path.suffix.lower().lstrip(".") not in allowed:
            continue
        items.append(FileItem(source_path=path))

    return items

