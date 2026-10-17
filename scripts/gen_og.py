#!/usr/bin/env python3
"""Generate Open Graph PNGs for the resume site.

Default invocation produces og-image.png with the canonical resume header.
Per-case invocation produces a card tailored to a single case study so that
sharing /case/<slug>/ on Slack / LinkedIn unfurls with case-specific art.

Examples
--------
    python3 scripts/gen_og.py
    python3 scripts/gen_og.py \\
        --slug payment-portal \\
        --title "$85M Payment Portal" \\
        --strap "Full-stack AWS web app" \\
        --tags AWS,React,Node.js,CI/CD,IAM \\
        --accent "47,100,255" \\
        --out og-case-payment-portal.png
"""

import argparse, os, sys
from PIL import Image, ImageDraw, ImageFont

W, H = 1200, 630

FONTS_BASE = "/usr/share/fonts/truetype/liberation"
FONT_BOLD = os.path.join(FONTS_BASE, "LiberationSans-Bold.ttf")
FONT_REG  = os.path.join(FONTS_BASE, "LiberationSans-Regular.ttf")

# Shared palette (matches the site's --bg / --accent CSS vars).
BG          = (4, 7, 15)
PANEL       = (10, 16, 31)
ACCENT_DEF  = (47, 100, 255)
ACCENT2_DEF = (103, 232, 200)
FG          = (238, 244, 255)
MUTED       = (169, 182, 216)
TAG_BG      = (18, 28, 54)


def parse_rgb(s):
    parts = [int(p.strip()) for p in s.split(",")]
    if len(parts) != 3:
        raise ValueError("expected R,G,B")
    return tuple(parts)


def safe_font(path, size, fallback):
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return fallback


def render(name, title, strap, tags, accent, accent2, url, out):
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img, "RGBA")

    # background gradient
    for y in range(H):
        t = y / H
        r = int(BG[0] + (PANEL[0] - BG[0]) * t * 0.6)
        g = int(BG[1] + (PANEL[1] - BG[1]) * t * 0.6)
        b = int(BG[2] + (PANEL[2] - BG[2]) * t * 0.6)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    # top/bottom accent bars
    draw.rectangle([0, 0, W, 5], fill=accent)
    draw.rectangle([0, H - 4, W, H], fill=accent)

    # radial glow top-left
    for r in range(320, 0, -4):
        alpha = int(18 * (1 - r / 320))
        draw.ellipse([-r + 160, -r + 180, r + 160, r + 180], fill=(*accent, alpha))

    # card panel
    pad = 72
    cx, cy = pad, 90
    cw, ch = W - pad * 2, H - 160
    draw.rounded_rectangle(
        [cx, cy, cx + cw, cy + ch],
        radius=28,
        fill=(*PANEL, 230),
        outline=(*accent, 40),
        width=1,
    )

    default = ImageFont.load_default()
    fn_name  = safe_font(FONT_BOLD, 76, default)
    fn_title = safe_font(FONT_BOLD, 34, default)
    fn_strap = safe_font(FONT_REG,  28, default)
    fn_tag   = safe_font(FONT_REG,  22, default)
    fn_url   = safe_font(FONT_REG,  20, default)

    # name (or case title, depending on invocation)
    bbox = draw.textbbox((0, 0), name, font=fn_name)
    nx = (W - (bbox[2] - bbox[0])) // 2
    draw.text((nx, 148), name, font=fn_name, fill=FG)

    # title
    bbox = draw.textbbox((0, 0), title, font=fn_title)
    tx = (W - (bbox[2] - bbox[0])) // 2
    draw.text((tx, 252), title, font=fn_title, fill=accent)

    # strap
    bbox = draw.textbbox((0, 0), strap, font=fn_strap)
    sx = (W - (bbox[2] - bbox[0])) // 2
    draw.text((sx, 306), strap, font=fn_strap, fill=MUTED)

    # divider
    div_y = 362
    draw.line([(cx + 60, div_y), (cx + cw - 60, div_y)], fill=(*accent, 40), width=1)

    # skill tags row
    tag_h = 38
    padding_x = 20
    gap = 14
    total_w = 0
    widths = []
    for s in tags:
        bb = draw.textbbox((0, 0), s, font=fn_tag)
        tw = bb[2] - bb[0] + padding_x * 2
        widths.append(tw)
        total_w += tw + gap
    if tags:
        total_w -= gap
    row_x = (W - total_w) // 2
    row_y = 384
    for i, s in enumerate(tags):
        tw = widths[i]
        draw.rounded_rectangle(
            [row_x, row_y, row_x + tw, row_y + tag_h],
            radius=8, fill=TAG_BG, outline=(*accent, 55), width=1,
        )
        bb = draw.textbbox((0, 0), s, font=fn_tag)
        th = bb[3] - bb[1]
        draw.text(
            (row_x + padding_x, row_y + (tag_h - th) // 2 - 1),
            s, font=fn_tag, fill=accent2,
        )
        row_x += tw + gap

    # url
    bbox = draw.textbbox((0, 0), url, font=fn_url)
    ux = (W - (bbox[2] - bbox[0])) // 2
    draw.text((ux, 456), url, font=fn_url, fill=(*MUTED, 160))

    img.save(out, "PNG", optimize=True)
    print(f"Saved {out} ({W}x{H})")


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--name",   default="Brandon S. Clark")
    p.add_argument("--title",  default="Senior Software Engineer")
    p.add_argument("--strap",  default="Cloud · Data · IoT Platforms")
    p.add_argument("--tags",   default="AWS,IoT,Terraform,TypeScript,Python,Node.js,Serverless")
    p.add_argument("--accent", default="47,100,255", help="R,G,B")
    p.add_argument("--accent2", default="103,232,200", help="R,G,B")
    p.add_argument("--url",    default="northwoodscode.github.io/resume")
    p.add_argument("--out",    default="og-image.png")
    # Case mode: --slug shifts defaults so per-case invocation is one flag.
    p.add_argument("--slug",   default="")
    args = p.parse_args(argv)

    tags = [t.strip() for t in args.tags.split(",") if t.strip()]
    accent  = parse_rgb(args.accent)
    accent2 = parse_rgb(args.accent2)

    out = args.out
    if args.slug and out == "og-image.png":
        out = f"og-case-{args.slug}.png"

    render(args.name, args.title, args.strap, tags, accent, accent2, args.url, out)


if __name__ == "__main__":
    main()
