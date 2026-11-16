#!/usr/bin/env python3
"""Stamp "last updated" dates from git history at build time.

- Every <time id="lastUpdated" datetime="YYYY-MM-DD">...</time> in *.html gets
  the date of the last commit that touched that file.
- sw.js: the VERSION line becomes bsc-<commit date>-<short SHA> of HEAD, so
  every deploy gets a new cache name and old caches are deleted on activate.
  (Skipped quietly when sw.js is absent.)
- Every <lastmod> in sitemap.xml gets the last-commit date of the page it
  points at (case/<slug>/ URLs follow cases.json).

Run from the repo root after checkout (needs full git history for accurate
dates): python3 scripts/stamp_dates.py

Runs at deploy time in the GitHub Actions build job, editing the checked-out
files in place before they are copied into the published site. Nothing is
committed back, so the repository keeps its source dates. Standard library only.
"""
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def last_commit_date(path):
    """Return the date (YYYY-MM-DD) of the last commit touching `path`, or None.

    %cs is the committer date in short form. A shallow clone would report the
    clone date for every file, which is why the workflow fetches full history.
    """
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%cs", "--", str(path)],
            cwd=REPO, capture_output=True, text=True, check=True,
        ).stdout.strip()
        return out or None
    except Exception:
        return None


def stamp_service_worker():
    """Rewrite the VERSION line in sw.js to the HEAD commit's date and short SHA.

    Returns 1 when the file changed, else 0. Missing sw.js or git: do nothing.
    """
    sw = REPO / "sw.js"
    if not sw.exists():
        return 0
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%cs %h"],
            cwd=REPO, capture_output=True, text=True, check=True,
        ).stdout.split()
        date, sha = out[0], out[1]
    except Exception:
        return 0
    src = sw.read_text()
    version = f"bsc-{date}-{sha}"
    new = re.sub(r"^(const VERSION = ')[^']*(';)", lambda m: m.group(1) + version + m.group(2), src, flags=re.M)
    if new != src:
        sw.write_text(new)
        print(f"  sw.js: VERSION -> {version}")
        return 1
    return 0


def main():
    """Update lastUpdated tags and sitemap lastmod values; return exit code 0."""
    changed = 0
    for page in sorted(REPO.glob("*.html")):
        date = last_commit_date(page)
        if not date:
            continue
        src = page.read_text()
        new = re.sub(
            r'(<time id="lastUpdated" datetime=")[^"]*(">)[^<]*(</time>)',
            lambda m: f"{m.group(1)}{date}{m.group(2)}{date}{m.group(3)}",
            src,
        )
        if new != src:
            page.write_text(new)
            changed += 1
            print(f"  {page.name}: lastUpdated -> {date}")

    sitemap = REPO / "sitemap.xml"
    if sitemap.exists():
        src = sitemap.read_text()

        def stamp(m):
            # Map each sitemap URL to the source file that determines its date.
            loc = m.group(1)
            tail = loc.rstrip("/").split("/")[-1]
            if "/case/" in loc:
                target = REPO / "cases.json"
            elif tail.endswith(".html"):
                target = REPO / tail
            else:
                target = REPO / "index.html"
            date = last_commit_date(target)
            return f"{m.group(0).split('<lastmod>')[0]}<lastmod>{date}</lastmod>" if date else m.group(0)

        new = re.sub(r"<loc>([^<]+)</loc>\s*<lastmod>[^<]*</lastmod>", stamp, src)
        if new != src:
            sitemap.write_text(new)
            changed += 1
            print("  sitemap.xml: lastmod refreshed")
    changed += stamp_service_worker()
    print(f"Stamped {changed} file(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
