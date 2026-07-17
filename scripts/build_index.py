#!/usr/bin/env python3
"""Regenerate index.json from every file in metadata/.

index.json is the ONLY file consuming agents (Claude Design / Claude Code) should
read. It is generated — never edit it by hand.

Usage:
    python scripts/build_index.py
"""
from __future__ import annotations

import datetime as _dt
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
METADATA_DIR = REPO_ROOT / "metadata"
INDEX_PATH = REPO_ROOT / "index.json"

# Fields the index is expected to be searchable by. We surface them at the top
# level of every entry so a consumer can filter cheaply.
SEARCHABLE_FIELDS = ("tags", "category", "tone", "primary_emotion")


def load_metadata_files() -> list[dict]:
    if not METADATA_DIR.exists():
        return []
    entries: list[dict] = []
    for path in sorted(METADATA_DIR.glob("*.json")):
        try:
            with path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"  ! skipping {path.name}: {exc}", file=sys.stderr)
            continue
        if not isinstance(data, dict) or "id" not in data:
            print(f"  ! skipping {path.name}: missing 'id'", file=sys.stderr)
            continue
        entries.append(data)
    return entries


def build_index(entries: list[dict]) -> dict:
    entries_sorted = sorted(entries, key=lambda e: e.get("id", ""))
    published = [e for e in entries_sorted if not e.get("review_pending", False)]
    pending = [e for e in entries_sorted if e.get("review_pending", False)]
    return {
        "version": 1,
        "last_updated": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "count_total": len(entries_sorted),
        "count_published": len(published),
        "count_review_pending": len(pending),
        "searchable_fields": list(SEARCHABLE_FIELDS),
        "gifs": entries_sorted,
    }


def main() -> int:
    entries = load_metadata_files()
    index = build_index(entries)
    with INDEX_PATH.open("w", encoding="utf-8") as fh:
        json.dump(index, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(
        f"Wrote {INDEX_PATH.relative_to(REPO_ROOT)}: "
        f"{index['count_total']} total "
        f"({index['count_published']} published, "
        f"{index['count_review_pending']} pending review)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
