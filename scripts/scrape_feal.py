#!/usr/bin/env python3
"""
Scrape FEAL product pages (Swedish + English) into Figma Sites CMS CSVs.

Outputs one products_*.csv and one variants_*.csv per category under
data/csv/<category_key>/.
"""

from __future__ import annotations

import csv
import json
import re
import time
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, NavigableString, Tag

BASE = "https://www.feal.se"
ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "csv"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FEAL-product-scraper/1.0; +local)",
    "Accept-Language": "sv,en;q=0.8",
}
REQUEST_DELAY_S = 0.35

# Top-level categories → CSV file keys and display names
CATEGORIES: dict[str, dict[str, str]] = {
    "portabla-ramper": {
        "sv_slug": "portabla-ramper",
        "en_slug": "portable-ramps",
        "sv": "Portabla ramper",
        "en": "Portable Ramps",
        "sv_path": "/ramper/portabla-ramper",
        "en_path": "/ramps/portable-ramps",
    },
    "fordonsramper": {
        "sv_slug": "fordonsramper",
        "en_slug": "vehicle-ramps",
        "sv": "Fordonsramper",
        "en": "Vehicle ramps",
        "sv_path": "/ramper/fordonsramper",
        "en_path": "/ramps/vehicle-ramps",
    },
    "drive-in-ramper": {
        "sv_slug": "drive-in-ramper",
        "en_slug": "drive-in-ramps",
        "sv": "Drive in-ramper",
        "en": "Drive in ramps",
        "sv_path": "/ramper/drive-in-ramper",
        "en_path": "/ramps/drive-in-ramps",
    },
    "system-och-modulramper": {
        "sv_slug": "system-och-modulramper",
        "en_slug": "system-and-modular-ramps",
        "sv": "System- och modulramper",
        "en": "System and modular ramps",
        "sv_path": "/ramper/system-och-modulramper",
        "en_path": "/ramps/system-and-modular-ramps",
    },
    "troskelramper-och-tackplatar": {
        "sv_slug": "troeskelramper-och-taeckplatar",
        "en_slug": "threshold-ramps-cover-plates",
        "sv": "Tröskelramper och täckplåtar",
        "en": "Threshold ramps - Cover plates",
        "sv_path": "/ramper/troeskelramper-och-taeckplatar",
        "en_path": "/ramps/threshold-ramps-cover-plates",
    },
    "accessories": {
        "sv_slug": "accessories",
        "en_slug": "accessories",
        "sv": "Tillbehör",
        "en": "Accessories",
        "sv_path": "",
        "en_path": "",
    },
}

# Leaf product pages: (category_key, sv_path, en_path, kind)
# kind: "leaf" | "system"
PRODUCT_PAGES: list[tuple[str, str, str, str]] = [
    # Portabla
    ("portabla-ramper", "/ramper/portabla-ramper/fasta-ramper", "/ramps/portable-ramps/fixed-ramps", "leaf"),
    ("portabla-ramper", "/ramper/portabla-ramper/teleskopramper", "/ramps/portable-ramps/teleskopic-ramps", "leaf"),
    ("portabla-ramper", "/ramper/portabla-ramper/vikbara-ramper", "/ramps/portable-ramps/folding-ramps", "leaf"),
    (
        "portabla-ramper",
        "/ramper/portabla-ramper/vikbara-teleskopramper",
        "/ramps/portable-ramps/folding-telescopic-ramps",
        "leaf",
    ),
    ("portabla-ramper", "/ramper/portabla-ramper/lastskenor", "/ramps/portable-ramps/loading-rails", "leaf"),
    ("portabla-ramper", "/ramper/portabla-ramper/anyramp", "/ramps/portable-ramps/anyramp", "leaf"),
    ("portabla-ramper", "/ramper/portabla-ramper/iramp-portabel", "/ramps/portable-ramps/iramp-portabel", "leaf"),
    ("portabla-ramper", "/ramper/portabla-ramper/iramp-carbon", "/ramps/portable-ramps/iramp-carbon", "leaf"),
    # Fordons
    (
        "fordonsramper",
        "/ramper/fordonsramper/iramp-vehicle-tvadelad",
        "/ramps/vehicle-ramps/iramp-vehicle-two-piece",
        "leaf",
    ),
    (
        "fordonsramper",
        "/ramper/fordonsramper/iramp-vehicle-tredelad",
        "/ramps/vehicle-ramps/iramp-vehicle-three-piece",
        "leaf",
    ),
    ("fordonsramper", "/ramper/fordonsramper/lastramper", "/ramps/vehicle-ramps/loading-ramps", "leaf"),
    # Drive-in (leaf = category page itself)
    ("drive-in-ramper", "/ramper/drive-in-ramper", "/ramps/drive-in-ramps", "leaf"),
    # System (split into section products)
    (
        "system-och-modulramper",
        "/ramper/system-och-modulramper/systemramp-standard",
        "/ramps/system-and-modular-ramps/system-ramp-standard",
        "system",
    ),
    (
        "system-och-modulramper",
        "/ramper/system-och-modulramper/systemramp-professional",
        "/ramps/system-and-modular-ramps/system-ramp-professional",
        "system",
    ),
    # Threshold
    (
        "troskelramper-och-tackplatar",
        "/ramper/troeskelramper-och-taeckplatar/troeskelramper-aluminium",
        "/ramps/threshold-ramps-cover-plates/threshold-ramps-aluminium",
        "leaf",
    ),
    (
        "troskelramper-och-tackplatar",
        "/ramper/troeskelramper-och-taeckplatar/troeskelramper-plast",
        "/ramps/threshold-ramps-cover-plates/threshold-ramps-plastic",
        "leaf",
    ),
    (
        "troskelramper-och-tackplatar",
        "/ramper/troeskelramper-och-taeckplatar/troeskelramper-gummi",
        "/ramps/threshold-ramps-cover-plates/threshold-ramps-rubber",
        "leaf",
    ),
    (
        "troskelramper-och-tackplatar",
        "/ramper/troeskelramper-och-taeckplatar/taeckplatar",
        "/ramps/threshold-ramps-cover-plates/cover-plates",
        "leaf",
    ),
]

