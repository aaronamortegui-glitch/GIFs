# GIF Library — cataloged GIFs for presentations

A local, metadata-cataloged repository of GIFs that **Claude Design** and **Claude Code**
can query programmatically when building presentations. GIFs are classified on two
independent axes and downloaded from GIPHY according to a brand's tone.

- **Structural axis** = physical folder (what the GIF does in a deck).
- **Meaning axis** = metadata fields `tags`, `tone`, `primary_emotion` (what it conveys).

`index.json` is the single source of truth for search. Consuming agents read it and never
crawl the folders directly.

Remote: <https://github.com/aaronamortegui-glitch/GIFs> (private)

---

## 1. What this is

A curated set of GIFs, each described by tone/meaning metadata, so an agent (or a person)
can pick the right GIF for a slide by **intent** — "celebratory, professional, for a
positive metric" — instead of eyeballing files. Everything searchable lives in
`index.json`; the GIFs themselves are stored with **Git LFS** (they're binary).

---

## 2. Setup (cloning the repo)

```bash
git clone https://github.com/aaronamortegui-glitch/GIFs.git
cd GIFs
git lfs pull          # pull the actual GIF binaries (LFS)
copy .env.example .env    # Windows  (macOS/Linux: cp .env.example .env)
pip install -r requirements.txt
```

Then get a **free GIPHY API key** at <https://developers.giphy.com/> (choose **API**, not
SDK) and paste it into `.env`:

```
GIPHY_API_KEY=your_key_here
```

`.env` is git-ignored — your key never leaves your machine. The scripts read `.env`
automatically, so you don't need to export anything.

---

## 3. Repository layout

```
GIFs/
├── README.md
├── index.json                  # Master manifest — GENERATED, do not edit by hand
├── requirements.txt
├── .env.example                # Copy to .env and add your key
├── .gitattributes              # Git LFS tracking for gifs/**/*.gif
├── schema/
│   ├── gif-metadata.schema.json   # JSON Schema for one GIF's metadata
│   └── tags-controlled.json       # Controlled tag vocabulary
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
    ├── build_deck_with_gifs.py    # Resolve which GIF goes on each slide of a brief
    ├── tone_to_query_map.json     # Editable tone -> English query mapping
    └── brand_tone.example.json    # Example run config
```

**Rules**
- Each GIF lives in **exactly one** category subfolder (the most specific one). "Belongs to
  several" is expressed via `tags`, not by duplicating files.
- A GIF's filename is its `id` (short hash) + `.gif` — never the original GIPHY name.
- `index.json` is the only file a consumer reads for search.

---

## 4. Classification (two axes)

**Axis 1 — Function in the presentation** (= physical folder, stable taxonomy):
`reactions`, `transitions`, `emphasis`, `collaboration`, `closing`.

**Axis 2 — Tone / meaning** (= `tags`, `tone`, `primary_emotion`, grows freely):
`tags` are drawn from a **controlled vocabulary** (`schema/tags-controlled.json`) to avoid
variants (`success` vs `sucess` vs `exito`). Allowed `tone` values: `professional`,
`casual`, `energetic`, `calm`, `playful`, `formal`, `minimalist`.

---

## 5. Adding new GIFs

```bash
# 1. Search + download from GIPHY by tone (writes review_pending=true metadata)
python scripts/fetch_by_brand_tone.py --config scripts/brand_tone.json
#    or with CLI flags:
python scripts/fetch_by_brand_tone.py --brand "Acme" --tones energetic professional \
    --category reactions --subcategory celebration --rating g --limit 5

# 2. List what needs human review
python scripts/validate_metadata.py

# 3. For each pending metadata/*.json, a human fills:
#    tags, primary_emotion, recommended_use, avoid_if, brand_compatible
#    confirms category/subcategory (move the file if it changes)
#    and sets  review_pending: false

# 4. Regenerate the index — only now are the GIFs available to consumers
python scripts/build_index.py
```

**Idempotent:** re-running the fetch script never re-downloads a GIF already present (it
checks the GIPHY `source_id`).

**Review-gated:** the fetch script never trusts its own category guess — every new GIF is
`review_pending: true` and is excluded from consumers until a human confirms it.

---

## 6. Read contract for Claude Design / Claude Code

Any agent inserting a GIF into a presentation must:
1. Read `index.json` — never crawl the folders by hand.
2. Filter by `tone` / `tags` / `category` (and `primary_emotion`) for the slide context.
3. **Exclude any GIF with `review_pending: true`.**
4. Use `filename` for the asset path (relative to `gifs/`) and `recommended_use` as
   placement guidance. Respect `avoid_if`.

`scripts/build_deck_with_gifs.py` implements this contract: given a brief (slides with
optional `desired_tone` / `desired_category`), it returns a slide → GIF `filename` mapping
and reports any slide with no match (it never invents one).

---

## 7. Technical note — GIFs in PowerPoint

Animated GIFs **play** in **PowerPoint Desktop** (during Slide Show). They do **not**
animate in:
- PowerPoint Online (web),
- Keynote,
- Google Slides,
- any export to PDF or image (only the first frame is captured).

If the deck will be presented from PowerPoint Desktop, GIFs animate. For any other target,
treat the GIF as a static first-frame image.

---

## 8. License & usage note

Before automating bulk downloads or redistributing outside internal use, review GIPHY's
API & Terms of Use (<https://developers.giphy.com/docs/api>) regarding rate limits (free
key = 100 API calls/hour), attribution, local caching, and internal-vs-external
distribution. Each GIF carries a `license_note`; this summary does not replace legal review
for large-scale or public use. `.env` and `brand_tone.json` are git-ignored so keys and
client configs are never committed.
