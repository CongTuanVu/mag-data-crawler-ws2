"""Crawl raw HTML cho danh sách Aerotropolis / Airport City.

Đọc URL từ file CSV (mặc định: refer_file/Aerotropolis.csv) -> tải HTML thô của
từng `website_url` -> lưu vào raw_data/output/ws1_airport/raw/aerotropolis/ kèm
manifest.json (provenance) và crawl_log.csv (kết quả từng URL).

Chỉ tải & lưu thô. Không parse feature (việc đó thuộc agent_extractor/).
Chạy độc lập hoặc qua scripts/run_ws.py.

Ví dụ:
    python raw_data/crawler/crawl_aerotropolis.py
    python raw_data/crawler/crawl_aerotropolis.py --limit 5 --delay 0.5
    python raw_data/crawler/crawl_aerotropolis.py --csv refer_file/Aerotropolis.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from pathlib import Path

import requests

from base_crawler import DEFAULT_HEADERS, now_iso  # cùng thư mục

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

WS = "ws1_airport"
ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CSV = ROOT / "refer_file" / "Aerotropolis.csv"
OUT_DIR = ROOT / "raw_data" / "output" / WS / "raw" / "aerotropolis"
PAGES_DIR = OUT_DIR / "pages"

# Header giống trình duyệt để giảm chặn bot (giữ mô tả trung thực trong UA gốc).
HEADERS = {
    **DEFAULT_HEADERS,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en,vi;q=0.9",
}


def slugify(*parts: str) -> str:
    raw = "_".join(p for p in parts if p)
    raw = raw.lower().strip()
    raw = re.sub(r"[^a-z0-9]+", "_", raw)
    return raw.strip("_") or "page"


def read_rows(csv_path: Path) -> list[dict]:
    with csv_path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def fetch(url: str, *, timeout: int, retries: int, backoff: float,
          allow_insecure: bool = True) -> requests.Response:
    """GET bền cho crawl hàng loạt.

    - Retry chỉ khi lỗi mạng hoặc HTTP 5xx.
    - KHÔNG raise ở 4xx: trả về Response để ghi lại status và đi tiếp.
    - Nếu chứng chỉ TLS lỗi và allow_insecure=True: thử lại 1 lần với verify=False
      và đánh dấu resp.tls_verified=False (đã hạ bảo mật, ghi rõ trong log).
    """
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
            if resp.status_code >= 500 and attempt < retries:
                raise requests.HTTPError(f"{resp.status_code} server error")
            resp.tls_verified = True
            return resp
        except requests.exceptions.SSLError as exc:
            last_exc = exc
            if allow_insecure:
                try:
                    import urllib3
                    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
                    resp = requests.get(url, headers=HEADERS, timeout=timeout,
                                        allow_redirects=True, verify=False)
                    resp.tls_verified = False
                    print("  ⚠ TLS verify lỗi -> fallback verify=False")
                    return resp
                except requests.RequestException as exc2:
                    last_exc = exc2
            if attempt < retries:
                time.sleep(backoff ** attempt)
        except requests.RequestException as exc:
            last_exc = exc
            if attempt < retries:
                wait = backoff ** attempt
                print(f"  retry {attempt}/{retries} sau {wait:.0f}s: {exc}")
                time.sleep(wait)
    raise RuntimeError(f"fetch thất bại: {url}") from last_exc


def main() -> None:
    ap = argparse.ArgumentParser(description="Crawl raw HTML từ danh sách Aerotropolis")
    ap.add_argument("--csv", type=Path, default=DEFAULT_CSV, help="đường dẫn file CSV nguồn")
    ap.add_argument("--limit", type=int, default=0, help="chỉ crawl N dòng đầu (0 = tất cả)")
    ap.add_argument("--delay", type=float, default=1.0, help="nghỉ giữa các request (giây)")
    ap.add_argument("--timeout", type=int, default=25, help="timeout mỗi request (giây)")
    ap.add_argument("--retries", type=int, default=2, help="số lần thử lại khi lỗi mạng/5xx")
    args = ap.parse_args()

    if not args.csv.exists():
        raise SystemExit(f"Không thấy CSV: {args.csv}")

    rows = read_rows(args.csv)
    if args.limit > 0:
        rows = rows[: args.limit]
    PAGES_DIR.mkdir(parents=True, exist_ok=True)

    manifest_sources: list[dict] = []
    log_rows: list[dict] = []
    ok = fail = 0

    for i, row in enumerate(rows, 1):
        url = (row.get("website_url") or "").strip()
        country = (row.get("country") or "").strip()
        airport = (row.get("airport") or "").strip()
        slug = slugify(airport) if slugify(airport) != "page" else slugify(country, airport)
        print(f"[{i}/{len(rows)}] {country} / {airport} <- {url}")

        entry = {
            "country": country,
            "airport": airport,
            "aerotropolis": (row.get("aerotropolis") or "").strip(),
            "source_url": url,
            "slug": slug,
            "accessed_at": now_iso(),
        }

        if not url:
            entry.update(status="skipped", http_status=None, saved_file=None, error="empty url")
            log_rows.append(entry); fail += 1
            continue

        try:
            resp = fetch(url, timeout=args.timeout, retries=args.retries, backoff=2.0)
        except RuntimeError as exc:
            entry.update(status="error", http_status=None, saved_file=None,
                         bytes=0, final_url=None, content_type=None, error=str(exc))
            log_rows.append(entry); fail += 1
            print(f"  ✗ lỗi: {exc}")
            time.sleep(args.delay)
            continue

        content_type = resp.headers.get("Content-Type", "")
        ext = "html" if "html" in content_type or not content_type else "bin"
        fname = f"{slug}.{ext}"
        (PAGES_DIR / fname).write_bytes(resp.content)

        good = resp.ok  # 2xx/3xx
        entry.update(
            status="ok" if good else "http_error",
            http_status=resp.status_code,
            final_url=resp.url,
            content_type=content_type,
            bytes=len(resp.content),
            saved_file=f"pages/{fname}",
            encoding=resp.encoding,
            tls_verified=getattr(resp, "tls_verified", True),
            error=None if good else f"HTTP {resp.status_code}",
        )
        log_rows.append(entry)
        manifest_sources.append(entry)
        if good:
            ok += 1
            print(f"  ✓ {resp.status_code} · {len(resp.content):,} bytes -> pages/{fname}")
        else:
            fail += 1
            print(f"  ✗ HTTP {resp.status_code} (vẫn lưu body) -> pages/{fname}")

        time.sleep(args.delay)

    # --- Ghi manifest.json ---
    manifest = {
        "workstream": WS,
        "dataset": "aerotropolis",
        "source_csv": str(args.csv.relative_to(ROOT)) if args.csv.is_relative_to(ROOT) else str(args.csv),
        "accessed_at": now_iso(),
        "total": len(rows),
        "ok": ok,
        "fail": fail,
        "sources": manifest_sources,
    }
    (OUT_DIR / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # --- Ghi crawl_log.csv ---
    log_fields = ["country", "airport", "aerotropolis", "source_url", "final_url",
                  "slug", "status", "http_status", "content_type", "bytes",
                  "saved_file", "encoding", "tls_verified", "accessed_at", "error"]
    with (OUT_DIR / "crawl_log.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=log_fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(log_rows)

    print(f"\n[done] ok={ok} fail={fail}/{len(rows)}")
    print(f"       raw   -> {PAGES_DIR}")
    print(f"       log   -> {OUT_DIR / 'crawl_log.csv'}")
    print(f"       meta  -> {OUT_DIR / 'manifest.json'}")


if __name__ == "__main__":
    main()