# System section name normalization (SV / EN heading → key)
SECTION_ALIASES: dict[str, str] = {
    "ramper": "ramper",
    "ramps": "ramper",
    "vilplaner": "vilplaner",
    "panels": "vilplaner",
    "landing platforms": "vilplaner",
    "modultrappor": "modultrappor",
    "modultrappa": "modultrappor",
    "modular stair case": "modultrappor",
    "modular stairs": "modultrappor",
    "modular stair": "modultrappor",
    "räcken": "racken",
    "racken": "racken",
    "handrails": "racken",
    "railings": "racken",
    "övriga delar": "ovriga-delar",
    "ovriga delar": "ovriga-delar",
    "other parts": "ovriga-delar",
}

SECTION_NAMES = {
    "ramper": {"sv": "Ramper", "en": "Ramps"},
    "vilplaner": {"sv": "Vilplaner", "en": "Landing platforms"},
    "modultrappor": {"sv": "Modultrappor", "en": "Modular stairs"},
    "racken": {"sv": "Räcken", "en": "Handrails"},
    "ovriga-delar": {"sv": "Övriga delar", "en": "Other parts"},
}

ACCESSORY_SECTION_KEYS = {"ovriga-delar"}

ARTICLE_HEAD_RE = re.compile(r"^(\d{4,6})\b")
ARTICLE_INLINE_RE = re.compile(
    r"(?<!\d)(\d{4,6})\s+([A-Za-zÅÄÖåäö][^•\n]{2,120}?)(?=(?:\s*[•·]\s*|\s*$))"
)
SPEC_LABELS = sorted(
    [
        "Längd utfälld",
        "Extended length",
        "Längd ihopvikt",
        "Längd plattform",
        "Length folded",
        "Folded length",
        "Folded height",
        "Höjd hopvikt",
        "Höjd ihopvikt",
        "Bredd plattform",
        "Bredd insida",
        "Inside width",
        "Rek. maxhöjd",
        "Recommended max. height",
        "Recommended max height",
        "Justerbar höjd",
        "Adjustable height",
        "Max. load",
        "Max load",
        "Maxlast",
        "Längd",
        "Length",
        "Bredd",
        "Width",
        "Vikt",
        "Weight",
        "Vinkel",
        "Angle",
        "Mått",
        "Size",
        "Stegdjup",
        "Tread depth",
        "Höjd",
        "Height",
        "Djup",
        "Depth",
    ],
    key=len,
    reverse=True,
)

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower()
    text = text.replace("å", "a").replace("ä", "a").replace("ö", "o")
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "item"


def abs_url(href: str | None) -> str:
    if not href:
        return ""
    return urljoin(BASE, href)


def is_product_image(url: str) -> bool:
    if not url or "feal.se" not in url:
        return False
    path = urlparse(url).path.lower()
    if not any(path.endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".gif")):
        return False
    # logo / chrome
    if "/1446/" in path or "logo" in path:
        return False
    return True


def fetch(path: str) -> BeautifulSoup:
    url = abs_url(path)
    time.sleep(REQUEST_DELAY_S)
    resp = SESSION.get(url, timeout=45)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or "utf-8"
    return BeautifulSoup(resp.text, "lxml")


def content_surfaces(soup: BeautifulSoup) -> list[Tag]:
    """Main page body plus all subsurface content blocks (i/ii/iii/iv/…)."""
    surfaces: list[Tag] = []
    seen: set[int] = set()
    for el in soup.select(".sd-surface-page, [class*='sd-surface-subsurface']"):
        classes = " ".join(el.get("class") or [])
        if "sd-surface-footer" in classes or "sd-surface-header" in classes:
            continue
        if "sd-surface-breadcrumbs" in classes:
            continue
        ident = id(el)
        if ident in seen:
            continue
        seen.add(ident)
        surfaces.append(el)
    return surfaces


