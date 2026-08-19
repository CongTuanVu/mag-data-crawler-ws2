"""Dựng REGISTRY nguồn tập trung cho WS1 từ các bảng .txt đã tuyển + manifest crawl.

Thay cho 10 file `refer_file/<case>.txt` rời rạc, script sinh ra:

  refer_file/cases.csv     — 1 dòng / aerotropolis (định danh + thống kê nguồn)
  refer_file/sources.csv   — 1 dòng / URL nguồn (case_id, url, purpose, target_fields, priority,
                             trạng thái crawl lấy từ manifest.json)
  refer_file/sources.xlsx  — cùng nội dung, 2 sheet `cases` + `sources` (bản cho người biên tập)

Đầu vào (theo thứ tự ưu tiên, tự động fallback):
  1. refer_file/<case>.txt trong working tree
  2. `git show <rev>:refer_file/<case>.txt`  (dùng khi file đã bị xoá khỏi working tree)
  3. raw_data/output/ws1_airport/raw/<case>/manifest.json (URL thực tế đã crawl)

Bảng .txt có 2 layout khác nhau (5 cột có "Mức độ ưu tiên", 3 cột không có) nên parser
bám vào ô chứa markdown link thay vì chỉ số cột cố định.

Chạy:
    python scripts/build_source_registry.py
    python scripts/build_source_registry.py --rev HEAD --no-xlsx
"""
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

WS = "ws1_airport"
ROOT = Path(__file__).resolve().parents[1]
REFER = ROOT / "refer_file"
RAW = ROOT / "raw_data" / "output" / WS / "raw"
EXTRACTOR = ROOT / "agent_extractor" / WS / "extract_airport_city.py"

LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
FIELD_RE = re.compile(r"`([a-z][a-z0-9_]{2,})`")
NUM_CELL_RE = re.compile(r"^\*{0,2}\d+\*{0,2}$")

# case_id -> tên file .txt gốc (đa số trùng case_id, Schiphol viết hoa)
TXT_NAME = {"schiphol": "Schiphol.txt"}

CASE_COLS = ["case_id", "case_name", "aerotropolis", "country", "is_target", "airport_name",
             "reference_city", "official_website", "source_list", "n_sources", "n_crawled",
             "n_pages", "last_crawl"]
SOURCE_COLS = ["case_id", "idx", "priority", "anchor", "url", "purpose", "target_fields",
               "origin", "discovered_at", "kind", "crawl_status", "http_status", "chars",
               "text_file", "accessed_at"]


# Cụm chung có mặt ở hầu hết tên khu -> bỏ đi thì case_id mới ngắn và phân biệt được
GENERIC_RE = re.compile(
    r"\b(aerotropolis|aeropolis|airportcity|airport city|airport economy zone|"
    r"airport economic zone|airport business city|airport business district|"
    r"business district|economy zone|economic zone|aerocity|airport|international)\b")


