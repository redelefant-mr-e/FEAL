# FEAL — page meta titles & descriptions

Draft SEO copy for non-product pages on the Figma Sites rebuild.  
Paste into **Site settings → per-page Title + Meta description**. Product detail / CMS pages are out of scope.

**Current preview state:** every page uses title `feal`, description `Created with Figma`, and `robots: noindex`. Replace these before launch and turn off noindex.

**How to apply (Figma Sites)**

1. Open the Sites file → Site settings (or the page’s settings).
2. Set **Title** and **Meta description** per page (site-wide values are fallbacks only).
3. Set language code to `sv` or `en` per page.
4. Before go-live: disable “exclude from search engines” / remove `noindex`.
5. Optional: site favicon + social sharing image (1200×630).

Title pattern: `Page | FEAL` (home is brand-forward). Descriptions aim for ~140–160 characters.

---

## Swedish

| Page | Path | Title | Description |
|------|------|-------|-------------|
| Home | `/` | FEAL – Improving life \| Ramplösningar för mobilitet, transport och special | Vi bygger inte ramper för rampernas skull. FEAL utvecklar lösningar för självständighet, effektivare arbete och trygga uppdrag – från mobilitet till transport och specialfordon. |
| Om Feal | `/sv-om-feal` | Om FEAL \| Byggt av människor som bryr sig sedan 1991 | FEAL i Horndal, Bergslagen. Sedan 1991 utvecklar och tillverkar vi ramplösningar med hantverk, kvalitet och omtanke – improving life på riktigt. |
| Kontakt | `/sv-kontakt` | Kontakta FEAL \| Horndal – telefon, e-post och team | Kontakta FEAL i Horndal. Telefon, e-post och kontaktuppgifter till VD, försäljning, produktion, ekonomi, inköp, konstruktion och logistik. |
| Mobilitet | `/sv-mobilitet` | Mobilitet \| Ramplösningar för självständighet och tillgänglighet \| FEAL | Säg ja till livet. FEALs mobilitetsramper – fordonsmonterade, portabla, modulära och tröskelramper – skapar tillgänglighet på egna villkor. |
| Transport | `/sv-transport-ramper` | Transport \| Lastramper för smidigare lastning \| FEAL | Smidigare lastning. Effektivare arbetsdagar. FEALs lastramper och lastskenor för servicefordon, transportbilar och släp – lätta, robusta och säkra. |
| Special | `/sv-special` | Special \| Ramper för ambulans, räddning och specialfordon \| FEAL | När varje sekund räknas. FEAL tillverkar tillförlitliga ramper för ambulans, räddning och andra specialfordon där säkerhet och driftsäkerhet är avgörande. |

---

## English

*(Language switcher exists; EN routes are not fully wired yet. Use these when EN pages go live — adjust paths to match your final slug scheme.)*

| Page | Suggested path | Title | Description |
|------|----------------|-------|-------------|
| Home | `/en` (or EN home slug) | FEAL – Improving life \| Ramps for mobility, transport and special vehicles | We don’t build ramps for the sake of ramps. FEAL develops solutions for independence, efficient work and reliable missions — from everyday mobility to transport and special vehicles. |
| About | `/en-about` (TBD) | About FEAL \| Built by people who care since 1991 | FEAL in Horndal, Bergslagen. Since 1991 we design and manufacture ramp solutions with craftsmanship, quality and care — improving life for real. |
| Contact | `/en-contact` (TBD) | Contact FEAL \| Horndal – phone, email and team | Get in touch with FEAL in Horndal. Phone, email and contacts for leadership, sales, production, finance, purchasing, engineering and logistics. |
| Mobility | `/en-mobility` (TBD) | Mobility \| Ramp solutions for independence and accessibility \| FEAL | Say yes to life. FEAL mobility ramps — vehicle-mounted, portable, modular and threshold ramps — create accessibility on your own terms. |
| Transport | `/en-transport` (TBD) | Transport \| Loading ramps for smoother operations \| FEAL | Smoother loading. More efficient workdays. FEAL loading ramps and rails for service vans, transport vehicles and trailers — light, robust and safe. |
| Special | `/en-special` (TBD) | Special \| Ramps for ambulance, rescue and specialty vehicles \| FEAL | When every second counts. FEAL builds reliable ramps for ambulance, rescue and other specialty vehicles where safety and uptime are non-negotiable. |

---

## Housekeeping checklist

Findings from the live preview and this repo. Fix in Figma / process as needed; this pass only delivers meta copy + `embed/site-chrome.js`.

### Figma Sites (manual)

- [ ] Replace site-wide title / `Created with Figma` metas with the table above
- [ ] Remove `noindex` before public launch
- [ ] Strip leftover **Lorem ipsum** on `/sv-special` (start and end of body)
- [ ] Fix typo **“Säj ja!” → “Säg ja!”** on Mobilitet (and update meta title if you change on-page H1)
- [ ] Normalize **rampar → ramper** on Mobilitet cards (Portabla / Modulära / Tröskel)
- [ ] Wire **English** switcher + EN page paths; align suggested EN paths above
- [ ] Fix **Produkter** nav (currently points to `/`); submenu to hubs or a real products page
- [ ] Add favicon, OG/social image (1200×630), language codes per page
- [ ] Install global site chrome (see [`embed/README.md`](../embed/README.md)): page transition + mobile menu reset + richtext heading margins (`?v=2`)

### This repo

- [ ] After pushing `embed/site-chrome.js`, bump `?v=` in the Sites custom-code script tag (jsDelivr caches `@main`)
- [ ] Optional: ignore `.DS_Store`; keep `OneDrive_1_16.9.2026/` out of git if it is local source-only
- [ ] Optional: dedupe the doubled “Figma Sites import checklist” section in root `README.md`
