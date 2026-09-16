#!/usr/bin/env python3
"""
Build embed/data/variants.json from application variant CSVs for the Sites picker.
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_DIR = ROOT / "data" / "csv" / "application"
OUT_PATH = ROOT / "embed" / "data" / "variants.json"

APPS = ("fordon", "portable", "transport")

METRIC_KEYS = (
    "length_mm",
    "width_mm",
    "folded_height_mm",
    "folded_length_mm",
    "inside_width_mm",
    "weight_kg",
    "max_load_kg",
    "rec_max_height_mm",
)


def col(row: dict[str, str], key: str) -> str:
    return (row.get(f"{key} (Plain text)") or row.get(key) or "").strip()


def empty_to_none(value: str) -> str | None:
    return value if value else None


def load_app_variants(app: str) -> list[dict[str, str]]:
    path = APP_DIR / app / f"variants_{app}.csv"
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def variant_record(row: dict[str, str]) -> dict:
    rec: dict = {
        "article_number": col(row, "article_number") or row.get("Slug", "").strip(),
        "name_sv": col(row, "name_sv"),
        "name_en": col(row, "name_en"),
        "slug": row.get("Slug", "").strip(),
    }
    for key in METRIC_KEYS:
        rec[key] = empty_to_none(col(row, key))
    return rec


def build() -> dict:
    by_product: dict[str, list[dict]] = defaultdict(list)
    for app in APPS:
        for row in load_app_variants(app):
            product_slug = col(row, "product_slug")
            if not product_slug:
                continue
            rec = variant_record(row)
            rec["category_key"] = col(row, "category_key") or app
            by_product[product_slug].append(rec)

    # Stable order: by length then width then article
    out: dict[str, dict] = {}
    for product_slug, variants in sorted(by_product.items()):
        variants.sort(
            key=lambda v: (
                _num(v.get("length_mm")),
                _num(v.get("width_mm")),
                v.get("article_number") or "",
            )
        )
        out[product_slug] = {"variants": variants}
    return out


def _num(value: str | None) -> float:
    if not value:
        return 0.0
    try:
        return float(value.replace(",", "."))
    except ValueError:
        return 0.0


def main() -> None:
    data = build()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    n_var = sum(len(p["variants"]) for p in data.values())
    print(f"Wrote {len(data)} products, {n_var} variants → {OUT_PATH}")


if __name__ == "__main__":
    main()
