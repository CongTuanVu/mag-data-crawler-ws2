"""Orchestrator: chạy end-to-end 1 workstream (registry -> crawl -> extract -> validate -> web).

Dùng:
    python scripts/run_ws.py ws1_airport                    # chạy đủ 5 bước
    python scripts/run_ws.py ws1_airport --steps extract,validate,web
    python scripts/run_ws.py ws1_airport --steps crawl --cases incheon,changi
    python scripts/run_ws.py ws1_airport --dry-run          # chỉ in lệnh sẽ chạy

Các bước (`--steps`, mặc định tất cả, chạy đúng thứ tự liệt kê dưới):

  discover  scripts/discover_sources.py            -> LLM tra web tìm URL nguồn (case chưa có)
  registry  scripts/build_source_registry.py       -> refer_file/{cases,sources}.csv|.xlsx
  crawl     raw_data/crawler/crawl_sources.py      -> raw_data/output/<ws>/raw/<case>/
  extract   agent_extractor/<ws>/extract_llm.py    -> .../features/<case>_airport_city.json
  validate  scripts/validate_features.py           -> benchmark + coverage_report/summary
  web       html/build_portal.py                   -> html/index.html

Đầu vào duy nhất bắt buộc là `refer_file/aerotropolis.txt` (danh sách TÊN aerotropolis,
không cần URL) — bước `discover` nhờ LLM tra web tìm nguồn cho từng khu.

Hai bước `discover` và `extract` gọi model qua code_proxy, nên proxy phải chạy trước:

    CLAUDE_PROXY_MODEL=claude-opus-5 ./code_proxy/start.sh --timeout 900
    export ANTHROPIC_BASE_URL=http://127.0.0.1:11439
"""
from __future__ import annotations

import argparse
import csv
import os
import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

ROOT = Path(__file__).resolve().parents[1]
STEPS = ("discover", "registry", "crawl", "extract", "validate", "web")

PIPELINES = {
    "ws1_airport": {
        # mặc định chỉ tìm nguồn cho case CHƯA có nguồn nào; dùng --steps discover với
        # scripts/discover_sources.py --all để chủ động bổ sung thêm cho case đã có
        "discover": [sys.executable, "scripts/discover_sources.py", "--missing"],
        "registry": [sys.executable, "scripts/build_source_registry.py"],
        # {case} được thay bằng từng case_id trong refer_file/cases.csv
        "crawl": [sys.executable, "raw_data/crawler/crawl_sources.py", "--name", "{case}"],
        "extract": [sys.executable, "agent_extractor/ws1_airport/extract_llm.py", "--all"],
        "validate": [sys.executable, "scripts/validate_features.py"],
        "web": [sys.executable, "html/build_portal.py"],
    },
}


def case_ids(ws: str) -> list[str]:
    path = ROOT / "refer_file" / "cases.csv"
    if not path.exists():
        raise SystemExit(f"Chưa có {path.relative_to(ROOT)} — chạy bước 'registry' trước.")
    with path.open(encoding="utf-8-sig", newline="") as f:
        return [r["case_id"] for r in csv.DictReader(f) if r.get("case_id")]


def run(cmd: list[str], dry: bool) -> int:
    print(f"\n$ {' '.join(cmd)}")
    if dry:
        return 0
    return subprocess.run(cmd, cwd=ROOT).returncode


def main() -> None:
    ap = argparse.ArgumentParser(description="Chạy pipeline 1 workstream")
    ap.add_argument("workstream", choices=sorted(PIPELINES))
    ap.add_argument("--steps", default=",".join(STEPS), help=f"chọn bước: {','.join(STEPS)}")
    ap.add_argument("--cases", default="", help="giới hạn case cho bước crawl/extract")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    steps = [s.strip() for s in args.steps.split(",") if s.strip()]
    if bad := [s for s in steps if s not in STEPS]:
        raise SystemExit(f"Bước không hợp lệ: {', '.join(bad)} (có: {', '.join(STEPS)})")
    steps = [s for s in STEPS if s in steps]  # luôn chạy đúng thứ tự pipeline
    pipe = PIPELINES[args.workstream]
    only = [c.strip() for c in args.cases.split(",") if c.strip()]

    if {"extract", "discover"} & set(steps) and not args.dry_run and not os.getenv("ANTHROPIC_BASE_URL"):
        print("[cảnh báo] chưa đặt ANTHROPIC_BASE_URL — extract_llm.py sẽ thử "
              "http://127.0.0.1:11439 (code_proxy). Khởi động proxy trước nếu chưa chạy.")

    failed = []
    for step in steps:
        print(f"\n{'=' * 60}\n== {step}\n{'=' * 60}")
        if step == "crawl":
            for case in only or case_ids(args.workstream):
                cmd = [c.replace("{case}", case) for c in pipe["crawl"]]
                if run(cmd, args.dry_run):
                    failed.append(f"{step}:{case}")
        else:
            cmd = list(pipe[step])
            if step in ("extract", "discover") and only:
                cmd = [c for c in cmd if c not in ("--all", "--missing")]
                for case in only:
                    if run(cmd + ["--case", case], args.dry_run):
                        failed.append(f"{step}:{case}")
                continue
            if run(cmd, args.dry_run):
                failed.append(step)

    print(f"\n[done] pipeline {args.workstream}: {len(steps)} bước"
          + (f" — LỖI ở {', '.join(failed)}" if failed else " — không lỗi"))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
