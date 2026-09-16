#!/usr/bin/env python3
"""
Build application-based products/variants CSVs from client Excel tabs + existing scrape CSVs.

Each Excel tab = one product; each Artikelnummer row = one size variant.
"""

from __future__ import annotations

import csv
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any

import openpyxl

from scripts.scrape_feal import IMAGE_SLOT_COUNT, VARIANT_FIELDS, normalize_rich_text

ROOT = Path(__file__).resolve().parents[1]
EXCEL_DIR = ROOT / "OneDrive_1_16.9.2026"
OLD_CSV_DIR = ROOT / "data" / "csv"
OUT_DIR = ROOT / "data" / "csv" / "application"

APPLICATIONS: list[dict[str, str]] = [
    {
        "key": "fordon",
        "sv": "Fordonsmonterade",
        "en": "Vehicle-mounted",
        "xlsx": "Artiklar till produktsidorna Fordonsmonterade ramper.xlsx",
    },
    {
        "key": "portable",
        "sv": "Portabla",
        "en": "Portable",
        "xlsx": "Artiklar till produktsidorna Portabla ramper.xlsx",
    },
    {
        "key": "transport",
        "sv": "Transport",
        "en": "Transport",
        "xlsx": "Artiklar till produktsidorna Transport.xlsx",
    },
]

# Excel sheet title (exact) → existing scraped product Slug (for marketing fields)
SHEET_TO_OLD_PRODUCT: dict[str, str] = {
    "Fordonsmonterad 2-delad ramp": "iramp-vehicle-tvadelad",
    "Fordonsmonterad 3-delad ramp": "iramp-vehicle-tredelad",
    "Enkelskena": "fasta-ramper",
    "Vikbar skena": "vikbara-ramper",
    "Teleskopisk skena": "teleskopramper",
    "Vikbar Teleskopisk skena": "vikbara-teleskopramper",
    "Vikbar Teleskopisk skena ": "vikbara-teleskopramper",
    "Suitcase ramp Kolfiber": "iramp-carbon",
    "Suitcase ramp Aluminium": "iramp-portabel",
    "Vikbar ramp": "anyramp",
    "Fordonsmonterad 2-delad Lastram": "lastramper",
    "Portabla Lastskenor": "lastskenor",
}

# Intentionally not in Transport Excel (narrow lastramper widths)
EXCLUDED_NOTE_ARTICLES = [str(n) for n in range(10910, 10918)]

HEADER_ALIASES: dict[str, str] = {
    "artikelnummer": "article",
    "namn": "name",
    "längd": "length_mm",
    "langd": "length_mm",
    "bredd åkyta": "width_mm",
    "bredd akyta": "width_mm",
    "höjd ihopvikt": "folded_height_mm",
    "hojd ihopvikt": "folded_height_mm",
    "längd ihopvikt": "folded_length_mm",
    "langd ihopvikt": "folded_length_mm",
    "bredd ihopvikt": "folded_width_mm",
    "vikt": "weight_kg",
    "lastvikt/swl": "max_load_kg",
    "lastvikt": "max_load_kg",
    "rek. maxhöjd": "rec_max_height_mm",
    "rek. maxhojd": "rec_max_height_mm",
    "rek maxhöjd": "rec_max_height_mm",
    "totalbredd": "total_width_mm",
    "djup ihopvikt": "folded_depth_mm",
}

APP_PRODUCT_FIELDS = [
    "Title",
    "Slug",
    "category_key (Plain text)",
    "category_sv (Plain text)",
    "category_en (Plain text)",
    "subcategory_sv (Plain text)",
    "subcategory_en (Plain text)",
    "name_sv (Plain text)",
    "name_en (Plain text)",
    "article_numbers (Plain text)",
    "overview_sv (Plain text)",
    "overview_en (Plain text)",
    "description_sv (Rich text)",
    "description_en (Rich text)",
    "features_sv (Rich text)",
    "features_en (Rich text)",
    *[
        col
        for i in range(1, IMAGE_SLOT_COUNT + 1)
        for col in (
            f"image_{i} (Image)",
            f"caption_sv_{i} (Plain text)",
            f"caption_en_{i} (Plain text)",
        )
    ],
    "source_url_sv (Link)",
    "source_url_en (Link)",
    "parent_page_sv (Plain text)",
    "parent_page_en (Plain text)",
    "source_product_slug (Plain text)",
]


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-") or "item"


def clean(text: str | None) -> str:
    if text is None:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip()


def parse_measure(value: str | None) -> str:
    """Extract numeric part from '1600 mm', '400 kg*', '1,5 kg'."""
    if not value:
        return ""
    s = clean(value).replace(",", ".")
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    if not m:
        return ""
    num = m.group(0)
    if num.endswith(".0"):
        num = num[:-2]
    return num


