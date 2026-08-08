"""HTTP client dùng chung cho mọi crawler.

Cung cấp:
  - fetch(url) với retry + timeout + User-Agent.
  - save_raw(...) lưu file thô + ghi/append manifest.json (provenance).

Dùng requests. Với trang cần render JS, tách sang crawler riêng (Playwright);
base này cố ý giữ nhẹ theo stack requests + BeautifulSoup + pandas.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "raw_data" / "output"

DEFAULT_HEADERS = {
    "User-Agent": "mag-data-crawler/0.1 (+research; contact: set-your-email)",
    "Accept": "*/*",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def fetch(url: str, *, timeout: int = 30, retries: int = 3, backoff: float = 2.0) -> requests.Response:
    """GET với retry luỹ tiến. Trả về Response (raise nếu thất bại hết)."""
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:  # noqa: PERF203
            last_exc = exc
            wait = backoff ** attempt
            print(f"[fetch] lỗi ({attempt}/{retries}) {url}: {exc} -> chờ {wait:.0f}s")
            time.sleep(wait)
    raise RuntimeError(f"fetch thất bại sau {retries} lần: {url}") from last_exc


def raw_dir(workstream: str) -> Path:
    d = OUTPUT / workstream / "raw"
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_raw(
    workstream: str,
    filename: str,
    content: bytes,
    *,
    source_name: str,
    source_url: str,
    encoding: str = "utf-8",
) -> Path:
    """Lưu 1 file thô và cập nhật manifest.json (append provenance)."""
    d = raw_dir(workstream)
    path = d / filename
    path.write_bytes(content)

    manifest_path = d / "manifest.json"
    manifest = {"workstream": workstream, "accessed_at": now_iso(), "sources": []}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    manifest["accessed_at"] = now_iso()
    manifest.setdefault("sources", [])
    # ghi đè entry cùng file, tránh trùng
    manifest["sources"] = [s for s in manifest["sources"] if s.get("raw_file") != filename]
    manifest["sources"].append({
        "name": source_name,
        "url": source_url,
        "raw_file": filename,
        "bytes": len(content),
        "encoding": encoding,
        "accessed_at": now_iso(),
    })
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[raw] lưu {len(content)} bytes -> {path}")
    return path
