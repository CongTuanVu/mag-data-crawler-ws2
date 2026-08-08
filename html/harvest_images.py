"""Thu ảnh minh hoạ cho trang hồ sơ của 1 aerotropolis.

Với mỗi MỤC trình bày, lấy ảnh đại diện (og:image, fallback ảnh lớn đầu tiên) từ
trang đã crawl tương ứng -> tải -> nén/resize -> lưu html/assets/<case>/<mục>.jpg
và ghi images.json (mục -> file, source_image, page_url, caption).

build_html.py sẽ đọc images.json và nhúng ảnh (base64) vào đúng mục.

Chạy:
    python html/harvest_images.py --name schiphol
"""
from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from PIL import Image

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}

# Mục trình bày -> (slug trang nguồn, caption). Curate cho từng case.
CURATION = {
    "schiphol": [
        ("hero",       "03_schiphol_business_district",        "Khu Thương mại Schiphol (Business District)"),
        ("planning",   "17_sadc_schiphol_logistics_park",      "Ảnh trên không khu hậu cần Schiphol Logistics Park"),
        ("vision",     "29_schiphol_airport_of_the_future",    "Định hướng 'Sân bay của tương lai'"),
        ("experience", "08_schiphol_real_estate_facilities",   "Tiện ích & không gian trải nghiệm tại Schiphol"),
    ],
}


def page_url_map(case_dir: Path) -> dict:
    man = case_dir / "manifest.json"
    if not man.exists():
        return {}
    data = json.loads(man.read_text(encoding="utf-8"))
    out = {}
    for s in data.get("sources", []):
        out[s.get("slug", "")] = s.get("url", "")
    return out


def pick_image_url(html_path: Path) -> str | None:
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8", errors="ignore"), "html.parser")
    og = soup.find("meta", attrs={"property": "og:image"})
    if og and og.get("content"):
        return og["content"]
    for i in soup.find_all("img"):
        u = i.get("src") or i.get("data-src") or ""
        if u and any(e in u.lower() for e in (".jpg", ".jpeg", ".png", ".webp")) \
           and not any(x in u.lower() for x in ("icon", "logo", "sprite", "favicon")):
            return u
    return None


def fetch_resize(url: str, max_w: int = 820) -> bytes | None:
    r = requests.get(url, headers=HEADERS, timeout=25)
    r.raise_for_status()
    im = Image.open(io.BytesIO(r.content)).convert("RGB")
    if im.width > max_w:
        im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=80, optimize=True)
    return buf.getvalue()


def main() -> None:
    ap = argparse.ArgumentParser(description="Thu ảnh minh hoạ cho trang hồ sơ")
    ap.add_argument("--name", default="schiphol")
    ap.add_argument("--max-width", type=int, default=820)
    args = ap.parse_args()

    cur = CURATION.get(args.name)
    if not cur:
        raise SystemExit(f"Chưa curate ảnh cho '{args.name}'. Thêm vào CURATION.")

    case_dir = ROOT / "raw_data" / "output" / "ws1_airport" / "raw" / args.name
    pages_dir = case_dir / "pages"
    urls = page_url_map(case_dir)
    out_dir = HERE / "assets" / args.name
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest = {}
    for section, slug, caption in cur:
        html_path = pages_dir / f"{slug}.html"
        if not html_path.exists():
            print(f"  [skip] {section}: không thấy {html_path.name}")
            continue
        img_url = pick_image_url(html_path)
        if not img_url:
            print(f"  [skip] {section}: trang {slug} không có ảnh")
            continue
        try:
            data = fetch_resize(img_url, args.max_width)
        except Exception as exc:  # noqa: BLE001
            print(f"  [fail] {section}: {img_url[:60]} -> {exc}")
            continue
        fname = f"{section}.jpg"
        (out_dir / fname).write_bytes(data)
        manifest[section] = {"file": fname, "source_image": img_url,
                             "page_url": urls.get(slug, ""), "caption": caption,
                             "bytes": len(data)}
        print(f"  [ok] {section}: {len(data):,} bytes <- {img_url[:60]}")

    (out_dir / "images.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[done] {len(manifest)} ảnh -> {out_dir}")


if __name__ == "__main__":
    main()
