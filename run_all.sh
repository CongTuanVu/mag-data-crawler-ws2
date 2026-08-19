#!/usr/bin/env bash
# MỘT LỆNH: refer_file/aerotropolis.txt  ──▶  html/index.html
#
#   ./run_all.sh              # chạy mọi khu chưa có dữ liệu, 4 luồng song song
#   JOBS=6 ./run_all.sh       # 6 luồng (nhớ nâng LLM_PROXY_MAX_CONCURRENCY cho khớp)
#   ./run_all.sh zhengzhou delhi     # chỉ vài khu chỉ định
#   FRESH=1 ./run_all.sh      # làm lại cả những khu đã có feature
#
# Tự lo: khởi động code_proxy nếu chưa chạy, chia nhóm, chạy song song, chờ xong,
# rồi registry -> validate -> build_portal. Ngắt giữa chừng chạy lại là tiếp tục,
# không làm lại phần đã xong.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

PY="${PYTHON:-python3}"
JOBS="${JOBS:-4}"
export ANTHROPIC_BASE_URL="${ANTHROPIC_BASE_URL:-http://127.0.0.1:11439}"
STAMP="$(date +%Y%m%d_%H%M%S)"
LOGDIR="raw_data/output/ws1_airport"
mkdir -p "$LOGDIR"

say() { printf '\n\033[1m[%s] %s\033[0m\n' "$(date +%H:%M:%S)" "$*"; }
die() { printf '\n\033[31m[lỗi] %s\033[0m\n' "$*" >&2; exit 1; }

# ── 1. proxy ────────────────────────────────────────────────────────────────
if curl -fsS -m 5 "$ANTHROPIC_BASE_URL/healthz" > /dev/null 2>&1; then
    say "proxy đã chạy: $ANTHROPIC_BASE_URL"
elif [ -n "${ANTHROPIC_API_KEY:-}" ]; then
    say "dùng ANTHROPIC_API_KEY (gọi thẳng api.anthropic.com, không cần proxy)"
else
    say "khởi động code_proxy…"
    command -v claude > /dev/null || die "chưa có Claude Code CLI. Cài rồi chạy: claude auth login"
    claude auth status 2>/dev/null | grep -q '"loggedIn": true' \
        || die "Claude CLI chưa đăng nhập. Chạy: claude auth login"
    CLAUDE_PROXY_MODEL="${CLAUDE_PROXY_MODEL:-claude-opus-5}" \
        nohup ./code_proxy/start.sh --timeout 900 > "$LOGDIR/_proxy_$STAMP.log" 2>&1 &
    for _ in $(seq 30); do
        curl -fsS -m 2 "$ANTHROPIC_BASE_URL/healthz" > /dev/null 2>&1 && break
        sleep 1
    done
    curl -fsS -m 5 "$ANTHROPIC_BASE_URL/healthz" > /dev/null 2>&1 \
        || die "proxy không lên được — xem $LOGDIR/_proxy_$STAMP.log"
    say "proxy sẵn sàng"
fi

# ── 2. danh sách khu cần chạy ───────────────────────────────────────────────
if [ $# -gt 0 ]; then
    CASES="$*"
else
    CASES=$(FRESH="${FRESH:-}" $PY - <<'PYEOF'
import importlib.util, os
from pathlib import Path
spec = importlib.util.spec_from_file_location("b", "scripts/build_source_registry.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
reg = m.load_registry(); taken = set(reg)
feat = Path("raw_data/output/ws1_airport/features")
fresh = bool(os.environ.get("FRESH"))
ids = [m.match_case_id(e, reg, taken) for e in m.parse_case_list()]
print(" ".join(c for c in ids if fresh or not (feat / f"{c}_airport_city.json").exists()))
PYEOF
    ) || die "không đọc được refer_file/aerotropolis.txt"
fi

# shellcheck disable=SC2086
set -- $CASES
if [ $# -eq 0 ]; then
    say "mọi khu đã có dữ liệu — bỏ qua thẳng tới bước dựng trang (FRESH=1 để làm lại)"
else
    say "$# khu cần chạy, $JOBS luồng song song · ước tính $(( ($# * 15 + JOBS - 1) / JOBS )) phút"
    i=0
    for case_id in "$@"; do
        i=$((i + 1))
        eval "G$(( (i - 1) % JOBS + 1 ))=\"\${G$(( (i - 1) % JOBS + 1 )):-} $case_id\""
    done
    pids=()
    for n in $(seq "$JOBS"); do
        eval "grp=\${G$n:-}"
        [ -z "${grp// /}" ] && continue
        # shellcheck disable=SC2086
        ./scripts/run_batch.sh "n$n" $grp > "$LOGDIR/_batch_n${n}_$STAMP.out" 2>&1 &
        pids+=($!)
    done
    say "đang chạy… theo dõi: tail -f $LOGDIR/_batch_n*.log"
    for pid in "${pids[@]}"; do wait "$pid"; done
    say "xong toàn bộ khu"
fi

# ── 3. gộp, kiểm tra, dựng trang ────────────────────────────────────────────
say "dựng registry nguồn"
$PY scripts/build_source_registry.py || die "build_source_registry thất bại"

say "kiểm tra dữ liệu"
$PY scripts/validate_features.py || die "validate_features thất bại"

say "dựng trang web"
$PY html/build_portal.py || die "build_portal thất bại"

printf '\n\033[32m════ HOÀN TẤT ════\033[0m\n'
printf '  trang web : %s/html/index.html\n' "$ROOT"
printf '  bảng phủ  : raw_data/output/ws1_airport/features/coverage_summary.csv\n'
printf '  chi tiết  : raw_data/output/ws1_airport/features/coverage_report.csv\n\n'
