# FEAL variant picker (Figma Sites embed)

Small embeddable size selector for application product pages. It reads the page
slug, loads variants from static JSON, and mirrors the Style Guide
`embed-feature` UI (dropdown → specs → Offertförfrågan mailto).

## Drop into Figma Sites

On each product page (or the CMS product template), add a **Custom code / Embed** block:

```html
<div id="feal-variant-picker" data-lang="sv"></div>
<script
  src="https://cdn.jsdelivr.net/gh/redelefant-mr-e/FEAL@main/embed/variant-picker.js"
  defer
></script>
```

English pages:

```html
<div id="feal-variant-picker" data-lang="en"></div>
<script
  src="https://cdn.jsdelivr.net/gh/redelefant-mr-e/FEAL@main/embed/variant-picker.js"
  defer
></script>
```

### How the product is resolved

1. `data-product="fordonsmonterad-2-delad-ramp"` on the mount node (optional override)
2. Else `?product=…` query param
3. Else last path segment of `window.location.pathname`  
   e.g. `/fordonsmonterad-2-delad-ramp` → `fordonsmonterad-2-delad-ramp`

Language: `data-lang="sv|en"` (default `sv`). If omitted, paths containing `/en/` use English.

### Optional attributes

| Attribute | Purpose |
|---|---|
| `data-product` | Force product slug |
| `data-lang` | `sv` or `en` |
| `data-variants-url` | Alternate JSON URL (defaults to sibling `data/variants.json`) |

### Embed height (Figma Sites)

Sites embeds are usually a **fixed height** and do not auto-grow with content.

- Size the embed for the **selected** state (dropdown + specs + button): about **560px** tall (and full content width, ~616px+).
- The open size list is an **overlay** (does not grow the page), so you do not need extra height for long variant lists.
- If anything still clips, give the embed `overflow: visible` if Sites allows it, or bump height slightly.

### Typography / breakpoint modes

v1 uses the type sizes bound on the Style Guide **embed-feature** component (H2 24/36, body-l 18/28, etc.). Figma variable **modes** (Desktop / Mobile) are not switched in CSS yet — the API returns one mode’s values, and for these utility styles Mobile currently reports the same H2/body-l sizes. If Display/H1-scale modes differ for this block on your Sites breakpoints, share the mode table (or a Desktop vs Mobile screenshot) and we can add matching `@media` / `@container` rules.

## Quote button

`mailto:order@feal.se` with subject/body including the **selected variant name**
(and article number when present). Same address for SV and EN.

## Rebuild data after CSV changes

```bash
PYTHONPATH=. python3 scripts/build_variant_embed_data.py
```

Also runs automatically at the end of `scripts/build_application_csvs.py`.

## Local preview

Open `embed/preview.html` via a local static server (fetch needs HTTP):

```bash
cd embed && python3 -m http.server 8765
# http://localhost:8765/preview.html
```

## Files

| File | Role |
|---|---|
| `variant-picker.js` | Mount, slug/lang, UI, mailto |
| `variant-picker.css` | Figma Style Guide tokens |
| `data/variants.json` | Application variants keyed by `product_slug` |
| `preview.html` | Local smoke test |