def slugify_case(name: str) -> str:
    """Tên aerotropolis -> case_id ngắn (bỏ dấu, bỏ cụm chung, giữ tối đa 3 từ định danh)."""
    import unicodedata
    s = unicodedata.normalize("NFD", name.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").replace("đ", "d")
    s = re.sub(r"\([^)]*\)", " ", s)          # bỏ phần trong ngoặc: "(ZAEZ)", "(HICity)"
    s = s.split("/")[0]                        # "Dubai Aerotropolis / Dubai South" -> vế đầu
    s = GENERIC_RE.sub(" ", s)
    tokens = [t for t in re.split(r"[^a-z0-9]+", s) if t]
    return "_".join(tokens[:3])[:32] or "case"


def parse_case_list(path: Path | None = None) -> list[dict]:
    """Đọc refer_file/aerotropolis.txt -> danh sách case gốc (chỉ tên, chưa có URL).

    Đây là đầu vào duy nhất bắt buộc của pipeline: mọi URL nguồn về sau hoặc do
    người tuyển tay, hoặc do `discover_sources.py` nhờ LLM tra web mà có.
    """
    path = path or REFER / "aerotropolis.txt"
    if not path.exists():
        return []
    cases = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = [strip_md(c) for c in line.strip().strip("|").split("|")]
        if len(cells) < 4 or not NUM_CELL_RE.match(cells[0].replace("*", "") or "x"):
            continue
        name = cells[1]
        if not name or name.startswith("---"):
            continue
        cases.append({"name": name, "country": cells[2], "airport": cells[3],
                      "note": cells[4] if len(cells) > 4 else ""})
    return cases


def match_case_id(entry: dict, registry: dict, taken: set[str] | None = None) -> str:
    """Khớp 1 dòng aerotropolis.txt với case_id trong REGISTRY, không khớp thì tạo slug.

    Khớp theo RANH GIỚI TỪ, không phải chuỗi con: "Shanghai Hongqiao" từng bị gán nhầm
    vào `hong_kong` vì "hong" nằm trong "hongqiao".
    """
    hay = f"{entry.get('name', '')} {entry.get('airport', '')}".lower()
    for cid, meta in registry.items():
        needles = {cid.replace("_", " ")} | {str(meta.get(k, "")).lower()
                                             for k in ("case_name", "airport_name", "aerotropolis")}
        for n in needles:
            if n and re.search(rf"\b{re.escape(n)}\b", hay):
                return cid
    slug = slugify_case(entry.get("name", ""))
    if taken is not None:                      # hai khu khác nhau không được chung case_id
        base, i = slug, 2
        while slug in taken:
            slug = f"{base}_{i}"
            i += 1
        taken.add(slug)
    return slug


def clean_url(url: str) -> str:
    """Bỏ tham số tracking để join .txt <-> manifest không trượt."""
    p = urlparse(url)
    q = [(k, v) for k, v in parse_qsl(p.query) if not k.lower().startswith("utm_")]
    return urlunparse(p._replace(query=urlencode(q), fragment=""))


def strip_md(text: str) -> str:
    return re.sub(r"\s{2,}", " ", re.sub(r"\*\*|`", "", text)).strip()


def read_txt(case_id: str, rev: str) -> tuple[str, str]:
    """Trả (nội dung, nguồn lấy từ đâu). Ưu tiên working tree; chỉ đụng git khi có --rev.

    Mặc định KHÔNG đọc từ git: bảng .txt đã bị bỏ khỏi working tree là chủ ý, dựng lại
    tự động sẽ hồi sinh nguồn mà người dùng cố tình loại.
    """
    name = TXT_NAME.get(case_id, f"{case_id}.txt")
    path = REFER / name
    if path.exists():
        return path.read_text(encoding="utf-8"), f"refer_file/{name}"
    if not rev:
        return "", ""
    try:
        out = subprocess.run(["git", "show", f"{rev}:refer_file/{name}"], cwd=ROOT,
                             capture_output=True, text=True, check=True)
        return out.stdout, f"git:{rev}:refer_file/{name}"
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "", ""


def read_discovered_file(path: Path) -> list[dict]:
    """Đọc một file refer_file/_discovered/<case>.csv do discover_sources.py ghi ra."""
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r.get("url")]
    for r in rows:
        r["url"] = clean_url(r["url"])
        r["idx"] = int(r["idx"]) if str(r.get("idx", "")).isdigit() else None
        r.setdefault("origin", "llm")
    return rows


def read_existing_csv(case_id: str) -> list[dict]:
    """Đọc lại sources.csv đã dựng — dùng khi bảng .txt gốc không còn ở đâu nữa.

    Sau khi .txt bị xoá khỏi cả working tree lẫn lịch sử git, sources.csv chính là
    bản chốt: không có nó thì `purpose`/`target_fields`/`priority` sẽ mất trắng vì
    manifest.json không lưu mấy cột đó.
    """
    path = REFER / "sources.csv"
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r.get("case_id") == case_id and r.get("url")]
    return [{"idx": int(r["idx"]) if (r.get("idx") or "").isdigit() else None,
             "anchor": r.get("anchor", ""), "url": clean_url(r["url"]),
             "purpose": r.get("purpose", ""), "target_fields": r.get("target_fields", ""),
             "priority": r.get("priority", ""), "origin": r.get("origin", "") or "curated",
             "discovered_at": r.get("discovered_at", "")} for r in rows]


