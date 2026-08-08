"""Extractor: đọc text đã crawl của MỘT aerotropolis -> điền feature_spec.

FILE.PY sinh từ:
  - features/ws1_airport/feature_spec.md   (định nghĩa trường)
  - agent_extractor/SKILL.md               (quy trình)
  - raw_data/output/ws1_airport/raw/<name>/pages/*.txt  (dữ liệu đã crawl)

Deterministic (không gọi LLM/mạng): dùng thư viện regex + từ khoá để rút số liệu
và trường định tính, ghi PROVENANCE cho từng trường (nguồn URL + file + snippet +
confidence). Trường không tìm thấy để null (không bịa).

Chạy:
    python agent_extractor/ws1_airport/extract_airport_city.py --name schiphol
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

WS = "ws1_airport"
ROOT = Path(__file__).resolve().parents[2]

# Định danh (không nằm chắc chắn trong text) — khai báo theo case đã biết.
REGISTRY = {
    "schiphol": {
        "case_name": "Schiphol Airport City",
        "aerotropolis": "Schiphol Airport City / Amsterdam Aerotropolis",
        "country": "Hà Lan",
        "is_target": False,
        "airport_name": "Amsterdam Airport Schiphol",
        "reference_city": "Amsterdam",
        "official_website": "https://www.schiphol.nl",
    },
}


def load_pages(name: str):
    base = ROOT / "raw_data" / "output" / WS / "raw" / name
    if not base.exists():
        raise FileNotFoundError(f"Chưa có raw cho '{name}': {base}\n"
                                f"Chạy trước: python raw_data/crawler/crawl_sources.py --name {name} --input ...")
    url_by_file: dict[str, str] = {}
    man_path = base / "manifest.json"
    if man_path.exists():
        man = json.loads(man_path.read_text(encoding="utf-8"))
        for s in man.get("sources", []):
            tf = s.get("text_file")
            if tf:
                url_by_file[Path(tf).name] = s.get("url", "")
    pages = []
    for txt in sorted((base / "pages").glob("*.txt")):
        pages.append({"file": txt.name, "url": url_by_file.get(txt.name, ""),
                      "text": txt.read_text(encoding="utf-8", errors="ignore")})
    return pages


def _search(pages, pattern, flags=re.I, prefer=None):
    """Tìm pattern; nếu `prefer` (chuỗi con tên file) thì ưu tiên trang đó trước.

    Dùng khi cùng một chỉ số xuất hiện ở nhiều trang với số khác nhau (vd marketing
    'over 300' vs Facts&Figures '301') -> ưu tiên trang nguồn chuẩn.
    """
    ordered = pages
    if prefer:
        ordered = sorted(pages, key=lambda p: 0 if prefer.lower() in p["file"].lower() else 1)
    rx = re.compile(pattern, flags)
    for p in ordered:
        m = rx.search(p["text"])
        if m:
            return m, p
    return None, None


def field_num(pages, pattern, cast=float, group=1, unit="", conf="high", prefer=None):
    m, p = _search(pages, pattern, prefer=prefer)
    if not m:
        return None
    raw = m.group(group).replace(",", "").replace(" ", "")
    try:
        val = cast(raw)
    except ValueError:
        val = m.group(group)
    return {"value": val, "unit": unit, "source_url": p["url"],
            "source_file": p["file"], "snippet": " ".join(m.group(0).split())[:140], "confidence": conf}


def field_text(pages, pattern, group=1, conf="high"):
    m, p = _search(pages, pattern)
    if not m:
        return None
    return {"value": " ".join(m.group(group).split()), "source_url": p["url"],
            "source_file": p["file"], "snippet": " ".join(m.group(0).split())[:160], "confidence": conf}


def field_range(pages, pattern, unit="", conf="high", prefer=None):
    """Gom TẤT CẢ số khớp trong corpus -> {min, max, count} (vd giá €/m²)."""
    ordered = pages
    if prefer:
        ordered = sorted(pages, key=lambda p: 0 if prefer.lower() in p["file"].lower() else 1)
    rx = re.compile(pattern, re.I)
    vals, url, file = [], None, None
    for p in ordered:
        for m in rx.finditer(p["text"]):
            try:
                vals.append(float(m.group(1).replace(",", "").replace(" ", "")))
                if url is None:
                    url, file = p["url"], p["file"]
            except ValueError:
                pass
    if not vals:
        return None
    return {"value": {"min": min(vals), "max": max(vals), "count": len(vals)}, "unit": unit,
            "source_url": url, "source_file": file, "confidence": conf}


def field_collect(pages, patterns, conf="high"):
    """Gom nhiều snippet khớp (mỗi pattern lấy match đầu) thành 1 list + nguồn."""
    items, urls, files = [], set(), set()
    for pat in patterns:
        m, p = _search(pages, pat)
        if m:
            items.append(" ".join(m.group(0).split()))
            if p["url"]:
                urls.add(p["url"])
            files.add(p["file"])
    if not items:
        return None
    return {"value": items, "source_urls": sorted(urls),
            "source_files": sorted(files), "confidence": conf}


def field_presence(pages, tokens, conf="high"):
    """Trả về danh sách token xuất hiện trong corpus, kèm nguồn đầu tiên."""
    found = []
    for tok in tokens:
        m, p = _search(pages, re.escape(tok))
        if m:
            found.append({"item": tok, "source_url": p["url"], "source_file": p["file"]})
    if not found:
        return None
    return {"value": [f["item"] for f in found],
            "source_urls": sorted({f["source_url"] for f in found}),
            "confidence": conf}


def extract(name: str) -> dict:
    pages = load_pages(name)
    ident = REGISTRY.get(name, {"case_name": name})
    rec: dict = dict(ident)

    # --- Định vị & khái niệm (Group A) ---
    rec["positioning"] = ({"value": "AirportCity", "confidence": "high"}
                          if _search(pages, r"AirportCity")[0] else None)
    rec["planning_concept"] = field_text(
        pages, r"(has been developed as an AirportCity[^.]*\.)")
    cs = field_text(pages, r"cornerstones of the AirportCity concept:\s*([^.]+)\.")
    if cs:
        parts = re.split(r",\s*|\s+and\s+", cs["value"])
        cs["value"] = [x.strip() for x in parts if x.strip()]
    rec["cornerstones"] = cs
    rec["subzones"] = field_presence(pages, [
        "Schiphol Central Business District", "Schiphol East",
        "Schiphol Southeast", "Schiphol Business District"])

    # --- Sản phẩm / BĐS thương mại (Group B1) ---
    rec["commercial_re"] = field_presence(pages, [
        "logistics", "cargo", "office", "real estate", "retail", "hotel",
        "World Trade Center", "The Base"])
    rec["num_office_buildings"] = field_num(pages, r"(\d+)\s+business buildings", cast=int, unit="buildings")
    rec["num_companies_realestate"] = field_num(pages, r"more than\s*([\d,]+)\s*companies", cast=int, unit="companies")
    rec["num_companies_airport"] = field_num(pages, r"around\s*([\d,]+)\s*(?:other\s*)?(?:different\s*)?companies", cast=int, unit="companies")

    # Nhà ở: Schiphol AirportCity thiên về business/office -> thường không có
    rec["residential_product_desc"] = None  # không thấy trong nguồn (business-focused)

    # --- Tiện ích (Group B1) ---
    rec["basic_amenities"] = field_presence(pages, [
        "meeting", "sports", "restaurants", "catering", "child care", "childcare",
        "shops", "Schiphol Plaza", "café", "fitness"])
    rec["highlight_amenities"] = field_presence(pages, [
        "World Trade Center", "WTC", "Hilton Hotel", "Sheraton Hotel",
        "The Base", "The Outlook", "BREEAM"])

    # --- Chỉ số quy mô sân bay-đô thị (mở rộng, hợp domain) ---
    rec["airport_area_ha"] = field_num(pages, r"([\d,]+)\s*hectares", cast=float, unit="ha")
    rec["employees"] = field_num(pages, r"[Aa]round\s*([\d,]+)\s*people work", cast=int, unit="people")
    # Chỉ số headline: ưu tiên trang "Facts & Figures 2025" (số chính thức, mới nhất)
    FF = "facts_figures"
    rec["passengers_million"] = field_num(pages, r"([\d.,]+)\s*million passengers", cast=float, unit="million/năm", prefer=FF)
    rec["air_movements"] = field_num(pages, r"([\d,]+)\s*air transport movements", cast=int, unit="movements/năm", prefer=FF)
    rec["cargo_million_tonnes"] = field_num(pages, r"([\d.,]+)\s*million tonnes of Cargo", cast=float, unit="triệu tấn/năm", prefer=FF)
    rec["destinations"] = field_num(pages, r"(\d+)\s*direct destinations", cast=int, unit="điểm đến", prefer=FF)
    rec["airlines"] = field_num(pages, r"(\d+)\s*airlines", cast=int, unit="hãng", prefer=FF)
    rec["transfer_pct"] = field_num(pages, r"([\d.,]+)\s*%\s*Transfer", cast=float, unit="%", prefer=FF)

    # --- Group B — Phân tích CVP (6 trụ) ---
    rec["cvp_product"] = field_presence(pages, [
        "office", "commercial space", "development", "logistics", "cargo", "retail", "real estate"])
    rec["cvp_price"] = field_text(pages, r"(income from a range of sources[^.]*\.|property rents and leaseholds[^.]*\.)")
    # Chỉ bắt GIÁ THUÊ (mở đầu "Starting at"/"From") -> loại "Service costs €65/m²"
    rec["office_rent_eur_m2_year"] = field_range(
        pages, r"(?:Starting at|From)\s*€\s*([\d.,]+)\s*per\s*m", unit="€/m²/năm (excl. VAT)")
    rec["cvp_price_note"] = "Giá chào thuê văn phòng; đơn giá tuỳ toà & phân khu"
    rec["cvp_service"] = field_presence(pages, [
        "Spot", "Leasing Managers", "area director", "flexible real estate"])
    rec["cvp_experience"] = field_presence(pages, [
        "restaurants", "sports", "meeting", "Schiphol Plaza", "Hilton Hotel", "Sheraton Hotel", "café"])
    rec["cvp_convenience"] = field_collect(pages, [
        r"Accessible by [^.]+\.",
        r"highways?[^.]*A\d[^.]*",
        r"high-speed train to Paris[^.]*\.",
        r"2-8 minutes'? walk to the NS train station[^.]*\.",
    ])
    rec["cvp_brand"] = field_presence(pages, ["Royal Schiphol Group", "Schiphol Real Estate"])
    rec["rail_connections"] = field_collect(pages, [
        r"Amsterdam ?- ?Schiphol Airport",
        r"Schiphol Airport ?- ?Rotterdam",
        r"Intercity direct",
    ])

    # --- Bổ sung từ nguồn mở rộng (lịch sử · tầm nhìn · park vùng · bền vững) ---
    rec["founded_year"] = field_num(pages, r"began life in (\d{4})", cast=int, unit="năm", prefer="history")
    rec["vision_label"] = "Vision 2050" if _search(pages, r"Vision 2050")[0] else None
    rec["vision_qualities"] = field_presence(pages, [
        "Quality of Network", "Quality of Life", "Quality of Service", "Quality of Work"])
    rec["aviation_policy"] = field_text(pages, r"(Aviation Policy Memorandum 2020[–-]2050)")
    rec["logistics_park_ha"] = field_num(pages, r"(\d+)\s*hectare", cast=float, unit="ha", prefer="logistics_park")
    rec["trade_park_ha"] = field_num(pages, r"(\d+)[- ]hectare", cast=float, unit="ha", prefer="trade_park")
    rec["sustainability"] = field_presence(pages, [
        "BREEAM", "circular", "most sustainable", "biodiversity", "CO2"])

    rec["_pages_used"] = len(pages)
    return rec


def split_value_provenance(rec: dict):
    """Tách record thành {field: value} phẳng + {field: provenance}."""
    flat, prov = {}, {}
    for k, v in rec.items():
        if k.startswith("_"):
            flat[k] = v
            continue
        if isinstance(v, dict) and ("value" in v):
            flat[k] = v["value"]
            prov[k] = {kk: vv for kk, vv in v.items() if kk != "value"}
        else:
            flat[k] = v
    return flat, prov


def main() -> None:
    ap = argparse.ArgumentParser(description="Extract feature_spec cho 1 aerotropolis")
    ap.add_argument("--name", required=True, help="tên aerotropolis (vd schiphol)")
    args = ap.parse_args()

    rec = extract(args.name)
    flat, prov = split_value_provenance(rec)

    out_dir = ROOT / "raw_data" / "output" / WS / "features"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1) Bản ghi đầy đủ + provenance
    full = {"record": flat, "provenance": prov}
    (out_dir / f"{args.name}_airport_city.json").write_text(
        json.dumps(full, ensure_ascii=False, indent=2), encoding="utf-8")

    # 2) Append vào benchmark JSONL (1 dòng / case)
    jsonl = out_dir / "airport_city_benchmark.jsonl"
    lines = []
    if jsonl.exists():
        lines = [ln for ln in jsonl.read_text(encoding="utf-8").splitlines()
                 if ln.strip() and json.loads(ln).get("case_name") != flat.get("case_name")]
    lines.append(json.dumps(flat, ensure_ascii=False, default=str))
    jsonl.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # 3) CSV phẳng (list -> "; ", dict provenance bỏ qua)
    def cell(v):
        if isinstance(v, list):
            return "; ".join(map(str, v))
        return v
    records = [json.loads(ln) for ln in lines]
    cols = list(dict.fromkeys(k for r in records for k in r))
    with (out_dir / "airport_city_benchmark.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in records:
            w.writerow({k: cell(v) for k, v in r.items()})

    # --- Báo cáo coverage ---
    filled = [k for k, v in flat.items() if not k.startswith("_") and v not in (None, [], "")]
    empty = [k for k, v in flat.items() if not k.startswith("_") and v in (None, [], "")]
    print(f"[extract] {args.name}: đọc {flat.get('_pages_used')} trang")
    print(f"[extract] điền {len(filled)} trường, {len(empty)} trường null")
    print(f"  null: {', '.join(empty) or '(không)'}")
    print(f"[ok] -> {out_dir / f'{args.name}_airport_city.json'}")
    print(f"[ok] -> {jsonl}")
    print(f"[ok] -> {out_dir / 'airport_city_benchmark.csv'}")


if __name__ == "__main__":
    main()
