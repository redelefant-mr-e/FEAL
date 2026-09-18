#!/usr/bin/env python3
"""
Audit live Figma Sites product URLs against embed/data/variants.json.

Exits non-zero if any linked product slug is missing from the catalog.
"""

from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "embed" / "data" / "variants.json"
BASE = "https://rich-alter-33788512.figma.site"
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

SV_CATEGORIES = (
    "/sv-mobilitet-fordonsramper",
    "/sv-mobilitet-portabla-ramper",
    "/sv-transport-ramper",
)
EN_CATEGORIES = (
    "/en-mobility-vehicle-ramps",
    "/en-mobility-portable-ramps",
    "/en-transport-ramps",
)


def fetch(path: str) -> str:
    req = urllib.request.Request(BASE + path, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as res:
        return res.read().decode("utf-8", "ignore")


def product_links(html: str) -> set[str]:
    hrefs = re.findall(r'href="([^"]+)"', html)
    out: set[str] = set()
    for href in hrefs:
        if "produkt" in href or "product" in href:
            out.add(href.split("?")[0])
    return out


def main() -> int:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    paths: set[str] = set()
    for cat in SV_CATEGORIES + EN_CATEGORIES:
        try:
            html = fetch(cat)
        except urllib.error.HTTPError as exc:
            print(f"WARN category {cat}: HTTP {exc.code}")
            continue
        found = product_links(html)
        print(f"{cat}: {len(found)} product links")
        paths |= found

    missing: list[tuple[str, str]] = []
    ok = 0
    for path in sorted(paths):
        slug = path.rstrip("/").split("/")[-1].lower()
        if slug in catalog:
            n = len(catalog[slug]["variants"])
            print(f"OK   {path} → {slug} ({n} variants)")
            ok += 1
        else:
            print(f"MISS {path} → {slug}")
            missing.append((path, slug))

    print(f"\nChecked {len(paths)} product URLs: {ok} matched, {len(missing)} missing")
    if missing:
        print("Add aliases in scripts/build_variant_embed_data.py SLUG_ALIASES, then rebuild.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
