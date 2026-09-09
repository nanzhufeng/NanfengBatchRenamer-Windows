from __future__ import annotations

from pathlib import Path

from .models import RuleSettings


def apply_rules(stem: str, suffix: str, settings: RuleSettings, index: int) -> tuple[str, str]:
    """按固定规则链生成新文件名主体和扩展名。"""

    name = f"{stem}{suffix}" if settings.include_extension else stem

    if settings.find_enabled and settings.find_text:
        if settings.find_case_sensitive:
            name = name.replace(settings.find_text, settings.replace_text)
        else:
            name = replace_ignore_case(name, settings.find_text, settings.replace_text)

    if settings.trim_enabled:
        left = max(settings.trim_left, 0)
        right = max(settings.trim_right, 0)
        trim_start = max(settings.trim_start, 0)
        trim_count = max(settings.trim_count, 0)
        if left:
            name = name[left:]
        if right:
            name = name[:-right] if right < len(name) else ""
        if trim_start and trim_count:
            start = min(trim_start - 1, len(name))
            end = min(start + trim_count, len(name))
            name = f"{name[:start]}{name[end:]}"

    if settings.prefix_enabled and settings.prefix_text:
        name = f"{settings.prefix_text}{name}"

    if settings.suffix_enabled and settings.suffix_text:
        name = f"{name}{settings.suffix_text}"

    if settings.insert_enabled and settings.insert_text:
        position = min(max(settings.insert_position, 0), len(name))
        name = f"{name[:position]}{settings.insert_text}{name[position:]}"

    if settings.number_enabled:
        number = settings.number_start + index * settings.number_step
        number_text = str(number).zfill(max(settings.number_digits, 1))
        sep = settings.number_separator
        if settings.number_position == "前缀":
            name = f"{number_text}{sep}{name}" if sep else f"{number_text}{name}"
        else:
            name = f"{name}{sep}{number_text}" if sep else f"{name}{number_text}"

    new_suffix = suffix
    if settings.include_extension:
        new_suffix = Path(name).suffix
        if new_suffix:
            name = name[:-len(new_suffix)]
    if settings.extension_mode == "统一小写":
        new_suffix = new_suffix.lower()
    elif settings.extension_mode == "统一大写":
        new_suffix = new_suffix.upper()

    return name, new_suffix


def replace_ignore_case(text: str, old: str, new: str) -> str:
    """大小写不敏感替换，避免引入正则。"""

    if not old:
        return text

    lowered_text = text.lower()
    lowered_old = old.lower()
    result: list[str] = []
    start = 0

    while True:
        pos = lowered_text.find(lowered_old, start)
        if pos == -1:
            result.append(text[start:])
            break
        result.append(text[start:pos])
        result.append(new)
        start = pos + len(old)

    return "".join(result)
