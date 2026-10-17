#!/usr/bin/env python3
"""Generate per-case OG images and shareable case stub pages.

Reads cases.json (at repo root) and for each entry produces:
  - og-case-<slug>.png       (case-specific Open Graph art)
  - case/<slug>/index.html   (tiny stub page with OG meta + redirect
                              to /proof-hub.html#case-<slug>)

The point: when someone shares https://.../case/payment-portal/ on
Slack or LinkedIn, the unfurl card is specific to that case. Clicking
the link lands them on the right anchor of proof-hub.

Run from repo root: python3 scripts/gen_cases.py
"""

import json, os, sys, html, subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CASES = REPO / "cases.json"
BASE_URL = "https://northwoodscode.github.io/resume"


STUB_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>{name} — Brandon S. Clark</title>
  <meta name="description" content="{strap}" />
  <link rel="canonical" href="{canonical}" />
  <meta property="og:title" content="{name} — {title}" />
  <meta property="og:description" content="{strap}" />
  <meta property="og:type" content="article" />
  <meta property="og:url" content="{share_url}" />
  <meta property="og:image" content="{og_image_url}" />
  <meta name="twitter:card" content="summary_large_image" />
  <meta name="twitter:title" content="{name} — {title}" />
  <meta name="twitter:description" content="{strap}" />
  <meta name="twitter:image" content="{og_image_url}" />
  <meta http-equiv="refresh" content="0; url={canonical}" />
  <script>location.replace({canonical_js});</script>
  <style>body{{font:14px/1.5 system-ui;margin:40px auto;max-width:480px;color:#444;text-align:center}} a{{color:#2563eb}}</style>
</head>
<body>
  <p>Redirecting to <a href="{canonical}">{name} case study</a>…</p>
</body>
</html>
"""


def parse_rgb(s):
    parts = [int(p.strip()) for p in s.split(",")]
    return parts


def main():
    if not CASES.exists():
        print(f"cases.json not found at {CASES}", file=sys.stderr)
        sys.exit(1)

    cases = json.loads(CASES.read_text())
    gen_og = REPO / "scripts" / "gen_og.py"
    case_dir = REPO / "case"
    case_dir.mkdir(exist_ok=True)

    for c in cases:
        slug = c["slug"]
        # 1. Generate the OG image via gen_og.py (subprocess keeps single source of truth)
        out_png = REPO / f"og-case-{slug}.png"
        cmd = [
            sys.executable, str(gen_og),
            "--slug", slug,
            "--name", c["name"],
            "--title", c["title"],
            "--strap", c["strap"],
            "--tags", ",".join(c["tags"]),
            "--accent", c["accent"],
            "--accent2", c["accent2"],
            "--out", str(out_png),
        ]
        subprocess.run(cmd, check=True)

        # 2. Generate the case stub page
        case_slug_dir = case_dir / slug
        case_slug_dir.mkdir(exist_ok=True)
        canonical = f"{BASE_URL}/proof-hub.html#case-{slug}"
        share_url = f"{BASE_URL}/case/{slug}/"
        og_image_url = f"{BASE_URL}/og-case-{slug}.png"
        stub = STUB_TEMPLATE.format(
            name=html.escape(c["name"]),
            title=html.escape(c["title"]),
            strap=html.escape(c["strap"]),
            canonical=canonical,
            canonical_js=json.dumps(canonical),
            share_url=share_url,
            og_image_url=og_image_url,
        )
        (case_slug_dir / "index.html").write_text(stub)
        print(f"  → case/{slug}/index.html")

    # 3. Append the new case URLs to a sitemap snippet for review/copy-paste.
    snippet = REPO / "case" / "sitemap-cases.xml"
    lines = []
    for c in cases:
        lines.append(
            f"  <url>\n"
            f"    <loc>{BASE_URL}/case/{c['slug']}/</loc>\n"
            f"    <changefreq>monthly</changefreq>\n"
            f"    <priority>0.7</priority>\n"
            f"  </url>"
        )
    snippet.write_text("\n".join(lines) + "\n")
    print(f"\nWrote {snippet.relative_to(REPO)} ({len(cases)} entries) — splice into sitemap.xml if/when stable.")


if __name__ == "__main__":
    main()
