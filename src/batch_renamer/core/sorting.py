from __future__ import annotations

import re


def natural_sort_key(text: str) -> tuple[object, ...]:
    """按文字片段和整数片段排序，保证 1、2、10、120 的数值顺序。"""

    parts: list[object] = []
    for part in re.split(r"(\d+)", text):
        if not part:
            continue
        if part.isdigit():
            parts.append((1, int(part)))
        else:
            parts.append((0, part.casefold()))
    return tuple(parts)
