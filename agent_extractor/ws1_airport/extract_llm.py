"""Extractor LLM cho WS1: dossier raw -> record 75 trường + provenance từng trường.

Khác `extract_airport_city.py` (regex, chỉ bắt được trường có mẫu cố định), bản này
đọc hiểu văn bản nên lấy được cả nhóm định tính (`brand_desc`, `connectivity_desc`,
`price_vs_reference`, các cờ `has_*`…). Gọi model qua **code_proxy** nên không cần
ANTHROPIC_API_KEY — proxy chuyển tiếp sang Claude Code CLI đã đăng nhập.

Chống bịa dữ liệu:
  - Model chỉ thấy dossier đã trích từ raw đã crawl, không có mạng.
  - Mỗi giá trị phải kèm mã nguồn [Snn]; mã đó được đối chiếu ngược với manifest.json,
    mã lạ -> hạ confidence xuống `low` và ghi cờ `unverified_source`.
  - Trường không có bằng chứng phải trả null kèm `reason`, ghi vào khối `missing`.
  - Record deterministic cũ được đưa vào làm mốc; giá trị chỉ bị thay khi dossier có
    bằng chứng, ngược lại giữ nguyên và đánh dấu nguồn `baseline`.

Chuẩn bị:
    CLAUDE_PROXY_MODEL=claude-opus-5 ./code_proxy/start.sh --timeout 900   # terminal 1
    export ANTHROPIC_BASE_URL=http://127.0.0.1:11439                       # terminal 2

Chạy:
    python agent_extractor/ws1_airport/extract_llm.py --case incheon
    python agent_extractor/ws1_airport/extract_llm.py --all
    python agent_extractor/ws1_airport/extract_llm.py --all --dry-run   # chỉ in prompt size
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from llm_prep import (RAW, ROOT, WS, baseline_record, build_dossier, group_fields,  # noqa: E402
                      load_schema, source_index)

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

FEATURES = ROOT / "raw_data" / "output" / WS / "features"
BACKUP = FEATURES / "_deterministic"
LOGS = ROOT / "raw_data" / "output" / WS / "_llm_log"

# Hai lượt hỏi: dữ kiện cứng và phân tích CVP. Tách ra để prompt ngắn, model bám sát
# nhóm trường đang hỏi thay vì trả lan man 75 trường một lần.
PASSES = {
    "facts": ["identity", "location", "positioning", "kpi", "investment", "parks"],
    "cvp": ["product", "price", "service", "experience", "convenience", "brand", "vision"],
}

SYSTEM_RULES = """Bạn là trợ lý trích xuất dữ liệu benchmark khu đô thị sân bay (airport city).
Bạn CHỈ được dùng thông tin trong phần TÀI LIỆU bên dưới. Không dùng kiến thức nền, không suy đoán.

Quy tắc bắt buộc:
1. Mỗi trường trả về một object: {"value": <giá trị>, "source": "Snn", "snippet": "<trích dẫn gốc <=200 ký tự>", "confidence": "high|medium|low"}.
2. Không tìm được bằng chứng -> {"value": null, "reason": "<vì sao thiếu>"}. TUYỆT ĐỐI không đoán.
3. "source" phải là mã [Snn] của đúng đoạn chứa bằng chứng. "snippet" phải copy nguyên văn từ tài liệu.
4. Đúng kiểu dữ liệu: float/int trả số trần (không kèm đơn vị, không dấu phẩy ngăn nghìn);
   string_list trả mảng chuỗi; bool trả true/false; string trả chuỗi.
5. Quy đổi về đúng đơn vị ghi trong bảng trường (vd nguồn ghi m² mà trường yêu cầu ha thì chia 10.000).
6. Số liệu headline (hành khách, hàng hoá, lượt bay) ưu tiên trang thống kê chính thức, không lấy số marketing kiểu "hơn 300".
7. confidence: "high" khi nguồn chính thức nêu trực tiếp; "medium" khi phải suy ra từ câu văn; "low" khi mơ hồ.
8. **Số liệu vận hành phải là số ĐÃ GHI NHẬN THỰC TẾ** (passengers_million, cargo_million_tonnes,
   air_movements, destinations, airlines, transfer_pct, employees, jobs_created…). Tuyệt đối KHÔNG lấy
   công suất thiết kế, mục tiêu hay dự báo — dấu hiệu: "capacity for", "when complete", "expected",
   "will handle", "by 2030", "planned", "công suất", "dự kiến". Nguồn chỉ có số tương lai -> value null,
   reason ghi rõ đó là công suất/dự báo chứ không phải số thực tế.