def clean_text(text: str) -> str:
    text = text.replace("\xa0", " ").replace("\u200b", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_metric_number(value: str) -> str:
    """Take the first metric-looking number from mixed '550/22 mm/in' strings."""
    if not value:
        return ""
    # Prefer number before slash if present with unit after
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*/", value)
    if m:
        return m.group(1).replace(",", ".")
    m = re.search(r"(\d+(?:[.,]\d+)?)", value)
    return m.group(1).replace(",", ".") if m else ""


def parse_specs(raw: str) -> dict[str, str]:
    raw = clean_text(raw)
    raw = re.sub(r"\([A-Za-z]\)\s*", "", raw)
    raw = raw.replace("\n", " ")
    out: dict[str, str] = {
        "length_mm": "",
        "width_mm": "",
        "inside_width_mm": "",
        "folded_length_mm": "",
        "folded_height_mm": "",
        "weight_kg": "",
        "max_load_kg": "",
        "rec_max_height_mm": "",
        "adjustable_height_mm": "",
        "angle_deg": "",
        "other_specs": "",
    }
    others: list[str] = []

    matches: list[tuple[int, int, str]] = []
    for label in SPEC_LABELS:
        for m in re.finditer(
            rf"(?i)(?<![A-Za-zÅÄÖåäö]){re.escape(label)}\s*\*?\s*:",
            raw,
        ):
            matches.append((m.start(), m.end(), label))
    matches.sort(key=lambda x: (x[0], -(x[1] - x[0])))
    # Drop overlaps (prefer longer / earlier label)
    filtered: list[tuple[int, int, str]] = []
    last_end = -1
    for start, end, label in matches:
        if start < last_end:
            continue
        filtered.append((start, end, label))
        last_end = end

    pairs: list[tuple[str, str]] = []
    for i, (start, end, label) in enumerate(filtered):
        value_end = filtered[i + 1][0] if i + 1 < len(filtered) else len(raw)
        value = clean_text(raw[end:value_end])
        pairs.append((label, value))

    for label_raw, value in pairs:
        label = label_raw.lower().strip()
        num = extract_metric_number(value)
        if ("ihopvikt" in label or "hopvikt" in label or "folded" in label) and (
            "längd" in label or "length" in label
        ):
            out["folded_length_mm"] = num
        elif ("ihopvikt" in label or "hopvikt" in label or "folded" in label) and (
            "höjd" in label or "height" in label
        ):
            out["folded_height_mm"] = num
        elif "insida" in label or "inside width" in label:
            out["inside_width_mm"] = num
        elif (
            label.startswith("längd")
            or label.startswith("length")
            or "utfälld" in label
            or "extended" in label
        ):
            if not out["length_mm"]:
                out["length_mm"] = num
        elif label.startswith("bredd") or label.startswith("width"):
            if not out["width_mm"]:
                out["width_mm"] = num
        elif label.startswith("vikt") or label.startswith("weight"):
            out["weight_kg"] = num
        elif "maxlast" in label or "max. load" in label or "max load" in label:
            out["max_load_kg"] = num
        elif (
            "maxhöjd" in label
            or "max. height" in label
            or "max height" in label
            or "rek." in label
            or "recommended" in label
        ):
            out["rec_max_height_mm"] = num
        elif "justerbar" in label or "adjustable" in label:
            out["adjustable_height_mm"] = value
        elif label.startswith("höjd") or label.startswith("height"):
            # Rubber threshold tables: height of the ramp lip
            if not out["rec_max_height_mm"]:
                out["rec_max_height_mm"] = num
        elif label.startswith("djup") or label.startswith("depth"):
            if not out["length_mm"]:
                out["length_mm"] = num
        elif "vinkel" in label or "angle" in label:
            out["angle_deg"] = num
        else:
            others.append(f"{label_raw}: {value}")
    out["other_specs"] = " | ".join(others)
    return out


@dataclass
class VariantData:
    article_number: str
    name: str
    specs_raw: str
    image: str = ""


@dataclass
class PageLangData:
    title: str = ""
    description: str = ""
    features_md: str = ""
    images: list[str] = field(default_factory=list)
    variants: list[VariantData] = field(default_factory=list)
    # For system pages: section_key -> (section intro, variants)
    sections: dict[str, dict[str, Any]] = field(default_factory=dict)
    url: str = ""


def extract_images(soup: BeautifulSoup) -> list[str]:
    seen: set[str] = set()
    images: list[str] = []
    for surface in content_surfaces(soup):
        for img in surface.select("img"):
            src = abs_url(img.get("src"))
            if not is_product_image(src) or src in seen:
                continue
            seen.add(src)
            images.append(src)
        # fancybox full-size links
        for a in surface.select("a.fancybox_group, a[rel='images']"):
            href = abs_url(a.get("href"))
            if is_product_image(href) and href not in seen:
                seen.add(href)
                images.append(href)
    return images


def extract_features(soup: BeautifulSoup) -> str:
    blocks: list[str] = []
    for h3 in soup.select("h3.SUBHEADING"):
        title = clean_text(h3.get_text())
        body = ""
        col = h3.find_parent(class_=re.compile(r"col-"))
        search_root = col or h3.find_parent(class_=re.compile(r"sd-object"))
        if search_root:
            for obj in search_root.select(".sd-object"):
                classes = " ".join(obj.get("class") or [])
                if "SUBHEADING" in classes:
                    continue
                t = clean_text(obj.get_text(" ", strip=True))
                if t and t != title and not t.startswith("http"):
                    body = t
                    break
        if title:
            if body:
                blocks.append(f"### {title}\n{body}")
            else:
                blocks.append(f"### {title}")
    return "\n\n".join(blocks)


def extract_intro(soup: BeautifulSoup) -> tuple[str, str]:
    """Return (h1 title, description paragraph)."""
    h1 = soup.select_one(".sd-surface-page h1.TITLE") or soup.select_one("h1.TITLE")
    title = clean_text(h1.get_text()) if h1 else ""
    description = ""
    if h1:
        obj = h1.find_parent(class_=re.compile(r"sd-object"))
        if obj:
            for sib in obj.next_siblings:
                if not isinstance(sib, Tag):
                    continue
                classes = " ".join(sib.get("class") or [])
                if "sd-object" not in classes:
                    continue
                if "TITLE" in classes or "SUBHEADING" in classes or "HEADING" in classes:
                    break
                t = clean_text(sib.get_text(" ", strip=True))
                if t and len(t) > 20:
                    description = t
                    break
    return title, description


def variant_from_block(name: str, specs_raw: str, image: str = "") -> VariantData | None:
    name = clean_text(name.replace("\n", " "))
    m = ARTICLE_HEAD_RE.match(name)
    if not m:
        return None
    article = m.group(1)
    return VariantData(
        article_number=article,
        name=name,
        specs_raw=clean_text(specs_raw),
        image=image,
    )


def extract_table_variants(soup: BeautifulSoup) -> list[VariantData]:
    """Parse ART.NR / ART.NO style spec tables (e.g. rubber threshold ramps)."""
    variants: list[VariantData] = []
    seen: set[str] = set()
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        if len(rows) < 2:
            continue
        headers = [
            clean_text(c.get_text(" ", strip=True)).lower()
            for c in rows[0].find_all(["th", "td"])
        ]
        if not headers:
            continue
        # Find article column
        art_idx = None
        for i, h in enumerate(headers):
            if "art" in h and ("nr" in h or "no" in h or "nr." in h):
                art_idx = i
                break
        if art_idx is None:
            continue

        original_headers = [
            clean_text(c.get_text(" ", strip=True))
            for c in rows[0].find_all(["th", "td"])
        ]

        for tr in rows[1:]:
            cells = [clean_text(c.get_text(" ", strip=True)) for c in tr.find_all(["td", "th"])]
            if len(cells) <= art_idx:
                continue
            article = cells[art_idx]
            if not re.fullmatch(r"\d{4,6}", article):
                continue
            if article in seen:
                continue
            seen.add(article)
            spec_parts = []
            for i, val in enumerate(cells):
                if i == art_idx or not val:
                    continue
                label = original_headers[i] if i < len(original_headers) else f"col{i}"
                spec_parts.append(f"{label}: {val}")
            specs_raw = "\n".join(spec_parts)
            dim_bits = [v for i, v in enumerate(cells) if i != art_idx and v][:3]
            name = f"{article} " + ", ".join(dim_bits) if dim_bits else article
            variants.append(
                VariantData(article_number=article, name=name, specs_raw=specs_raw)
            )
    return variants


def extract_leaf_variants(soup: BeautifulSoup) -> list[VariantData]:
    variants: list[VariantData] = []
    seen: set[str] = set()
    for surface in content_surfaces(soup):
        for h3 in surface.find_all("h3"):
            text = clean_text(h3.get_text())
            if not ARTICLE_HEAD_RE.match(text):
                continue
            obj = h3.find_parent(class_=re.compile(r"sd-object"))
            if not obj:
                continue
            # specs = object text minus title
            full = clean_text(obj.get_text("\n", strip=True))
            specs = full[len(text) :].strip() if full.startswith(text) else full
            img = ""
            img_el = obj.find("img")
            if img_el:
                cand = abs_url(img_el.get("src"))
                if is_product_image(cand):
                    img = cand
            v = variant_from_block(text, specs, img)
            if v and v.article_number not in seen:
                seen.add(v.article_number)
                variants.append(v)

        # Also catch strong-led model blocks (system-style on some pages)
        for strong in surface.find_all("strong"):
            text = clean_text(strong.get_text())
            if not ARTICLE_HEAD_RE.match(text):
                continue
            obj = strong.find_parent(class_=re.compile(r"sd-object"))
            if not obj:
                continue
            full = clean_text(obj.get_text("\n", strip=True))
            # May contain multiple articles separated by bullets in one object
            if "•" in full or "·" in full:
                continue  # handled by inline extractor
            specs = full[len(text) :].strip() if full.startswith(text) else full
            v = variant_from_block(text, specs)
            if v and v.article_number not in seen:
                seen.add(v.article_number)
                variants.append(v)

    for v in extract_table_variants(soup):
        if v.article_number not in seen:
            seen.add(v.article_number)
            variants.append(v)
    return variants


def normalize_section_key(heading: str) -> str | None:
    key = clean_text(heading).lower()
    key = key.replace("ä", "a").replace("å", "a").replace("ö", "o")
    # try direct
    if heading.lower() in SECTION_ALIASES:
        return SECTION_ALIASES[heading.lower()]
    if key in SECTION_ALIASES:
        return SECTION_ALIASES[key]
    # fuzzy contains
    for alias, mapped in SECTION_ALIASES.items():
        if alias == key or alias in key:
            return mapped
    return None


def is_section_heading(tag: Tag) -> bool:
    if tag.name not in ("h2", "h3"):
        return False
    text = clean_text(tag.get_text())
    if ARTICLE_HEAD_RE.match(text):
        return False
    lower = text.lower()
    if lower.startswith("which ramp") or "vilken ramp" in lower:
        return False
    # Skip long marketing headings that are not product groups
    if len(text) > 60:
        return False
    classes = " ".join(tag.get("class") or [])
    if "HEADING" in classes or tag.name == "h2":
        return normalize_section_key(text) is not None
    return False


def extract_variants_from_text_blob(text: str) -> list[VariantData]:
    """Parse blocks that list multiple articles, including bullet-separated lines."""
    text = clean_text(text)
    variants: list[VariantData] = []
    seen: set[str] = set()

    # Split on bullets / newlines that start with article numbers
    chunks = re.split(r"(?:•|·|\n(?=\d{4,6}\b))", text)
    for chunk in chunks:
        chunk = clean_text(chunk)
        if not chunk:
            continue
        m = ARTICLE_HEAD_RE.match(chunk)
        if not m:
            continue
        # name is first line / up to first known spec label
        lines = [ln.strip() for ln in re.split(r"[\n]", chunk) if ln.strip()]
        name_line = lines[0]
        # Sometimes "10960 Ramp, 500x900 mm Längd: ..."
        name_m = re.match(
            r"^(\d{4,6}\s+.+?)(?=\s+(?:Längd|Length|Bredd|Width|Vikt|Weight|Maxlast|Max\.|Mått|Size|Vinkel|Angle|Stegdjup)\b|$)",
            name_line,
        )
        name = clean_text(name_m.group(1) if name_m else name_line)
        specs = clean_text(chunk[len(name) :] if chunk.startswith(name) else "\n".join(lines[1:]))
        v = variant_from_block(name, specs)
        if v and v.article_number not in seen:
            seen.add(v.article_number)
            variants.append(v)
    return variants


def extract_system_sections(soup: BeautifulSoup) -> dict[str, dict[str, Any]]:
    """
    Split system page into sections keyed by SECTION_NAMES keys.
    Each value: {heading, intro, variants}
    """
    # Collect ordered content elements from main surfaces
    elements: list[Tag] = []
    for surface in content_surfaces(soup):
        for child in surface.descendants:
            if not isinstance(child, Tag):
                continue
            if child.name in ("h2", "h3") and (
                is_section_heading(child) or ARTICLE_HEAD_RE.match(clean_text(child.get_text()))
            ):
                elements.append(child)
            elif child.name == "div" and child.get("class") and "sd-object" in child.get("class", []):
                # only top-ish objects that contain strong article or text with articles
                if child.find(["h1", "h2", "h3"]):
                    continue
                text = clean_text(child.get_text(" ", strip=True))
                if ARTICLE_HEAD_RE.search(text) and len(text) > 5:
                    elements.append(child)

    # Deduplicate nested: keep outermost occurrences by identity order
    sections: dict[str, dict[str, Any]] = {}
    current_key: str | None = None

    def ensure(key: str, heading: str) -> None:
        if key not in sections:
            sections[key] = {"heading": heading, "intro": "", "variants": [], "seen": set()}

    for el in elements:
        if el.name in ("h2", "h3") and is_section_heading(el):
            heading = clean_text(el.get_text())
            key = normalize_section_key(heading)
            if key:
                current_key = key
                ensure(key, heading)
            continue

        if current_key is None:
            continue

        ensure(current_key, SECTION_NAMES[current_key]["sv"])

        if el.name in ("h2", "h3") and ARTICLE_HEAD_RE.match(clean_text(el.get_text())):
            obj = el.find_parent(class_=re.compile(r"sd-object")) or el
            full = clean_text(obj.get_text("\n", strip=True))
            title = clean_text(el.get_text())
            specs = full[len(title) :].strip() if full.startswith(title) else full
            v = variant_from_block(title, specs)
            if v and v.article_number not in sections[current_key]["seen"]:
                sections[current_key]["seen"].add(v.article_number)
                sections[current_key]["variants"].append(v)
            continue

        if el.name == "div":
            text = clean_text(el.get_text("\n", strip=True))
            # section intro if no article yet and no article number
            if not ARTICLE_HEAD_RE.search(text):
                if not sections[current_key]["intro"] and len(text) > 30:
                    sections[current_key]["intro"] = text
                continue
            for v in extract_variants_from_text_blob(text):
                if v.article_number not in sections[current_key]["seen"]:
                    sections[current_key]["seen"].add(v.article_number)
                    sections[current_key]["variants"].append(v)

    # cleanup internal seen sets
    for data in sections.values():
        data.pop("seen", None)
    return sections


def parse_page(path: str, kind: str) -> PageLangData:
    soup = fetch(path)
    data = PageLangData(url=abs_url(path))
    data.title, data.description = extract_intro(soup)
    data.features_md = extract_features(soup)
    data.images = extract_images(soup)
    if kind == "system":
        data.sections = extract_system_sections(soup)
    else:
        data.variants = extract_leaf_variants(soup)
    return data


def path_slug(path: str) -> str:
    return path.rstrip("/").split("/")[-1]


def merge_variants_sv_en(
    sv_list: list[VariantData], en_list: list[VariantData]
) -> list[dict[str, Any]]:
    en_by_art = {v.article_number: v for v in en_list}
    sv_by_art = {v.article_number: v for v in sv_list}
    articles = list(dict.fromkeys([*sv_by_art.keys(), *en_by_art.keys()]))
    rows = []
    for art in articles:
        sv = sv_by_art.get(art)
        en = en_by_art.get(art)
        name_sv = sv.name if sv else (en.name if en else art)
        name_en = en.name if en else (sv.name if sv else art)
        specs_sv = sv.specs_raw if sv else ""
        specs_en = en.specs_raw if en else ""
        parsed = parse_specs(specs_sv or specs_en)
        image = (sv.image if sv and sv.image else "") or (en.image if en and en.image else "")
        rows.append(
            {
                "article_number": art,
                "name_sv": name_sv,
                "name_en": name_en,
                "specs_raw_sv": specs_sv,
                "specs_raw_en": specs_en,
                "image": image,
                **{k: v for k, v in parsed.items() if k != "other_specs"},
                "other_specs_sv": parsed["other_specs"] if specs_sv else "",
                "other_specs_en": parse_specs(specs_en)["other_specs"] if specs_en else "",
            }
        )
    return rows


_OVERVIEWS_CACHE: dict[str, dict[str, str]] | None = None


def load_overviews() -> dict[str, dict[str, str]]:
    global _OVERVIEWS_CACHE
    if _OVERVIEWS_CACHE is not None:
        return _OVERVIEWS_CACHE
    path = ROOT / "data" / "overviews.json"
    if not path.exists():
        _OVERVIEWS_CACHE = {}
        return _OVERVIEWS_CACHE
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        _OVERVIEWS_CACHE = {}
        return _OVERVIEWS_CACHE
    _OVERVIEWS_CACHE = data if isinstance(data, dict) else {}
    return _OVERVIEWS_CACHE


def product_row(
    *,
    title: str,
    slug: str,
    category_key: str,
    name_sv: str,
    name_en: str,
    description_sv: str,
    description_en: str,
    features_sv: str,
    features_en: str,
    images: list[str],
    source_url_sv: str,
    source_url_en: str,
    parent_page_sv: str = "",
    parent_page_en: str = "",
    subcategory_sv: str = "",
    subcategory_en: str = "",
) -> dict[str, str]:
    cat = CATEGORIES[category_key]
    overview = load_overviews().get(slug, {})
    # Header suffixes hint Figma Sites field types on CSV import.
    row = {
        "Title": title,
        "Slug": slug,
        "category_key (Plain text)": category_key,
        "category_sv (Plain text)": cat["sv"],
        "category_en (Plain text)": cat["en"],
        "subcategory_sv (Plain text)": subcategory_sv,
        "subcategory_en (Plain text)": subcategory_en,
        "name_sv (Plain text)": name_sv,
        "name_en (Plain text)": name_en,
        "overview_sv (Plain text)": overview.get("overview_sv", ""),
        "overview_en (Plain text)": overview.get("overview_en", ""),
        "description_sv (Rich text)": description_sv,
        "description_en (Rich text)": description_en,
        "features_sv (Rich text)": features_sv,
        "features_en (Rich text)": features_en,
        "source_url_sv (Link)": source_url_sv,
        "source_url_en (Link)": source_url_en,
        "parent_page_sv (Plain text)": parent_page_sv,
        "parent_page_en (Plain text)": parent_page_en,
    }
    for i in range(1, 9):
        row[f"image_{i} (Image)"] = images[i - 1] if i <= len(images) else ""
    return row


def variant_row(
    *,
    merged: dict[str, Any],
    product_slug: str,
    category_key: str,
    source_url_sv: str,
    source_url_en: str,
    slug_suffix: str = "",
) -> dict[str, str]:
    art = merged["article_number"]
    slug = slugify(f"{art}-{slug_suffix}") if slug_suffix else art
    # Figma slug: lowercase letters, numbers, hyphens
    slug = re.sub(r"[^a-z0-9-]", "", slug.lower())
    return {
        "Title": merged["name_en"],
        "Slug": slug,
        "product_slug (Plain text)": product_slug,
        "category_key (Plain text)": category_key,
        "article_number (Plain text)": art,
        "name_sv (Plain text)": merged["name_sv"],
        "name_en (Plain text)": merged["name_en"],
        "length_mm (Plain text)": merged.get("length_mm", ""),
        "width_mm (Plain text)": merged.get("width_mm", ""),
        "inside_width_mm (Plain text)": merged.get("inside_width_mm", ""),
        "folded_length_mm (Plain text)": merged.get("folded_length_mm", ""),
        "folded_height_mm (Plain text)": merged.get("folded_height_mm", ""),
        "weight_kg (Plain text)": merged.get("weight_kg", ""),
        "max_load_kg (Plain text)": merged.get("max_load_kg", ""),
        "rec_max_height_mm (Plain text)": merged.get("rec_max_height_mm", ""),
        "adjustable_height_mm (Plain text)": merged.get("adjustable_height_mm", ""),
        "angle_deg (Plain text)": merged.get("angle_deg", ""),
        "other_specs_sv (Plain text)": merged.get("other_specs_sv", ""),
        "other_specs_en (Plain text)": merged.get("other_specs_en", ""),
        "specs_raw_sv (Rich text)": merged.get("specs_raw_sv", ""),
        "specs_raw_en (Rich text)": merged.get("specs_raw_en", ""),
        "image (Image)": merged.get("image", ""),
        "source_url_sv (Link)": source_url_sv,
        "source_url_en (Link)": source_url_en,
    }


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})