def normalize_header(h: str | None) -> str:
    h = clean(h).lower()
    h = unicodedata.normalize("NFKD", h)
    h = "".join(c for c in h if not unicodedata.combining(c))
    return HEADER_ALIASES.get(h, h)


def load_old_variants() -> dict[str, dict[str, str]]:
    by_art: dict[str, dict[str, str]] = {}
    for path in OLD_CSV_DIR.rglob("variants_*.csv"):
        if "application" in path.parts:
            continue
        with path.open(encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                art = (row.get("article_number (Plain text)") or "").strip()
                if art:
                    by_art[art] = row
    return by_art


def load_old_products() -> dict[str, dict[str, str]]:
    by_slug: dict[str, dict[str, str]] = {}
    for path in OLD_CSV_DIR.rglob("products_*.csv"):
        if "application" in path.parts:
            continue
        with path.open(encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                slug = (row.get("Slug") or "").strip()
                if slug:
                    by_slug[slug] = row
    return by_slug


def parse_workbook(path: Path) -> list[dict[str, Any]]:
    """Return list of {sheet, title, slug, variants: [{article, name, fields...}]}."""
    wb = openpyxl.load_workbook(path, data_only=True)
    products: list[dict[str, Any]] = []
    for ws in wb.worksheets:
        sheet_name = ws.title
        title = clean(sheet_name)
        headers: list[str] | None = None
        header_keys: list[str] = []
        variants: list[dict[str, str]] = []

        for i, row in enumerate(ws.iter_rows(values_only=True), 1):
            vals = [None if v is None else str(v).strip() for v in row]
            if i == 1 and vals and vals[0]:
                title = clean(vals[0]) or title
            if vals and vals[0] and clean(vals[0]).lower() == "artikelnummer":
                headers = [clean(v) for v in vals]
                header_keys = [normalize_header(h) for h in headers]
                continue
            if not headers or not vals or not vals[0]:
                continue
            art = clean(vals[0])
            if not re.match(r"^\d{4,6}$", art):
                continue
            raw: dict[str, str] = {}
            for key, val in zip(header_keys, vals):
                if key and val is not None and clean(val):
                    raw[key] = clean(val)
            variants.append(
                {
                    "article": art,
                    "name": raw.get("name", ""),
                    "length_mm": parse_measure(raw.get("length_mm")),
                    "width_mm": parse_measure(raw.get("width_mm")),
                    "folded_height_mm": parse_measure(raw.get("folded_height_mm")),
                    "folded_length_mm": parse_measure(raw.get("folded_length_mm")),
                    "folded_width_mm": parse_measure(raw.get("folded_width_mm")),
                    "weight_kg": parse_measure(raw.get("weight_kg")),
                    "max_load_kg": parse_measure(raw.get("max_load_kg")),
                    "rec_max_height_mm": parse_measure(raw.get("rec_max_height_mm")),
                    "total_width_mm": parse_measure(raw.get("total_width_mm")),
                    "folded_depth_mm": parse_measure(raw.get("folded_depth_mm")),
                    "raw": raw,
                }
            )

        if not variants:
            continue
        products.append(
            {
                "sheet": sheet_name,
                "title": title,
                "slug": slugify(sheet_name),
                "variants": variants,
            }
        )
    return products


def merge_other_specs(
    scraped_sv: str,
    scraped_en: str,
    excel_extra: dict[str, str],
) -> tuple[str, str]:
    parts_sv: list[str] = []
    parts_en: list[str] = []
    if scraped_sv:
        parts_sv.append(scraped_sv)
    if scraped_en:
        parts_en.append(scraped_en)
    labels = {
        "total_width_mm": ("Totalbredd", "Total width"),
        "folded_depth_mm": ("Djup ihopvikt", "Folded depth"),
        "folded_width_mm": ("Bredd ihopvikt", "Folded width"),
    }
    for key, (sv_l, en_l) in labels.items():
        val = excel_extra.get(key, "")
        if val:
            parts_sv.append(f"{sv_l}: {val} mm")
            parts_en.append(f"{en_l}: {val} mm")
    return " | ".join(parts_sv), " | ".join(parts_en)


def build_variant_row(
    *,
    excel_v: dict[str, Any],
    old: dict[str, str] | None,
    product_slug: str,
    category_key: str,
) -> dict[str, str]:
    art = excel_v["article"]
    old = old or {}
    name_sv = excel_v["name"] or old.get("name_sv (Plain text)", "") or art
    name_en = old.get("name_en (Plain text)", "") or name_sv

    def pick(excel_key: str, csv_key: str) -> str:
        return excel_v.get(excel_key) or old.get(csv_key, "") or ""

    other_sv, other_en = merge_other_specs(
        old.get("other_specs_sv (Plain text)", ""),
        old.get("other_specs_en (Plain text)", ""),
        {
            "total_width_mm": excel_v.get("total_width_mm", ""),
            "folded_depth_mm": excel_v.get("folded_depth_mm", ""),
            "folded_width_mm": excel_v.get("folded_width_mm", ""),
        },
    )

    # Prefer Excel measures when present; keep scraped for remaining fields
    row = {
        "Title": name_en,
        "Slug": art,
        "product_slug (Plain text)": product_slug,
        "category_key (Plain text)": category_key,
        "article_number (Plain text)": art,
        "name_sv (Plain text)": name_sv,
        "name_en (Plain text)": name_en,
        "length_mm (Plain text)": pick("length_mm", "length_mm (Plain text)"),
        "width_mm (Plain text)": pick("width_mm", "width_mm (Plain text)"),
        "inside_width_mm (Plain text)": old.get("inside_width_mm (Plain text)", ""),
        "folded_length_mm (Plain text)": pick(
            "folded_length_mm", "folded_length_mm (Plain text)"
        ),
        "folded_height_mm (Plain text)": pick(
            "folded_height_mm", "folded_height_mm (Plain text)"
        ),
        "weight_kg (Plain text)": pick("weight_kg", "weight_kg (Plain text)"),
        "max_load_kg (Plain text)": pick("max_load_kg", "max_load_kg (Plain text)"),
        "rec_max_height_mm (Plain text)": pick(
            "rec_max_height_mm", "rec_max_height_mm (Plain text)"
        ),
        "adjustable_height_mm (Plain text)": old.get(
            "adjustable_height_mm (Plain text)", ""
        ),
        "angle_deg (Plain text)": old.get("angle_deg (Plain text)", ""),
        "other_specs_sv (Plain text)": other_sv,
        "other_specs_en (Plain text)": other_en,
        "specs_raw_sv (Rich text)": old.get("specs_raw_sv (Rich text)", ""),
        "specs_raw_en (Rich text)": old.get("specs_raw_en (Rich text)", ""),
        "image (Image)": old.get("image (Image)", ""),
        "source_url_sv (Link)": old.get("source_url_sv (Link)", ""),
        "source_url_en (Link)": old.get("source_url_en (Link)", ""),
    }
    return row


def build_product_row(
    *,
    app: dict[str, str],
    excel_product: dict[str, Any],
    old_product: dict[str, str] | None,
    article_numbers: list[str],
) -> dict[str, str]:
    old = old_product or {}
    title_sv = excel_product["title"]
    title_en = old.get("name_en (Plain text)") or old.get("Title") or title_sv
    slug = excel_product["slug"]
    row: dict[str, str] = {
        "Title": title_en,
        "Slug": slug,
        "category_key (Plain text)": app["key"],
        "category_sv (Plain text)": app["sv"],
        "category_en (Plain text)": app["en"],
        "subcategory_sv (Plain text)": title_sv,
        "subcategory_en (Plain text)": title_en,
        "name_sv (Plain text)": title_sv,
        "name_en (Plain text)": title_en,
        "article_numbers (Plain text)": ", ".join(article_numbers),
        "overview_sv (Plain text)": old.get("overview_sv (Plain text)", ""),
        "overview_en (Plain text)": old.get("overview_en (Plain text)", ""),
        "description_sv (Rich text)": normalize_rich_text(
            old.get("description_sv (Rich text)", "")
        ),
        "description_en (Rich text)": normalize_rich_text(
            old.get("description_en (Rich text)", "")
        ),
        "features_sv (Rich text)": normalize_rich_text(
            old.get("features_sv (Rich text)", "")
        ),
        "features_en (Rich text)": normalize_rich_text(
            old.get("features_en (Rich text)", "")
        ),
        "source_url_sv (Link)": old.get("source_url_sv (Link)", ""),
        "source_url_en (Link)": old.get("source_url_en (Link)", ""),
        "parent_page_sv (Plain text)": old.get("parent_page_sv (Plain text)", ""),
        "parent_page_en (Plain text)": old.get("parent_page_en (Plain text)", ""),
        "source_product_slug (Plain text)": old.get("Slug", ""),
    }
    for i in range(1, IMAGE_SLOT_COUNT + 1):
        for col in (
            f"image_{i} (Image)",
            f"caption_sv_{i} (Plain text)",
            f"caption_en_{i} (Plain text)",
        ):
            row[col] = old.get(col, "")
    return row


def prune_empty_columns(
    rows: list[dict[str, str]], fieldnames: list[str]
) -> list[str]:
    """Keep only columns that have at least one non-empty value (plus Title/Slug)."""
    keep: list[str] = []
    for col in fieldnames:
        if col in ("Title", "Slug"):
            keep.append(col)
            continue
        if any((r.get(col) or "").strip() for r in rows):
            keep.append(col)
    return keep


def write_csv(
    path: Path,
    rows: list[dict[str, str]],
    fieldnames: list[str],
    *,
    drop_empty: bool = False,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = prune_empty_columns(rows, fieldnames) if drop_empty else fieldnames
    dropped = [c for c in fieldnames if c not in cols]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in cols})
    if drop_empty and dropped:
        print(f"  pruned {len(dropped)} empty columns from {path.name}")


def run() -> None:
    old_variants = load_old_variants()
    old_products = load_old_products()
    reconcile: list[dict[str, str]] = []

    print(f"Loaded {len(old_variants)} scraped variants, {len(old_products)} products")

    for app in APPLICATIONS:
        xlsx_path = EXCEL_DIR / app["xlsx"]
        if not xlsx_path.exists():
            raise FileNotFoundError(xlsx_path)
        excel_products = parse_workbook(xlsx_path)
        print(f"\n[{app['key']}] {xlsx_path.name}: {len(excel_products)} tabs/products")

        product_rows: list[dict[str, str]] = []
        variant_rows: list[dict[str, str]] = []
        seen_variant_slugs: set[str] = set()

        for ep in excel_products:
            sheet = ep["sheet"]
            old_slug = SHEET_TO_OLD_PRODUCT.get(sheet) or SHEET_TO_OLD_PRODUCT.get(
                sheet.strip()
            )
            if not old_slug:
                print(f"  WARNING: no old-product map for sheet {sheet!r}")
            old_product = old_products.get(old_slug or "", {})
            arts = [v["article"] for v in ep["variants"]]
            product_rows.append(
                build_product_row(
                    app=app,
                    excel_product=ep,
                    old_product=old_product,
                    article_numbers=arts,
                )
            )
            print(f"  product {ep['slug']}: {len(arts)} variants ← {old_slug or '?'}")

            for ev in ep["variants"]:
                art = ev["article"]
                old_v = old_variants.get(art)
                status = "matched" if old_v else "missing_in_scrape"
                if not old_v:
                    print(f"    MISSING scrape match for {art}")
                vslug = art
                if vslug in seen_variant_slugs:
                    vslug = f"{art}-{ep['slug']}"
                seen_variant_slugs.add(vslug)
                vrow = build_variant_row(
                    excel_v=ev,
                    old=old_v,
                    product_slug=ep["slug"],
                    category_key=app["key"],
                )
                vrow["Slug"] = vslug
                variant_rows.append(vrow)
                reconcile.append(
                    {
                        "article_number": art,
                        "application": app["key"],
                        "new_product_slug": ep["slug"],
                        "excel_sheet": sheet,
                        "excel_name_sv": ev.get("name", ""),
                        "old_product_slug": (old_v or {}).get(
                            "product_slug (Plain text)", ""
                        ),
                        "old_category_key": (old_v or {}).get(
                            "category_key (Plain text)", ""
                        ),
                        "match_status": status,
                    }
                )

        cat_dir = OUT_DIR / app["key"]
        write_csv(
            cat_dir / f"products_{app['key']}.csv",
            product_rows,
            APP_PRODUCT_FIELDS,
            drop_empty=True,
        )
        write_csv(
            cat_dir / f"variants_{app['key']}.csv",
            variant_rows,
            VARIANT_FIELDS,
            drop_empty=True,
        )
        print(
            f"  Wrote {len(product_rows)} products, {len(variant_rows)} variants → {cat_dir}"
        )

    # Excluded note rows
    for art in EXCLUDED_NOTE_ARTICLES:
        old_v = old_variants.get(art, {})
        reconcile.append(
            {
                "article_number": art,
                "application": "transport",
                "new_product_slug": "",
                "excel_sheet": "",
                "excel_name_sv": "",
                "old_product_slug": old_v.get("product_slug (Plain text)", ""),
                "old_category_key": old_v.get("category_key (Plain text)", ""),
                "match_status": "excluded_not_in_excel",
            }
        )

    report_path = OUT_DIR / "reconcile_report.csv"
    write_csv(
        report_path,
        reconcile,
        [
            "article_number",
            "application",
            "new_product_slug",
            "excel_sheet",
            "excel_name_sv",
            "old_product_slug",
            "old_category_key",
            "match_status",
        ],
    )
    matched = sum(1 for r in reconcile if r["match_status"] == "matched")
    missing = sum(1 for r in reconcile if r["match_status"] == "missing_in_scrape")
    excluded = sum(1 for r in reconcile if r["match_status"] == "excluded_not_in_excel")
    print(
        f"\nReconcile: {matched} matched, {missing} missing, {excluded} excluded → {report_path}"
    )


if __name__ == "__main__":
    run()
