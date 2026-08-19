#!/usr/bin/env bash
# Chạy trọn pipeline cho MỘT NHÓM case, tuần tự trong nhóm nhưng nhiều nhóm chạy song song.
#
# Vì sao cần: proxy chỉ cho ~4 tiến trình CLI đồng thời, mà mỗi khu mất ~15 phút
# (discover ~11, crawl ~2, extract ~3). Chạy 4 nhóm song song rút tổng thời gian
# xuống còn khoảng 1/4 mà không vượt trần đồng thời của proxy.
#
# Mỗi bước tự bỏ qua phần đã làm xong, nên script chạy lại được sau khi gián đoạn:
#   discover -> bỏ qua case đã có refer_file/_discovered/<case>.csv
#   crawl    -> append-only, bỏ URL đã có trong manifest
#   extract  -> --skip-done bỏ case đã có file feature
#
# Dùng:
#   ./scripts/run_batch.sh nhom1 zhengzhou beijing_daxing chengdu_tianfu
#   WANT=15 ./scripts/run_batch.sh nhom2 delhi noida bengaluru
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PY="${PYTHON:-python3}"
WANT="${WANT:-16}"                 # số nguồn xin mỗi khu
export ANTHROPIC_BASE_URL="${ANTHROPIC_BASE_URL:-http://127.0.0.1:11439}"

LABEL="$1"; shift
LOG="raw_data/output/ws1_airport/_batch_${LABEL}.log"
mkdir -p "$(dirname "$LOG")"

say() { echo "[$(date +%H:%M:%S)] [$LABEL] $*" | tee -a "$LOG"; }

say "bắt đầu $# case: $*"
for case_id in "$@"; do
    say "=== $case_id"

    if [ -s "refer_file/_discovered/${case_id}.csv" ]; then
        say "  discover: đã có nguồn, bỏ qua"
    else
        say "  discover…"
        $PY scripts/discover_sources.py --case "$case_id" --want "$WANT" --no-registry \
            >> "$LOG" 2>&1 || say "  ! discover lỗi"
    fi

    if [ -s "refer_file/_discovered/${case_id}.csv" ]; then
        say "  crawl…"
        $PY raw_data/crawler/crawl_sources.py --name "$case_id" \
            --input "refer_file/_discovered/${case_id}.csv" >> "$LOG" 2>&1 || say "  ! crawl lỗi"
    else
        say "  bỏ qua crawl: không tìm được nguồn nào"
        continue
    fi

    if [ -s "raw_data/output/ws1_airport/features/${case_id}_airport_city.json" ]; then
        say "  extract: đã có feature, bỏ qua"
    else
        say "  extract…"
        $PY agent_extractor/ws1_airport/extract_llm.py --case "$case_id" \
            >> "$LOG" 2>&1 || say "  ! extract lỗi"
    fi

    cov=$($PY - "$case_id" <<'PYEOF' 2>/dev/null || echo "?"
import json, sys
from pathlib import Path
p = Path("raw_data/output/ws1_airport/features") / f"{sys.argv[1]}_airport_city.json"
print(json.loads(p.read_text(encoding="utf-8"))["_meta"]["coverage_pct"] if p.exists() else "?")
PYEOF
)
    say "  xong — độ phủ ${cov}%"
done
say "HOÀN TẤT nhóm ($# case)"