9. **Diện tích (area_km2)** phải là quy mô TOÀN khu đô thị sân bay. TUYỆT ĐỐI không lấy diện tích của
   một khu chuyên biệt đã có trường riêng (logistics park, trade/business park, một toà nhà, một phân
   khu nhỏ) — những con số đó thuộc `logistics_park_ha` / `trade_park_ha`. Nếu nguồn chỉ có diện tích
   phân khu chứ không có tổng, trả null và ghi rõ lý do trong reason.
10. **Được phép bác bỏ giá trị baseline.** Nếu giá trị regex ở mục mốc đối chiếu sai định nghĩa trường
   (vd lấy nhầm công suất tương lai, nhầm đơn vị, nhầm thực thể), trả {"value": null,
   "reason": "BASELINE_SAI: <giải thích>"} — hệ thống sẽ xoá giá trị cũ thay vì giữ lại.
11. **Giá trị chữ phải viết bằng TIẾNG VIỆT** — trang web hiển thị thẳng giá trị này cho người đọc Việt:
   - dịch mọi trường mô tả (`*_desc`, `positioning`, `planning_concept`, `cvp_*`, `sustainability`,
     `investor_governance`, `sales_scheme`, `smart_city`, `airport_privilege`, `experience_desc`…);
   - **GIỮ NGUYÊN tên riêng**: tên công ty/cơ quan (Changi Airport Group, IFEZ), tên phân khu và địa
     danh (Songdo, SKYCITY, Schiphol East), tên công trình (Jewel, WTC), tên chương trình/chính sách,
     tên viết tắt (MRO, FTZ, MICE, AREX). Cần thì viết "tên gốc (giải nghĩa tiếng Việt)";
   - danh mục chung thì dịch: "office" -> "văn phòng", "logistics" -> "logistics/kho vận",
     "free-trade zone" -> "khu thương mại tự do", "retail" -> "bán lẻ";
   - KHÔNG dịch: `case_name`, `aerotropolis`, `airport_name`, `official_website`,
     `economic_zone_name`, `logistics_park_name`, `trade_park_name`, `vision_label`, `brand_partners`;
   - **`snippet` phải giữ NGUYÊN VĂN ngôn ngữ gốc** — đó là bằng chứng để đối chiếu, tuyệt đối không dịch.
12. Chỉ xuất DUY NHẤT một object JSON, không thêm lời dẫn, không bọc markdown."""


def endpoint() -> str:
    """Chọn nơi gọi model: API thật khi có ANTHROPIC_API_KEY, ngược lại code_proxy ở máy.

    Trên server headless không đăng nhập được Claude Code CLI nên code_proxy không dùng
    được ở đó — đặt ANTHROPIC_API_KEY là script tự trỏ sang api.anthropic.com.
    """
    default = "https://api.anthropic.com" if os.getenv("ANTHROPIC_API_KEY") else "http://127.0.0.1:11439"
    return os.getenv("ANTHROPIC_BASE_URL", default).rstrip("/") + "/v1/messages"


# Trên API thật, `max_tokens` bao gồm CẢ phần suy luận lẫn phần trả lời, và các model
# đời mới bật suy luận mặc định — để 8k thì JSON 39 trường bị cắt giữa chừng và chỉ lộ
# ra dưới dạng lỗi parse. Qua code_proxy thì tham số này bị bỏ qua (CLI tự quản).
MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "16000"))


def call_model(prompt: str, model: str, timeout: int) -> str:
    body = json.dumps({"model": model, "max_tokens": MAX_TOKENS,
                       "messages": [{"role": "user", "content": prompt}]}).encode("utf-8")
    headers = {"content-type": "application/json", "anthropic-version": "2023-06-01"}
    key = (os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN")
           or os.getenv("LLM_PROXY_API_KEY"))
    if key:
        headers["x-api-key"] = key
    req = urllib.request.Request(endpoint(), data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if data.get("stop_reason") == "max_tokens":
        raise ValueError(f"phản hồi bị cắt vì chạm max_tokens={MAX_TOKENS} — "
                         f"tăng biến môi trường LLM_MAX_TOKENS")
    return "".join(b.get("text", "") for b in data.get("content", []))


def extract_json(text: str) -> dict:
    """Bóc object JSON đầu tiên; model đôi khi vẫn kèm lời dẫn dù đã dặn."""
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if fence:
        return json.loads(fence.group(1))
    start = text.find("{")
    if start < 0:
        raise ValueError("không thấy JSON trong phản hồi")
    depth, in_str, esc = 0, False, False
    for i, ch in enumerate(text[start:], start):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start:i + 1])
    raise ValueError("JSON không đóng ngoặc")


def field_table(fields: list[dict]) -> str:
    rows = ["| trường | kiểu | đơn vị | ý nghĩa |", "|---|---|---|---|"]
    for f in fields:
        rows.append(f"| `{f['name']}` | {f['type']} | {f.get('unit', '—')} | {f['desc']} |")
    return "\n".join(rows)


def build_prompt(case: str, fields: list[dict], dossier: str, baseline: dict) -> str:
    hint = {f["name"]: baseline[f["name"]] for f in fields if f["name"] in baseline}
    return f"""{SYSTEM_RULES}

