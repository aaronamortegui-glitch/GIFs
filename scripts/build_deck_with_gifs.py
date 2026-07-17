#!/usr/bin/env python3
"""Resolve which GIF goes on each slide of a brief.

This script does NOT build a .pptx. It only reads index.json and returns a
slide -> GIF filename mapping, honouring the read contract:
  - never crawl folders; read index.json only
  - exclude review_pending == true
  - filter by category/subcategory and by tone/tags intersection
  - if no GIF matches a slide, leave it empty and report it (never invent one)

The deck itself is assembled elsewhere (e.g. the pptx skill / pptxgenjs addImage)
using this mapping.

Brief format (JSON):
    {
      "slides": [
        {
          "title": "Q2 Results",
          "desired_tone": ["professional", "energetic"],
          "desired_category": "emphasis/important-data"
        },
        {
          "title": "Thank you",
          "desired_tone": ["calm"],
          "desired_category": "closing/thank-you"
        }
      ]
    }

`desired_category` may be "category/subcategory" or just "category". `desired_tone`
and `desired_tags` are optional lists; a candidate matches if it shares at least one
value (intersection).

Usage:
    python scripts/build_deck_with_gifs.py --brief scripts/brief.example.json
    python scripts/build_deck_with_gifs.py --brief brief.json --select random --seed 7
    python scripts/build_deck_with_gifs.py --brief brief.json --out mapping.json
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
INDEX_PATH = REPO_ROOT / "index.json"


def load_published() -> list[dict]:
    """All index entries that are NOT pending review."""
    with INDEX_PATH.open("r", encoding="utf-8") as fh:
        index = json.load(fh)
    return [g for g in index.get("gifs", []) if not g.get("review_pending", False)]


def split_category(desired: str | None) -> tuple[str | None, str | None]:
    if not desired:
        return None, None
    parts = desired.replace("\\", "/").split("/", 1)
    category = parts[0] or None
    subcategory = parts[1] if len(parts) > 1 and parts[1] else None
    return category, subcategory


def candidates_for(slide: dict, published: list[dict]) -> tuple[list[dict], list[str]]:
    """Return (matching gifs, list of filters applied) for one slide."""
    category, subcategory = split_category(slide.get("desired_category"))
    desired_tone = set(slide.get("desired_tone") or [])
    desired_tags = set(slide.get("desired_tags") or [])

    applied: list[str] = []
    pool = published

    if category:
        applied.append(f"category={category}" + (f"/{subcategory}" if subcategory else ""))
        pool = [g for g in pool if g.get("category") == category]
        if subcategory:
            pool = [g for g in pool if g.get("subcategory") == subcategory]

    if desired_tone:
        applied.append(f"tone in {sorted(desired_tone)}")
        pool = [g for g in pool if desired_tone & set(g.get("tone") or [])]

    if desired_tags:
        applied.append(f"tags in {sorted(desired_tags)}")
        pool = [g for g in pool if desired_tags & set(g.get("tags") or [])]

    return pool, applied


def select(pool: list[dict], strategy: str, rng: random.Random) -> dict:
    if strategy == "random":
        return rng.choice(pool)
    # "newest" (default): most recently added by date_added.
    return max(pool, key=lambda g: g.get("date_added", ""))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--brief", required=True, help="Path to the brief JSON.")
    parser.add_argument("--select", choices=["newest", "random"], default="newest",
                        help="How to pick when several GIFs match (default: newest).")
    parser.add_argument("--seed", type=int, default=None, help="Seed for --select random.")
    parser.add_argument("--out", help="Optional path to write the mapping JSON.")
    args = parser.parse_args()

    brief_path = Path(args.brief)
    if not brief_path.is_absolute():
        brief_path = REPO_ROOT / brief_path
    with brief_path.open("r", encoding="utf-8") as fh:
        brief = json.load(fh)

    slides = brief.get("slides", [])
    if not slides:
        raise SystemExit("Brief has no 'slides'.")

    published = load_published()
    rng = random.Random(args.seed)

    mapping: list[dict] = []
    misses: list[dict] = []

    print(f"Published GIFs available: {len(published)}")
    print("-" * 60)

    for i, slide in enumerate(slides, 1):
        title = slide.get("title", f"slide {i}")
        pool, applied = candidates_for(slide, published)
        filt = ", ".join(applied) if applied else "(no filter — any published GIF)"

        if not pool:
            misses.append({"slide": title, "wanted": filt})
            mapping.append({"slide": title, "gif": None})
            print(f"[{i}] {title}\n      wanted: {filt}\n      -> NO MATCH")
            continue

        chosen = select(pool, args.select, rng)
        mapping.append({
            "slide": title,
            "gif": chosen.get("filename"),
            "gif_id": chosen.get("id"),
            "candidates": len(pool),
        })
        print(f"[{i}] {title}\n      wanted: {filt}\n      -> {chosen.get('filename')} "
              f"({len(pool)} candidate(s), picked by {args.select})")

    print("-" * 60)
    matched = sum(1 for m in mapping if m["gif"])
    print(f"{len(slides) - matched} of {len(slides)} slides without GIF.")
    if misses:
        print("Coverage gaps (add + review GIFs for these):")
        for m in misses:
            print(f"  - '{m['slide']}'  needed: {m['wanted']}")

    result = {"mapping": mapping, "slides_without_gif": len(slides) - matched}
    if args.out:
        out_path = Path(args.out)
        if not out_path.is_absolute():
            out_path = REPO_ROOT / out_path
        with out_path.open("w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        print(f"\nWrote mapping -> {out_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
