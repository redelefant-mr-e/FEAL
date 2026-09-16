#!/usr/bin/env python3
"""
Download FEAL product images, fit-resize into a 1600×1600 box (no crop, no upscale),
save Figma-compatible JPEG/PNG under assets/images/, and rewrite CSV image URLs
to stable jsDelivr links for a public GitHub repo.
"""

from __future__ import annotations

import csv
import json
import os
import re
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
CSV_DIR = ROOT / "data" / "csv"
ASSETS_DIR = ROOT / "assets" / "images"
CACHE_DIR = ROOT / "assets" / ".cache"
URL_MAP_PATH = ROOT / "assets" / "image_url_map.json"

MAX_BOX = 1600
JPEG_QUALITY = 82
REQUEST_DELAY_S = 0.2
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; FEAL-image-host/1.0)"}

# Product CSVs use image_N (Image); team CSV uses photo (Image).
IMAGE_COL_RE = re.compile(r"^image(_\d+)?(\s|\(|$)", re.I)
IMAGE_HINT_RE = re.compile(r"\(Image\)", re.I)
FILENAME_RE = re.compile(r"/([^/]+)\.(jpe?g|png|gif)(?:\?|$)", re.I)


def is_image_column(name: str | None) -> bool:
    if not name:
        return False
    return bool(IMAGE_COL_RE.match(name) or IMAGE_HINT_RE.search(name))


def detect_github_repo() -> str:
    env = os.environ.get("GITHUB_REPO", "").strip()
    if env:
        return env
    try:
        remote = subprocess.check_output(
            ["git", "remote", "get-url", "origin"],
            cwd=ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        # git@github.com:owner/repo.git or https://github.com/owner/repo.git
        m = re.search(r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/.]+)", remote)
        if m:
            return f"{m.group('owner')}/{m.group('repo')}"
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    # Fallback from local folder naming
    return "redelefant-mr-e/FEAL"


def public_url(repo: str, filename: str, ref: str = "main") -> str:
    return f"https://cdn.jsdelivr.net/gh/{repo}@{ref}/assets/images/{filename}"


