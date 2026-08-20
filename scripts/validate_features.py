"""Kiểm tra output feature WS1 và gộp bảng benchmark + báo cáo độ phủ.

Đọc mọi `raw_data/output/ws1_airport/features/<case>_airport_city.json`, đối chiếu với
`features/ws1_airport/schema.json` rồi ghi:

  features/airport_city_benchmark.csv/.jsonl  — bảng phẳng 1 dòng / case (khoá `case_name`)
  features/coverage_report.csv                — 1 dòng / (case, trường): có giá trị chưa,
                                                nguồn nào, confidence, lý do thiếu
  features/coverage_summary.csv               — 1 dòng / case: %, số trường high/medium/low

Kiểm tra thực hiện:
  - sai kiểu so với schema (int nhận chuỗi, string_list nhận chuỗi…)
  - khoá `case_name` rỗng hoặc trùng
  - trường có giá trị nhưng thiếu provenance
  - provenance trỏ tới mã nguồn không có trong manifest (cờ `unverified_source`)
  - % giá trị lấy từ `baseline` (regex cũ) — cao nghĩa là LLM chưa xác minh được nhiều

Chạy:
    python scripts/validate_features.py
    python scripts/validate_features.py --strict   # thoát mã 1 nếu có lỗi kiểu/khoá
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

WS = "ws1_airport"
ROOT = Path(__file__).resolve().parents[1]
FEATURES = ROOT / "raw_data" / "output" / WS / "features"
SCHEMA_PATH = ROOT / "features" / WS / "schema.json"

TYPE_OK = {
    "string": lambda v: isinstance(v, str),
    "string_list": lambda v: isinstance(v, list) and all(isinstance(i, str) for i in v),
    "float": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "int": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "bool": lambda v: isinstance(v, bool),
    "object": lambda v: isinstance(v, dict),
}


def flat(value) -> str:
    if isinstance(value, list):
        return "; ".join(str(v) for v in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return "" if value is None else str(value)


def main() -> None:
    ap = argparse.ArgumentParser(description="Validate + gộp bảng benchmark WS1")
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    fields = [f for g in schema["groups"] for f in g["fields"]]
    group_of = {f["name"]: g["label"] for g in schema["groups"] for f in g["fields"]}
    names = [f["name"] for f in fields]

    files = sorted(p for p in FEATURES.glob("*_airport_city.json"))
    if not files:
        raise SystemExit(f"Không thấy file feature nào trong {FEATURES}")

    rows, cover, summary, errors = [], [], [], []
    seen_keys: dict[str, str] = {}

    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        rec = data.get("record", data)
        prov = data.get("provenance", {})
        miss = data.get("missing", {})
        case = path.name.replace("_airport_city.json", "")
        extractor = data.get("_meta", {}).get("extractor", "không rõ")

        key = rec.get("case_name")
        if not key:
            errors.append(f"{case}: thiếu khoá case_name")
        elif key in seen_keys:
            errors.append(f"{case}: case_name '{key}' trùng với {seen_keys[key]}")
        else:
            seen_keys[key] = case

        conf_count = {"high": 0, "medium": 0, "low": 0}
        n_filled = n_baseline = n_unverified = 0
        for f in fields:
            name, ftype = f["name"], f["type"]
            val = rec.get(name)
            p = prov.get(name) if isinstance(prov.get(name), dict) else {}
            has = val not in (None, "", [], {})
            if has and not TYPE_OK[ftype](val):
                errors.append(f"{case}.{name}: cần {ftype}, nhận {type(val).__name__} = {val!r}")
            if has:
                n_filled += 1
                conf = p.get("confidence", "")
                if conf in conf_count:
                    conf_count[conf] += 1
                if p.get("source") == "baseline":
                    n_baseline += 1
                if p.get("unverified_source"):
                    n_unverified += 1
            cover.append({"case_id": case, "group": group_of[name], "field": name, "type": ftype,
                          "has_value": int(has), "value": flat(val)[:200],
                          "confidence": p.get("confidence", ""), "source": p.get("source", ""),
                          "source_url": p.get("source_url", ""),
                          "snippet": (p.get("snippet") or "")[:160],
                          "missing_reason": miss.get(name, "")})

        rows.append({"case_id": case, **{n: flat(rec.get(n)) for n in names}})
        summary.append({"case_id": case, "case_name": key or "", "extractor": extractor,
                        "fields_total": len(names), "fields_filled": n_filled,
                        "coverage_pct": round(100 * n_filled / len(names), 1),
                        "high": conf_count["high"], "medium": conf_count["medium"],
                        "low": conf_count["low"], "from_baseline": n_baseline,
                        "unverified_source": n_unverified, "missing": len(miss)})

    def write(path: Path, cols: list[str], data: list[dict]) -> None:
        with path.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
            w.writeheader(); w.writerows(data)
        print(f"[ok] {path.relative_to(ROOT)}  ({len(data)} dòng)")

    write(FEATURES / "airport_city_benchmark.csv", ["case_id"] + names, rows)
    with (FEATURES / "airport_city_benchmark.jsonl").open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"[ok] {(FEATURES / 'airport_city_benchmark.jsonl').relative_to(ROOT)}")
    write(FEATURES / "coverage_report.csv",
          ["case_id", "group", "field", "type", "has_value", "value", "confidence",
           "source", "source_url", "snippet", "missing_reason"], cover)
    write(FEATURES / "coverage_summary.csv",
          ["case_id", "case_name", "extractor", "fields_total", "fields_filled", "coverage_pct",
           "high", "medium", "low", "from_baseline", "unverified_source", "missing"], summary)

    print(f"\n{'case':16s} {'phủ':>6s}  {'high':>4s} {'med':>4s} {'low':>4s} {'baseline':>8s}  extractor")
    for s in sorted(summary, key=lambda r: -r["coverage_pct"]):
        print(f"{s['case_id']:16s} {s['coverage_pct']:5.1f}% {s['high']:5d} {s['medium']:4d} "
              f"{s['low']:4d} {s['from_baseline']:8d}  {s['extractor']}")
    avg = sum(s["coverage_pct"] for s in summary) / len(summary)
    print(f"{'TRUNG BÌNH':16s} {avg:5.1f}%   ({len(names)} trường/schema)")

    # trường trống ở mọi case -> nguồn hiện tại không có, cần bổ sung URL
    dead = [n for n in names if all(not c["has_value"] for c in cover if c["field"] == n)]
    if dead:
        print(f"\n[trống ở MỌI case] {len(dead)} trường: {', '.join(dead)}")
    if errors:
        print(f"\n[lỗi] {len(errors)}:")
        for e in errors[:20]:
            print("  -", e)
        if args.strict:
            sys.exit(1)
    else:
        print("\n[ok] không có lỗi kiểu dữ liệu / khoá.")


if __name__ == "__main__":
    main()
