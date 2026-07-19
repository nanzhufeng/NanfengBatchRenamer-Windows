from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = PROJECT_ROOT / "build_assets" / "app_icon_source.png"
PNG_PATH = PROJECT_ROOT / "build_assets" / "app_icon.png"
ICO_PATH = PROJECT_ROOT / "build_assets" / "app_icon.ico"
ICO_SIZES = (16, 20, 24, 32, 40, 48, 64, 96, 128, 256)
CORNER_RADIUS_RATIO = 0.19
MASK_SCALE = 4


def neutralize_warm_whites(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    pixels = list(rgba.get_flattened_data())
    result: list[tuple[int, int, int, int]] = []
    for red, green, blue, alpha in pixels:
        if max(red, green, blue) >= 95 and red >= green >= blue and red - blue <= 45:
            neutral = (54 * red + 183 * green + 19 * blue + 128) // 256
            result.append((neutral, neutral, neutral, alpha))
        else:
            result.append((red, green, blue, alpha))
    rgba.putdata(result)
    return rgba


def rounded_alpha_mask(size: tuple[int, int]) -> Image.Image:
    width, height = size
    scaled_size = (width * MASK_SCALE, height * MASK_SCALE)
    radius = round(min(width, height) * CORNER_RADIUS_RATIO * MASK_SCALE)
    mask = Image.new("L", scaled_size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle(
        (0, 0, scaled_size[0] - 1, scaled_size[1] - 1),
        radius=radius,
        fill=255,
    )
    return mask.resize(size, Image.Resampling.LANCZOS)


def main() -> int:
    if not SOURCE_PATH.is_file():
        raise SystemExit(f"缺少图标原图：{SOURCE_PATH}")

    with Image.open(SOURCE_PATH) as source:
        icon = neutralize_warm_whites(source)
    if icon.width != icon.height:
        raise SystemExit(f"图标原图必须为正方形：{icon.width}x{icon.height}")

    icon.putalpha(rounded_alpha_mask(icon.size))
    icon.save(PNG_PATH, format="PNG", optimize=True)
    icon.save(
        ICO_PATH,
        format="ICO",
        sizes=[(size, size) for size in ICO_SIZES],
        bitmap_format="png",
    )
    print(
        f"已生成 {PNG_PATH.name} 与 {ICO_PATH.name}："
        f"圆角半径 {CORNER_RADIUS_RATIO:.0%}，ICO 尺寸 {list(ICO_SIZES)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