## Nhiệm vụ
Trích {len(fields)} trường dưới đây cho case `{case}`.

{field_table(fields)}

## Giá trị đã trích bằng regex ở lần chạy trước (mốc đối chiếu, CÓ THỂ SAI hoặc thiếu)
Giữ nguyên giá trị nào tài liệu xác nhận; sửa nếu tài liệu cho thấy khác; nếu tài liệu
không nhắc tới, vẫn giữ nhưng đặt "source": "baseline" và "confidence": "medium".
```json
{json.dumps(hint, ensure_ascii=False, indent=1)}
```

## TÀI LIỆU (trích từ các trang đã crawl; mã [Snn] để dẫn nguồn)
{dossier}

## Định dạng trả về
{{"fields": {{"<tên trường>": {{"value": ..., "source": "Snn", "snippet": "...", "confidence": "high"}}, ...}}}}
Phải có ĐỦ {len(fields)} trường, kể cả trường null. Chỉ xuất JSON."""


def coerce(value, ftype: str):
    """Ép kiểu theo schema; trả (giá trị, cảnh báo|None)."""
    if value is None:
        return None, None
    if ftype in ("float", "int"):
        if isinstance(value, bool):
            return None, "bool cho trường số"
        if isinstance(value, (int, float)):
            num = value
        else:
            m = re.search(r"-?\d[\d.,]*", str(value))
            if not m:
                return None, f"không parse được số: {value!r}"
            num = float(m.group(0).replace(",", ""))
        return (int(round(num)), None) if ftype == "int" else (float(num), None)
    if ftype == "bool":
        if isinstance(value, bool):
            return value, None
        s = str(value).strip().lower()
        if s in ("true", "yes", "có", "1"):
            return True, None
        if s in ("false", "no", "không", "0"):
            return False, None
        return None, f"không parse được bool: {value!r}"
    if ftype == "string_list":
        if isinstance(value, list):
            items = [str(v).strip() for v in value]
        else:
            items = [p.strip() for p in re.split(r"[;\n]", str(value))]
        items = [i for i in items if i]
        return (items or None), None
    if ftype == "object":
        return (value if isinstance(value, dict) else None,
                None if isinstance(value, dict) else f"cần object, nhận {type(value).__name__}")
    text = str(value).strip()
    return (text or None), None


def run_pass(case: str, pass_name: str, model: str, timeout: int, retries: int,
             budget: int, dry_run: bool) -> tuple[dict, dict]:
    schema = load_schema()
    fields = group_fields(schema, PASSES[pass_name])
    dossier, stats = build_dossier(case, PASSES[pass_name], case_budget=budget)
    prompt = build_prompt(case, fields, dossier, baseline_record(case))
    print(f"  [{pass_name}] {len(fields)} trường · dossier {stats['dossier_chars']//1000}k ký tự "
          f"· prompt {len(prompt)//1000}k ký tự (~{len(prompt)//4000}k token)")
    if dry_run:
        return {}, {"prompt_chars": len(prompt), **stats}

    last_err = ""
    for attempt in range(1, retries + 1):
        try:
            t0 = time.time()
            raw = call_model(prompt if attempt == 1 else prompt + "\n\nLƯU Ý: lần trước bạn trả sai "
                             "định dạng. CHỈ xuất một object JSON, không thêm chữ nào khác.",
                             model, timeout)
            out = extract_json(raw)
            got = out.get("fields", out)
            if not isinstance(got, dict) or not got:
                raise ValueError("khối 'fields' rỗng")
            print(f"      -> {len(got)} trường, {time.time() - t0:.0f}s")
            LOGS.mkdir(parents=True, exist_ok=True)
            (LOGS / f"{case}_{pass_name}.json").write_text(
                json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
            return got, stats
        except (urllib.error.URLError, ValueError, json.JSONDecodeError, TimeoutError) as exc:
            last_err = f"{type(exc).__name__}: {exc}"
            print(f"      ! lần {attempt}/{retries} lỗi — {last_err}")
            if attempt < retries:
                time.sleep(5 * attempt)
    raise SystemExit(f"[{case}/{pass_name}] thất bại sau {retries} lần: {last_err}")


NARRATIVE_RULES = """Bạn viết lời văn cho hồ sơ benchmark khu đô thị sân bay, đọc bởi người Việt.

