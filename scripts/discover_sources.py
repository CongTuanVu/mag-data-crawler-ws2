"""Tìm nguồn crawl bằng LLM tra web, từ danh sách chỉ có TÊN aerotropolis.

`refer_file/aerotropolis.txt` chỉ liệt kê tên khu + quốc gia + sân bay, không có URL.
Script này nhờ model dùng `web_search` / `web_fetch` (code_proxy mở đúng 2 tool đó cho
Claude Code CLI) đi tìm trang nguồn cho từng khu, gán mỗi nguồn với các trường trong
`features/ws1_airport/schema.json` mà nó có thể trả lời, rồi trộn vào
`refer_file/sources.csv` — sau đó crawl/extract chạy như thường.

Chống nguồn rác:
  - model phải trả URL đã thực sự mở được bằng web_search/web_fetch, không suy đoán;
  - script tự probe lại từng URL (HEAD rồi GET) trước khi ghi, URL chết bị loại;
  - URL trùng với dòng đã có trong registry bị bỏ qua, không ghi đè nguồn tuyển tay;
  - dòng mới đánh dấu `origin=llm` + `discovered_at` để phân biệt với nguồn người tuyển.

Cần proxy chạy trước (xem code_proxy/README.md):
    CLAUDE_PROXY_MODEL=claude-opus-5 ./code_proxy/start.sh --timeout 900
    export ANTHROPIC_BASE_URL=http://127.0.0.1:11439

Chạy:
    python scripts/discover_sources.py --all
    python scripts/discover_sources.py --case taoyuan --want 25
    python scripts/discover_sources.py --missing        # chỉ case chưa có nguồn nào
    python scripts/discover_sources.py --all --dry-run  # in prompt, không gọi model
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import importlib.util
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

ROOT = Path(__file__).resolve().parents[1]
REFER = ROOT / "refer_file"
SCHEMA_PATH = ROOT / "features" / "ws1_airport" / "schema.json"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

_spec = importlib.util.spec_from_file_location("_registry", ROOT / "scripts" / "build_source_registry.py")
registry_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(registry_mod)


def endpoint() -> str:
    """API thật khi có ANTHROPIC_API_KEY, ngược lại code_proxy ở máy (xem extract_llm.py)."""
    default = "https://api.anthropic.com" if os.getenv("ANTHROPIC_API_KEY") else "http://127.0.0.1:11439"
    return os.getenv("ANTHROPIC_BASE_URL", default).rstrip("/") + "/v1/messages"


def call_model(prompt: str, model: str, timeout: int) -> str:
    """Gọi model KÈM server tool web_search/web_fetch — proxy sẽ mở WebSearch/WebFetch."""
    body = json.dumps({
        "model": model, "max_tokens": int(os.getenv("LLM_MAX_TOKENS", "16000")),
        "tools": [{"type": "web_search_20260209", "name": "web_search"},
                  {"type": "web_fetch_20260209", "name": "web_fetch"}],
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")
    headers = {"content-type": "application/json", "anthropic-version": "2023-06-01"}
    if key := (os.getenv("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_AUTH_TOKEN")
               or os.getenv("LLM_PROXY_API_KEY")):
        headers["x-api-key"] = key
    req = urllib.request.Request(endpoint(), data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return "".join(b.get("text", "") for b in data.get("content", []))


def extract_json(text: str) -> dict:
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if fence:
        return json.loads(fence.group(1))
    start = text.find("{")
    if start < 0:
        raise ValueError("không thấy JSON trong phản hồi")
    depth, in_str, esc = 0, False, False
    for i, ch in enumerate(text[start:], start):
        if in_str:
            esc = (ch == "\\") and not esc
            if ch == '"' and not esc:
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


def field_menu() -> str:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return "\n".join(f"- **{g['label']}**: " + ", ".join(f["name"] for f in g["fields"])
                     for g in schema["groups"])


# Từ khoá tra web cho từng trường hay thiếu. Lượt discover đầu chỉ mô tả trường bằng
# tên schema nên model tìm chung chung; nêu thẳng cụm từ mà trang nguồn thật sự dùng
# (kể cả tiếng bản địa) thì kết quả bám sát số liệu hơn hẳn.
FIELD_KEYWORDS = {
    "passengers_million": [
        "annual passenger traffic", "passenger throughput", "traffic statistics",
        "passengers per year", "annual report traffic figures",
        "lượng hành khách mỗi năm", "旅客吞吐量", "年間旅客数",
    ],
    "area_km2": [
        "total site area hectares", "land area km2", "development footprint",
        "master plan area", "gross site area", "acres of land",
        "tổng diện tích quy hoạch", "占地面积", "敷地面積",
    ],
    "employees": [
        "jobs created", "direct employment", "number of employees", "workforce",
        "on-site jobs", "employment impact study", "economic impact jobs",
        "số lao động làm việc", "就业人数", "雇用者数",
    ],
    "subzones": [
        "zones and precincts", "sub-zones", "development districts", "clusters",
        "masterplan zoning", "precinct list",
        "các phân khu chức năng", "功能分区", "地区区分",
    ],
}


def focus_block(focus: list[str]) -> str:
    """Phần prompt nhấn vào các trường còn trống, kèm từ khoá tra web cụ thể."""
    if not focus:
        return ""
    lines = ["\n## TRỌNG TÂM LẦN NÀY — các trường sau đang TRỐNG, phải tìm cho bằng được"]
    for f in focus:
        kws = FIELD_KEYWORDS.get(f, [])
        lines.append(f"- `{f}`" + (f" — thử tra: {', '.join(kws)}" if kws else ""))
    lines.append(
        "\nMỗi trường trên hãy chạy ÍT NHẤT một lượt web_search riêng, ghép từ khoá với "
        "tên khu và tên sân bay. Nguồn hay có các số này: báo cáo thường niên của đơn vị "
        "vận hành sân bay, báo cáo tác động kinh tế (economic impact study), hồ sơ master "
        "plan của cơ quan quy hoạch, trang 'facts & figures' hoặc 'about' của khu. "
        "Trang nào KHÔNG chứa được ít nhất một trong các trường trọng tâm thì đừng trả về.")
    return "\n".join(lines)


def build_prompt(entry: dict, case_id: str, have: list[str], want: int,
                 focus: list[str] | None = None) -> str:
    known = "\n".join(f"- {u}" for u in have[:40]) or "(chưa có nguồn nào)"
    return f"""Bạn đang tuyển nguồn dữ liệu để benchmark một khu đô thị sân bay (aerotropolis).

