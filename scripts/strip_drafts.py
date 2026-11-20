#!/usr/bin/env python3
"""Remove author-only material from evidence.json before the site is published.

Two kinds of content never reach the live site:
  - any object with a truthy "draft" marker (a decision, incident or answer that
    is still being written), wherever it sits in a list or a mapping. Receipts
    are never drafts: check_evidence.py rejects that, because a number on a
    page always needs its receipt;
  - any key whose name starts with "_" (author notes such as "_todo").

Locally the pages show draft entries with a DRAFT badge so the author can
preview them; this script runs in the GitHub Actions build job right before
the site is assembled, editing the checked-out copy in place. Nothing is
committed back. Standard library only.

Usage: python3 scripts/strip_drafts.py [path/to/evidence.json]
"""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DROP = object()  # sentinel: "remove this node"; distinct from a legitimate null


def clean(node, stats):
    """Return a copy of `node` without drafts and underscore keys, or DROP."""
    if isinstance(node, dict):
        if bool(node.get("draft")):
            stats["drafts"] += 1
            return DROP
        out = {}
        for key, value in node.items():
            if key.startswith("_"):
                stats["notes"] += 1
                continue
            kept = clean(value, stats)
            if kept is DROP:
                continue
            out[key] = kept
        return out
    if isinstance(node, list):
        out = []
        for value in node:
            kept = clean(value, stats)
            if kept is DROP:
                continue
            out.append(kept)
        return out
    return node


def main(argv):
    path = Path(argv[1]) if len(argv) > 1 else REPO / "evidence.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    stats = {"drafts": 0, "notes": 0}
    cleaned = clean(data, stats)
    if cleaned is DROP:
        cleaned = {}
    path.write_text(json.dumps(cleaned, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"  {path.name}: removed {stats['drafts']} draft entries and {stats['notes']} author notes")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
