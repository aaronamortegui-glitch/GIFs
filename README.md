# GIF Library — cataloged GIFs for presentations

A local, metadata-cataloged repository of GIFs that **Claude Design** and **Claude Code**
can query programmatically when building presentations. GIFs are classified on two
independent axes and downloaded from GIPHY according to a brand's tone.

- **Structural axis** = physical folder (what the GIF does in a deck).
- **Meaning axis** = metadata fields `tags`, `tone`, `primary_emotion` (what it conveys).

`index.json` is the single source of truth for search. Consuming agents read it and never
crawl the folders directly.

---

## Repository layout

```
gif-library/
├── README.md
├── index.json                  # Master manifest — GENERATED, do not edit by hand
├── requirements.txt
├── schema/
│   ├── gif-metadata.schema.json   # JSON Schema for one GIF's metadata
│   └── tags-controlled.json       # Controlled tag vocabulary (no spelling/language variants)
├── gifs/
│   ├── reactions/        (celebration, approval, surprise, error-frustration, waiting-loading)
│   ├── transitions/      (intro, outro, topic-change)
│   ├── emphasis/         (key-point, important-data)
│   ├── collaboration/    (team, brainstorm-ideas)
│   └── closing/          (thank-you, call-to-action)
├── metadata/
│   └── {gif_id}.json           # One metadata file per GIF, mirrored into index.json
└── scripts/
    ├── fetch_by_brand_tone.py     # Search + download from GIPHY by brand tone
    ├── build_index.py             # Regenerate index.json from metadata/
    ├── validate_metadata.py       # Validate + list GIFs awaiting review
    ├── tone_to_query_map.json     # Editable tone -> English query mapping
    └── brand_tone.example.json    # Example run config (copy to brand_tone.json)
```

**Rules**
- Each GIF lives in **exactly one** category subfolder (the most specific one). "Belongs to
  several" is expressed via `tags`, not by duplicating files.
- A GIF's filename is its `id` (short hash) + `.gif` — never the original GIPHY name.
- `index.json` is the only file a consumer should read for search.

---

## Classification (two axes)

**Axis 1 — Function in the presentation** (= physical folder, stable taxonomy):
`reactions`, `transitions`, `emphasis`, `collaboration`, `closing`.

**Axis 2 — Tone / meaning** (= `tags`, `tone`, `primary_emotion`, free to grow):
Grows organically per GIF, but `tags` are drawn from a **controlled vocabulary**
(`schema/tags-controlled.json`) so you never get `success` vs `sucess` vs `exito`.
Allowed `tone` values: `professional`, `casual`, `energetic`, `calm`, `playful`,
`formal`, `minimalist`.

This enables two search styles:
- **By structure:** "give me a GIF in `transitions/intro`".
- **By meaning:** "give me a GIF tagged `celebration` with tone `professional`".

---

## Getting a GIPHY API key

1. Go to <https://developers.giphy.com/> and sign in / register (free).
2. Create an app → choose the **API** (not SDK) option → copy the API key.
3. Provide it to the script **via environment variable** (never hardcoded, never committed):

   ```powershell
   # Windows PowerShell
   $env:GIPHY_API_KEY = "your_key_here"
   ```
   ```bash
   # macOS / Linux
   export GIPHY_API_KEY=your_key_here
   ```

---

## Install

```bash
pip install -r requirements.txt   # just 'requests'
```

---

## Running the fetch script

Copy the example config and edit it (real configs are git-ignored):

```bash
cp scripts/brand_tone.example.json scripts/brand_tone.json
```

`brand_tone.json`:
```json
{
  "brand": "Acme Corp",
  "tones": ["energetic", "friendly", "professional"],
  "content_rating": "g",
  "target_category": "reactions",
  "target_subcategory": "celebration",
  "per_query_limit": 5,
  "selection": "trending"
}
```

Run it:

```bash
# From a config file
python scripts/fetch_by_brand_tone.py --config scripts/brand_tone.json

# Or fully from CLI flags
python scripts/fetch_by_brand_tone.py --brand "Acme" --tones energetic friendly \
    --category reactions --subcategory celebration --rating g --limit 5

# See what it would do without downloading anything
python scripts/fetch_by_brand_tone.py --config scripts/brand_tone.json --dry-run
```

What it does:
1. Maps each tone → 2-3 English queries via `scripts/tone_to_query_map.json`.
2. Searches GIPHY per query, filtered by `content_rating`.
3. Selects the best N (`trending` order, or GIPHY relevance) — configurable.
4. Downloads each GIF to `gifs/{category}/{subcategory}/{id}.gif`.
5. Writes `metadata/{id}.json` with inferred fields (dimensions, size, source URL, date)
   and **placeholders** for human fields (`tags`, `recommended_use`, `avoid_if`,
   `primary_emotion`). Every new GIF gets **`review_pending: true`**.
6. Runs `build_index.py` to regenerate `index.json`.

**Idempotent:** the script records each GIF's GIPHY `source_id`; running it again with the
same tones will **not** re-download GIFs already present.

**No auto-publishing:** the script never trusts its own category assignment. GIFs stay
`review_pending: true` until a human confirms category, tags and tone.

---

## Reviewing and publishing

```bash
python scripts/validate_metadata.py          # lists errors + the review queue
python scripts/validate_metadata.py --strict # non-zero exit if any error (for CI)
```

For each pending GIF, a human edits `metadata/{id}.json`:
- confirm/fix `category` + `subcategory` (move the file too if it changes),
- fill `tags` (from `schema/tags-controlled.json`), `tone`, `primary_emotion`,
  `recommended_use`, and optionally `avoid_if` / `brand_compatible`,
- set `review_pending: false`.

Then regenerate the index:
```bash
python scripts/build_index.py
```

---

## Read contract for Claude Design / Claude Code

Any agent inserting a GIF into a presentation must:
1. Read `index.json`.
2. Filter by `tone` and/or `tags` (and/or `category`/`primary_emotion`) for the slide context.
3. **Exclude any GIF with `review_pending: true`.**
4. Use `filename` for the asset path (relative to `gifs/`) and `recommended_use` as guidance
   for where/when to place it. Respect `avoid_if`.

Example query intent: *"celebratory reaction for a positive metric, professional tone"* →
filter `category == reactions`, `tone` contains `professional`, `tags` contains
`celebration` or `success`, `review_pending == false`.

---

## License & usage note

Before automating bulk downloads, review GIPHY's API & Terms of Use
(<https://developers.giphy.com/docs/api>) regarding:
- **Rate limits** on the free API key (requests per hour/day).
- **Attribution** and **local storage / caching** conditions for downloaded GIFs.
- **Internal vs external use** — terms can differ between internal-only decks and content
  that ships to external clients.

Each GIF carries a `license_note` field; this file's summary does not replace a legal
review for large-scale or public use. `brand_tone.json` and `.env` are git-ignored so keys
and client configs never get committed.
