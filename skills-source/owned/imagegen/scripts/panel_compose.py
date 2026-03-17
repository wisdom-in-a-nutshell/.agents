#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Bradley Hand Bold.ttf",
    "/System/Library/Fonts/Noteworthy.ttc",
    "/System/Library/Fonts/MarkerFelt.ttc",
    "/System/Library/Fonts/Supplemental/ChalkboardSE.ttc",
    "/System/Library/Fonts/Supplemental/Chalkboard.ttc",
]


def load_font(size: int, explicit_path: str | None = None) -> tuple[ImageFont.FreeTypeFont | ImageFont.ImageFont, str]:
    candidates = [explicit_path] if explicit_path else []
    candidates.extend(FONT_CANDIDATES)
    for path in candidates:
        if not path:
            continue
        p = Path(path)
        if p.exists():
            try:
                return ImageFont.truetype(str(p), size=size), str(p)
            except Exception:
                continue
    return ImageFont.load_default(), "PIL default"


def text_size(draw: ImageDraw.ImageDraw, text: str, font) -> tuple[int, int]:
    if not text:
        return 0, 0
    l, t, r, b = draw.multiline_textbbox((0, 0), text, font=font, spacing=6)
    return r - l, b - t


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> str:
    if not text:
        return ""
    paragraphs = text.splitlines() or [text]
    out_lines: list[str] = []
    for paragraph in paragraphs:
        if not paragraph.strip():
            out_lines.append("")
            continue
        words = paragraph.split()
        current = words[0]
        for word in words[1:]:
            candidate = f"{current} {word}"
            width, _ = text_size(draw, candidate, font)
            if width <= max_width:
                current = candidate
            else:
                out_lines.append(current)
                current = word
        out_lines.append(current)
    return "\n".join(out_lines)


def line_height(draw: ImageDraw.ImageDraw, font, spacing: int = 0) -> int:
    l, t, r, b = draw.textbbox((0, 0), "Ag", font=font)
    return (b - t) + spacing


def phrase_boxes(draw: ImageDraw.ImageDraw, wrapped_text: str, phrases: list[str], font, x: int, y: int, spacing: int) -> list[tuple[float, float, float, float]]:
    if not wrapped_text or not phrases:
        return []
    lines = wrapped_text.splitlines()
    current_y = y
    h = line_height(draw, font, spacing=0)
    results: list[tuple[float, float, float, float]] = []
    for line in lines:
        lower_line = line.lower()
        for phrase in phrases:
            idx = lower_line.find(phrase.lower())
            if idx >= 0:
                prefix = line[:idx]
                matched = line[idx : idx + len(phrase)]
                x1 = x + draw.textlength(prefix, font=font)
                x2 = x1 + draw.textlength(matched, font=font)
                y1 = current_y + max(2, int(h * 0.18))
                y2 = current_y + h - max(2, int(h * 0.08))
                results.append((x1, y1, x2, y2))
        current_y += h + spacing
    return results


def draw_marker_swatch(base: Image.Image, box: tuple[float, float, float, float], fill=(180, 180, 180, 90)) -> None:
    overlay = Image.new("RGBA", base.size, (255, 255, 255, 0))
    od = ImageDraw.Draw(overlay)
    x1, y1, x2, y2 = box
    pad_x = 10
    h = y2 - y1
    top = y1 + h * 0.18
    bottom = y2 - h * 0.08
    points = [
        (x1 - pad_x, top + 2),
        (x2 + pad_x * 0.6, top - 2),
        (x2 + pad_x, bottom + 1),
        (x1 - pad_x * 0.6, bottom + 3),
    ]
    od.polygon(points, fill=fill)
    # second pass for a hand-drawn layered feel
    points2 = [
        (x1 - pad_x * 0.7, top + 5),
        (x2 + pad_x * 0.4, top + 1),
        (x2 + pad_x * 0.7, bottom + 4),
        (x1 - pad_x * 0.3, bottom + 6),
    ]
    od.polygon(points2, fill=(170, 170, 170, 55))
    base.alpha_composite(overlay)