PRODUCT_FIELDS = [
    "Title",
    "Slug",
    "category_key (Plain text)",
    "category_sv (Plain text)",
    "category_en (Plain text)",
    "subcategory_sv (Plain text)",
    "subcategory_en (Plain text)",
    "name_sv (Plain text)",
    "name_en (Plain text)",
    "overview_sv (Plain text)",
    "overview_en (Plain text)",
    "description_sv (Rich text)",
    "description_en (Rich text)",
    "features_sv (Rich text)",
    "features_en (Rich text)",
    *[f"image_{i} (Image)" for i in range(1, 9)],
    "source_url_sv (Link)",
    "source_url_en (Link)",
    "parent_page_sv (Plain text)",
    "parent_page_en (Plain text)",
]

VARIANT_FIELDS = [
    "Title",
    "Slug",
    "product_slug (Plain text)",
    "category_key (Plain text)",
    "article_number (Plain text)",
    "name_sv (Plain text)",
    "name_en (Plain text)",
    "length_mm (Plain text)",
    "width_mm (Plain text)",
    "inside_width_mm (Plain text)",
    "folded_length_mm (Plain text)",
    "folded_height_mm (Plain text)",
    "weight_kg (Plain text)",
    "max_load_kg (Plain text)",
    "rec_max_height_mm (Plain text)",
    "adjustable_height_mm (Plain text)",
    "angle_deg (Plain text)",
    "other_specs_sv (Plain text)",
    "other_specs_en (Plain text)",
    "specs_raw_sv (Rich text)",
    "specs_raw_en (Rich text)",
    "image (Image)",
    "source_url_sv (Link)",
    "source_url_en (Link)",
]


