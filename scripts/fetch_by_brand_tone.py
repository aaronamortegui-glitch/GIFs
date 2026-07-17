#!/usr/bin/env python3
"""Search and download GIFs from GIPHY based on a brand's tone.

Reads a brand_tone config (JSON file or CLI overrides), maps each tone adjective
to English search terms via scripts/tone_to_query_map.json, queries the GIPHY
search API, downloads the selected GIFs into the correct category folder, and
writes one metadata/{id}.json per GIF with review_pending = true. Finally it runs
build_index.py to regenerate index.json.

The GIPHY API key is read from the GIPHY_API_KEY environment variable. It is never
hardcoded. If it is missing, the script stops and tells you how to set it.

The script is idempotent: it will not download a GIF whose GIPHY source_id already
exists in metadata/.

Usage:
    export GIPHY_API_KEY=xxxxxxxx            # (Windows PowerShell: $env:GIPHY_API_KEY="xxxx")
    python scripts/fetch_by_brand_tone.py --config scripts/brand_tone.json
    python scripts/fetch_by_brand_tone.py --brand "Acme" --tones energetic friendly \\
        --category reactions --subcategory celebration --rating g --limit 5
    python scripts/fetch_by_brand_tone.py --config scripts/brand_tone.json --dry-run
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

try:
    import requests
except ImportError:  # pragma: no cover
    print(
        "This script needs the 'requests' package.\n"
        "Install it with:  pip install requests",
        file=sys.stderr,
    )
    raise SystemExit(1)

REPO_ROOT = Path(__file__).resolve().parents[1]
METADATA_DIR = REPO_ROOT / "metadata"
GIFS_DIR = REPO_ROOT / "gifs"
TONE_MAP_PATH = REPO_ROOT / "scripts" / "tone_to_query_map.json"
BUILD_INDEX = REPO_ROOT / "scripts" / "build_index.py"

GIPHY_SEARCH_URL = "https://api.giphy.com/v1/gifs/search"
VALID_CATEGORIES = {"reactions", "transitions", "emphasis", "collaboration", "closing"}
# The schema 'tone' field is a controlled enum. Brand tone adjectives used for
# searching (e.g. 'friendly', 'bold') are a broader vocabulary — only the ones that
# are valid schema tones are carried into metadata as a starting hint; the rest are
# left for the human reviewer.
VALID_SCHEMA_TONES = {
    "professional", "casual", "energetic", "calm", "playful", "formal", "minimalist",
}


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
def load_dotenv() -> None:
    """Load KEY=VALUE lines from a repo-root .env into os.environ (no overwrite)."""
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_config(args: argparse.Namespace) -> dict:
    config: dict = {}
    if args.config:
        cfg_path = Path(args.config)
        if not cfg_path.is_absolute():
            cfg_path = REPO_ROOT / cfg_path
        with cfg_path.open("r", encoding="utf-8") as fh:
            config = json.load(fh)

    # CLI overrides take precedence over the file.
    if args.brand:
        config["brand"] = args.brand
    if args.tones:
        config["tones"] = args.tones
    if args.category:
        config["target_category"] = args.category
    if args.subcategory:
        config["target_subcategory"] = args.subcategory
    if args.rating:
        config["content_rating"] = args.rating
    if args.limit is not None:
        config["per_query_limit"] = args.limit

    config.setdefault("content_rating", "g")
    config.setdefault("per_query_limit", 5)
    config.setdefault("selection", "trending")
    config.setdefault("added_by", "automatic-script")
    config.setdefault("brand_compatible", [config["brand"]] if config.get("brand") else [])

    # Validation
    missing = [k for k in ("brand", "tones", "target_category", "target_subcategory") if not config.get(k)]
    if missing:
        raise SystemExit(
            "Missing required config: " + ", ".join(missing) +
            "\nProvide them in the --config file or as CLI flags."
        )
    if config["target_category"] not in VALID_CATEGORIES:
        raise SystemExit(
            f"target_category '{config['target_category']}' is not valid. "
            f"Choose one of: {', '.join(sorted(VALID_CATEGORIES))}"
        )
    return config


def load_tone_map() -> dict:
    with TONE_MAP_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh).get("map", {})


def known_source_ids() -> set[str]:
    """Every GIPHY source_id already in metadata/ (for idempotency)."""
    ids: set[str] = set()
    if not METADATA_DIR.exists():
        return ids
    for path in METADATA_DIR.glob("*.json"):
        try:
            with path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError):
            continue
        sid = data.get("source_id")
        if sid:
            ids.add(str(sid))
    return ids


# --------------------------------------------------------------------------- #
# GIPHY
# --------------------------------------------------------------------------- #
def search_giphy(api_key: str, query: str, rating: str, limit: int) -> list[dict]:
    params = {
        "api_key": api_key,
        "q": query,
        "rating": rating,
        "limit": max(1, min(limit, 50)),
        "bundle": "messaging_non_clips",
    }
    resp = requests.get(GIPHY_SEARCH_URL, params=params, timeout=30)
    if resp.status_code == 401:
        raise SystemExit("GIPHY returned 401 Unauthorized — check GIPHY_API_KEY.")
    if resp.status_code == 429:
        raise SystemExit("GIPHY returned 429 Too Many Requests — rate limited, try later.")
    resp.raise_for_status()
    return resp.json().get("data", [])


def select_best(results: list[dict], selection: str, limit: int) -> list[dict]:
    if selection == "trending":
        def sort_key(item: dict):
            return item.get("trending_datetime", "") or ""
        results = sorted(results, key=sort_key, reverse=True)
    # "first" (or anything else) keeps GIPHY's own relevance order.
    return results[:limit]


def short_id(source_id: str) -> str:
    return hashlib.sha1(source_id.encode("utf-8")).hexdigest()[:10]


def download_gif(url: str, dest: Path) -> int:
    resp = requests.get(url, timeout=60, stream=True)
    resp.raise_for_status()
    dest.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    with dest.open("wb") as fh:
        for chunk in resp.iter_content(chunk_size=8192):
            if chunk:
                fh.write(chunk)
                total += len(chunk)
    return total


def build_metadata(item: dict, config: dict, gif_id: str, rel_filename: str, weight_kb: float | None) -> dict:
    original = item.get("images", {}).get("original", {})

    def to_num(v):
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    return {
        "id": gif_id,
        "filename": rel_filename,
        "source": "giphy",
        "source_id": item.get("id"),
        "source_url": item.get("url"),
        # Category/subcategory come from config, but they are NOT trusted:
        # review_pending stays true until a human confirms them.
        "category": config["target_category"],
        "subcategory": config["target_subcategory"],
        # Human-review placeholders:
        "tags": [],
        "tone": [t for t in config.get("tones", []) if t in VALID_SCHEMA_TONES],
        "primary_emotion": "",
        "recommended_use": "",
        "avoid_if": None,
        "content_rating": config["content_rating"],
        "duration_seconds": None,
        "dimensions": {
            "width": to_num(original.get("width")),
            "height": to_num(original.get("height")),
        },
        "weight_kb": round(weight_kb, 1) if weight_kb is not None else None,
        "brand_compatible": config.get("brand_compatible", []),
        "license_note": (
            "Sourced via GIPHY API. Review GIPHY API & Terms of Use "
            "(developers.giphy.com/docs/api) before external/client use. "
            "Attribution and caching terms may differ for external distribution."
        ),
        "date_added": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "added_by": config.get("added_by", "automatic-script"),
        "review_pending": True,
    }


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", help="Path to a brand_tone.json config file.")
    parser.add_argument("--brand", help="Brand name.")
    parser.add_argument("--tones", nargs="+", help="Tone adjectives, e.g. energetic friendly.")
    parser.add_argument("--category", help="Target level-1 category.")
    parser.add_argument("--subcategory", help="Target level-2 subcategory.")
    parser.add_argument("--rating", choices=["g", "pg", "pg-13", "r"], help="Content rating filter.")
    parser.add_argument("--limit", type=int, help="How many GIFs to keep per search query.")
    parser.add_argument("--dry-run", action="store_true", help="Search and report, but download nothing.")
    args = parser.parse_args()

    load_dotenv()
    api_key = os.environ.get("GIPHY_API_KEY")
    if not api_key and not args.dry_run:
        raise SystemExit(
            "GIPHY_API_KEY is not set.\n"
            "Get a free key at https://developers.giphy.com/ then set it:\n"
            "  PowerShell:  $env:GIPHY_API_KEY=\"your_key\"\n"
            "  bash/zsh:    export GIPHY_API_KEY=your_key"
        )

    config = load_config(args)
    tone_map = load_tone_map()
    seen_ids = known_source_ids()

    print(f"Brand: {config['brand']}")
    print(f"Tones: {', '.join(config['tones'])}")
    print(f"Target: {config['target_category']}/{config['target_subcategory']}")
    print(f"Rating: {config['content_rating']}  |  per-query limit: {config['per_query_limit']}")
    print(f"Already cataloged (source_ids): {len(seen_ids)}")
    print("-" * 60)

    downloaded = 0
    skipped_dupes = 0
    unknown_tones = []

    for tone in config["tones"]:
        queries = tone_map.get(tone)
        if not queries:
            unknown_tones.append(tone)
            print(f"  ! no query mapping for tone '{tone}' — add it to tone_to_query_map.json")
            continue

        for query in queries:
            print(f"[{tone}] query: '{query}'")
            if args.dry_run and not api_key:
                print("    (dry-run without API key: skipping network call)")
                continue

            results = search_giphy(api_key, query, config["content_rating"], config["per_query_limit"] * 2)
            picked = select_best(results, config["selection"], config["per_query_limit"])

            for item in picked:
                source_id = str(item.get("id", ""))
                if not source_id:
                    continue
                if source_id in seen_ids:
                    skipped_dupes += 1
                    print(f"    - skip (already have): {source_id}")
                    continue

                gif_id = short_id(source_id)
                rel_filename = f"{config['target_category']}/{config['target_subcategory']}/{gif_id}.gif"
                dest = GIFS_DIR / rel_filename
                gif_url = item.get("images", {}).get("original", {}).get("url")

                if args.dry_run:
                    print(f"    - would download: {source_id} -> gifs/{rel_filename}")
                    seen_ids.add(source_id)
                    continue

                if not gif_url:
                    print(f"    - skip (no original url): {source_id}")
                    continue

                size_bytes = download_gif(gif_url, dest)
                weight_kb = size_bytes / 1024 if size_bytes else None

                metadata = build_metadata(item, config, gif_id, rel_filename, weight_kb)
                METADATA_DIR.mkdir(parents=True, exist_ok=True)
                with (METADATA_DIR / f"{gif_id}.json").open("w", encoding="utf-8") as fh:
                    json.dump(metadata, fh, indent=2, ensure_ascii=False)
                    fh.write("\n")

                seen_ids.add(source_id)
                downloaded += 1
                print(f"    + downloaded: {source_id} -> gifs/{rel_filename} ({metadata['weight_kb']} KB)")

    print("-" * 60)
    print(f"Downloaded: {downloaded}   Skipped duplicates: {skipped_dupes}")
    if unknown_tones:
        print(f"Unmapped tones (add to tone_to_query_map.json): {', '.join(unknown_tones)}")

    if downloaded and not args.dry_run:
        print("\nRegenerating index.json ...")
        subprocess.run([sys.executable, str(BUILD_INDEX)], check=True)
        print(
            "\nNext step: run  python scripts/validate_metadata.py  to review the new "
            "GIFs (they are review_pending=true and excluded from consumers until confirmed)."
        )
    elif args.dry_run:
        print("\n(dry-run: nothing written, index.json unchanged)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