def draw_rough_underline(base: Image.Image, box: tuple[float, float, float, float], fill=(80, 80, 80, 170), width: int = 3, pad: int = 2) -> None:
    overlay = Image.new("RGBA", base.size, (255, 255, 255, 0))
    od = ImageDraw.Draw(overlay)
    x1, y1, x2, y2 = box
    underline_y = y2 + 2
    od.line((x1 - pad, underline_y, x2 + pad * 2, underline_y - 1), fill=fill, width=width)
    # slightly offset second pass for hand-drawn feel
    secondary = fill[:3] + (max(60, int(fill[3] * 0.65)),)
    od.line((x1 - max(1, pad // 2), underline_y + max(3, width // 2), x2 + pad, underline_y + max(1, width // 3)), fill=secondary, width=max(1, width - 1))
    base.alpha_composite(overlay)


def parse_rgba(value: str, default: tuple[int, int, int, int]) -> tuple[int, int, int, int]:
    if not value:
        return default
    parts = [p.strip() for p in value.split(",")]
    try:
        nums = [int(p) for p in parts]
    except Exception:
        return default
    if len(nums) == 3:
        nums.append(default[3])
    if len(nums) != 4:
        return default
    return tuple(max(0, min(255, n)) for n in nums)  # type: ignore[return-value]


def compose_panel(
    image_path: Path,
    out_path: Path,
    kicker: str = "",
    title: str = "",
    subtitle: str = "",
    brand: str = "",
    footer: str = "",
    bottom_note: str = "",
    font_path: str | None = None,
    title_size: int = 62,
    subtitle_size: int = 34,
    kicker_size: int = 34,
    footer_size: int = 26,
    highlight_title: str = "",
    highlight_subtitle: str = "",
    highlight_style: str = "swash",
    highlight_color: tuple[int, int, int, int] = (175, 175, 175, 90),
    highlight_width: int = 3,
    highlight_pad: int = 2,
    title_highlight_color: tuple[int, int, int, int] | None = None,
    subtitle_highlight_color: tuple[int, int, int, int] | None = None,
    crop_px: int = 0,
    border_px: int = 4,
    outer_pad_x: int = 44,
    outer_pad_y: int = 30,
    band_gap: int = 18,
    divider_gap: int = 22,
) -> dict:
    base = Image.open(image_path).convert("RGBA")
    if crop_px > 0:
        w0, h0 = base.size
        inset = min(crop_px, max(0, (w0 // 2) - 1), max(0, (h0 // 2) - 1))
        cropped = base.crop((inset, inset, w0 - inset, h0 - inset))
        base = cropped.resize((w0, h0), Image.Resampling.LANCZOS)
    width, height = base.size

    canvas = Image.new("RGBA", (width, height + 320), (255, 255, 255, 255))
    draw = ImageDraw.Draw(canvas)

    kicker_font, kicker_name = load_font(kicker_size, font_path)
    title_font, title_name = load_font(title_size, font_path)
    subtitle_font, subtitle_name = load_font(subtitle_size, font_path)
    brand_font, brand_name = load_font(28, font_path)
    footer_font, footer_name = load_font(footer_size, font_path)
    note_font, note_name = load_font(max(footer_size + 12, 38), font_path)

    text_width_max = width - outer_pad_x * 2
    if brand:
        brand_w, _ = text_size(draw, brand, brand_font)
        text_width_max = max(300, width - outer_pad_x * 3 - brand_w)

    kicker_wrapped = wrap_text(draw, kicker, kicker_font, text_width_max) if kicker else ""
    title_wrapped = wrap_text(draw, title, title_font, text_width_max)
    subtitle_wrapped = wrap_text(draw, subtitle, subtitle_font, text_width_max) if subtitle else ""

    y = outer_pad_y
    if kicker_wrapped:
        draw.multiline_text((outer_pad_x, y), kicker_wrapped, font=kicker_font, fill=(0, 0, 0), spacing=6)
        _, kicker_h = text_size(draw, kicker_wrapped, kicker_font)
        y += kicker_h + 8

    title_phrases = [p.strip() for p in highlight_title.split("||") if p.strip()]
    title_boxes = phrase_boxes(draw, title_wrapped, title_phrases, title_font, outer_pad_x, y, spacing=8) if title_phrases else []
    for box in title_boxes:
        if highlight_style == "underline":
            draw_rough_underline(canvas, box, fill=(title_highlight_color or highlight_color), width=highlight_width, pad=highlight_pad)
        else:
            draw_marker_swatch(canvas, box, fill=(title_highlight_color or highlight_color))
    draw.multiline_text((outer_pad_x, y), title_wrapped, font=title_font, fill=(0, 0, 0), spacing=8)
    _, title_h = text_size(draw, title_wrapped, title_font)
    y += title_h

    if subtitle_wrapped:
        y += band_gap
        subtitle_phrases = [p.strip() for p in highlight_subtitle.split("||") if p.strip()]
        subtitle_boxes = phrase_boxes(draw, subtitle_wrapped, subtitle_phrases, subtitle_font, outer_pad_x, y, spacing=6) if subtitle_phrases else []
        for box in subtitle_boxes:
            if highlight_style == "underline":
                draw_rough_underline(canvas, box, fill=(subtitle_highlight_color or highlight_color), width=max(2, highlight_width - 1), pad=highlight_pad)
            else:
                draw_marker_swatch(canvas, box, fill=(subtitle_highlight_color or highlight_color))
        draw.multiline_text((outer_pad_x, y), subtitle_wrapped, font=subtitle_font, fill=(0, 0, 0), spacing=6)
        _, subtitle_h = text_size(draw, subtitle_wrapped, subtitle_font)
        y += subtitle_h

    if brand:
        brand_w, brand_h = text_size(draw, brand, brand_font)
        draw.multiline_text((width - outer_pad_x - brand_w, outer_pad_y + 4), brand, font=brand_font, fill=(0, 0, 0), align="right")
        y = max(y, outer_pad_y + brand_h)

    y += divider_gap
    draw.line((outer_pad_x, y, width - outer_pad_x, y), fill=(0, 0, 0), width=2)
    y += divider_gap

    footer_h = 0
    note_h = 0
    note_wrapped = ""
    note_block_h = 0
    if bottom_note:
        note_wrapped = wrap_text(draw, bottom_note, note_font, width - outer_pad_x * 2)
        _, note_h = text_size(draw, note_wrapped, note_font)
        note_block_h = note_h + 28
    if footer:
        _, footer_h = text_size(draw, footer, footer_font)
    final_h = y + height + outer_pad_y + note_block_h + (footer_h + 12 if footer else 0)
    final = Image.new("RGBA", (width, final_h), (255, 255, 255, 255))
    final.paste(canvas.crop((0, 0, width, y)), (0, 0))
    final.paste(base, (0, y), base)

    final_draw = ImageDraw.Draw(final)
    if bottom_note:
        note_x = outer_pad_x + max(0, ((width - outer_pad_x * 2) - text_size(final_draw, note_wrapped, note_font)[0]) // 2)
        note_y = y + height + 18
        bbox = final_draw.multiline_textbbox((note_x, note_y), note_wrapped, font=note_font, spacing=4)
        pad_x, pad_y = 10, 6
        final_draw.rounded_rectangle((bbox[0]-pad_x, bbox[1]-pad_y, bbox[2]+pad_x, bbox[3]+pad_y), radius=10, fill=(255,255,255,215))
        final_draw.multiline_text((note_x, note_y), note_wrapped, font=note_font, fill=(0,0,0), spacing=4, align="left")
    if footer:
        footer_w, footer_h = text_size(final_draw, footer, footer_font)
        footer_x = width - outer_pad_x - footer_w
        footer_y = final_h - outer_pad_y - footer_h
        final_draw.multiline_text((footer_x, footer_y), footer, font=footer_font, fill=(0, 0, 0), align="right")
    if border_px > 0:
        for i in range(border_px):
            final_draw.rectangle((i, i, width - 1 - i, final_h - 1 - i), outline=(0, 0, 0), width=1)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    final.save(out_path)
    return {
        "output": str(out_path),
        "font_title": title_name,
        "font_subtitle": subtitle_name,
        "font_brand": brand_name,
        "font_footer": footer_name,
        "font_note": note_name,
        "size": f"{width}x{final_h}",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compose an existing image into a finished panel with optional top text, footer, emphasis, and bottom note.")
    parser.add_argument("--image", required=True, help="Input image path")
    parser.add_argument("--out", required=True, help="Output image path")
    parser.add_argument("--kicker", default="", help="Small top label")
    parser.add_argument("--title", required=True, help="Main title")
    parser.add_argument("--subtitle", default="", help="Optional subtitle")
    parser.add_argument("--brand", default="", help="Optional right-aligned brand label")
    parser.add_argument("--footer", default="", help="Optional bottom-right footer label")
    parser.add_argument("--bottom-note", default="", help="Optional centered bottom note or quoted inner monologue")
    parser.add_argument("--font", default=None, help="Optional explicit font path")
    parser.add_argument("--title-size", type=int, default=62, help="Headline font size")
    parser.add_argument("--subtitle-size", type=int, default=34, help="Subtitle font size")
    parser.add_argument("--kicker-size", type=int, default=34, help="Kicker font size")
    parser.add_argument("--footer-size", type=int, default=26, help="Footer font size")
    parser.add_argument("--band-gap", type=int, default=18, help="Gap between title and subtitle")
    parser.add_argument("--divider-gap", type=int, default=22, help="Gap around the divider line")
    parser.add_argument("--highlight-title", default="", help="Phrase to emphasize in the title")
    parser.add_argument("--highlight-subtitle", default="", help="Phrase to emphasize in the subtitle")
    parser.add_argument("--highlight-style", choices=["swash", "underline"], default="swash", help="How to emphasize the phrase")
    parser.add_argument("--highlight-color", default="", help="RGBA like '180,180,180,120' or '180,40,40,180'")
    parser.add_argument("--title-highlight-color", default="", help="Optional RGBA override for title highlights")
    parser.add_argument("--subtitle-highlight-color", default="", help="Optional RGBA override for subtitle highlights")
    parser.add_argument("--highlight-width", type=int, default=3, help="Underline width when using underline emphasis")
    parser.add_argument("--highlight-pad", type=int, default=2, help="Extra width padding for underline emphasis")
    parser.add_argument("--crop-px", type=int, default=0, help="Crop inward by this many pixels on each side before placing the image, then scale back to original size")
    args = parser.parse_args()

    info = compose_panel(
        image_path=Path(args.image),
        out_path=Path(args.out),
        kicker=args.kicker,
        title=args.title,
        subtitle=args.subtitle,
        brand=args.brand,
        footer=args.footer,
        bottom_note=args.bottom_note,
        font_path=args.font,
        title_size=args.title_size,
        subtitle_size=args.subtitle_size,
        kicker_size=args.kicker_size,
        footer_size=args.footer_size,
        band_gap=args.band_gap,
        divider_gap=args.divider_gap,
        highlight_title=args.highlight_title,
        highlight_subtitle=args.highlight_subtitle,
        highlight_style=args.highlight_style,
        highlight_color=parse_rgba(args.highlight_color, (175, 175, 175, 90) if args.highlight_style == "swash" else (80, 80, 80, 170)),
        highlight_width=args.highlight_width,
        highlight_pad=args.highlight_pad,
        title_highlight_color=parse_rgba(args.title_highlight_color, (0, 0, 0, 0)) if args.title_highlight_color else None,
        subtitle_highlight_color=parse_rgba(args.subtitle_highlight_color, (0, 0, 0, 0)) if args.subtitle_highlight_color else None,
        crop_px=args.crop_px,
    )
    print(f"output: {info['output']}")
    print(f"size: {info['size']}")
    print(f"font: {info['font_title']}")


if __name__ == "__main__":
    main()