Nhiệm vụ: với mỗi NHÓM dưới đây, viết MỘT đoạn văn tiếng Việt 1–4 câu tóm tắt các dữ kiện của nhóm đó.

Quy tắc bắt buộc:
1. CHỈ dùng dữ kiện có trong danh sách. Tuyệt đối không thêm số, tên, sự kiện nào khác — kể cả khi bạn
   biết về khu này. Không suy đoán, không "có thể", không nhận định chủ quan.
2. Bọc **hai dấu sao** quanh mỗi con số và tên riêng quan trọng, ví dụ: **70 triệu** lượt khách,
   khu **Songdo**. Đây là phần được tô đậm khi hiển thị.
3. Văn xuôi mạch lạc, nối các dữ kiện thành câu; KHÔNG liệt kê kiểu "trường: giá trị".
4. Giữ nguyên tên riêng và số liệu đúng như đã cho, kể cả đơn vị.
5. Nhóm không có dữ kiện nào -> trả chuỗi rỗng "". Không bịa để lấp chỗ trống.
6. Không mở đầu bằng "Nhóm này...", "Dữ liệu cho thấy..."; vào thẳng nội dung.
7. Viết số theo kiểu Việt: dấu chấm ngăn hàng nghìn và dấu phẩy thập phân —
   `358000` -> **358.000**, `70.86` -> **70,86**, `2.95` -> **2,95**. Giữ nguyên giá trị, chỉ đổi cách viết.