def collect_image_urls() -> set[str]:
    urls: set[str] = set()
    for path in CSV_DIR.rglob("*.csv"):
        with path.open(encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                continue
            for row in reader:
                for key, value in row.items():
                    if not value or not is_image_column(key):
                        continue
                    value = value.strip()
                    if value.startswith("http"):
                        urls.add(value)
    return urls


def stable_basename(url: str) -> str:
    """Derive a stable filename stem from FEAL CDN paths."""
    path = urlparse(url).path
    m = FILENAME_RE.search(path)
    if m:
        return m.group(1)
    # Fallback: last path segments
    parts = [p for p in path.split("/") if p]
    return "_".join(parts[-2:]).replace(".", "_") if parts else "image"


def download(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    time.sleep(REQUEST_DELAY_S)
    resp = requests.get(url, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    dest.write_bytes(resp.content)
    return dest


def has_alpha(img: Image.Image) -> bool:
    if img.mode in ("RGBA", "LA"):
        return True
    if img.mode == "P" and "transparency" in img.info:
        return True
    return False


def fit_resize(img: Image.Image, max_box: int = MAX_BOX) -> Image.Image:
    """Fit inside max_box×max_box without cropping or upscaling."""
    w, h = img.size
    longest = max(w, h)
    if longest <= max_box:
        return img
    scale = max_box / float(longest)
    new_size = (max(1, int(round(w * scale))), max(1, int(round(h * scale))))
    return img.resize(new_size, Image.Resampling.LANCZOS)


def process_image(src_path: Path, out_stem: str) -> str:
    """
    Process one image; return output filename (with extension).
    Opaque images → JPEG; images with transparency → PNG.
    """
    with Image.open(src_path) as im:
        im.load()
        if im.mode == "P":
            im = im.convert("RGBA")
        elif im.mode == "LA":
            im = im.convert("RGBA")
        elif im.mode not in ("RGB", "RGBA", "L"):
            im = im.convert("RGBA") if "A" in im.getbands() else im.convert("RGB")

        use_png = has_alpha(im)
        im = fit_resize(im)

        if use_png:
            if im.mode != "RGBA":
                im = im.convert("RGBA")
            out_name = f"{out_stem}.png"
            out_path = ASSETS_DIR / out_name
            ASSETS_DIR.mkdir(parents=True, exist_ok=True)
            im.save(out_path, format="PNG", optimize=True)
        else:
            if im.mode != "RGB":
                im = im.convert("RGB")
            out_name = f"{out_stem}.jpg"
            out_path = ASSETS_DIR / out_name
            ASSETS_DIR.mkdir(parents=True, exist_ok=True)
            im.save(
                out_path,
                format="JPEG",
                quality=JPEG_QUALITY,
                optimize=True,
                progressive=True,
            )
        return out_name


def rewrite_csvs(url_map: dict[str, str]) -> int:
    changed_files = 0
    for path in sorted(CSV_DIR.rglob("*.csv")):
        with path.open(encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            fieldnames = list(reader.fieldnames or [])
            rows = list(reader)
        if not fieldnames:
            continue
        dirty = False
        for row in rows:
            for key in fieldnames:
                if not is_image_column(key):
                    continue
                old = (row.get(key) or "").strip()
                if old in url_map and row[key] != url_map[old]:
                    row[key] = url_map[old]
                    dirty = True
        if dirty:
            with path.open("w", encoding="utf-8", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
            changed_files += 1
            print(f"  updated {path.relative_to(ROOT)}")
    return changed_files


def run() -> None:
    repo = detect_github_repo()
    ref = os.environ.get("GITHUB_REF", "main").strip() or "main"
    print(f"GitHub repo: {repo} (ref={ref})")
    print(f"Max box: {MAX_BOX}×{MAX_BOX} (fit, no crop, no upscale)")

    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    urls = sorted(collect_image_urls())
    # Only process feal.se / not already jsdelivr unless forced
    feal_urls = [u for u in urls if "feal.se" in u]
    already = [u for u in urls if "jsdelivr.net" in u or "raw.githubusercontent.com" in u]
    print(f"Found {len(urls)} unique image URLs ({len(feal_urls)} from feal.se, {len(already)} already hosted)")

    url_map: dict[str, str] = {}
    if URL_MAP_PATH.exists():
        try:
            url_map = json.loads(URL_MAP_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            url_map = {}

    errors: list[str] = []
    for i, url in enumerate(feal_urls, 1):
        stem = stable_basename(url)
        cache_ext = Path(urlparse(url).path).suffix.lower() or ".bin"
        if cache_ext not in (".jpg", ".jpeg", ".png", ".gif"):
            cache_ext = ".bin"
        cache_path = CACHE_DIR / f"{stem}{cache_ext}"
        print(f"[{i}/{len(feal_urls)}] {stem}")
        try:
            download(url, cache_path)
            # Guess format from content if needed
            out_name = process_image(cache_path, stem)
            new_url = public_url(repo, out_name, ref=ref)
            url_map[url] = new_url
        except Exception as exc:  # noqa: BLE001 — collect and continue
            errors.append(f"{url}: {exc}")
            print(f"  ERROR: {exc}")

    URL_MAP_PATH.write_text(
        json.dumps(url_map, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {URL_MAP_PATH.relative_to(ROOT)} ({len(url_map)} mappings)")

    print("Rewriting CSV image columns…")
    n = rewrite_csvs(url_map)
    print(f"Updated {n} CSV files")

    # Summary
    asset_count = len(list(ASSETS_DIR.glob("*")))
    print(f"Assets in {ASSETS_DIR.relative_to(ROOT)}: {asset_count} files")
    if errors:
        print(f"\n{len(errors)} errors:")
        for e in errors:
            print(f"  - {e}")
        raise SystemExit(1)
    print("\nDone. Push this repo publicly, then Figma can load jsDelivr URLs.")
    print(f"Example: {next(iter(url_map.values()), '')}")


if __name__ == "__main__":
    run()
