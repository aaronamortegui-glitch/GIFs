#!/usr/bin/env python3
"""Validate metadata files and list GIFs awaiting human review.

Checks performed per metadata/*.json file:
  - required fields present
  - category is one of the level-1 folders
  - every tag exists in schema/tags-controlled.json (catches spelling/language variants)
  - the referenced GIF file actually exists under gifs/
  - filename matches the declared category/subcategory

Then prints a review queue of everything with review_pending = true so a human can
quickly confirm category, tags and tone before the asset is considered "published".

Usage:
    python scripts/validate_metadata.py
    python scripts/validate_metadata.py --strict   # exit non-zero if any error found
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
METADATA_DIR = REPO_ROOT / "metadata"
GIFS_DIR = REPO_ROOT / "gifs"
TAGS_CONTROLLED = REPO_ROOT / "schema" / "tags-controlled.json"

VALID_CATEGORIES = {"reactions", "transitions", "emphasis", "collaboration", "closing"}
VALID_TONES = {
    "professional", "casual", "energetic", "calm", "playful", "formal", "minimalist",
}
REQUIRED_FIELDS = (
    "id", "filename", "source", "category", "subcategory", "tags", "tone",
    "primary_emotion", "recommended_use", "content_rating", "dimensions",
    "date_added", "added_by", "review_pending",
)


def load_controlled_tags() -> set[str]:
    try:
        with TAGS_CONTROLLED.open("r", encoding="utf-8") as fh:
            return set(json.load(fh).get("tags", []))
    except (OSError, json.JSONDecodeError):
        print(f"  ! could not read {TAGS_CONTROLLED}", file=sys.stderr)
        return set()


def validate_entry(data: dict, controlled_tags: set[str]) -> list[str]:
    errors: list[str] = []

    for field in REQUIRED_FIELDS:
        if field not in data:
            errors.append(f"missing required field '{field}'")

    category = data.get("category")
    if category is not None and category not in VALID_CATEGORIES:
        errors.append(f"category '{category}' is not a valid level-1 folder")

    for tone in data.get("tone", []) or []:
        if tone not in VALID_TONES:
            errors.append(f"tone '{tone}' is not in the controlled tone list")

    if controlled_tags:
        for tag in data.get("tags", []) or []:
            if tag not in controlled_tags:
                errors.append(
                    f"tag '{tag}' is not in schema/tags-controlled.json "
                    "(add it deliberately or fix the variant)"
                )

    filename = data.get("filename")
    if filename:
        gif_path = GIFS_DIR / filename
        if not gif_path.exists():
            errors.append(f"referenced GIF not found: gifs/{filename}")
        if category and data.get("subcategory"):
            expected_prefix = f"{category}/{data['subcategory']}/"
            if not filename.replace("\\", "/").startswith(expected_prefix):
                errors.append(
                    f"filename '{filename}' does not sit under "
                    f"'{expected_prefix}'"
                )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--strict", action="store_true",
        help="exit with non-zero status if any validation error is found",
    )
    args = parser.parse_args()

    controlled_tags = load_controlled_tags()

    if not METADATA_DIR.exists():
        print("No metadata/ directory yet. Nothing to validate.")
        return 0

    files = sorted(METADATA_DIR.glob("*.json"))
    if not files:
        print("No metadata files yet. Nothing to validate.")
        return 0

    total_errors = 0
    review_queue: list[dict] = []

    for path in files:
        try:
            with path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"[INVALID JSON] {path.name}: {exc}")
            total_errors += 1
            continue

        errors = validate_entry(data, controlled_tags)
        if errors:
            total_errors += len(errors)
            print(f"[ERRORS] {path.name}")
            for err in errors:
                print(f"    - {err}")

        if data.get("review_pending", False):
            review_queue.append(data)

    print("\n" + "=" * 60)
    print("REVIEW QUEUE (review_pending = true)")
    print("=" * 60)
    if not review_queue:
        print("  (empty) — all cataloged GIFs are published.")
    else:
        for data in review_queue:
            print(
                f"  - {data.get('id', '??')}  "
                f"[{data.get('category', '?')}/{data.get('subcategory', '?')}]  "
                f"source_url={data.get('source_url', 'n/a')}"
            )
        print(f"\n  {len(review_queue)} GIF(s) awaiting human confirmation.")
        print("  Confirm category, tags, tone, recommended_use; set review_pending=false;")
        print("  then re-run: python scripts/build_index.py")

    print(f"\nValidation errors: {total_errors}")
    if args.strict and total_errors:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
