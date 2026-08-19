"""Crawl theo DANH SÁCH NGUỒN đã tuyển cho MỘT aerotropolis (có APPEND + PDF).

Nhận input là bảng nguồn (.txt markdown / .csv) — mỗi dòng 1 URL trỏ đúng nội
dung cần, kèm ghi chú "dùng để lấy gì". Render bằng Chromium; PDF thì tải & bóc
text bằng PyMuPDF.

Chế độ mặc định = APPEND: nếu raw/<name>/manifest.json đã có, sẽ GỘP THÊM, bỏ
URL đã crawl, đánh số tiếp — không làm mất data cũ. Dùng --fresh để crawl lại từ đầu.

Lưu mỗi nguồn:
  pages/<NN>_<slug>.html|.pdf  — bản gốc đã render/tải
  pages/<NN>_<slug>.txt        — text sạch (để extractor đọc)
  pages/<NN>_<slug>.png        — screenshot (chỉ khi bật --shots; ảnh rất nặng)

Ví dụ:
    python raw_data/crawler/crawl_sources.py --name schiphol           # đọc refer_file/sources.csv
    python raw_data/crawler/crawl_sources.py --name schiphol --fresh
    python raw_data/crawler/crawl_sources.py --name schiphol --input refer_file/Schiphol.txt
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import pymupdf
from bs4 import BeautifulSoup
from playwright.sync_api import Error as PWError
from playwright.sync_api import TimeoutError as PWTimeout
from playwright.sync_api import sync_playwright

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

WS = "ws1_airport"
ROOT = Path(__file__).resolve().parents[2]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def clean_url(url: str) -> str:
    p = urlparse(url)
    q = [(k, v) for k, v in parse_qsl(p.query) if not k.lower().startswith("utm_")]
    return urlunparse(p._replace(query=urlencode(q)))


def slugify(text: str, fallback: str = "page") -> str:
    s = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return s[:50] or fallback


def parse_input(path: Path, case: str = "") -> list[dict]:
    """Đọc danh sách nguồn. CSV registry (refer_file/sources.csv) lọc theo cột case_id."""
    rows: list[dict] = []
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                url = (r.get("website_url") or r.get("url") or "").strip()
                if not url:
                    continue
                if case and (r.get("case_id") or "").strip() and r["case_id"].strip() != case:
                    continue
                rows.append({"url": clean_url(url),
                             "anchor": (r.get("anchor") or r.get("name") or r.get("website_name") or "").strip(),
                             "purpose": (r.get("purpose") or "").strip()})
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        m = LINK_RE.search(line)
        if not m:
            continue
        anchor, url = m.group(1).strip(), clean_url(m.group(2).strip())
        purpose = ""
        if "|" in line:
            cells = [c.strip() for c in line.split("|")]
            link_idx = next((i for i, c in enumerate(cells) if "](" in c), None)
            if link_idx is not None and link_idx + 1 < len(cells):
                purpose = re.sub(r"\*\*|`", "", cells[link_idx + 1]).strip()
        rows.append({"url": url, "anchor": anchor, "purpose": purpose})
    return rows


def visible_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for t in soup(["script", "style", "noscript"]):
        t.decompose()
    return "\n".join(ln.strip() for ln in soup.get_text("\n").splitlines() if ln.strip())


def meta_of(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    def m(**kw):
        el = soup.find("meta", attrs=kw)
        return (el.get("content") or "").strip() if el else ""
    return {"title": (soup.title.string or "").strip() if soup.title else "",
            "description": m(name="description")}


def pdf_text(data: bytes) -> str:
    doc = pymupdf.open(stream=data, filetype="pdf")
    return "\n".join(page.get_text() for page in doc)


def is_pdf(url: str) -> bool:
    return urlparse(url).path.lower().endswith(".pdf")


def crawl_one(ctx, src: dict, idx: int, pages_dir: Path, args) -> dict:
    url = src["url"]
    # anchor không phải latin (Nhật/Hàn/Trung) slugify ra rỗng -> lùi về host+path cho còn đọc được
    p = urlparse(url)
    slug = f"{idx:02d}_" + (slugify(src["anchor"], "") or slugify(f"{p.netloc}_{p.path}"))
    entry = {"idx": idx, "anchor": src["anchor"], "purpose": src["purpose"],
             "url": url, "slug": slug, "accessed_at": now_iso(),
             "kind": "pdf" if is_pdf(url) else "html", "http_status": None,
             "chars": 0, "title": "", "html_file": None, "text_file": None,
             "shot_file": None, "status": "error", "error": None}
    page = ctx.new_page()
    try:
        if is_pdf(url):
            r = ctx.request.get(url, timeout=args.timeout * 1000)
            entry["http_status"] = r.status
            if r.ok:
                data = r.body()
                (pages_dir / f"{slug}.pdf").write_bytes(data)
                txt = pdf_text(data)
                (pages_dir / f"{slug}.txt").write_text(txt, encoding="utf-8")
                entry.update(chars=len(txt), html_file=f"pages/{slug}.pdf",
                             text_file=f"pages/{slug}.txt", status="ok")
                print(f"  ✓ PDF {r.status} · {len(txt):,} ký tự -> {slug}")
            else:
                entry["error"] = f"HTTP {r.status}"
                print(f"  ✗ PDF HTTP {r.status}")
            return entry

        resp = page.goto(url, wait_until="domcontentloaded", timeout=args.timeout * 1000)
        entry["http_status"] = resp.status if resp else None
        try:
            page.wait_for_load_state("networkidle", timeout=8000)
        except PWTimeout:
            pass
        try:
            for _ in range(4):
                page.mouse.wheel(0, 2200)
                page.wait_for_timeout(350)
            page.evaluate("window.scrollTo(0,0)")
        except PWError:
            pass
        html = page.content()
        (pages_dir / f"{slug}.html").write_text(html, encoding="utf-8", errors="ignore")
        txt = visible_text(html)
        (pages_dir / f"{slug}.txt").write_text(txt, encoding="utf-8")
        entry.update(chars=len(txt), title=meta_of(html)["title"],
                     html_file=f"pages/{slug}.html", text_file=f"pages/{slug}.txt")
        if args.shots:
            try:
                page.screenshot(path=str(pages_dir / f"{slug}.png"), full_page=True)
                entry["shot_file"] = f"pages/{slug}.png"
            except PWError as exc:
                entry["error"] = f"shot: {str(exc).splitlines()[0][:120]}"
        entry["status"] = "ok" if (resp and resp.ok) else "http_error"
        if resp and not resp.ok and not entry["error"]:
            entry["error"] = f"HTTP {resp.status}"
        print(f"  ✓ {entry['http_status']} · {entry['chars']:,} ký tự -> {slug}")
    except PWTimeout:
        entry["error"] = "timeout"; print("  ✗ timeout")
    except PWError as exc:
        entry["error"] = str(exc).splitlines()[0][:200]; print(f"  ✗ {entry['error']}")
    finally:
        page.close()
    return entry


def main() -> None:
    ap = argparse.ArgumentParser(description="Crawl danh sách nguồn (append + PDF) cho 1 aerotropolis")
    ap.add_argument("--name", required=True)
    ap.add_argument("--input", type=Path, default=ROOT / "refer_file" / "sources.csv",
                    help="bảng nguồn: registry CSV (mặc định) hoặc .txt markdown")
    ap.add_argument("--case", default="", help="lọc case_id trong registry CSV (mặc định = --name)")
    ap.add_argument("--timeout", type=int, default=40)
    ap.add_argument("--shots", action="store_true",
                    help="chụp screenshot mỗi trang (mặc định tắt: ảnh chiếm ~80% dung lượng raw mà không khâu nào đọc tới)")
    ap.add_argument("--fresh", action="store_true", help="bỏ qua data cũ, crawl lại từ đầu")
    ap.add_argument("--headful", action="store_true")
    args = ap.parse_args()

    if not args.input.exists():
        raise SystemExit(f"Không thấy input: {args.input}")
    sources = parse_input(args.input, args.case or args.name)
    if not sources:
        raise SystemExit(f"Không tách được URL nào từ {args.input} (case={args.case or args.name})")

    out_dir = ROOT / "raw_data" / "output" / WS / "raw" / args.name
    pages_dir = out_dir / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)

    # --- APPEND: nạp data cũ, bỏ URL trùng, đánh số tiếp ---
    existing: list[dict] = []
    man_path = out_dir / "manifest.json"
    if man_path.exists() and not args.fresh:
        existing = json.loads(man_path.read_text(encoding="utf-8")).get("sources", [])
    seen = {clean_url(s["url"]) for s in existing}
    start = max([s.get("idx", 0) for s in existing], default=0)
    todo = [s for s in sources if s["url"] not in seen]
    skipped = len(sources) - len(todo)
    print(f"[input] {len(sources)} nguồn | đã có {len(existing)} | bỏ trùng {skipped} | crawl mới {len(todo)}")

    new_rows: list[dict] = []
    if todo:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=not args.headful)
            ctx = browser.new_context(user_agent=UA, viewport={"width": 1440, "height": 900},
                                      locale="en-US", ignore_https_errors=True)
            ctx.set_default_timeout(args.timeout * 1000)
            for i, src in enumerate(todo, 1):
                idx = start + i
                print(f"[{i}/{len(todo)}] (#{idx}) {src['anchor'][:48]} <- {src['url']}")
                new_rows.append(crawl_one(ctx, src, idx, pages_dir, args))
            ctx.close(); browser.close()

    all_rows = existing + new_rows
    ok = sum(1 for r in all_rows if r["status"] == "ok")
    manifest = {"workstream": WS, "aerotropolis": args.name, "engine": "playwright",
                "inputs_last": str(args.input.relative_to(ROOT)) if args.input.is_relative_to(ROOT) else str(args.input),
                "accessed_at": now_iso(), "total": len(all_rows), "ok": ok, "sources": all_rows}
    man_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    fields = ["idx", "anchor", "purpose", "url", "slug", "kind", "status", "http_status",
              "chars", "title", "html_file", "text_file", "shot_file", "accessed_at", "error"]
    with (out_dir / "crawl_log.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader(); w.writerows(all_rows)

    print(f"\n[done] {args.name}: tổng {len(all_rows)} nguồn, ok={ok} (mới crawl {len(new_rows)})")
    print(f"       -> {out_dir}")


if __name__ == "__main__":
    main()