8. Chỉ xuất DUY NHẤT một object JSON."""


def narrate(case: str, out: dict, model: str, timeout: int, retries: int) -> None:
    """Viết lời văn tiếng Việt cho từng nhóm — lớp trình bày kiểu hồ sơ, không thêm dữ kiện.

    Chạy SAU khi record đã chốt và chỉ nhìn thấy record đó (không nhìn dossier), nên không
    thể đưa vào dữ kiện ngoài những gì đã trích và đã có provenance.
    """
    schema = load_schema()
    record = out["record"]
    blocks, wanted = [], []
    for g in schema["groups"]:
        rows = []
        for f in g["fields"]:
            v = record.get(f["name"])
            if v in (None, "", [], {}):
                continue
            val = "; ".join(str(x) for x in v) if isinstance(v, list) else \
                  json.dumps(v, ensure_ascii=False) if isinstance(v, dict) else str(v)
            unit = f" {f['unit']}" if f.get("unit") else ""
            rows.append(f"  - {f['label']}: {val}{unit}")
        if rows:
            wanted.append(g["id"])
            blocks.append(f"### {g['id']} — {g['label']}\n" + "\n".join(rows))

    if not blocks:
        out["narrative"] = {}
        return
    prompt = (f"{NARRATIVE_RULES}\n\n## Khu: {record.get('case_name') or case}\n\n"
              + "\n\n".join(blocks)
              + '\n\n## Định dạng trả về\n{"narrative": {'
              + ", ".join(f'"{g}": "…"' for g in wanted[:3]) + ", …}}\n"
              + f"Phải có đủ {len(wanted)} khoá: {', '.join(wanted)}. Chỉ xuất JSON.")

    for attempt in range(1, retries + 1):
        try:
            got = extract_json(call_model(prompt, model, timeout)).get("narrative", {})
            if not isinstance(got, dict) or not got:
                raise ValueError("khối 'narrative' rỗng")
            text = {k: str(v).strip() for k, v in got.items() if str(v).strip()}
            out["narrative"] = text
            out["_meta"]["narrative_groups"] = len(text)
            check_narrative(text, record, out["_meta"]["warnings"])
            print(f"      -> lời văn {len(text)}/{len(wanted)} nhóm")
            return
        except (urllib.error.URLError, ValueError, json.JSONDecodeError, TimeoutError) as exc:
            print(f"      ! lời văn lần {attempt}/{retries}: {type(exc).__name__}: {exc}")
            if attempt < retries:
                time.sleep(5 * attempt)
    out["narrative"] = {}
    out["_meta"]["warnings"].append("không sinh được lời văn sau nhiều lần thử")


NUM_TOKEN = re.compile(r"\d[\d.,]*\d|\d")


def _as_float(tok: str, vietnamese: bool) -> float | None:
    """Đọc một token số. Record viết kiểu Anh (1905.0), lời văn viết kiểu Việt (1.905)."""
    tok = tok.rstrip(".,")
    try:
        if vietnamese:
            if re.fullmatch(r"\d{1,3}(\.\d{3})+", tok):   # 358.000 -> ngăn nghìn
                tok = tok.replace(".", "")
            return float(tok.replace(",", "."))
        return float(tok.replace(",", ""))
    except ValueError:
        return None


def check_narrative(text: dict, record: dict, warns: list[str]) -> None:
    """Mọi con số trong lời văn phải truy được về record — chặn model tự thêm số.

    So khớp bằng GIÁ TRỊ, không bằng chuỗi: record ghi `1905.0` còn lời văn ghi
    `1.905`, so chuỗi sẽ báo động giả hàng loạt.
    """
    # Record trộn hai cách viết: trường số dùng kiểu Anh (1905.0) còn chuỗi mô tả đã
    # dịch sang tiếng Việt nên viết 167.000. Nhận cả hai để khỏi báo động giả.
    pool: list[float] = []
    for v in record.values():
        for item in (v if isinstance(v, list) else [v]):
            for tok in NUM_TOKEN.findall(str(item)):
                for vi in (False, True):
                    num = _as_float(tok, vietnamese=vi)
                    if num is not None:
                        pool.append(num)
    for gid, para in text.items():
        for tok in NUM_TOKEN.findall(para):
            num = _as_float(tok, vietnamese=True)
            if num is None or num < 10:          # số nhỏ thường là thứ tự/đếm trong câu
                continue
            if not any(abs(num - b) <= max(0.05, abs(b) * 0.005) for b in pool):
                warns.append(f"lời văn [{gid}] có số {tok!r} không thấy trong record")


def cross_check(record: dict, prov: dict, missing: dict, warns: list[str]) -> None:
    """Hậu kiểm quan hệ giữa các trường — bắt lỗi mà đọc từng trường riêng lẻ không thấy.

    Lỗi hay gặp nhất: `area_km2` vớ phải diện tích của một khu chuyên biệt (logistics/trade
    park) vốn đã có trường riêng, làm quy mô khu đô thị bị thu nhỏ hàng chục lần.
    """
    area = record.get("area_km2")
    if not isinstance(area, (int, float)):
        return
    for park in ("trade_park_ha", "logistics_park_ha"):
        ha = record.get(park)
        if isinstance(ha, (int, float)) and ha > 0 and abs(area * 100 - ha) <= max(1.0, ha * 0.02):
            record["area_km2"] = None
            prov.pop("area_km2", None)
            missing["area_km2"] = (f"loại tự động: giá trị {area} km² trùng với {park}={ha} ha "
                                   f"— đó là diện tích khu chuyên biệt, không phải toàn khu đô thị")
            warns.append(f"area_km2: bỏ {area} km² vì trùng {park}")
            return
    airport_ha = record.get("airport_area_ha")
    if isinstance(airport_ha, (int, float)) and airport_ha > 0 and area * 100 < airport_ha * 0.5:
        warns.append(f"area_km2={area} km² nhỏ hơn nửa diện tích sân bay "
                     f"({airport_ha} ha) — kiểm tra lại phạm vi con số")


def assemble(case: str, answers: dict, stats: dict) -> dict:
    """Gộp phản hồi 2 pass -> record + provenance + missing, có kiểm tra mã nguồn."""
    schema = load_schema()
    fields = {f["name"]: f for f in group_fields(schema)}
    srcs = source_index(case)
    baseline = baseline_record(case)

    record: dict = {}
    prov: dict = {}
    missing: dict = {}
    warns: list[str] = []

    for name, spec in fields.items():
        ans = answers.get(name)
        if not isinstance(ans, dict):
            if name in baseline:  # model bỏ quên trường -> không đánh mất số cũ
                record[name] = baseline[name]
                prov[name] = {"source": "baseline", "confidence": "medium",
                              "note": "extractor deterministic; LLM không trả lời"}
                warns.append(f"{name}: LLM không trả, giữ baseline")
            else:
                record[name] = None
                missing[name] = "LLM không trả lời trường này"
            continue

        value, warn = coerce(ans.get("value"), spec["type"])
        if warn:
            warns.append(f"{name}: {warn}")
        if value is None:
            reason = str(ans.get("reason") or "không có bằng chứng trong nguồn đã crawl")
            # model chủ động bác giá trị regex cũ (sai đơn vị / lấy nhầm công suất tương lai…)
            if reason.upper().startswith("BASELINE_SAI"):
                record[name] = None
                missing[name] = reason
                if name in baseline:
                    warns.append(f"{name}: bỏ giá trị baseline {baseline[name]!r} — {reason[:120]}")
                continue
            record[name] = baseline.get(name)
            if record[name] is not None:
                prov[name] = {"source": "baseline", "confidence": "low",
                              "note": "LLM không xác minh được, giữ giá trị regex cũ"}
            else:
                missing[name] = reason
            continue

        tag = str(ans.get("source") or "").strip().upper()
        conf = str(ans.get("confidence") or "medium").lower()
        entry = {"confidence": conf if conf in ("high", "medium", "low") else "medium",
                 "snippet": str(ans.get("snippet") or "")[:300]}
        if tag == "BASELINE":
            entry.update({"source": "baseline", "confidence": "medium"})
        elif tag in srcs:
            entry.update({"source": tag, "source_url": srcs[tag]["url"],
                          "source_file": srcs[tag]["text_file"], "source_name": srcs[tag]["anchor"]})
        else:
            entry.update({"source": tag or "?", "confidence": "low", "unverified_source": True})
            warns.append(f"{name}: mã nguồn lạ {tag!r} -> hạ confidence")
        record[name] = value
        prov[name] = entry

    cross_check(record, prov, missing, warns)
    filled = sum(1 for v in record.values() if v not in (None, "", [], {}))
    return {"record": record, "provenance": prov, "missing": missing,
            "_meta": {"case": case, "extractor": "extract_llm.py", "schema": "features/ws1_airport/schema.json",
                      "model": stats.get("model", ""), "generated_at": stats.get("generated_at", ""),
                      "fields_total": len(fields), "fields_filled": filled,
                      "coverage_pct": round(100 * filled / len(fields), 1),
                      "high_confidence": sum(1 for p in prov.values() if p.get("confidence") == "high"),
                      "from_baseline": sum(1 for p in prov.values() if p.get("source") == "baseline"),
                      "dossier": {k: stats.get(k) for k in ("pages_total", "pages_kept", "raw_chars", "dossier_chars")},
                      "warnings": warns}}


def rewrite_narrative(case: str, model: str, timeout: int, retries: int) -> dict | None:
    """Chỉ viết lại lời văn từ record đã có — không gọi lại 2 lượt trích tốn kém."""
    dest = FEATURES / f"{case}_airport_city.json"
    if not dest.exists():
        print(f"  [bỏ qua] chưa có {dest.name}, chạy extract đầy đủ trước")
        return None
    out = json.loads(dest.read_text(encoding="utf-8"))
    out.setdefault("_meta", {}).setdefault("warnings", [])
    print(f"\n=== {case} (chỉ lời văn) ===")
    narrate(case, out, model, timeout, retries)
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def process(case: str, model: str, timeout: int, retries: int, budget: int, dry_run: bool,
            no_narrative: bool = False) -> dict | None:
    print(f"\n=== {case} ===")
    answers: dict = {}
    merged_stats: dict = {}
    for pass_name in PASSES:
        got, stats = run_pass(case, pass_name, model, timeout, retries, budget, dry_run)
        answers.update(got)
        for k, v in stats.items():
            if isinstance(v, (int, float)) and k != "ratio":
                merged_stats[k] = merged_stats.get(k, 0) + v if k.endswith("chars") else v
    if dry_run:
        return None

    merged_stats["model"] = model
    merged_stats["generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    out = assemble(case, answers, merged_stats)
    if not no_narrative:
        print("  [lời văn] tóm tắt từng nhóm bằng tiếng Việt")
        narrate(case, out, model, timeout, retries)

    dest = FEATURES / f"{case}_airport_city.json"
    if dest.exists() and not (BACKUP / f"{case}.json").exists():
        BACKUP.mkdir(parents=True, exist_ok=True)
        (BACKUP / f"{case}.json").write_text(dest.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"  [backup] bản regex -> {(BACKUP / f'{case}.json').relative_to(ROOT)}")
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    m = out["_meta"]
    print(f"  [ok] {m['fields_filled']}/{m['fields_total']} trường ({m['coverage_pct']}%) · "
          f"high={m['high_confidence']} · baseline={m['from_baseline']} · thiếu={len(out['missing'])}")
    if m["warnings"]:
        print(f"  [cảnh báo] {len(m['warnings'])}: " + "; ".join(m["warnings"][:3]))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Trích feature WS1 bằng LLM qua code_proxy")
    ap.add_argument("--case", help="một case_id")
    ap.add_argument("--all", action="store_true", help="chạy mọi case có raw")
    ap.add_argument("--model", default=os.getenv("CLAUDE_PROXY_MODEL", "claude-opus-5"))
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--retries", type=int, default=3)
    ap.add_argument("--budget", type=int, default=80_000, help="ký tự dossier mỗi pass")
    ap.add_argument("--skip-done", action="store_true",
                    help="bỏ qua case đã có file feature (để chạy lại loạt dài sau khi gián đoạn)")
    ap.add_argument("--narrative-only", action="store_true",
                    help="chỉ viết lại lời văn từ record đã có (nhanh, không trích lại)")
    ap.add_argument("--no-narrative", action="store_true",
                    help="bỏ lượt viết lời văn tiếng Việt cho từng nhóm")
    ap.add_argument("--dry-run", action="store_true", help="chỉ dựng prompt, không gọi model")
    args = ap.parse_args()

    if args.all:
        cases = sorted(d.name for d in RAW.iterdir() if (d / "manifest.json").exists())
    elif args.case:
        cases = [args.case]
    else:
        raise SystemExit("cần --case <id> hoặc --all")

    if not args.dry_run:
        print(f"proxy: {endpoint()} · model: {args.model}")
    if args.skip_done and not args.narrative_only:
        before = len(cases)
        cases = [c for c in cases if not (FEATURES / f"{c}_airport_city.json").exists()]
        print(f"[skip-done] bỏ qua {before - len(cases)} case đã có feature, còn {len(cases)}")
    ok = 0
    for case in cases:
        try:
            done = (rewrite_narrative(case, args.model, args.timeout, args.retries)
                    if args.narrative_only else
                    process(case, args.model, args.timeout, args.retries, args.budget,
                            args.dry_run, args.no_narrative))
            if done:
                ok += 1
        except SystemExit as exc:
            print(f"  [bỏ qua] {exc}")
    print(f"\n[done] {ok}/{len(cases)} case -> {FEATURES.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