def parse_table(text: str) -> list[dict]:
    """Bóc các dòng bảng markdown có link -> {idx, anchor, url, purpose, target_fields, priority}."""
    rows: list[dict] = []
    for line in text.splitlines():
        if "](" not in line or not line.lstrip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        link_idx = next((i for i, c in enumerate(cells) if "](" in c), None)
        if link_idx is None:
            continue
        m = LINK_RE.search(cells[link_idx])
        if not m:
            continue
        idx = next((int(re.sub(r"\*", "", c)) for c in cells[:link_idx] if NUM_CELL_RE.match(c)), None)
        rest = cells[link_idx + 1:]
        priority = ""
        if rest and "⭐" in rest[-1]:
            priority = str(rest.pop().count("⭐"))
        fields = sorted({f for c in rest for f in FIELD_RE.findall(c)})
        rows.append({"idx": idx, "anchor": strip_md(m.group(1)), "url": clean_url(m.group(2)),
                     "purpose": " | ".join(strip_md(c) for c in rest if c.strip()),
                     "target_fields": ";".join(fields), "priority": priority})
    return rows


def load_manifest(case_id: str) -> tuple[dict, dict]:
    """Trả (map url -> entry crawl, meta manifest)."""
    path = RAW / case_id / "manifest.json"
    if not path.exists():
        return {}, {}
    man = json.loads(path.read_text(encoding="utf-8"))
    return {clean_url(s["url"]): s for s in man.get("sources", [])}, man


def load_registry() -> dict:
    spec = importlib.util.spec_from_file_location("_extract_airport_city", EXTRACTOR)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.REGISTRY


def build(rev: str) -> tuple[list[dict], list[dict]]:
    """Gộp 3 nguồn thông tin về nguồn crawl, ưu tiên theo thứ tự khai báo:

      1. bảng .txt đã tuyển tay còn trong working tree (thêm --rev để lấy lại từ git)
      2. sources.csv của lần dựng trước — chứa cả URL do LLM tra web mà có
      3. manifest.json — URL đã crawl thật, kể cả URL thêm ngoài registry
    """
    registry = load_registry()
    case_list = parse_case_list()
    # aerotropolis.txt là danh sách case gốc; case chưa có trong REGISTRY vẫn phải xuất hiện
    order: dict[str, dict] = {}
    taken: set[str] = set(registry)
    for entry in case_list:
        order[match_case_id(entry, registry, taken)] = entry
    for cid in registry:
        order.setdefault(cid, {})

    cases: list[dict] = []
    sources: list[dict] = []

    for case_id, entry in order.items():
        meta = registry.get(case_id, {})
        text, origin = read_txt(case_id, rev)
        curated = parse_table(text) if text else []
        for r in curated:
            r.setdefault("origin", "curated")
            r.setdefault("discovered_at", "")
        seen = {r["url"] for r in curated}
        # nguồn do discover tìm được, mỗi case một file (an toàn khi chạy song song)
        found = [r for r in read_discovered_file(REFER / "_discovered" / f"{case_id}.csv")
                 if r["url"] not in seen]
        if found:
            curated += found
            seen |= {r["url"] for r in found}
            origin = origin or "refer_file/_discovered/"
        # giữ lại dòng đã có trong sources.csv (đáng kể nhất: origin=llm của lần dựng trước)
        kept = [r for r in read_existing_csv(case_id) if r["url"] not in seen]
        if kept:
            curated += kept
            seen |= {r["url"] for r in kept}
            origin = origin or "refer_file/sources.csv"
        crawled, man = load_manifest(case_id)

        rows: list[dict] = []
        for r in curated:
            hit = crawled.get(r["url"], {})
            rows.append({**r, "case_id": case_id,
                         "kind": hit.get("kind", ""),
                         "crawl_status": hit.get("status", "chưa crawl"),
                         "http_status": hit.get("http_status", ""),
                         "chars": hit.get("chars", ""),
                         "text_file": hit.get("text_file", ""),
                         "accessed_at": hit.get("accessed_at", "")})
        # URL có trong raw nhưng không có trong registry (crawl bổ sung sau) -> vẫn giữ
        for url, hit in crawled.items():
            if url in seen:
                continue
            rows.append({"case_id": case_id, "idx": hit.get("idx"), "priority": "",
                         "anchor": hit.get("anchor") or hit.get("title", ""), "url": url,
                         "purpose": hit.get("purpose", ""), "target_fields": "",
                         "origin": "manifest", "discovered_at": "",
                         "kind": hit.get("kind", ""), "crawl_status": hit.get("status", ""),
                         "http_status": hit.get("http_status", ""), "chars": hit.get("chars", ""),
                         "text_file": hit.get("text_file", ""),
                         "accessed_at": hit.get("accessed_at", "")})

        rows.sort(key=lambda r: (r["idx"] is None, r["idx"] or 0))
        for i, r in enumerate(rows, 1):
            r["idx"] = i
        sources.extend(rows)

        pages = RAW / case_id / "pages"
        cases.append({"case_id": case_id,
                      "case_name": meta.get("case_name") or entry.get("name", ""),
                      "aerotropolis": meta.get("aerotropolis") or entry.get("name", ""),
                      "country": meta.get("country") or entry.get("country", ""),
                      "is_target": meta.get("is_target", ""),
                      "airport_name": meta.get("airport_name") or entry.get("airport", ""),
                      "reference_city": meta.get("reference_city", ""),
                      "official_website": meta.get("official_website", ""),
                      "source_list": origin or ("manifest (raw đã crawl)" if rows
                                                else "(chưa có nguồn — chạy discover_sources.py)"),
                      "n_sources": len(rows),
                      "n_crawled": sum(1 for r in rows if r["crawl_status"] == "ok"),
                      "n_pages": len(list(pages.glob("*.txt"))) if pages.is_dir() else 0,
                      "last_crawl": man.get("accessed_at", "")})
    return cases, sources