def parent_names_for_category(category_key: str) -> tuple[str, str]:
    cat = CATEGORIES[category_key]
    return cat["sv"], cat["en"]


def run() -> None:
    products_by_cat: dict[str, list[dict[str, str]]] = defaultdict(list)
    variants_by_cat: dict[str, list[dict[str, str]]] = defaultdict(list)
    # Track slugs for uniqueness within each collection
    product_slugs: dict[str, set[str]] = defaultdict(set)
    variant_slugs: dict[str, set[str]] = defaultdict(set)

    print(f"Scraping {len(PRODUCT_PAGES)} product page pairs…")

    for category_key, sv_path, en_path, kind in PRODUCT_PAGES:
        print(f"  [{kind}] {sv_path}")
        sv = parse_page(sv_path, kind)
        en = parse_page(en_path, kind)
        sub_sv, sub_en = parent_names_for_category(category_key)

        if kind == "leaf":
            slug = path_slug(sv_path)
            # ensure unique
            base_slug = slug
            n = 2
            while slug in product_slugs[category_key]:
                slug = f"{base_slug}-{n}"
                n += 1
            product_slugs[category_key].add(slug)

            images = list(dict.fromkeys([*sv.images, *en.images]))
            title = en.title or sv.title or slug
            products_by_cat[category_key].append(
                product_row(
                    title=title,
                    slug=slug,
                    category_key=category_key,
                    name_sv=sv.title or title,
                    name_en=en.title or title,
                    description_sv=sv.description,
                    description_en=en.description,
                    features_sv=sv.features_md,
                    features_en=en.features_md,
                    images=images,
                    source_url_sv=sv.url,
                    source_url_en=en.url,
                    subcategory_sv=sub_sv,
                    subcategory_en=sub_en,
                )
            )

            merged = merge_variants_sv_en(sv.variants, en.variants)
            for m in merged:
                # unique variant slug within category CSV
                vslug = m["article_number"]
                if vslug in variant_slugs[category_key]:
                    vslug = f"{vslug}-{slug}"
                # still unique?
                base = vslug
                n = 2
                while vslug in variant_slugs[category_key]:
                    vslug = f"{base}-{n}"
                    n += 1
                variant_slugs[category_key].add(vslug)
                row = variant_row(
                    merged=m,
                    product_slug=slug,
                    category_key=category_key,
                    source_url_sv=sv.url,
                    source_url_en=en.url,
                )
                row["Slug"] = vslug
                variants_by_cat[category_key].append(row)

        else:  # system — one product per section
            parent_slug = path_slug(sv_path)
            parent_name_sv = sv.title or parent_slug
            parent_name_en = en.title or parent_slug
            section_keys = list(
                dict.fromkeys([*sv.sections.keys(), *en.sections.keys()])
            )
            # Prefer known order
            order = ["ramper", "vilplaner", "modultrappor", "racken", "ovriga-delar"]
            section_keys = [k for k in order if k in section_keys] + [
                k for k in section_keys if k not in order
            ]

            for section_key in section_keys:
                sv_sec = sv.sections.get(section_key, {})
                en_sec = en.sections.get(section_key, {})
                names = SECTION_NAMES.get(
                    section_key,
                    {
                        "sv": sv_sec.get("heading", section_key),
                        "en": en_sec.get("heading", section_key),
                    },
                )
                name_sv = names["sv"]
                name_en = names["en"]
                product_slug = f"{parent_slug}-{section_key}"

                target_cat = (
                    "accessories" if section_key in ACCESSORY_SECTION_KEYS else category_key
                )

                # Unique product slug in target collection
                slug = product_slug
                base = slug
                n = 2
                while slug in product_slugs[target_cat]:
                    slug = f"{base}-{n}"
                    n += 1
                product_slugs[target_cat].add(slug)

                images = list(dict.fromkeys([*sv.images, *en.images]))
                title = f"{parent_name_en} — {name_en}"
                products_by_cat[target_cat].append(
                    product_row(
                        title=title,
                        slug=slug,
                        category_key=target_cat,
                        name_sv=f"{parent_name_sv} — {name_sv}",
                        name_en=title,
                        description_sv=sv_sec.get("intro") or sv.description,
                        description_en=en_sec.get("intro") or en.description,
                        features_sv=sv.features_md if section_key == "ramper" else "",
                        features_en=en.features_md if section_key == "ramper" else "",
                        images=images,
                        source_url_sv=sv.url,
                        source_url_en=en.url,
                        parent_page_sv=parent_name_sv,
                        parent_page_en=parent_name_en,
                        subcategory_sv=CATEGORIES[target_cat]["sv"]
                        if target_cat == "accessories"
                        else sub_sv,
                        subcategory_en=CATEGORIES[target_cat]["en"]
                        if target_cat == "accessories"
                        else sub_en,
                    )
                )

                merged = merge_variants_sv_en(
                    sv_sec.get("variants", []), en_sec.get("variants", [])
                )
                for m in merged:
                    vslug = m["article_number"]
                    if vslug in variant_slugs[target_cat]:
                        vslug = f"{vslug}-{slug}"
                    base = vslug
                    n = 2
                    while vslug in variant_slugs[target_cat]:
                        vslug = f"{base}-{n}"
                        n += 1
                    variant_slugs[target_cat].add(vslug)
                    row = variant_row(
                        merged=m,
                        product_slug=slug,
                        category_key=target_cat,
                        source_url_sv=sv.url,
                        source_url_en=en.url,
                    )
                    row["Slug"] = vslug
                    variants_by_cat[target_cat].append(row)

    # Write CSVs for all categories into data/csv/<category_key>/
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    summary = []
    for category_key in CATEGORIES:
        prows = products_by_cat.get(category_key, [])
        vrows = variants_by_cat.get(category_key, [])
        cat_dir = OUT_DIR / category_key
        ppath = cat_dir / f"products_{category_key}.csv"
        vpath = cat_dir / f"variants_{category_key}.csv"
        write_csv(ppath, prows, PRODUCT_FIELDS)
        write_csv(vpath, vrows, VARIANT_FIELDS)
        summary.append((category_key, len(prows), len(vrows)))
        print(
            f"Wrote {ppath.relative_to(OUT_DIR)}: {len(prows)} products, "
            f"{vpath.relative_to(OUT_DIR)}: {len(vrows)} variants"
        )

    print("\nSummary")
    for cat, pc, vc in summary:
        print(f"  {cat}: {pc} products, {vc} variants")

    apply_hosted_image_urls()


def apply_hosted_image_urls() -> None:
    """If assets/image_url_map.json exists, rewrite feal.se image URLs to hosted ones."""
    map_path = ROOT / "assets" / "image_url_map.json"
    if not map_path.exists():
        return
    try:
        url_map = json.loads(map_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return
    if not url_map:
        return
    image_col = re.compile(r"^image(_\d+)?(\s|\(|$)", re.I)
    updated = 0
    for path in OUT_DIR.rglob("*.csv"):
        with path.open(encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            fieldnames = list(reader.fieldnames or [])
            rows = list(reader)
        if not fieldnames:
            continue
        dirty = False
        for row in rows:
            for key in fieldnames:
                if not image_col.match(key or ""):
                    continue
                old = (row.get(key) or "").strip()
                if old in url_map:
                    row[key] = url_map[old]
                    dirty = True
        if dirty:
            with path.open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            updated += 1
    if updated:
        print(f"Applied hosted image URL map to {updated} CSV files")


if __name__ == "__main__":
    run()
