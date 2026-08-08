"""Crawler Playwright cho danh sách Aerotropolis — lấy ẢNH (JS lazy-load).

Khác với crawl_aerotropolis.py (chỉ HTML tĩnh, requests), bản này mở trang bằng
Chromium thật để:
  - render JS + cuộn trang kích hoạt lazy-load,
  - thu thập ảnh nội dung (lọc theo kích thước, bỏ icon/logo),
  - chụp full-page screenshot (bản "giống slide"),
  - lưu HTML đã render,
  - thường vượt được tường 403 vì là trình duyệt thật.

Output: raw_data/output/ws1_airport/raw/aerotropolis/pages_assets/<slug>/
  screenshot.png, rendered.html, images/img_XXX.<ext>

Ví dụ:
    python raw_data/crawler/crawl_aerotropolis_pw.py --limit 3
    python raw_data/crawler/crawl_aerotropolis_pw.py --max-images 12
    python raw_data/crawler/crawl_aerotropolis_pw.py --headful   # xem trình duyệt chạy
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import Error as PWError
from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright

from base_crawler import now_iso  # cùng thư mục

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

WS = "ws1_airport"
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CSV = ROOT / "refer_file" / "Aerotropolis.csv"
OUT_DIR = ROOT / "raw_data" / "output" / WS / "raw" / "aerotropolis"
ASSETS_DIR = OUT_DIR / "pages_assets"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

# JS thu thập ảnh trong DOM đã render: <img> (kèm kích thước thật), og:image,
# và background-image từ CSS. Trả về list {url, w, h, kind}.
COLLECT_JS = r"""
() => {
  const out = [];
  const seen = new Set();
  const push = (url, w, h, kind) => {
    if (!url) return;
    if (url.startsWith('data:')) return;
    try { url = new URL(url, location.href).href; } catch (e) { return; }
    if (!/^https?:/.test(url)) return;
    if (seen.has(url)) return;
    seen.add(url);
    out.push({ url, w: w || 0, h: h || 0, kind });
  };
  document.querySelectorAll('img').forEach(im => {
    push(im.currentSrc || im.src, im.naturalWidth, im.naturalHeight, 'img');
  });
  document.querySelectorAll('meta[property="og:image"], meta[name="twitter:image"]').forEach(m => {
    push(m.content, 1200, 630, 'og');
  });
  document.querySelectorAll('*').forEach(el => {
    const bg = getComputedStyle(el).backgroundImage;
    if (bg && bg.startsWith('url(')) {
      const u = bg.slice(4, -1).replace(/["']/g, '');
      const r = el.getBoundingClientRect();
      push(u, Math.round(r.width), Math.round(r.height), 'bg');
    }
  });
  return out;
}
"""


def slugify(*parts: str) -> str:
    raw = "_".join(p for p in parts if p).lower().strip()
    raw = re.sub(r"[^a-z0-9]+", "_", raw)
    return raw.strip("_") or "page"


def read_rows(csv_path: Path) -> list[dict]:
    with csv_path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def ext_from(url: str, content_type: str) -> str:
    ct = (content_type or "").lower()
    for key, e in (("jpeg", "jpg"), ("jpg", "jpg"), ("png", "png"),
                   ("webp", "webp"), ("gif", "gif"), ("svg", "svg"), ("avif", "avif")):
        if key in ct:
            return e
    m = re.search(r"\.(jpg|jpeg|png|webp|gif|svg|avif)", urlparse(url).path.lower())
    return {"jpeg": "jpg"}.get(m.group(1), m.group(1)) if m else "img"


def auto_scroll(page, steps: int = 8, pause: float = 0.4) -> None:
    """Cuộn dần xuống cuối trang để kích hoạt lazy-load."""
    try:
        for _ in range(steps):
            page.mouse.wheel(0, 2000)
            time.sleep(pause)
        page.evaluate("window.scrollTo(0, 0)")
        time.sleep(0.2)
    except PWError:
        pass


def crawl_one(context, row: dict, args) -> dict:
    url = (row.get("website_url") or "").strip()
    country = (row.get("country") or "").strip()
    airport = (row.get("airport") or "").strip()
    slug = slugify(airport) if slugify(airport) != "page" else slugify(country, airport)

    entry = {
        "country": country, "airport": airport,
        "aerotropolis": (row.get("aerotropolis") or "").strip(),
        "source_url": url, "slug": slug, "accessed_at": now_iso(),
        "http_status": None, "n_images": 0, "screenshot": False,
        "rendered_html": False, "status": "error", "error": None,
    }
    if not url:
        entry["error"] = "empty url"
        return entry

    site_dir = ASSETS_DIR / slug
    img_dir = site_dir / "images"
    page = context.new_page()
    try:
        resp = page.goto(url, wait_until="domcontentloaded", timeout=args.timeout * 1000)
        entry["http_status"] = resp.status if resp else None
        try:
            page.wait_for_load_state("networkidle", timeout=8000)
        except PWTimeout:
            pass
        auto_scroll(page)

        site_dir.mkdir(parents=True, exist_ok=True)
        # HTML đã render
        (site_dir / "rendered.html").write_text(page.content(), encoding="utf-8", errors="ignore")
        entry["rendered_html"] = True

        # Full-page screenshot (bản "giống slide")
        try:
            page.screenshot(path=str(site_dir / "screenshot.png"), full_page=True)
            entry["screenshot"] = True
        except PWError as exc:
            entry["error"] = f"screenshot: {exc}"

        # Thu thập + lọc ảnh
        imgs = page.evaluate(COLLECT_JS)
        keep = [i for i in imgs
                if i["kind"] == "og"
                or (i["w"] >= args.min_width and i["h"] >= args.min_height)]
        keep.sort(key=lambda i: (i["kind"] != "og", -(i["w"] * i["h"])))
        keep = keep[: args.max_images]

        saved = 0
        for idx, im in enumerate(keep, 1):
            try:
                r = context.request.get(im["url"], timeout=20000)
                if not r.ok:
                    continue
                body = r.body()
                if len(body) < 3000:  # bỏ ảnh quá nhỏ (icon/placeholder)
                    continue
                ext = ext_from(im["url"], r.headers.get("content-type", ""))
                img_dir.mkdir(parents=True, exist_ok=True)
                (img_dir / f"img_{idx:03d}.{ext}").write_bytes(body)
                saved += 1
            except PWError:
                continue
        entry["n_images"] = saved
        entry["status"] = "ok" if (resp and resp.ok) else "http_error"
        if resp and not resp.ok and not entry["error"]:
            entry["error"] = f"HTTP {resp.status}"
        print(f"  ✓ {entry['http_status']} · {saved} ảnh · screenshot={entry['screenshot']} -> {slug}/")
    except PWTimeout:
        entry["error"] = "timeout"
        print(f"  ✗ timeout: {url}")
    except PWError as exc:
        entry["error"] = str(exc).splitlines()[0][:200]
        print(f"  ✗ lỗi: {entry['error']}")
    finally:
        page.close()
    return entry


def main() -> None:
    ap = argparse.ArgumentParser(description="Crawl ảnh (Playwright) từ danh sách Aerotropolis")
    ap.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    ap.add_argument("--limit", type=int, default=0, help="chỉ N dòng đầu (0 = tất cả)")
    ap.add_argument("--max-images", type=int, default=12, help="số ảnh tối đa mỗi site")
    ap.add_argument("--min-width", type=int, default=400, help="bỏ ảnh hẹp hơn (px)")
    ap.add_argument("--min-height", type=int, default=300, help="bỏ ảnh thấp hơn (px)")
    ap.add_argument("--timeout", type=int, default=35, help="timeout goto mỗi trang (giây)")
    ap.add_argument("--headful", action="store_true", help="hiện cửa sổ trình duyệt")
    args = ap.parse_args()

    if not args.csv.exists():
        raise SystemExit(f"Không thấy CSV: {args.csv}")
    rows = read_rows(args.csv)
    if args.limit > 0:
        rows = rows[: args.limit]
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    log_rows: list[dict] = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not args.headful)
        context = browser.new_context(
            user_agent=UA, viewport={"width": 1440, "height": 900},
            locale="en-US", ignore_https_errors=True,
        )
        context.set_default_timeout(args.timeout * 1000)
        for i, row in enumerate(rows, 1):
            print(f"[{i}/{len(rows)}] {row.get('country')} / {row.get('airport')} <- {row.get('website_url')}")
            log_rows.append(crawl_one(context, row, args))
        context.close()
        browser.close()

    ok = sum(1 for r in log_rows if r["status"] == "ok")
    total_imgs = sum(r["n_images"] for r in log_rows)
    manifest = {
        "workstream": WS, "dataset": "aerotropolis_images", "engine": "playwright",
        "source_csv": str(args.csv.relative_to(ROOT)) if args.csv.is_relative_to(ROOT) else str(args.csv),
        "accessed_at": now_iso(), "total": len(rows), "ok": ok,
        "total_images": total_imgs, "sources": log_rows,
    }
    (OUT_DIR / "pw_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    fields = ["country", "airport", "aerotropolis", "source_url", "slug", "status",
              "http_status", "n_images", "screenshot", "rendered_html", "accessed_at", "error"]
    with (OUT_DIR / "pw_crawl_log.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader(); w.writerows(log_rows)

    print(f"\n[done] ok={ok}/{len(rows)} · tổng {total_imgs} ảnh")
    print(f"       assets -> {ASSETS_DIR}")
    print(f"       log    -> {OUT_DIR / 'pw_crawl_log.csv'}")


if __name__ == "__main__":
    main()
