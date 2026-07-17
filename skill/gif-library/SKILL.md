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
  `https://raw.githubusercontent.com/aaronamortegui-glitch/GIFs/main/gifs/<filename>`

Both the catalog and the GIFs are plain files on `raw.githubusercontent.com` — fetch or
download them directly. (This host is reachable on claude.ai's network allowlist.)

The raw GIF URL returns the **actual GIF bytes** (a `GIF89a` file, roughly 0.2–9 MB) — it
is a normal file, NOT a Git LFS pointer, and there is no LFS anywhere in this repo anymore.
So: download that **single** file from its raw URL and embed it. Do **not** download the
whole repository archive (the repo ZIP is ~100 MB); you only need the one ~1 MB GIF. If a
raw response ever looks like a tiny text file starting with `version https://git-lfs...`,
that's a stale cache — just retry the same raw URL.

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
4. Build the asset URL from the entry's `filename` (the raw URL above), and use
   `recommended_use` as placement guidance. Respect `avoid_if`.
5. If nothing matches, **do not invent or force a GIF** — leave the slide without one and
   tell the user which tone/category has no coverage, so they can add GIFs there.

This exists because the library mixes confirmed and unconfirmed assets; shipping a
`review_pending` GIF, or jamming an off-tone GIF onto a slide, is worse than no GIF.

## Trust the catalog — no re-vetting at build time

A **published** GIF (`review_pending == false`) has already been vetted during curation:
its category, tone, tags, and content-appropriateness (including copyright/brand safety)
were confirmed by a human before it was published. So at build time, **trust it**:

- If a GIF's `category`/`subcategory` matches what the slide asks for (and tone/tags if
  specified), **use it — directly**. That match is the decision.
- Do **not** re-evaluate the GIF at insertion time: don't preview its frames, don't
  re-judge whether it "works", don't re-assess content or copyright. That vetting lives in
  the curation step, not here — repeating it every build is exactly what makes this slow.
- If several published GIFs match, just **pick one** (any is fine — e.g. random, or the
  most recent by `date_added`). Don't agonize or compare candidates frame-by-frame.
- The only build-time check is the read contract itself: exclude `review_pending == true`,
  and if literally nothing matches the requested category/tone, say so (don't force a
  mismatch).

If a published GIF turns out to be inappropriate (e.g. copyright/brand risk), that's a
**catalog** problem to fix at the source (unpublish/remove it), not something to re-check
on every deck. Mention it to the user in one line so they can clean the catalog, but still
proceed with the build.

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
`celebration`/`success`; pick one; return its raw URL and `recommended_use`.

## Inserting into the deck — just build it

When the user asks to put the GIF into a presentation (or asks for a deck/slide), **do it**
— don't stop to ask which candidate or whether it's PowerPoint. Pick the best match, build
the slide, and insert the GIF. Ask only if there is genuinely no acceptable match at all.

- Image source = the raw URL:
  `https://raw.githubusercontent.com/aaronamortegui-glitch/GIFs/main/gifs/<filename>`
  (or the local file path if you have a clone). Download it and embed it (e.g. the `pptx`
  skill's `addImage`). This host is reachable on claude.ai, so the download works on the web.
- **PowerPoint note (mention once, briefly):** animated GIFs play only in PowerPoint
  Desktop (Slide Show); in PowerPoint Online, Keynote, Google Slides, or PDF/image export
  they show the first frame. Insert the GIF anyway — just note this once, don't let it block
  building the deck.

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
