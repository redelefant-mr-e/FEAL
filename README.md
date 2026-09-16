# FEAL Product CSV Databases (Figma Sites)

Scrapes product content from [feal.se](https://www.feal.se/ramper) (Swedish) and [feal.se/ramps](https://www.feal.se/ramps) (English), then exports UTF-8 CSVs for [Figma Sites CMS import](https://help.figma.com/hc/en-us/articles/35691883305879-Import-a-CMS-collection-from-a-CSV).

## Quick start

```bash
pip install -r requirements.txt
python3 scripts/scrape_feal.py
python3 scripts/host_images.py   # download, resize, host locally + rewrite CSV image URLs
```

CSVs are written under `data/csv/<category_key>/` (products + variants together per category).

## Collections (12 files)

| Category | Folder | Products | Variants |
|---|---|---|---|
| Portabla ramper | `portabla-ramper/` | `products_portabla-ramper.csv` | `variants_portabla-ramper.csv` |
| Fordonsramper | `fordonsramper/` | `products_fordonsramper.csv` | `variants_fordonsramper.csv` |
| Drive in-ramper | `drive-in-ramper/` | `products_drive-in-ramper.csv` | `variants_drive-in-ramper.csv` |
| System- och modulramper | `system-och-modulramper/` | `products_system-och-modulramper.csv` | `variants_system-och-modulramper.csv` |
| Tröskelramper och täckplåtar | `troskelramper-och-tackplatar/` | `products_troskelramper-och-tackplatar.csv` | `variants_troskelramper-och-tackplatar.csv` |
| Tillbehör / Accessories | `accessories/` | `products_accessories.csv` | `variants_accessories.csv` |

`category_key` is present on every row so the category is easy to identify after import.

## Data model

- **Products** = leaf product pages (e.g. Fasta ramper) **or** Systemramp section groups (Ramper, Vilplaner, Modultrappor, Räcken).
- **Variants** = size/model SKUs (article numbers such as `11068`).
- **Accessories** = “Övriga delar / Other parts” from Systemramp Standard & Professional (own category).
- Same physical product listed in two site categories is kept as **separate product rows** (distinct slugs/URLs).

Link in Figma: match `variants.product_slug` → `products.Slug` (plain-text; Figma CMS has no relations).

## Images (stable hosting)

Figma Sites Image fields only accept **JPEG, PNG, GIF** — **not WebP**.

`scripts/host_images.py`:

1. Downloads every unique product image URL from the CSVs
2. Fits each image inside a **1600×1600** box (preserve aspect ratio, **no crop**, **no upscale**)
3. Saves opaque images as optimized JPEG (quality 82) and images with transparency as PNG under `assets/images/`
4. Rewrites CSV `image*` columns to **jsDelivr** URLs for a **public** GitHub repo
5. Writes `assets/image_url_map.json` (old → new URL)

URL pattern:

```text
https://cdn.jsdelivr.net/gh/<owner>/<repo>@main/assets/images/<file>
```

Repo is detected from `git remote origin`, or set explicitly:

```bash
GITHUB_REPO=owner/repo python3 scripts/host_images.py
```

Default fallback if no remote is set: `redelefant-mr-e/FEAL`.

**Important:** push this repo publicly (and keep `assets/images/` in git) so jsDelivr can serve the files. Until then, Figma cannot load the new URLs.

After a fresh scrape, either re-run `host_images.py` for new assets, or rely on `scrape_feal.py` applying the existing URL map for known feal.se URLs.

## Figma Sites import checklist

1. Export is already UTF-8 CSV with required **`Title`** and **`Slug`** columns.
2. In a Figma Sites file: **CMS → Add collection → Import CSV**.
3. Map fields:
   - `Title` → Title
   - `Slug` → Slug
   - `image_1`…`image_8` / `image` → **Image** (jsDelivr HTTPS URLs after `host_images.py`)
   - `source_url_sv` / `source_url_en` → Link
   - descriptions / features → Rich text or Plain text
   - remaining columns → Plain text
4. Limits while in beta: ≤200 items and ≤100 fields per collection (these exports are under both).
5. Import products and variants as **separate collections** per category (or one products + one variants collection per category file pair).

## Bilingual fields

Side-by-side columns: `name_sv` / `name_en`, `description_sv` / `description_en`, `features_sv` / `features_en`, `specs_raw_sv` / `specs_raw_en`, etc. `Title` uses the English name for Figma’s primary label.

Normalized variant metrics (`length_mm`, `weight_kg`, …) are metric-first; original copy stays in `specs_raw_*`.

## Re-scrape

```bash
python3 scripts/scrape_feal.py
python3 scripts/host_images.py   # only needed when new feal.se image URLs appear
```
