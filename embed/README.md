# FEAL embeds (Figma Sites)

## Global site chrome (all pages)

Smooth same-origin page fade + mobile menu reset when a nav link leaves an open menu.

Add **once** under **Site settings → Custom code → end of `<body>`**:

```html
<script
  src="https://cdn.jsdelivr.net/gh/redelefant-mr-e/FEAL@main/embed/site-chrome.js?v=2"
  defer
></script>
```

- **Page transition:** fades `html` on internal link clicks (`View Transitions` when available). Honors `prefers-reduced-motion`.
- **Menu reset:** if `stäng` / `close` is present, closes the menu, waits briefly for Figma’s boolean to update, then navigates. On the next page, retries close if the open state hydrates late. Does not open the menu; does not touch other UI.
- **Richtext headings:** `div.root h1–h6` get a little vertical margin (`1.25em` top / `0.75em` bottom; no top margin if the heading is first in the block).

> **Cache note:** bump `?v=` after updates (jsDelivr caches `@main`).

---

## Variant picker (product pages)

Small embeddable size selector for application product pages. It reads the page
slug, loads variants from static JSON, and mirrors the Style Guide
`embed-feature` UI (dropdown → specs → Offertförfrågan mailto).

### Drop into Figma Sites

On each product page (or the CMS product template), add a **Custom code / Embed** block:

```html
<div id="feal-variant-picker"></div>
<script
  src="https://cdn.jsdelivr.net/gh/redelefant-mr-e/FEAL@main/embed/variant-picker.js?v=20260918f"
  defer
></script>
```

**Important (CMS template):** do **not** hardcode `data-product` on the shared product template (e.g. `data-product="enkelskena"`). That forces every product page to the same sizes. Leave the mount empty and let the URL slug resolve the product. Only set `data-product` for a one-off override on a single page.

Optional language override if auto-detect is wrong:

```html
<div id="feal-variant-picker" data-lang="en"></div>
```

> **Cache note:** jsDelivr caches `@main` aggressively (up to 7 days). After updates, bump the `?v=` query, or purge:  
> `https://purge.jsdelivr.net/gh/redelefant-mr-e/FEAL@main/embed/variant-picker.css`

### How the product is resolved

1. `data-product="fordonsmonterad-2-delad-ramp"` on the mount node (optional override — not for templates)
2. Else `?product=…` query param
3. Else last path segment of `window.location.pathname`  
   e.g. `/sv-fordonsramper-produkt/fordonsmonterad-3-delad-ramp` → `fordonsmonterad-3-delad-ramp`

Prefer CMS **Slug** values that match catalog keys in `embed/data/variants.json`. A few live Sites slugs are aliased at build time:

| CMS / URL slug | Catalog key |
|---|---|
| `fast-skena` | `enkelskena` |
| `fordonsmonterade-2-delade-ramper` | `fordonsmonterad-2-delad-ramp` |
| `fordonsmonterad-2-delad-lastramp` | `fordonsmonterad-2-delad-lastram` |
| `teleskopisk-vikbar-skena` | `vikbar-teleskopisk-skena` |

### CMS variant tables (Figma Sites)

Variant measure columns come from the Excel sources in `OneDrive_1_16.9.2026/` and differ by collection:

| Collection CSV | Typical Excel headers (beyond Artikelnummer / Namn) |
|---|---|
| `data/csv/application/fordon/variants_fordon.csv` | Längd, Bredd åkyta, Höjd ihopvikt, **Totalbredd**, **Djup ihopvikt**, Lastvikt/SWL |
| `data/csv/application/portable/variants_portable.csv` | Längd, Bredd åkyta, Längd/Bredd ihopvikt (where relevant), Vikt, Lastvikt/SWL, Rek. Maxhöjd |
| `data/csv/application/transport/variants_transport.csv` | Längd, Bredd åkyta, Höjd/Längd ihopvikt, Vikt, Lastvikt/SWL |

After rebuilding CSVs:

1. Re-import the updated `variants_*.csv` into each Figma CMS collection (add any new fields such as `total_width_mm`, `folded_depth_mm`, `folded_width_mm`).
2. On **fordonsmonterade** product tables, bind **Totalbredd** + **Djup ihopvikt** — do **not** bind **Vikt** (not in that Excel).
3. Keep portable/transport tables on their own Excel headers.

The embed picker only shows non-empty measures for the selected variant (same source fields).

Language (first match wins):

1. `data-lang="sv|en"` on the mount node
2. `?lang=sv|en` query param
3. Path segment `/en/` **or** a slug starting with `en-` (e.g. `/en-portabla-ramper-produkt/…`)
4. `<html lang="en">` (Figma Sites **Language** page setting)
5. Default: `sv`

### Optional attributes

| Attribute | Purpose |
|---|---|
| `data-product` | Force product slug |
| `data-lang` | `sv` or `en` |
| `data-variants-url` | Alternate JSON URL (defaults to sibling `data/variants.json`) |

### Embed height (Figma Sites)

Sites embeds are usually a **fixed height** and do not auto-grow with content.

- Size the embed for the **selected** state (dropdown + specs + button): about **500px** tall (and full content width, ~616px+).
- The open size list is an **overlay** (does not grow the page), so you do not need extra height for long variant lists.
- If anything still clips, give the embed `overflow: visible` if Sites allows it, or bump height slightly.

### Typography / breakpoint modes

Type size + line-height follow Style Guide variables (`type/size/utility`, `type/line-height`) across **Desktop / Tablet / Mobile**:

| Token | Desktop | Tablet (≤991) | Mobile (≤767) |
|---|---:|---:|---:|
| h2 | 24/36 | 22/34 | 20/32 |
| body-l | 18/28 | 17/26 | 16/24 |
| body | 16/24 | 16/22 | 16/22 |
| body-s | 14/22 | 13/20 | 13/20 |
| button | 14/20 | 14/20 | 13/18 |
| label | 16/16 | 16/16 | 14/14 |

Applied via viewport `@media` and matching `@container` rules on the embed width.

## Quote button

`mailto:order@feal.se` with subject/body including the **selected variant name**
(and article number when present). Same address for SV and EN.

## Rebuild data after CSV changes

```bash
PYTHONPATH=. python3 scripts/build_variant_embed_data.py
```

Also runs automatically at the end of `scripts/build_application_csvs.py`.

## Audit live product slugs

Check that every linked product page on the Figma Sites preview resolves to a catalog key (including aliases):

```bash
PYTHONPATH=. python3 scripts/audit_variant_product_slugs.py
```

If anything is `MISS`, add it to `SLUG_ALIASES` in `scripts/build_variant_embed_data.py` and rebuild.

## Local preview

Open `embed/preview.html` via a local static server (fetch needs HTTP):

```bash
cd embed && python3 -m http.server 8765
# http://localhost:8765/preview.html
```

## Files

| File | Role |
|---|---|
| `site-chrome.js` | Global page fade, mobile menu close, richtext heading margins |
| `variant-picker.js` | Mount, slug/lang, UI, mailto |
| `variant-picker.css` | Figma Style Guide tokens |
| `data/variants.json` | Application variants keyed by `product_slug` |
| `preview.html` | Local smoke test |
