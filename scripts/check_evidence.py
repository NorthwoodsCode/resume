#!/usr/bin/env python3
"""Lint evidence.json against the pages that use it. Fails the build on drift.

Checks:
  - every receipt has the required fields, a known confidence level and a case
    slug that exists in cases.json;
  - every data-receipt="<id>" used in the HTML and JS files points at a receipt
    that exists (so a number can never claim a receipt it does not have);
  - every receipt is referenced by at least one page (warning only);
  - non-draft decisions, incidents and answers carry their required fields, and
    answer evidence references resolve to a receipt id or "case:<slug>";
  - the optional payload sample's byte counts match the numbers it states;
  - with --strict (used after strip_drafts.py in the build), no draft entries or
    author notes remain.

Usage: python3 scripts/check_evidence.py [--strict]
Standard library only; exit code 1 on any error.
"""
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RECEIPT_REQUIRED = ("headline", "claim", "where", "confidence", "case")
DECISION_REQUIRED = ("id", "case", "title", "context", "options", "choice")
INCIDENT_REQUIRED = ("id", "year", "system", "what", "detected_by", "impact", "fix", "guard")
ANSWER_REQUIRED = ("id", "q", "a")
PAGES = ("index.html", "resume-atlas.html", "resume-signal.html", "proof-hub.html",
         "resume-switchboard.html", "now.html", "shared-enhancements.js", "home-evidence.js")


def is_draft(entry):
    """Any truthy draft marker counts ("true", 1, True), so a typo cannot publish a draft."""
    return isinstance(entry, dict) and bool(entry.get("draft"))


def todo_strings(node, path="evidence"):
    """Yield paths of string values that still read as author placeholders."""
    if isinstance(node, dict):
        for k, v in node.items():
            yield from todo_strings(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from todo_strings(v, f"{path}[{i}]")
    elif isinstance(node, str) and (node.startswith("TODO") or "TODO:" in node):
        yield path


def walk_has_author_material(node):
    """True when any draft entry or "_" key is still present."""
    if isinstance(node, dict):
        if bool(node.get("draft")):
            return True
        return any(k.startswith("_") or walk_has_author_material(v) for k, v in node.items())
    if isinstance(node, list):
        return any(walk_has_author_material(v) for v in node)
    return False


def main(argv):
    strict = "--strict" in argv
    errors, warnings = [], []

    data = json.loads((REPO / "evidence.json").read_text(encoding="utf-8"))
    cases = {c["slug"] for c in json.loads((REPO / "cases.json").read_text(encoding="utf-8"))}
    levels = set((data.get("confidence_levels") or {}).keys())
    receipts = data.get("receipts") or {}

    # Receipts.
    for rid, r in receipts.items():
        if not re.fullmatch(r"[a-z0-9-]+", rid):
            errors.append(f"receipt id {rid!r} must be lowercase letters, digits and dashes")
        if is_draft(r):
            errors.append(f"receipt {rid}: receipts cannot be drafts (a number on a page always needs its receipt); remove the number instead")
        for key in RECEIPT_REQUIRED:
            if not r.get(key):
                errors.append(f"receipt {rid}: missing {key}")
        if r.get("confidence") not in levels:
            errors.append(f"receipt {rid}: confidence {r.get('confidence')!r} is not one of {sorted(levels)}")
        if r.get("case") not in cases:
            errors.append(f"receipt {rid}: case {r.get('case')!r} is not a slug in cases.json")
        art = r.get("artifact")
        if art is not None and not (isinstance(art, dict) and art.get("label") and art.get("href")):
            errors.append(f"receipt {rid}: artifact must be null or {{label, href}}")

    # Pages that claim a receipt.
    used = {}
    for name in PAGES:
        path = REPO / name
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        for m in re.finditer(r"""data-receipt=\\?["']([a-z0-9-]+)\\?["']""", text):
            used.setdefault(m.group(1), set()).add(name)
        # Proof Hub builds its tiles in script and maps tile names to receipt ids in RECEIPT_FOR.
        for block in re.finditer(r"RECEIPT_FOR\s*=\s*\{([^}]*)\}", text):
            for m in re.finditer(r"""['"]([A-Za-z /]+)['"]\s*:\s*['"]([a-z0-9-]+)['"]""", block.group(1)):
                used.setdefault(m.group(2), set()).add(name)
    for rid, pages in sorted(used.items()):
        if rid not in receipts:
            errors.append(f"data-receipt=\"{rid}\" in {', '.join(sorted(pages))} has no receipt in evidence.json")
    for rid in receipts:
        if rid not in used:
            warnings.append(f"receipt {rid} is not referenced by any page")

    # Facts.
    facts = data.get("facts") or {}
    for key in ("name", "title", "employer", "role_since", "career_since", "location"):
        if not facts.get(key):
            errors.append(f"facts: missing {key}")

    # Decisions, incidents, answers (drafts are exempt; they never publish).
    for d in data.get("decisions") or []:
        if is_draft(d):
            continue
        for key in DECISION_REQUIRED:
            if not d.get(key):
                errors.append(f"decision {d.get('id', '?')}: missing {key}")
        if d.get("case") not in cases:
            errors.append(f"decision {d.get('id', '?')}: case {d.get('case')!r} is not in cases.json")
        if isinstance(d.get("options"), list) and len(d["options"]) < 2:
            errors.append(f"decision {d.get('id', '?')}: needs at least two options (the road not taken)")
    for i in data.get("incidents") or []:
        if is_draft(i):
            continue
        for key in INCIDENT_REQUIRED:
            if not i.get(key):
                errors.append(f"incident {i.get('id', '?')}: missing {key}")
    for a in data.get("answers") or []:
        if is_draft(a):
            continue
        for key in ANSWER_REQUIRED:
            if not a.get(key):
                errors.append(f"answer {a.get('id', '?')}: missing {key}")
        for ref in a.get("evidence") or []:
            if ref.startswith("case:"):
                if ref[5:] not in cases:
                    errors.append(f"answer {a.get('id', '?')}: unknown case reference {ref!r}")
            elif ref not in receipts:
                errors.append(f"answer {a.get('id', '?')}: unknown receipt reference {ref!r}")

    # Payload sample: the byte counts are checked, not trusted.
    payload = data.get("payload")
    if payload is not None:
        for side in ("before", "after"):
            text = payload.get(side)
            stated = payload.get(side + "_bytes")
            if not isinstance(text, str) or not isinstance(stated, int):
                errors.append(f"payload: {side} must be a string and {side}_bytes an integer")
                continue
            actual = len(text.encode("utf-8"))
            if actual != stated:
                errors.append(f"payload: {side} is {actual} bytes, but {side}_bytes says {stated}")

    if strict and walk_has_author_material(data):
        errors.append("strict: draft entries or author notes are still present (run strip_drafts.py first)")
    if strict:
        for where in todo_strings(data):
            errors.append(f"strict: placeholder text (TODO) would publish at {where}")

    for w in warnings:
        print(f"  warning: {w}")
    for e in errors:
        print(f"  error: {e}")
    print(f"  check_evidence: {len(receipts)} receipts, {len(used)} referenced, "
          f"{len(errors)} errors, {len(warnings)} warnings{' (strict)' if strict else ''}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
