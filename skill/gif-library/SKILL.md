---
name: gif-library
description: >-
  Pick and insert cataloged GIFs into presentations, slide decks, or any
  fixed-canvas design using the local GIF library (index.json). Use this
  whenever the user is building or editing a deck/presentation/slides and wants
  to add a GIF, reaction, or animation — or asks to "find a GIF for this slide",
  "add a celebration GIF", "put something animated here", or mentions the gif
  library / gif catalog. Also use to add new GIFs to the library from GIPHY by
  tone or search term. Trigger even when the user doesn't say "gif-library"
  explicitly but clearly wants a GIF that fits a slide's tone/meaning.
---

# GIF Library

A local, metadata-cataloged repository of GIFs for presentations. Each GIF is
classified by **function** (folder: `reactions`/`transitions`/`emphasis`/
`collaboration`/`closing`) and by **meaning** (`tags`, `tone`, `primary_emotion`).
You pick GIFs by intent — "celebratory, professional, for a positive metric" —
instead of eyeballing files.

## Locate the library

The library is a git repo (GitHub: `aaronamortegui-glitch/GIFs`, stored with Git
LFS). Resolve its root in this order:

1. `GIF_LIBRARY_PATH` environment variable, if set.
2. Default: `C:\Repos\gif-library` (Windows) or a `gif-library` / `GIFs`
   checkout in the current workspace.

If none exists, tell the user to clone it and run `git lfs pull`, then set
`GIF_LIBRARY_PATH`. All paths below are relative to this root; call it `<LIB>`.

`<LIB>/index.json` is the **single source of truth for search** — always read it;
never crawl the `gifs/` folders by hand.

## The read contract (non-negotiable)

When choosing a GIF for a slide:

1. Read `<LIB>/index.json` (it has a `gifs` array).
2. **Exclude any GIF with `review_pending: true`** — those are unconfirmed and
   must not be used.
3. Filter by the slide's context: match `category`/`subcategory`, and intersect
   `tone` and/or `tags` (a GIF matches if it shares at least one value).
4. Use `filename` (relative to `<LIB>/gifs/`) as the asset path, and
   `recommended_use` as placement guidance. Respect `avoid_if`.
5. If nothing matches, **do not invent or force a GIF** — leave the slide without
   one and tell the user which tone/category has no coverage, so they can add
   GIFs there.

This exists because the library mixes confirmed and unconfirmed assets; shipping
a `review_pending` GIF, or jamming an off-tone GIF onto a slide, is worse than no
GIF at all.

## Workflow A — resolve GIFs for a whole deck (preferred)

When you have several slides, write a brief and let the resolver do the matching.
It implements the read contract and reports coverage gaps.

1. Build a brief JSON (one entry per slide that wants a GIF):

```json
{
  "slides": [
    {"title": "Q2 Results", "desired_tone": ["professional", "energetic"], "desired_category": "emphasis/important-data"},
    {"title": "Thank you",  "desired_tone": ["calm"], "desired_category": "closing/thank-you"}
  ]
}
```

`desired_category` may be `"category/subcategory"` or just `"category"`.
`desired_tone` / `desired_tags` are optional lists.

2. Run the resolver:

```bash
python <LIB>/scripts/build_deck_with_gifs.py --brief brief.json --out mapping.json
```

3. Read `mapping.json`. Each entry is `{slide, gif, gif_id, candidates}` (or
   `gif: null` for a gap). Use `gif` (relative to `<LIB>/gifs/`) as the image.

This does **not** build the deck — it only decides which GIF goes where. Assemble
the actual slides with your normal tool (e.g. the `pptx` skill / pptxgenjs
`addImage`) using `<LIB>/gifs/<gif>` as the image path.

## Workflow B — single ad-hoc lookup

For one slide, read `index.json` and filter directly. Example intent
"celebratory reaction, professional tone, for a positive metric":

- keep `review_pending == false`
- `category == "reactions"`, `tone` contains `professional` OR `tags` contains
  `celebration`/`success`
- pick one (most recent by `date_added`, or any good fit)

Return `<LIB>/gifs/<filename>` and mention `recommended_use`.

## Inserting into the deck

- The asset path is `<LIB>/gifs/<filename>` (absolute path recommended for
  slide tools).
- **PowerPoint caveat:** animated GIFs play only in **PowerPoint Desktop**
  (Slide Show). They do NOT animate in PowerPoint Online, Keynote, Google Slides,
  or any PDF/image export (only the first frame). If the target isn't PowerPoint
  Desktop, treat the GIF as a static first-frame image and set expectations.

## Adding new GIFs to the library

When the user wants more coverage (a tone/category with no matches, or a new
brand):

```bash
# by tone (expanded to English queries via tone_to_query_map.json)
python <LIB>/scripts/fetch_by_brand_tone.py --brand "Acme" --tones energetic professional \
    --category reactions --subcategory celebration --rating g --limit 5

# by explicit search terms (best for meaning-specific subcategories)
python <LIB>/scripts/fetch_by_brand_tone.py --brand "Acme" --queries "thank you" applause \
    --category closing --subcategory thank-you --tones calm formal --rating g --limit 4
```

Requires `GIPHY_API_KEY` in `<LIB>/.env` (the script auto-loads it). New GIFs land
as `review_pending: true`. Then:

```bash
python <LIB>/scripts/validate_metadata.py   # lists what needs review
# a human fills tags/primary_emotion/recommended_use and sets review_pending=false
python <LIB>/scripts/build_index.py          # regenerate index.json
```

Only after `build_index.py` (and `review_pending: false`) are new GIFs usable by
Workflows A/B.

## Metadata fields (for reference)

`id`, `filename`, `category`, `subcategory`, `tags` (controlled vocabulary in
`schema/tags-controlled.json`), `tone` (one of: professional, casual, energetic,
calm, playful, formal, minimalist), `primary_emotion`, `recommended_use`,
`avoid_if`, `content_rating`, `review_pending`, `date_added`. Full JSON Schema:
`<LIB>/schema/gif-metadata.schema.json`.
