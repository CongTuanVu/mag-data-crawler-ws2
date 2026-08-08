"""Orchestrator: chạy end-to-end 1 workstream (crawl raw -> extract feature).

Dùng:
    python scripts/run_ws.py ws1_airport
    python scripts/run_ws.py ws1_airport --extract-only
    python scripts/run_ws.py ws1_airport --crawl-only

Ánh xạ workstream -> (crawler, extractor) khai báo trong PIPELINES.
Thêm workstream mới: thêm 1 entry vào PIPELINES.
"""
from __future__ import annotations

import argparse
import runpy
import sys
from pathlib import Path

try:  # Windows console mặc định cp1252 -> ép UTF-8 để in tiếng Việt
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

ROOT = Path(__file__).resolve().parents[1]

PIPELINES = {
    "ws1_airport": {
        "crawler": ROOT / "raw_data" / "crawler" / "crawl_airport.py",
        "extractor": ROOT / "agent_extractor" / "ws1_airport" / "extract_airport.py",
    },
}


def run_script(path: Path) -> None:
    print(f"\n=== chạy {path.relative_to(ROOT)} ===")
    # thêm thư mục chứa script vào sys.path để import cạnh nhau (vd base_crawler)
    sys.path.insert(0, str(path.parent))
    try:
        runpy.run_path(str(path), run_name="__main__")
    finally:
        sys.path.pop(0)


def main() -> None:
    ap = argparse.ArgumentParser(description="Chạy pipeline crawl->extract cho 1 workstream")
    ap.add_argument("workstream", choices=sorted(PIPELINES), help="tên workstream")
    ap.add_argument("--crawl-only", action="store_true", help="chỉ crawl raw")
    ap.add_argument("--extract-only", action="store_true", help="chỉ extract (bỏ crawl)")
    args = ap.parse_args()

    pipe = PIPELINES[args.workstream]
    if not args.extract_only:
        run_script(pipe["crawler"])
    if not args.crawl_only:
        run_script(pipe["extractor"])

    print(f"\n[done] pipeline {args.workstream} hoàn tất.")


if __name__ == "__main__":
    main()