def write_csv(path: Path, cols: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"[ok] {path.relative_to(ROOT)}  ({len(rows)} dòng)")


def write_xlsx(path: Path, cases: list[dict], sources: list[dict]) -> None:
    try:
        import pandas as pd
    except ImportError:
        print("[skip] chưa có pandas -> bỏ qua .xlsx")
        return
    with pd.ExcelWriter(path, engine="openpyxl") as xl:
        pd.DataFrame(cases, columns=CASE_COLS).to_excel(xl, sheet_name="cases", index=False)
        pd.DataFrame(sources, columns=SOURCE_COLS).to_excel(xl, sheet_name="sources", index=False)
    print(f"[ok] {path.relative_to(ROOT)}  (2 sheet)")


def main() -> None:
    ap = argparse.ArgumentParser(description="Dựng refer_file/{cases,sources}.csv + sources.xlsx")
    ap.add_argument("--rev", default="", help="revision git để lấy lại bảng .txt đã xoá (vd HEAD); "
                    "mặc định chỉ dùng file còn trong working tree")
    ap.add_argument("--no-xlsx", action="store_true")
    args = ap.parse_args()

    REFER.mkdir(parents=True, exist_ok=True)
    cases, sources = build(args.rev)
    write_csv(REFER / "cases.csv", CASE_COLS, cases)
    write_csv(REFER / "sources.csv", SOURCE_COLS, sources)
    if not args.no_xlsx:
        write_xlsx(REFER / "sources.xlsx", cases, sources)

    miss = [c["case_id"] for c in cases if c["source_list"].startswith("(")]
    if miss:
        print(f"[cảnh báo] không tìm thấy bảng nguồn cho: {', '.join(miss)}")
    print(f"\n[done] {len(cases)} case · {len(sources)} nguồn · "
          f"{sum(c['n_crawled'] for c in cases)} đã crawl ok")


if __name__ == "__main__":
    main()
