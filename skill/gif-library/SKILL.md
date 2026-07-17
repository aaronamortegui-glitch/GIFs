---
name: gif-library
description: >-
  Pick and insert cataloged GIFs into presentations, slide decks, or any
  fixed-canvas design using the shared GIF library (a public GitHub repo with an
  index.json catalog). Use this whenever the user is building or editing a
  deck/presentation/slides and wants to add a GIF, reaction, or animation — or
  asks to "find a GIF for this slide", "add a celebration GIF", "put something
  animated here", or mentions the gif library / gif catalog. Also use to add new
  GIFs to the library from GIPHY by tone or search term. Trigger even when the
  user doesn't say "gif-library" explicitly but clearly wants a GIF that fits a
  slide's tone/meaning.
---

# GIF Library

A shared, metadata-cataloged repository of GIFs for presentations. Each GIF is
classified by **function** (`reactions`/`transitions`/`emphasis`/`collaboration`/
`closing`) and by **meaning** (`tags`, `tone`, `primary_emotion`). You pick GIFs by
intent — "celebratory, professional, for a positive metric" — instead of eyeballing
files.

## The library lives in a public GitHub repo

Repo: **`aaronamortegui-glitch/GIFs`** (public). Reference it by URL — this works in
any environment (claude.ai web or Claude Code), no local checkout required:

- **Catalog (search index):**
  `https://raw.githubusercontent.com/aaronamortegui-glitch/GIFs/main/index.json`
  (plain JSON — fetch it directly.)
- **A GIF asset**, given its `filename` field (e.g. `reactions/celebration/88e1bb887d.gif`):
  `https://media.githubusercontent.com/media/aaronamortegui-glitch/GIFs/main/gifs/<filename>`

Important: the GIFs are stored with **Git LFS**. The `media.githubusercontent.com/media/...`
URL above returns the real animated GIF. The ordinary `raw.githubusercontent.com/.../gifs/...`
URL returns only an LFS pointer file — **do not use raw for the GIF binaries**, only for
`index.json`.

**Optional local fast path (Claude Code only):** if a local clone exists (via
`GIF_LIBRARY_PATH` env var, default `C:\Repos\gif-library`), you may read the files and
run the bundled scripts locally instead of fetching over the network. If neither the
network nor a clone is available, tell the user.

`index.json` is the **single source of truth for search** — always use it; never try to
list the repo folders.

## The read contract (non-negotiable)

When choosing a GIF for a slide:

1. Get the catalog: fetch `index.json` from the URL above (or read the local clone). It
   has a `gifs` array.
2. **Exclude any GIF with `review_pending: true`** — those are unconfirmed and must not
   be used.
3. Filter by the slide's context: match `category`/`subcategory`, and intersect `tone`
   and/or `tags` (a GIF matches if it shares at least one value).
4. Build the asset URL from the entry's `filename` (the media URL above), and use
   `recommended_use` as placement guidance. Respect `avoid_if`.
5. If nothing matches, **do not invent or force a GIF** — leave the slide without one and
   tell the user which tone/category has no coverage, so they can add GIFs there.

This exists because the library mixes confirmed and unconfirmed assets; shipping a
`review_pending` GIF, or jamming an off-tone GIF onto a slide, is worse than no GIF.

## Response style — deliver first, don't over-explain

Lead with the pick: the GIF and its media URL, plus a one-line "when to show it." Keep it
tight. The user asked for a GIF, not a report.

- Add a caveat **only when it materially affects the choice** — most importantly when the
  user asked for a specific `tone`/`tag` that no confirmed GIF actually has. Then say so in
  **one short sentence** (e.g. "closest confirmed match — none are tagged `professional`").
  This honesty is the whole point: never silently pass off an off-tone GIF as an exact
  match. But one line is enough; don't offer to "leave the slide empty" unless the mismatch
  is severe.
- Do **not** surface incidental metadata (`brand_compatible`, `content_rating`, `id`,
  emotion) unless the user asks. Fields like `brand_compatible` may hold test values and
  are just noise in a normal answer.
- Don't interrogate. Assume the user wants the GIF. Offer at most **one** alternative in a
  single line. Mention the PowerPoint-animation caveat briefly and at most once (per deck,
  not per GIF) — or skip it if the target is already known.

## Workflow A — resolve GIFs for a whole deck

Given several slides, decide the GIF per slide by applying the read contract to
`index.json`.

1. Fetch `index.json` and keep only `review_pending == false` entries.
2. For each slide, from its title/context derive a desired `category`/`subcategory` and/or
   `tone`/`tags`, then filter (intersection). Pick one (most recent by `date_added`, or any
   strong fit). If none, record it as a gap.
3. Produce a mapping: `slide -> {filename, asset_url, recommended_use}` (or `null` + the
   gap reason). Report "N of M slides without a GIF" at the end.

**Local shortcut (Claude Code with a clone):** the repo bundles a resolver that already
implements this. Write a brief JSON and run it:

```json
{"slides": [
  {"title": "Q2 Results", "desired_tone": ["professional","energetic"], "desired_category": "emphasis/important-data"},
  {"title": "Thank you", "desired_category": "closing/thank-you"}
]}
```

```bash
python <LIB>/scripts/build_deck_with_gifs.py --brief brief.json --out mapping.json
```

`desired_category` may be `"category/subcategory"` or just `"category"`. This only decides
which GIF goes where — it does not build the deck.

## Workflow B — single ad-hoc lookup

For one slide, fetch `index.json` and filter directly. Example "celebratory reaction,
professional tone, for a positive metric": keep `review_pending == false`,
`category == "reactions"`, `tone` contains `professional` OR `tags` contains
`celebration`/`success`; pick one; return its media URL and `recommended_use`.

## Inserting into the deck

- Image source = the media URL:
  `https://media.githubusercontent.com/media/aaronamortegui-glitch/GIFs/main/gifs/<filename>`
  (or the local file path if you have a clone). Slide tools can download from that URL.
- **PowerPoint caveat:** animated GIFs play only in **PowerPoint Desktop** (Slide Show).
  They do NOT animate in PowerPoint Online, Keynote, Google Slides, or any PDF/image
  export (only the first frame). If the target isn't PowerPoint Desktop, treat the GIF as
  a static first-frame image and set expectations.

## Adding new GIFs to the library (maintainer task, local only)

Adding GIFs requires a local clone of the repo and a GIPHY API key, so it runs in Claude
Code, not on the web:

```bash
# by explicit search terms (best for a specific subcategory's meaning)
python <LIB>/scripts/fetch_by_brand_tone.py --brand "Acme" --queries "thank you" applause \
    --category closing --subcategory thank-you --tones calm formal --rating g --limit 4
# or by tone (expanded via tone_to_query_map.json)
python <LIB>/scripts/fetch_by_brand_tone.py --brand "Acme" --tones energetic professional \
    --category reactions --subcategory celebration --rating g --limit 5
```

Requires `GIPHY_API_KEY` in `<LIB>/.env` (auto-loaded). New GIFs land as
`review_pending: true`. Then a human fills `tags`/`primary_emotion`/`recommended_use` and
sets `review_pending: false`; run `python <LIB>/scripts/build_index.py` to regenerate
`index.json`; then commit + push so the public catalog updates. Only after that are the
GIFs usable by Workflows A/B.

## Metadata fields (reference)

`id`, `filename`, `category`, `subcategory`, `tags` (controlled vocabulary), `tone` (one
of: professional, casual, energetic, calm, playful, formal, minimalist),
`primary_emotion`, `recommended_use`, `avoid_if`, `content_rating`, `review_pending`,
`date_added`.