## Khu cần tìm nguồn
- Tên: {entry.get('name') or case_id}
- Quốc gia: {entry.get('country', '')}
- Sân bay trung tâm: {entry.get('airport', '')}
- Ghi chú: {entry.get('note', '')}

## Cần lấy được những trường này
{field_menu()}
{focus_block(focus or [])}

## Nguồn ĐÃ CÓ (đừng lặp lại)
{known}

## Việc phải làm
Dùng web_search và web_fetch để tìm **{want} trang nguồn MỚI** cho khu trên. Ưu tiên theo thứ tự:
1. Website chính thức của khu đô thị / cơ quan quản lý khu (authority, development corporation);
2. Website chính thức của sân bay và công ty vận hành (mục facts & figures, statistics, annual report);
3. Cơ quan quy hoạch / chính quyền địa phương công bố master plan, diện tích, phân khu, vốn đầu tư;
4. Trang chuyên đề: khu logistics, khu thương mại tự do, tuyến đường sắt kết nối, tổ hợp tiện ích lớn;
5. Wikipedia và báo cáo tư vấn (CBRE/JLL) — chỉ dùng để ĐỐI CHIẾU, đặt priority thấp hơn.

Quy tắc bắt buộc:
- CHỈ trả URL bạn đã thực sự mở được bằng web_search/web_fetch trong lượt này. Không đoán, không dựng URL theo mẫu.
- Ưu tiên trang tiếng Anh; trang bản địa chỉ lấy khi có số liệu mà bản tiếng Anh không có.
- Mỗi URL trỏ ĐÚNG trang nội dung, không phải trang chủ chung chung (trừ khi trang chủ chính là nơi có dữ liệu).
- Không lấy trang tin tức trôi, blog cá nhân, trang bán hàng, PDF quá 30MB.
- `target_fields` chỉ liệt kê tên trường trong danh sách trên mà trang đó THỰC SỰ trả lời được.
- `priority`: 5 = nguồn chính thức giàu số liệu, 1 = chỉ đối chiếu phụ.

