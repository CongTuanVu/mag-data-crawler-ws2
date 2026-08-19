"""Nén raw đã crawl của 1 case thành "dossier" đủ nhỏ để LLM đọc.

Raw thô của WS1 là ~3,9 triệu ký tự (~965k token) — không thể đưa thẳng vào prompt.
Module này giảm ~90% khối lượng mà vẫn giữ chỗ chứa dữ kiện:

  1. Bỏ boilerplate: dòng xuất hiện lại ở >=40% số trang của cùng case (menu, footer,
     cookie banner) — chỉ bỏ dòng ngắn, không đụng đoạn nội dung.
  2. Chia trang thành block, chấm điểm theo `kw` khai báo trong features/ws1_airport/schema.json
     (+2 mỗi trường khớp), theo mật độ số liệu (+2), và theo vị trí đầu trang (+1).
  3. Giữ block điểm > 0 theo đúng thứ tự gốc tới khi chạm hạn ngạch trang/case.

Mỗi trang được gắn mã [S07] để LLM trích dẫn nguồn — mã này map ngược về url trong
manifest.json, nên provenance không phải do LLM bịa ra.

Dùng như thư viện (extract_llm.py import) hoặc chạy trực tiếp để xem trước:

    python agent_extractor/ws1_airport/llm_prep.py --case incheon --out /tmp/incheon.md
    python agent_extractor/ws1_airport/llm_prep.py --case incheon --groups kpi,investment
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

WS = "ws1_airport"
ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "raw_data" / "output" / WS / "raw"
FEATURES = ROOT / "raw_data" / "output" / WS / "features"
SCHEMA_PATH = ROOT / "features" / WS / "schema.json"

# Số liệu kèm đơn vị -> dấu hiệu block có dữ kiện định lượng.
NUM_RE = re.compile(
    r"\d[\d.,]*\s*(?:%|m2|m²|km2|km²|ha|hectare|acre|km|million|billion|trillion|tonne|ton|"
    r"passenger|movement|employee|job|compan|building|destination|airline|usd|eur|krw|won|"
    r"sgd|myr|twd|aud|hkd|aed|\$|€|£|¥|₩)", re.I)
BOILER_MAX_LEN = 200
BOILER_RATIO = 0.4


def load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def group_fields(schema: dict, group_ids: list[str] | None = None) -> list[dict]:
    """Trả danh sách field của các nhóm được chọn (None = tất cả)."""
    return [f for g in schema["groups"]
            if not group_ids or g["id"] in group_ids
            for f in g["fields"]]


def load_manifest(case: str) -> list[dict]:
    path = RAW / case / "manifest.json"
    if not path.exists():
        raise SystemExit(f"Chưa có raw cho case '{case}' — chạy crawl_sources.py trước ({path})")
    return json.loads(path.read_text(encoding="utf-8")).get("sources", [])


def boilerplate_lines(pages: list[tuple[dict, str]]) -> set[str]:
    """Dòng ngắn lặp lại trên nhiều trang -> nhiễu điều hướng."""
    if len(pages) < 3:
        return set()
    counter: Counter[str] = Counter()
    for _, text in pages:
        counter.update({ln.strip() for ln in text.splitlines() if ln.strip()})
    limit = max(3, int(len(pages) * BOILER_RATIO))
    return {ln for ln, n in counter.items() if n >= limit and len(ln) <= BOILER_MAX_LEN}


def split_blocks(text: str, boiler: set[str], max_lines: int = 6) -> list[str]:
    """Gom dòng thành block ngắn, bỏ dòng boilerplate và dòng rác 1-2 ký tự."""
    blocks, buf = [], []
    for line in text.splitlines():
        ln = line.strip()
        if not ln or ln in boiler or len(ln) < 3:
            if buf:
                blocks.append("\n".join(buf))
                buf = []
            continue
        buf.append(ln)
        if len(buf) >= max_lines:
            blocks.append("\n".join(buf))
            buf = []
    if buf:
        blocks.append("\n".join(buf))
    return blocks


def score_block(block: str, kw_map: dict[str, list[str]], head: bool) -> tuple[int, set[str]]:
    low = block.lower()
    hits = {name for name, kws in kw_map.items() if any(k in low for k in kws)}
    score = 2 * len(hits)
    if NUM_RE.search(block):
        score += 2
    if head:
        score += 1
    return score, hits


def build_dossier(case: str, group_ids: list[str] | None = None, *,
                  case_budget: int = 90_000, page_budget: int = 0,
                  head_blocks: int = 4) -> tuple[str, dict]:
    """Trả (markdown dossier, thống kê). Trang xếp theo thứ tự crawl (đã theo ưu tiên)."""
    schema = load_schema()
    fields = group_fields(schema, group_ids)
    kw_map = {f["name"]: [k.lower() for k in f.get("kw", [])] for f in fields if f.get("kw")}

    sources = [s for s in load_manifest(case) if s.get("status") == "ok" and s.get("text_file")]
    pages: list[tuple[dict, str]] = []
    for s in sources:
        p = RAW / case / s["text_file"]
        if p.exists():
            pages.append((s, p.read_text(encoding="utf-8", errors="ignore")))

    boiler = boilerplate_lines(pages)
    raw_chars = sum(len(t) for _, t in pages)
    # Chia đều hạn ngạch cho mọi trang: case nhiều nguồn thì mỗi nguồn gọn lại,
    # thay vì các trang đầu ăn hết budget rồi trang cuối bị bỏ trắng.
    if not page_budget:
        page_budget = max(2_500, case_budget // max(1, len(pages)))

    parts: list[str] = []
    used = 0
    kept_pages = 0
    covered: set[str] = set()
    for s, text in pages:
        blocks = split_blocks(text, boiler)
        scored = []
        for i, b in enumerate(blocks):
            sc, hits = score_block(b, kw_map, head=i < head_blocks)
            if sc > 0:
                scored.append((sc, i, b, hits))
        if not scored:
            continue
        # chọn block điểm cao trong hạn ngạch trang, rồi trả về đúng thứ tự gốc
        scored.sort(key=lambda x: (-x[0], x[1]))
        chosen, size = [], 0
        for sc, i, b, hits in scored:
            if size + len(b) > page_budget:
                continue
            chosen.append((i, b))
            covered |= hits
            size += len(b) + 1
        if not chosen or used + size > case_budget:
            continue  # trang này không lọt hạn ngạch -> thử trang sau, không dừng hẳn
        chosen.sort()
        tag = f"S{s['idx']:02d}"
        header = (f"\n### [{tag}] {s.get('anchor') or s.get('title') or 'nguồn'}\n"
                  f"url: {s['url']}\n"
                  f"mục đích: {s.get('purpose') or '—'}\n")
        parts.append(header + "\n".join(b for _, b in chosen))
        used += size
        kept_pages += 1

    stats = {"case": case, "pages_total": len(pages), "pages_kept": kept_pages,
             "raw_chars": raw_chars, "dossier_chars": used,
             "ratio": round(used / raw_chars, 3) if raw_chars else 0,
             "fields_touched": len(covered), "fields_asked": len(fields),
             "boilerplate_lines": len(boiler)}
    return "\n".join(parts), stats


def source_index(case: str) -> dict[str, dict]:
    """Map mã [Snn] -> {url, text_file, anchor} để dựng provenance không cần LLM tự bịa."""
    return {f"S{s['idx']:02d}": {"url": s["url"], "text_file": s.get("text_file", ""),
                                 "anchor": s.get("anchor", "")}
            for s in load_manifest(case)}


def baseline_record(case: str) -> dict:
    """Record deterministic (regex) làm mốc đối chiếu cho prompt.

    Phải đọc bản backup trong `features/_deterministic/` trước: file
    `<case>_airport_city.json` sau lần chạy đầu đã là output của LLM, lấy nó làm
    "baseline" sẽ khiến lần chạy sau tự xác nhận lại lỗi của lần trước.
    """
    path = FEATURES / "_deterministic" / f"{case}.json"
    if not path.exists():
        path = FEATURES / f"{case}_airport_city.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    rec = data.get("record", data)
    return {k: v for k, v in rec.items() if not k.startswith("_") and v not in (None, "", [], {})}


def main() -> None:
    ap = argparse.ArgumentParser(description="Nén raw 1 case thành dossier cho LLM")
    ap.add_argument("--case", required=True)
    ap.add_argument("--groups", default="", help="lọc nhóm schema, phân tách bằng dấu phẩy")
    ap.add_argument("--budget", type=int, default=90_000)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    gids = [g.strip() for g in args.groups.split(",") if g.strip()] or None
    text, stats = build_dossier(args.case, gids, case_budget=args.budget)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
        print(f"[ok] ghi {args.out}")
    else:
        print(text[:2000] + "\n…")
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
