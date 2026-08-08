"""Crawl raw cho WS1 Airport.

Đọc nguồn từ config/sources.yaml -> tải file thô -> lưu vào
raw_data/output/ws1_airport/raw/ kèm manifest.json.

Chỉ tải & lưu thô. Trích xuất feature thuộc agent_extractor/ws1_airport/.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

import base_crawler as bc  # cùng thư mục

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

WS = "ws1_airport"
ROOT = Path(__file__).resolve().parents[2]
SOURCES = ROOT / "config" / "sources.yaml"


def load_sources(workstream: str) -> list[dict]:
    cfg = yaml.safe_load(SOURCES.read_text(encoding="utf-8")) or {}
    return (cfg.get(workstream) or {}).get("sources", [])


def main() -> None:
    sources = load_sources(WS)
    if not sources:
        raise SystemExit(f"Không có source cho {WS} trong {SOURCES}")

    for src in sources:
        url = src["url"]
        print(f"[crawl] {src['name']} <- {url}")
        resp = bc.fetch(url)
        bc.save_raw(
            WS,
            src["raw_file"],
            resp.content,
            source_name=src["name"],
            source_url=url,
            encoding=resp.encoding or "utf-8",
        )

    print(f"[done] crawl {WS} xong -> raw_data/output/{WS}/raw/")


if __name__ == "__main__":
    main()