## Ảnh minh hoạ — tiêu chí phụ nhưng có tính điểm
Trang nguồn còn được dùng để lấy ảnh minh hoạ cho hồ sơ, nên **khi hai trang có giá trị số liệu
ngang nhau, hãy chọn trang có ảnh dùng được**. Ảnh dùng được nghĩa là:
- ảnh chụp thật hoặc bản vẽ quy hoạch của CHÍNH khu này: ảnh trên không, phối cảnh, bản đồ phân
  khu, nội thất nhà ga, công trình tiêu biểu;
- bề rộng từ **800px trở lên** (trang thường để bản lớn trong `srcset` hoặc thư viện ảnh);
- KHÔNG tính: logo, biểu tượng giao diện, ảnh chân dung lãnh đạo, banner quảng cáo, bản đồ định vị
  kiểu "nước X nằm ở đâu", đồ hoạ dải mỏng.
Đặt `has_images: true` khi trang có ít nhất một ảnh như vậy. Đừng vì ảnh mà hạ chuẩn số liệu —
trang nhiều ảnh nhưng không có dữ liệu thì vẫn bỏ.

## Định dạng trả về (chỉ JSON, không thêm chữ nào khác)
{{"sources": [
  {{"url": "https://...", "anchor": "tên trang ngắn gọn",
   "purpose": "trang này dùng để lấy gì (tiếng Việt, 1 câu)",
   "target_fields": ["passengers_million", "subzones"], "priority": 5,
   "has_images": true}}
]}}"""


def probe(url: str, timeout: int = 15) -> tuple[bool, str]:
    """Kiểm tra URL sống. 403/405 vẫn coi là được vì Playwright thường qua được."""
    for method in ("HEAD", "GET"):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA}, method=method)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return True, str(r.status)
        except urllib.error.HTTPError as e:
            if e.code in (403, 405, 406, 429):
                return True, f"{e.code} (bot-block, Playwright thử lại)"
            if method == "GET":
                return False, str(e.code)
        except Exception as e:  # DNS, TLS, timeout…
            if method == "GET":
                return False, type(e).__name__
    return False, "?"


def discover(case_id: str, entry: dict, have: list[str], want: int, model: str,
             timeout: int, retries: int, jobs: int, dry_run: bool,
             focus: list[str] | None = None) -> list[dict]:
    prompt = build_prompt(entry, case_id, have, want, focus)
    print(f"\n=== {case_id} · đã có {len(have)} nguồn · xin thêm {want}")
    if dry_run:
        print(prompt[:1200] + "\n…")
        return []

    found: list[dict] = []
    for attempt in range(1, retries + 1):
        try:
            t0 = time.time()
            out = extract_json(call_model(prompt, model, timeout))
            found = [s for s in out.get("sources", []) if isinstance(s, dict) and s.get("url")]
            print(f"  model trả {len(found)} nguồn ({time.time() - t0:.0f}s)")
            break
        except (urllib.error.URLError, ValueError, json.JSONDecodeError, TimeoutError) as exc:
            print(f"  ! lần {attempt}/{retries}: {type(exc).__name__}: {exc}")
            if attempt < retries:
                time.sleep(5 * attempt)
    if not found:
        return []

    seen = set(have)
    cand = []
    for s in found:
        url = registry_mod.clean_url(str(s["url"]).strip())
        if url in seen or not url.startswith("http"):
            continue
        seen.add(url)
        cand.append({**s, "url": url})

    stamp = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    rows: list[dict] = []
    with cf.ThreadPoolExecutor(max_workers=jobs) as pool:
        for s, (alive, note) in zip(cand, pool.map(lambda c: probe(c["url"]), cand)):
            mark = "ok " if alive else "chết"
            print(f"    [{mark}] {note:26s} {s['url'][:88]}")
            if not alive:
                continue
            tf = s.get("target_fields") or []
            rows.append({"case_id": case_id, "idx": None,
                         "priority": str(s.get("priority", "")).strip(),
                         "anchor": str(s.get("anchor", "")).strip(),
                         "url": s["url"], "purpose": str(s.get("purpose", "")).strip(),
                         "target_fields": ";".join(tf) if isinstance(tf, list) else str(tf),
                         "has_images": "1" if s.get("has_images") else "",
                         "origin": "llm", "discovered_at": stamp,
                         "kind": "", "crawl_status": "chưa crawl", "http_status": "",
                         "chars": "", "text_file": "", "accessed_at": ""})
    print(f"  -> giữ {len(rows)}/{len(cand)} nguồn mới")
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description="LLM tra web tìm nguồn cho từng aerotropolis")
    ap.add_argument("--case", help="một case_id")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--missing", action="store_true", help="chỉ case chưa có nguồn nào")
    ap.add_argument("--want", type=int, default=20, help="số nguồn mới xin mỗi case")
    ap.add_argument("--model", default=os.getenv("CLAUDE_PROXY_MODEL", "claude-opus-5"))
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--retries", type=int, default=2)
    ap.add_argument("--jobs", type=int, default=8, help="luồng probe URL song song")
    ap.add_argument("--no-registry", action="store_true",
                    help="không dựng lại sources.csv/xlsx (dùng khi chạy nhiều tiến trình song song)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--focus", default="",
                    help="danh sách trường cần nhắm, cách nhau bởi dấu phẩy "
                         "(vd: passengers_million,area_km2,employees,subzones)")
    args = ap.parse_args()

    reg = registry_mod.load_registry()
    entries = {registry_mod.match_case_id(e, reg): e for e in registry_mod.parse_case_list()}
    for cid in reg:
        entries.setdefault(cid, {})
    if not entries:
        raise SystemExit("Không đọc được case nào từ refer_file/aerotropolis.txt")

    existing = {cid: [r["url"] for r in registry_mod.read_existing_csv(cid)] for cid in entries}
    if args.case:
        targets = [args.case]
    elif args.missing:
        targets = [c for c in entries if not existing.get(c)]
    elif args.all:
        targets = list(entries)
    else:
        raise SystemExit("cần --case <id>, --all hoặc --missing")
    if not targets:
        print("[bỏ qua] mọi case đều đã có nguồn (dùng --all để bổ sung thêm).")
        return

    focus = [f.strip() for f in args.focus.split(',') if f.strip()]
    new_rows: list[dict] = []
    for cid in targets:
        new_rows += discover(cid, entries.get(cid, {}), existing.get(cid, []), args.want,
                             args.model, args.timeout, args.retries, args.jobs, args.dry_run,
                             focus)
    if args.dry_run or not new_rows:
        print("\n[done] không ghi gì.")
        return

    # Ghi mỗi case một file riêng trong _discovered/ thay vì sửa chung sources.csv:
    # nhiều tiến trình discover chạy song song sẽ ghi đè lẫn nhau nếu dùng chung một file.
    # build_source_registry.py gom các file này lại khi dựng sources.csv.
    outdir = REFER / "_discovered"
    outdir.mkdir(parents=True, exist_ok=True)
    by_case: dict[str, list[dict]] = {}
    for r in new_rows:
        by_case.setdefault(r["case_id"], []).append(r)
    for cid, rows in by_case.items():
        path = outdir / f"{cid}.csv"
        old = registry_mod.read_discovered_file(path)
        seen = {r["url"] for r in rows}
        merged = rows + [r for r in old if r["url"] not in seen]
        registry_mod.write_csv(path, registry_mod.SOURCE_COLS, merged)

    if not args.no_registry:
        cases, sources = registry_mod.build("")
        registry_mod.write_csv(REFER / "cases.csv", registry_mod.CASE_COLS, cases)
        registry_mod.write_csv(REFER / "sources.csv", registry_mod.SOURCE_COLS, sources)
        registry_mod.write_xlsx(REFER / "sources.xlsx", cases, sources)

    print(f"\n[done] thêm {len(new_rows)} nguồn mới cho {len(targets)} case."
          f"\n       chạy tiếp: python scripts/run_ws.py ws1_airport --steps crawl,extract,validate,web")


if __name__ == "__main__":
    main()
