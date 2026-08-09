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

# Một câu văn xuôi, CHO PHÉP dấu chấm thập phân bên trong.
# Dùng `[^.]+\.` sẽ cắt cụt ngay tại số: "exceeding NT$2.3 trillion" -> "exceeding NT$2."
SENT = r"(?:[^.]|\.(?=\d))*\."

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
    "incheon": {
        "case_name": "Incheon Airport City / IFEZ",
        "aerotropolis": "Incheon Aerotropolis / Incheon Free Economic Zone",
        "country": "Hàn Quốc",
        "is_target": False,
        "airport_name": "Incheon International Airport",
        "reference_city": "Incheon – Seoul",
        "official_website": "https://www.airport.kr",
    },
    "taoyuan": {
        "case_name": "Taoyuan Aerotropolis",
        "aerotropolis": "Taoyuan Aerotropolis / Đô thị sân bay Đào Viên",
        "country": "Đài Loan",
        "is_target": False,
        "airport_name": "Taiwan Taoyuan International Airport",
        "reference_city": "Đào Viên – Đài Bắc",
        "official_website": "https://www.taoyuanairport.com.tw",
    },
    "western_sydney": {
        "case_name": "Western Sydney Aerotropolis",
        "aerotropolis": "Western Sydney Aerotropolis / Bradfield City",
        "country": "Úc",
        "is_target": False,
        "airport_name": "Western Sydney International (Nancy-Bird Walton)",
        "reference_city": "Sydney",
        "official_website": "https://www.wsiairport.com.au",
    },
    "dubai_south": {
        "case_name": "Dubai South",
        "aerotropolis": "Dubai South / Dubai World Central",
        "country": "UAE",
        "is_target": False,
        "airport_name": "Al Maktoum International Airport",
        "reference_city": "Dubai",
        "official_website": "https://www.dubaisouth.ae",
    },
    "changi": {
        "case_name": "Singapore Changi Aerotropolis",
        "aerotropolis": "Changi Airport City / Changi East",
        "country": "Singapore",
        "is_target": False,
        "airport_name": "Singapore Changi Airport",
        "reference_city": "Singapore",
        "official_website": "https://www.changiairport.com",
    },
    "hong_kong": {
        "case_name": "Hong Kong Airport City / SKYCITY",
        "aerotropolis": "Hong Kong Airport City / SKYCITY",
        "country": "Hong Kong",
        "is_target": False,
        "airport_name": "Hong Kong International Airport",
        "reference_city": "Hong Kong",
        "official_website": "https://www.hongkongairport.com",
    },
    "frankfurt": {
        "case_name": "Frankfurt Airport City",
        "aerotropolis": "Frankfurt Airport City / Gateway Gardens",
        "country": "Đức",
        "is_target": False,
        "airport_name": "Frankfurt Airport",
        "reference_city": "Frankfurt Rhine-Main",
        "official_website": "https://www.fraport.com",
    },
    "dfw": {
        "case_name": "Dallas–Fort Worth Aerotropolis",
        "aerotropolis": "DFW Aerotropolis / DFW Airport commercial land",
        "country": "Mỹ",
        "is_target": False,
        "airport_name": "Dallas Fort Worth International Airport",
        "reference_city": "Dallas – Fort Worth",
        "official_website": "https://www.dfwairport.com",
    },
    "kuala_lumpur": {
        "case_name": "KLIA Aeropolis",
        "aerotropolis": "KLIA Aeropolis / Airport City Sepang",
        "country": "Malaysia",
        "is_target": False,
        "airport_name": "Kuala Lumpur International Airport",
        "reference_city": "Kuala Lumpur – Sepang",
        "official_website": "https://www.aeropolis.com.my",
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


def field_num(pages, pattern, cast=float, group=1, unit="", conf="high", prefer=None,
              factor=None):
    """`factor` quy đổi đơn vị tại nguồn (vd m²->ha dùng 1e-4, ha->km² dùng 0.01).

    Cần vì nhiều nguồn công bố ở đơn vị khác spec (Incheon ghi ㎡, Taoyuan ghi ha)
    và regex không tự tính được — không quy đổi thì số vào record sai đơn vị.
    """
    m, p = _search(pages, pattern, prefer=prefer)
    if not m:
        return None
    # Bỏ MỌI khoảng trắng (kể cả xuống dòng): nhiều trang render số đếm tách từng
    # chữ số trên các dòng riêng (vd Incheon "7\n0\nMillion Passengers" = 70).
    raw = re.sub(r"[\s,]", "", m.group(group))
    try:
        val = cast(raw)
    except ValueError:
        val = m.group(group)
    if factor is not None and isinstance(val, (int, float)):
        val = round(val * factor, 2)
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


def build_schiphol(pages, rec: dict) -> None:
    """Bộ pattern bám ngôn ngữ schiphol.nl — KHÔNG dùng lại cho case khác."""
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
    rec["logistics_park_name"] = "Schiphol Logistics Park" if rec.get("logistics_park_ha") else None
    rec["trade_park_name"] = "Schiphol Trade Park" if rec.get("trade_park_ha") else None


def build_incheon(pages, rec: dict) -> None:
    """Incheon: hai lõi — Air City do IIAC vận hành + IFEZ ba phân khu.

    Bẫy riêng của airport.kr: trang "At a Glance" render số đếm TÁCH TỪNG CHỮ SỐ
    trên các dòng riêng ("7\\n0\\nMillion Passengers" = 70 triệu). Pattern phải neo
    vào nhãn phía sau và cho phép khoảng trắng bên trong số.
    """
    AAG = "at_a_glance"  # nguồn chuẩn cho chỉ số headline (IIAC công bố)

    # --- Định vị & khái niệm ---
    rec["positioning"] = ({"value": "Airport Economic Zone", "confidence": "high"}
                          if _search(pages, r"Airport Economic Zone")[0] else None)
    rec["planning_concept"] = field_text(pages, r"(A vast economic area where[^.]+\.)")
    rec["cornerstones"] = field_presence(pages, [
        "Business/R&D Hub", "Tourism/Logistics Hub", "Advanced Industry Hub", "Aviation Support Hub"])
    rec["subzones"] = field_presence(pages, [
        "Songdo International City", "Yeongjong International City",
        "Cheongna International City", "Airport Logistics Complex"])

    # --- Quy mô ---
    rec["area_km2"] = field_num(pages, r"total area of ([\d.,]+) square kilometers", unit="km²")
    rec["distance_to_city_km"] = field_num(pages, r"about\s*([\d.,]+)\s*km from central Seoul", unit="km")
    rec["passengers_million"] = field_num(pages, r"(\d[\d.,\s]{0,6}?)\s*Million Passengers",
                                          unit="triệu/năm", prefer=AAG)
    rec["cargo_million_tonnes"] = field_num(pages, r"([\d.,]+)\s*Million Tons",
                                            unit="triệu tấn/năm", prefer=AAG)
    rec["air_movements"] = field_num(pages, r"([\d,]+)\s*Flights\s*Number of flights",
                                     cast=int, unit="lượt/năm", prefer=AAG)
    rec["destinations"] = field_num(pages, r"([\d,]+)\s*Cities\s*Served", cast=int,
                                    unit="thành phố", prefer=AAG)
    rec["airlines"] = field_num(pages, r"([\d,]+)\s*Airlines\s*Serving", cast=int,
                                unit="hãng", prefer=AAG)
    # transfer_pct: nguồn chỉ nêu 38% là HÀNG hoá chuyển tải, không phải khách
    # trung chuyển -> để None thay vì gán nhầm chỉ số.
    rec["transfer_pct"] = None
    rec["airport_area_ha"] = None
    rec["employees"] = None
    rec["num_companies_airport"] = field_num(pages, r"([\d,]+)\s*businesses", cast=int, unit="doanh nghiệp")
    rec["num_companies_realestate"] = field_num(pages, r"Currently,\s*([\d,]+)\s*logistics companies",
                                                cast=int, unit="doanh nghiệp")
    rec["num_office_buildings"] = None
    rec["jobs_created"] = field_num(pages, r"Creation of new jobs\s*\(by \d{4}\)\s*([\d,]+)",
                                    cast=int, unit="việc làm")
    rec["founded_year"] = field_num(pages, r"opened for business on \d+ \w+ (\d{4})",
                                    cast=int, unit="năm", prefer="wikipedia_incheon_international")

    # --- Đặc khu & bối cảnh ---
    rec["economic_zone_name"] = field_text(pages, r"(Incheon Free Economic Zone)\s*\(IFEZ\)")
    rec["economic_zone_year"] = field_num(pages, r"designation in (\d{4}) as Korea.s first free economic zone",
                                          cast=int, unit="năm")
    rec["development_context"] = field_text(pages, r"(Designated as Korea.s first free economic zone in \d{4}[^.]+\.)")
    rec["location_desc"] = field_text(pages, r"(Located just [\d.,]+km away from downtown Incheon[^.]+\.)")
    # Neo vào CÂU giới thiệu, không neo vào tên cơ quan trần — tên đó còn nằm trong
    # menu điều hướng và footer, bắt trúng đó sẽ nuốt cả khối menu (kể cả tiếng Hàn).
    rec["investor_governance"] = field_text(
        pages, r"(The Incheon Free Economic Zone is positioning itself as[^.]+\.)")
    rec["lead_developer"] = field_text(pages, r"(Incheon International Airport Corporation)")

    # --- Sản phẩm / BĐS / tiện ích ---
    rec["commercial_re"] = field_presence(pages, [
        "logistics", "cargo", "MRO", "office", "retail", "hotel", "casino", "resort",
        "GDC", "fulfillment center"])
    rec["residential_product_desc"] = None  # nguồn EN đã crawl không mô tả sản phẩm nhà ở
    rec["basic_amenities"] = field_presence(pages, [
        "Seminar rooms", "sports complex", "fitness center", "business center", "banquet hall"])
    rec["highlight_amenities"] = field_presence(pages, [
        "15,000-seat performance arena", "indoor water park", "foreigner-only casino",
        "largest hotel ballroom in Korea", "digital entertainment street"])
    rec["logistics_park_ha"] = field_num(
        pages, r"([\d,]+) square meters was designated as a Free Trade Area",
        factor=1e-4, unit="ha")
    rec["logistics_park_name"] = "Airport Logistics Complex (Free Trade Area)" if rec["logistics_park_ha"] else None
    rec["trade_park_ha"] = None
    rec["trade_park_name"] = None

    # --- CVP 6 trụ ---
    rec["cvp_product"] = field_presence(pages, [
        "logistics", "MRO", "R&D", "fulfillment center", "industrial complex", "business platform"])
    rec["cvp_price"] = None
    rec["office_rent_eur_m2_year"] = None
    rec["cvp_price_note"] = None
    rec["cvp_service"] = field_presence(pages, [
        "Visa-Free Entry", "English as an Official Language", "Regulatory Free Zone",
        "customs duty deferment", "low rental fees"])
    rec["cvp_experience"] = field_presence(pages, [
        "arena", "water park", "casino", "banquet hall", "fitness center", "resort"])
    rec["cvp_convenience"] = field_collect(pages, [
        r"Located just [\d.,]+km away from downtown Incheon[^.]+\.",
        r"Non-stop between Incheon Int.l Airport and Seoul Station",
    ])
    rec["rail_connections"] = field_collect(pages, [
        r"Airport Railroad Express \(AREX\) takes you[^.]+\.",
        r"\d+ min from Incheon Int.l Airport Terminal 1 to Seoul Station",
    ])
    rec["cvp_brand"] = field_presence(pages, [
        "Incheon International Airport Corporation", "Incheon Free Economic Zone Authority", "INSPIRE"])

    # --- Tầm nhìn & bền vững ---
    rec["vision_label"] = ("Beyond an Airport, Changing the World"
                           if _search(pages, r"Beyond an Airport, Changing the World")[0] else None)
    cv = field_text(pages, r"CORE VALUE\s+(Challenge\s+Cooperation\s+Creativity\s+Integrity)")
    if cv:
        cv["value"] = ["Challenge", "Cooperation", "Creativity", "Integrity"]
    rec["vision_qualities"] = cv
    rec["aviation_policy"] = None
    rec["sustainability"] = field_presence(pages, [
        "RE100", "Green Mobility", "Low-Carbon Eco-Friendly Airport", "renewable energy"])


def build_taoyuan(pages, rec: dict) -> None:
    """Taoyuan: "lòng đỏ" MOTC/CAA (đường băng + FTZ) và "lòng trắng" TP Đào Viên.

    Nguồn số liệu khai thác nằm ở infobox Wikipedia (trang tiac JS-rendered chỉ ra
    bảng rỗng); quy mô & vốn nằm ở Executive Yuan và tycg.gov.tw.
    """
    WIKI_AP = "wikipedia_taoyuan_international"

    # --- Định vị & khái niệm ---
    rec["positioning"] = ({"value": "Aerotropolis", "confidence": "high"}
                          if _search(pages, r"Taoyuan Aerotropolis")[0] else None)
    rec["planning_concept"] = field_text(pages, r"(comprising the .egg yolk zone. managed by[^.]+\.)")
    rec["cornerstones"] = None
    rec["subzones"] = field_presence(pages, [
        "industry zone", "free-trade zone", "commercial zone", "residence zone",
        "Air Cargo Terminal", "International Logistics Center", "Value-Added Park"])

    # --- Quy mô (nguồn ghi ha -> quy đổi km²) ---
    rec["area_km2"] = field_num(pages, r"total urban planning area of ([\d,]+) hectares",
                                factor=0.01, unit="km²")
    rec["distance_to_city_km"] = None
    rec["passengers_million"] = field_num(pages, r"Number of passengers\s*([\d,]+)",
                                          factor=1e-6, unit="triệu/năm", prefer=WIKI_AP)
    rec["cargo_million_tonnes"] = field_num(pages, r"Airfreight movements\s*([\d,]+\.?\d*)\s*tonnes",
                                            factor=1e-6, unit="triệu tấn/năm", prefer=WIKI_AP)
    rec["air_movements"] = field_num(pages, r"Aircraft movements\s*([\d,]+)", cast=int,
                                     unit="lượt/năm", prefer=WIKI_AP)
    rec["destinations"] = None
    rec["airlines"] = None
    rec["transfer_pct"] = None
    rec["airport_area_ha"] = field_num(pages, r"existing ([\d,]+)-hectare Taiwan Taoyuan International Airport",
                                       unit="ha")
    rec["employees"] = None
    rec["num_companies_airport"] = None
    rec["num_companies_realestate"] = field_num(
        pages, r"there are ([\d,]+) Free Trade Zone enterprises", cast=int, unit="doanh nghiệp")
    rec["num_office_buildings"] = None
    rec["jobs_created"] = field_num(pages, r"create over ([\d,]+) jobs", cast=int,
                                    unit="việc làm", prefer="executive_yuan")
    rec["founded_year"] = field_num(pages, r"airport opened for commercial operations in (\d{4})",
                                    cast=int, unit="năm", prefer=WIKI_AP)

    # --- Bối cảnh / đầu tư / quản trị ---
    rec["total_investment_usd"] = field_text(
        pages, r"(Over NT\$[\d,]+ billion \(US\$[\d,]+ billion\))")
    rec["development_context"] = field_text(
        pages, r"(Over NT\$[\d,]+ billion \(US\$[\d,]+ billion\) will be invested in the aerotropolis" + SENT + ")")
    rec["location_desc"] = field_text(pages, r"(The project covers the Dayuan and Luzhu Districts[^.]+\.)")
    rec["investor_governance"] = field_text(
        pages, r"(The Taoyuan Aerotropolis Engineering Office of the Civil Aviation Administration[^.]+\.)")
    rec["lead_developer"] = field_text(pages, r"(Far Glory Aviation Free Trade Zone Co., Ltd\.)")
    rec["economic_zone_name"] = field_text(pages, r"(Taoyuan (?:International Airport|Aviation) Free Trade Zone)")
    rec["economic_zone_year"] = field_num(pages, r"has started to operation on January 1, (\d{4})",
                                          cast=int, unit="năm")

    # --- Sản phẩm / BĐS / tiện ích ---
    rec["commercial_re"] = field_presence(pages, [
        "logistics", "cargo", "free trade zone", "industrial", "commercial", "residential",
        "semiconductor", "warehouse"])
    rec["residential_product_desc"] = None
    rec["basic_amenities"] = field_presence(pages, [
        "bike paths", "park landscapes", "waterfront plazas", "community amenities"])
    rec["highlight_amenities"] = field_presence(pages, [
        "smart streetlights", "common utility tunnels", "retention ponds"])
    rec["logistics_park_ha"] = field_num(pages, r"is ([\d,]+) hectares in area", unit="ha",
                                         prefer="caa_motc")
    rec["logistics_park_name"] = "Taoyuan Aviation Free Trade Zone (Air Cargo Park)" if rec["logistics_park_ha"] else None
    rec["trade_park_ha"] = None
    rec["trade_park_name"] = None

    # --- CVP 6 trụ ---
    rec["cvp_product"] = field_presence(pages, [
        "logistics", "warehouse", "Value-Added Park", "industry zone", "free-trade zone"])
    rec["cvp_price"] = None
    rec["office_rent_eur_m2_year"] = None
    rec["cvp_price_note"] = None
    rec["cvp_service"] = field_presence(pages, [
        "In-Town Check-In", "customs clearance", "duty", "BIM", "GIS", "IoT"])
    rec["cvp_experience"] = field_presence(pages, [
        "recreational corridors", "bike paths", "waterfront plazas", "park"])
    rec["cvp_convenience"] = field_collect(pages, [
        r"From Taipei Main Station to Taiwan Taoyuan International Airport Terminal 1 Station[^.]+\.",
        r"It is only \d+ km from Sun Yat-Sen freeway to the Park",
    ])
    rec["rail_connections"] = field_collect(pages, [
        r"from A1~A12 takes \d+ minutes",
        r"from A1~A12 takes \d+ minutes and from A1~A21 takes \d+ minutes",
    ])
    rec["cvp_brand"] = field_presence(pages, [
        "Taoyuan Aerotropolis", "Far Glory", "AECOM", "Taoyuan Metro"])

    # --- Tầm nhìn & bền vững ---
    rec["vision_label"] = None
    rec["vision_qualities"] = None
    rec["aviation_policy"] = None
    rec["smart_city"] = field_text(pages, r"(The project integrates BIM \(Building Information Modeling\)[^.]+\.)")
    rec["sustainability"] = field_presence(pages, [
        "recycled materials", "circular economy", "carbon emissions", "retention ponds",
        "smart streetlights"])


def build_western_sydney(pages, rec: dict) -> None:
    """Western Sydney: aerotropolis xây từ đất trống, quy hoạch trước khi sân bay chạy.

    Khác hai case kia: chỉ số vận hành gần như chưa có (sân bay mở khách 25/10/2026),
    nên phần lớn KPI khai thác là CÔNG SUẤT THIẾT KẾ, không phải sản lượng thực.
    """
    WIKI_AP = "wikipedia_western_sydney_airport"

    # --- Định vị & khái niệm ---
    rec["positioning"] = ({"value": "Aerotropolis", "confidence": "high"}
                          if _search(pages, r"Western Sydney Aerotropolis")[0] else None)
    rec["planning_concept"] = field_text(pages, r"(The Aerotropolis will create an innovation precinct[^:]+:)")
    rec["cornerstones"] = None
    rec["subzones"] = field_presence(pages, [
        "Aerotropolis Core", "Badgerys Creek", "Wianamatta-South Creek",
        "Northern Gateway", "Agribusiness", "Bradfield City"])

    # --- Quy mô ---
    rec["area_km2"] = field_num(pages, r"([\d,]+) hectares of rezoned land", factor=0.01, unit="km²")
    rec["distance_to_city_km"] = None
    rec["passengers_million"] = field_num(
        pages, r"capacity of up to ([\d,]+) million annual passengers",
        unit="triệu/năm (công suất giai đoạn 1)", prefer=WIKI_AP)
    rec["cargo_million_tonnes"] = field_num(
        pages, r"capacity to deliver ([\d.,]+) million tonnes of air cargo",
        unit="triệu tấn/năm (công suất)")
    rec["air_movements"] = None
    rec["destinations"] = None
    rec["airlines"] = None
    rec["transfer_pct"] = None
    # Neo ngữ nghĩa: trang Wikipedia có 2 con số "… hectares (… acres)" — 1.780 ha là
    # TỔNG diện tích đất đã thu hồi, 1.700 ha mới là diện tích sân bay. Bắt số trần
    # sẽ lấy nhầm số đầu tiên.
    rec["airport_area_ha"] = field_num(pages, r"consists of approximately\s+([\d,]+)\s*hectares",
                                       unit="ha", prefer=WIKI_AP)
    rec["employees"] = None
    rec["num_companies_airport"] = None
    rec["num_companies_realestate"] = None
    rec["num_office_buildings"] = None
    rec["jobs_created"] = field_num(pages, r"expected to create ([\d,]+) jobs", cast=int, unit="việc làm")
    # Sân bay chưa khai thác khách khi crawl -> "năm hình thành" = năm mở cửa đón khách.
    rec["founded_year"] = field_num(
        pages, r"will welcome its first passengers on \d+ \w+ (\d{4})", cast=int, unit="năm")
    rec["urban_build_period"] = field_text(
        pages, r"(Western Sydney to open to passengers on \d+ \w+ and freight on \d+ \w+ \d{4})")

    # --- Bối cảnh / đầu tư / quản trị ---
    # Không nuốt dấu chấm cuối câu: build_html tự thêm "." sau giá trị này.
    rec["total_investment_usd"] = field_text(
        pages, r"(Over \$[\d.,]+ billion investment by the NSW and Commonwealth Governments[^.]*)")
    rec["development_context"] = field_text(
        pages, r"(With over \$[\d.,]+ billion in planned developments[^.]+\.)")
    rec["location_desc"] = field_text(pages, r"(As Australia.s first new city in 100 years[^.]+\.)")
    rec["investor_governance"] = field_text(
        pages, r"(The Bradfield Development Authority is building[^.]+\.)")
    rec["lead_developer"] = field_text(pages, r"(Bradfield Development Authority)")
    rec["airport_build_period"] = field_text(pages, r"(Construction of Stage 1 began on [^.]+\.)")

    # --- Sản phẩm / BĐS / tiện ích ---
    rec["commercial_re"] = field_presence(pages, [
        "advanced manufacturing", "logistics", "agribusiness", "retail", "hotel",
        "university", "cargo", "commercial"])
    rec["residential_product_desc"] = field_text(
        pages, r"(Major Australian infrastructure developer Plenary will deliver the first [\d,]+ homes" + SENT + ")")
    rec["basic_amenities"] = field_presence(pages, [
        "university", "retail", "childcare", "health facilities", "Central Park", "open space"])
    rec["highlight_amenities"] = field_presence(pages, [
        "Advanced Manufacturing Readiness Facility", "Central Park", "Bradfield Metro Station"])
    rec["logistics_park_ha"] = None
    rec["logistics_park_name"] = None
    rec["trade_park_ha"] = None
    rec["trade_park_name"] = None

    # --- CVP 6 trụ ---
    rec["cvp_product"] = field_presence(pages, [
        "advanced manufacturing", "commercial", "residential", "university", "industrial"])
    rec["cvp_price"] = None
    rec["office_rent_eur_m2_year"] = None
    rec["cvp_price_note"] = None
    rec["cvp_service"] = field_presence(pages, [
        "Investor Concierge", "InvestorLink", "Planning referrals", "Special Infrastructure Contributions"])
    rec["cvp_experience"] = field_presence(pages, [
        "Central Park", "open space", "walkable", "cycle"])
    rec["cvp_convenience"] = field_collect(pages, [
        r"Most homes will be within a \d+ metre walk of the Bradfield Metro Station[^.]+\.",
        r"The airport offers 24-hour and curfew-free operations",
    ])
    rec["rail_connections"] = field_collect(pages, [
        r"deliver six new stations between St Marys and the new Bradfield City Centre",
        r"The city-shaping project, from St Marys through to the new airport[^.]+\.",
    ])
    rec["cvp_brand"] = field_presence(pages, [
        "Bradfield Development Authority", "WSA Co", "Investment NSW", "Sydney Metro"])

    # --- Tầm nhìn & bền vững ---
    rec["vision_label"] = None
    rec["vision_qualities"] = None
    rec["aviation_policy"] = None
    rec["sustainability"] = field_presence(pages, [
        "sustainability", "open space", "biodiversity", "blue-green", "net zero"])


def build_dubai_south(pages, rec: dict) -> None:
    """Dubai South: đại đô thị sân bay do nhà nước Dubai làm chủ, chia theo 'district'.

    Trang chính chủ nặng marketing và render bằng JS nên rất ít số; phần lớn KPI
    phải lấy từ trang Wikipedia của Al Maktoum. Số khách là CÔNG SUẤT THIẾT KẾ,
    không phải sản lượng thực — sân bay mới đang mở rộng.
    """
    WIKI_AP = "al_maktoum"
    rec["positioning"] = ({"value": "Airport City / Dubai World Central", "confidence": "high"}
                          if _search(pages, r"Dubai South")[0] else None)
    rec["planning_concept"] = field_text(pages, r"(Dubai South is [^.]{20,}\.)")
    rec["cornerstones"] = field_presence(pages, ["aviation", "logistics", "real estate"])
    rec["subzones"] = field_presence(pages, [
        "Logistics District", "Aviation District", "Business District",
        "Residential District", "Commercial District", "Golf District", "Expo City"])

    rec["area_km2"] = field_num(pages, r"([\d,]+)\s*(?:square kilometres|square kilometers|km2)", unit="km²")
    rec["distance_to_city_km"] = None
    rec["passengers_million"] = field_num(
        pages, r"capacity for up to ([\d,]+) million passengers",
        unit="triệu/năm (công suất thiết kế)", prefer=WIKI_AP)
    rec["cargo_million_tonnes"] = field_num(pages, r"([\d.,]+)\s*million tonnes",
                                            unit="triệu tấn/năm (công suất)", prefer=WIKI_AP)
    rec["air_movements"] = None
    rec["destinations"] = None
    rec["airlines"] = None
    rec["transfer_pct"] = None
    rec["airport_area_ha"] = None
    rec["employees"] = None
    rec["num_companies_airport"] = field_num(
        pages, r"total number of operational businesses to more than ([\d,]+)",
        cast=int, unit="doanh nghiệp")
    rec["num_companies_realestate"] = None
    rec["num_office_buildings"] = None
    rec["jobs_created"] = None
    # "launched in 2025" trong newsroom là tin của năm đó, KHÔNG phải năm thành lập
    # -> neo vào câu mô tả gốc trên Wikipedia.
    rec["founded_year"] = field_num(pages, r"in (\d{4}), planned to be an economic zone",
                                    cast=int, unit="năm", prefer="wikipedia_dubai_south")

    rec["total_investment_usd"] = field_text(
        pages, r"([\d,]+ billion AED \(\$[\d.,]+ billion USD\))")
    rec["development_context"] = field_text(
        pages, r"(During the year, Dubai South welcomed [\d,]+ new companies" + SENT + ")")
    rec["location_desc"] = field_text(pages, r"(The [\d,]+-kilometre Logistics District" + SENT + ")")
    rec["investor_governance"] = None
    rec["lead_developer"] = field_text(pages, r"(Dubai South)")
    rec["economic_zone_name"] = field_text(pages, r"(Dubai South Free Zone|Dubai World Central)")
    rec["economic_zone_year"] = None

    rec["commercial_re"] = field_presence(pages, [
        "logistics", "warehouse", "office", "retail", "aviation", "MRO", "e-commerce", "business centre"])
    rec["residential_product_desc"] = None  # trang Live là marketing JS, không có câu mô tả sản phẩm
    rec["basic_amenities"] = field_presence(pages, [
        "retail", "schools", "parks", "community", "gym", "supermarket"])
    rec["highlight_amenities"] = field_presence(pages, [
        "Expo City", "EZDubai", "Emirates Flight Training Academy", "golf"])
    rec["logistics_park_ha"] = None
    rec["logistics_park_name"] = None
    rec["trade_park_ha"] = None
    rec["trade_park_name"] = None

    rec["cvp_product"] = field_presence(pages, [
        "warehouse", "office", "logistics", "retail", "plots", "business centre"])
    rec["cvp_price"] = None
    rec["office_rent_eur_m2_year"] = None
    rec["cvp_price_note"] = None
    rec["cvp_service"] = field_presence(pages, [
        "business setup", "licence", "free zone", "100% foreign ownership", "one-stop"])
    rec["cvp_experience"] = field_presence(pages, ["Expo City", "retail", "parks", "golf", "community"])
    rec["cvp_convenience"] = field_collect(pages, [
        r"movement of cargo between the seaport and airport in as little as \d+ minutes",
        r"The [\d,]+-kilometre Logistics District features several zones[^.]+\.",
    ])
    rec["rail_connections"] = field_collect(pages, [
        r"Expo Stations on Dubai Metro Route 2020 are now open",
    ])
    rec["cvp_brand"] = field_presence(pages, ["Dubai South", "Emirates", "DP World", "Expo City Dubai"])

    rec["vision_label"] = None
    rec["vision_qualities"] = None
    rec["aviation_policy"] = None
    rec["sustainability"] = field_presence(pages, ["sustainability", "solar", "green", "net zero"])


def build_changi(pages, rec: dict) -> None:
    """Changi: airport city do Changi Airport Group (DNNN) vận hành.

    Nguồn chuẩn cho KPI là thông cáo "chỉ số vận hành" hằng năm (trang 03), không
    phải trang Facts & Figures — trang đó thiên về mô tả nhà ga.
    """
    OPS = "03_changi"  # thông cáo chỉ số vận hành năm gần nhất
    rec["positioning"] = ({"value": "Airport City / Air Hub", "confidence": "high"}
                          if _search(pages, r"air hub")[0] else None)
    rec["planning_concept"] = field_text(pages, r"(The Changi East development[^.]{20,}\.)")
    rec["cornerstones"] = None
    rec["subzones"] = field_presence(pages, [
        "Changi East", "Terminal 5", "Jewel", "Changi Business Park", "Changi Airfreight Centre"])

    # Trang Changi East đã crawl KHÔNG nêu diện tích 1.080 ha; pattern "…hectare" trần
    # bắt nhầm con số khác trên trang khác -> để None (không bịa).
    rec["area_km2"] = None
    rec["distance_to_city_km"] = None
    rec["passengers_million"] = field_num(pages, r"([\d.,]+) million passenger movements",
                                          unit="triệu/năm", prefer=OPS)
    rec["cargo_million_tonnes"] = field_num(
        pages, r"Airfreight throughput totalled ([\d.,]+) million tonnes",
        unit="triệu tấn/năm", prefer=OPS)
    rec["air_movements"] = field_num(pages, r"to ([\d,]+) movements", cast=int,
                                     unit="lượt/năm", prefer=OPS)
    rec["destinations"] = field_num(pages, r"over ([\d,]+) cities in \d+ countries", cast=int,
                                    unit="thành phố", prefer=OPS)
    rec["airlines"] = field_num(pages, r"some ([\d,]+) airlines operate", cast=int,
                                unit="hãng", prefer=OPS)
    rec["transfer_pct"] = None
    rec["airport_area_ha"] = None
    rec["employees"] = None
    rec["num_companies_airport"] = None
    rec["num_companies_realestate"] = None
    rec["num_office_buildings"] = None
    rec["jobs_created"] = None
    rec["founded_year"] = field_num(pages, r"officially commenced operations in (\d{4})",
                                    cast=int, unit="năm", prefer="our_story")

    rec["total_investment_usd"] = None
    rec["development_context"] = field_text(
        pages, r"(Passenger traffic at (?:Singapore )?Changi Airport was an all-time high" + SENT + ")")
    rec["location_desc"] = None
    rec["investor_governance"] = field_text(pages, r"(Changi Airport Group \(CAG\)[^.]{20,}\.)")
    rec["lead_developer"] = field_text(pages, r"(Changi Airport Group)")
    rec["economic_zone_name"] = None
    rec["economic_zone_year"] = None

    rec["commercial_re"] = field_presence(pages, [
        "retail", "dining", "office", "business park", "hotel", "cargo", "logistics", "MRO"])
    rec["residential_product_desc"] = None
    rec["basic_amenities"] = field_presence(pages, [
        "retail", "dining", "gardens", "lounge", "cinema", "swimming pool", "playground"])
    rec["highlight_amenities"] = field_presence(pages, [
        "Rain Vortex", "Forest Valley", "Canopy Park", "Jewel", "Changi Experience Studio"])
    rec["logistics_park_ha"] = None
    rec["logistics_park_name"] = None
    rec["trade_park_ha"] = None
    rec["trade_park_name"] = None

    rec["cvp_product"] = field_presence(pages, [
        "office", "business park", "retail", "cargo", "logistics", "industrial"])
    rec["cvp_price"] = None
    rec["office_rent_eur_m2_year"] = None
    rec["cvp_price_note"] = None
    rec["cvp_service"] = field_presence(pages, [
        "transit", "lounge", "free tour", "baggage", "concierge"])
    rec["cvp_experience"] = field_presence(pages, [
        "Rain Vortex", "Canopy Park", "gardens", "cinema", "retail", "dining"])
    rec["cvp_convenience"] = field_collect(pages, [
        r"some [\d,]+ airlines operate more than [\d,]+ weekly scheduled flights[^.]+\.",
        r"connecting Singapore to over [\d,]+ cities in \d+ countries[^.]*\.",
    ])
    rec["rail_connections"] = field_collect(pages, [
        r"East West Line[^.]{10,}\.",
        r"Thomson[- ]East Coast Line[^.]{10,}\.",
    ])
    rec["cvp_brand"] = field_presence(pages, ["Changi Airport Group", "Jewel", "JTC", "CapitaLand"])

    rec["vision_label"] = None
    rec["vision_qualities"] = None
    rec["aviation_policy"] = None
    rec["sustainability"] = field_presence(pages, [
        "sustainability", "solar", "carbon", "green", "net zero"])


def _blank(rec: dict) -> None:
    """Đặt None cho mọi trường của spec — builder chỉ cần gán trường thật sự có nguồn.

    Có hàm này vì `split_value_provenance` và benchmark CSV cần bộ cột ổn định giữa
    các case; thiếu khoá thì cột lệch nhau giữa các dòng jsonl.
    """
    for k in ("positioning planning_concept cornerstones subzones area_km2 distance_to_city_km "
              "passengers_million cargo_million_tonnes air_movements destinations airlines "
              "transfer_pct airport_area_ha employees num_companies_airport "
              "num_companies_realestate num_office_buildings jobs_created founded_year "
              "total_investment_usd development_context location_desc investor_governance "
              "lead_developer economic_zone_name economic_zone_year commercial_re "
              "residential_product_desc basic_amenities highlight_amenities logistics_park_ha "
              "logistics_park_name trade_park_ha trade_park_name cvp_product cvp_price "
              "office_rent_eur_m2_year cvp_price_note cvp_service cvp_experience "
              "cvp_convenience rail_connections cvp_brand vision_label vision_qualities "
              "aviation_policy sustainability smart_city airport_build_period "
              "urban_build_period brand_partners connection_modes metro_lines "
              "airport_privilege experience_desc price_vs_reference sales_scheme").split():
        rec.setdefault(k, None)


def build_hong_kong(pages, rec: dict) -> None:
    """Hong Kong: AAHK vừa vận hành sân bay vừa là chủ đầu tư BĐS trên đảo Chek Lap Kok.

    Lưu ý nguồn: trang Facts & Figures của AAHK ghi rõ "*2019 figures" — đây là số
    trước COVID, KHÔNG phải sản lượng hiện tại. Đơn vị ghi kèm để không hiểu nhầm.
    """
    FF = "facts_figures"
    rec["positioning"] = ({"value": "Airport City / SKYCITY", "confidence": "high"}
                          if _search(pages, r"Airport City")[0] else None)
    rec["planning_concept"] = None  # cụm "Airport City" chỉ xuất hiện trong menu điều hướng
    rec["subzones"] = field_presence(pages, [
        "SKYCITY", "AsiaWorld-Expo", "11 SKIES", "SkyPier", "Tung Chung", "Cathay City"])
    rec["passengers_million"] = field_num(pages, r"([\d.,]+)\s*million\s*passengers handled",
                                          unit="triệu/năm (số 2019)", prefer=FF)
    rec["cargo_million_tonnes"] = field_num(
        pages, r"([\d.,]+)\s*million\s*tonnes of cargo and airmail",
        unit="triệu tấn/năm (số 2019)", prefer=FF)
    rec["air_movements"] = field_num(pages, r"([\d,]+)\s*air\s*traffic\s*movements", cast=int,
                                     unit="lượt/năm (số 2019)", prefer=FF)
    rec["destinations"] = field_num(pages, r"over\s*([\d,]+)\s*destinations worldwide", cast=int,
                                    unit="điểm đến", prefer=FF)
    rec["airlines"] = field_num(pages, r"destinations worldwide by around ([\d,]+) airlines",
                                cast=int, unit="hãng", prefer=FF)
    rec["founded_year"] = field_num(pages, r"opened (?:in|on)\D{0,14}(\d{4})", cast=int,
                                    unit="năm", prefer="wikipedia_hong_kong")
    rec["total_investment_usd"] = field_text(pages, r"(HK\$[\d.,]+ billion)")
    rec["investor_governance"] = field_text(pages, r"(Airport Authority Hong Kong[^.]{25,}\.)")
    rec["lead_developer"] = field_text(pages, r"(Airport Authority Hong Kong)")
    rec["commercial_re"] = field_presence(pages, [
        "retail", "dining", "hotel", "office", "cargo", "logistics", "exhibition", "entertainment"])
    rec["basic_amenities"] = field_presence(pages, ["retail", "dining", "hotel", "shopping"])
    rec["highlight_amenities"] = field_presence(pages, [
        "SKYCITY", "AsiaWorld-Expo", "11 SKIES", "arena"])
    rec["cvp_product"] = field_presence(pages, ["retail", "office", "hotel", "cargo", "exhibition"])
    rec["cvp_experience"] = field_presence(pages, ["retail", "dining", "entertainment", "exhibition"])
    rec["cvp_convenience"] = field_collect(pages, [
        r"SkyPier[^.]{20,}\.",
        r"Hong Kong[–-]Zhuhai[–-]Macau Bridge[^.]{15,}\.",
    ])
    rec["rail_connections"] = field_collect(pages, [
        r"Tung Chung line[^.]{15,}\.",
        r"Airport Express[^.]{15,}\.",
    ])
    rec["cvp_brand"] = field_presence(pages, [
        "Airport Authority Hong Kong", "Cathay Pacific", "AsiaWorld-Expo"])
    rec["sustainability"] = field_presence(pages, ["carbon", "sustainability", "green", "net zero"])


def build_frankfurt(pages, rec: dict) -> None:
    """Frankfurt: Fraport AG vừa vận hành sân bay vừa phát triển BĐS.

    `area_km2` ở đây là quy mô LÕI VĂN PHÒNG Gateway Gardens (~35 ha), không phải
    toàn sân bay — case này không có ranh giới "đô thị sân bay" thống nhất.
    """
    TR = "s_li_u_v_n_t_i"  # thông cáo số liệu cả năm
    rec["positioning"] = ({"value": "Airport City", "confidence": "high"}
                          if _search(pages, r"Airport City")[0] else None)
    rec["planning_concept"] = field_text(pages, r"(Gateway Gardens is[^.]{25,}\.)")
    rec["subzones"] = field_presence(pages, [
        "Gateway Gardens", "The Squaire", "CargoCity Süd", "Terminal 3", "Airport City"])
    rec["area_km2"] = field_num(pages, r"surface area of around ([\d,]+) hectares",
                                factor=0.01, unit="km² (khu Gateway Gardens)")
    rec["passengers_million"] = field_num(
        pages, r"welcomed (?:around|approximately) ([\d.,]+) million passengers",
        unit="triệu/năm", prefer=TR)
    rec["cargo_million_tonnes"] = field_num(pages, r"to around ([\d.,]+) million metric tons",
                                            unit="triệu tấn/năm", prefer=TR)
    rec["airlines"] = field_num(pages, r"a total of ([\d,]+) airlines served", cast=int,
                                unit="hãng", prefer=TR)
    rec["destinations"] = field_num(pages, r"airlines served ([\d,]+) destinations", cast=int,
                                    unit="điểm đến", prefer=TR)
    rec["founded_year"] = field_num(pages, r"first construction phase of Gateway Gardens was inaugurated on \d+ \w+ (\d{4})",
                                    cast=int, unit="năm (giai đoạn 1 Gateway Gardens)")
    rec["investor_governance"] = field_text(pages, r"(Gateway Gardens is a joint project[^.]{20,}\.)")
    rec["lead_developer"] = field_text(pages, r"(Fraport AG)")
    rec["development_context"] = field_text(pages, r"(Frankfurt Airport \(FRA\) welcomed[^.]{20,}\.)")
    rec["commercial_re"] = field_presence(pages, [
        "office", "hotel", "conference", "logistics", "retail", "warehouse", "real estate"])
    rec["basic_amenities"] = field_presence(pages, [
        "restaurants", "hotels", "park", "conference", "cafés", "shopping"])
    rec["highlight_amenities"] = field_presence(pages, ["The Squaire", "Gateway Gardens", "Hyatt Place"])
    rec["cvp_product"] = field_presence(pages, ["office", "logistics", "hotel", "retail", "real estate"])
    rec["cvp_service"] = field_presence(pages, ["energy", "facility management", "leasing", "property management"])
    rec["cvp_experience"] = field_presence(pages, ["restaurants", "hotels", "park", "shopping"])
    rec["cvp_convenience"] = field_collect(pages, [
        r"Frankfurter Kreuz[^.]{15,}\.",
        r"long[- ]distance station[^.]{15,}\.",
    ])
    rec["rail_connections"] = field_collect(pages, [
        r"S-Bahn[^.]{15,}\.",
        r"ICE \d[^.]{10,}\.",
    ])
    rec["cvp_brand"] = field_presence(pages, ["Fraport", "Lufthansa", "Groß & Partner", "OFB"])
    rec["sustainability"] = field_presence(pages, [
        "carbon", "climate", "sustainability", "renewable", "noise"])


def build_dfw(pages, rec: dict) -> None:
    """DFW: sân bay là pháp nhân sở hữu quỹ đất và tự cho thuê phát triển thương mại.

    Nguồn Mỹ dùng ACRE — phải quy đổi sang ha bằng `factor` (1 acre = 0,404686 ha),
    không quy đổi thì `airport_area_ha` sai gấp ~2,5 lần.
    """
    FACTS = "facts_figures"
    rec["positioning"] = ({"value": "Aerotropolis", "confidence": "high"}
                          if _search(pages, r"[Aa]erotropolis")[0] else None)
    rec["planning_concept"] = None  # cụm "commercial development" chỉ có trong menu điều hướng
    rec["subzones"] = field_presence(pages, [
        "Beltline Station District", "Passport Park", "Cargo", "Southgate Plaza", "Founders Plaza"])
    rec["airport_area_ha"] = field_num(pages, r"Real property consists of ([\d,]+) acres",
                                       factor=0.404686, unit="ha", prefer=FACTS)
    rec["passengers_million"] = field_num(pages, r"more than ([\d,]+) million customers",
                                          unit="triệu/năm", prefer=FACTS)
    rec["airlines"] = field_num(pages, r"([\d,]+) passenger airlines", cast=int, unit="hãng")
    rec["jobs_created"] = field_num(pages, r"([\d,]+) jobs supported", cast=int, unit="việc làm")
    rec["founded_year"] = field_num(pages, r"became operational for its first time on[^,]+, (\d{4})",
                                    cast=int, unit="năm", prefer=FACTS)
    rec["development_context"] = field_text(
        pages, r"(DFW Airport[^.]{0,40}\$[\d.,]+ billion[^.]{10,}\.)")
    rec["total_investment_usd"] = field_text(pages, r"(\$[\d.,]+ billion in total economic impact)")
    rec["investor_governance"] = None  # chỉ khớp infobox Wikipedia, không phải câu văn
    rec["lead_developer"] = field_text(pages, r"(Dallas Fort Worth International Airport)")
    rec["commercial_re"] = field_presence(pages, [
        "office", "retail", "hotel", "logistics", "industrial", "flex", "warehouse", "showroom"])
    rec["basic_amenities"] = field_presence(pages, ["retail", "hotel", "golf", "restaurants"])
    rec["highlight_amenities"] = field_presence(pages, [
        "Grapevine Mills", "Founders Plaza", "golf course", "Beltline Station District"])
    rec["cvp_product"] = field_presence(pages, [
        "office", "retail", "logistics", "industrial", "flex", "land lease"])
    rec["cvp_service"] = field_presence(pages, [
        "lease", "property management", "ground lease", "tenant"])
    rec["cvp_experience"] = field_presence(pages, ["retail", "hotel", "golf", "restaurants"])
    rec["cvp_convenience"] = field_collect(pages, [
        r"([\d,]+) domestic and [\d,]+ international nonstop destinations[^.]*\.",
        r"third-busiest airport in the world[^.]{10,}\.",
    ])
    rec["rail_connections"] = field_collect(pages, [
        r"Orange Line[^.]{15,}\.",
        r"TEXRail[^.]{15,}\.",
    ])
    rec["cvp_brand"] = field_presence(pages, ["American Airlines", "DFW Airport", "DART", "TEXRail"])
    rec["sustainability"] = field_presence(pages, ["carbon", "net zero", "sustainability", "renewable"])


def build_kuala_lumpur(pages, rec: dict) -> None:
    """KLIA Aeropolis: MAHB phát triển theo BA CỤM chức năng, không theo phân khu địa lý.

    Khác các case khác: "cluster" là trục tổ chức chính, nên đọc vào `cornerstones`
    chứ không phải `subzones`.
    """
    WIKI_AP = "wikipedia_kuala_lumpur"
    rec["positioning"] = ({"value": "Airport City of the 21st Century", "confidence": "high"}
                          if _search(pages, r"Airport City of the 21st Century")[0] else None)
    rec["planning_concept"] = field_text(pages, r"(The development spans across [\d,]+ sq km[^.]{10,}\.)")
    rec["cornerstones"] = field_presence(pages, [
        "Air Cargo and Logistics", "Air Cargo & Logistics", "Aerospace and Aviation",
        "Aerospace & Aviation", "MICE and Leisure", "MICE & Leisure"])
    rec["subzones"] = field_presence(pages, [
        "Aerospace Park", "Digital Free Trade Zone", "Gateway@klia2", "klia2", "Air Cargo"])
    rec["area_km2"] = field_num(pages, r"spans across ([\d,]+) sq km", unit="km²")
    # Neo vào nhãn infobox "Passengers" ĐỨNG TRƯỚC số; bắt "([\d,]+) Passengers" sẽ
    # nuốt nhầm "1500 passengers" trong một câu mô tả khác trên cùng trang.
    rec["passengers_million"] = field_num(pages, r"Passengers\s*([\d,]{7,})",
                                          factor=1e-6, unit="triệu/năm", prefer=WIKI_AP)
    rec["air_movements"] = field_num(pages, r"Aircraft movements\s*([\d,]+)", cast=int,
                                     unit="lượt/năm", prefer=WIKI_AP)
    rec["cargo_million_tonnes"] = field_num(pages, r"Cargo \(tonnes\)\s*([\d,]+)",
                                            factor=1e-6, unit="triệu tấn/năm", prefer=WIKI_AP)
    rec["founded_year"] = field_num(pages, r"Main Terminal Building[^)]*\)\s*\d+ \w+ (\d{4})",
                                    cast=int, unit="năm", prefer=WIKI_AP)
    rec["investor_governance"] = None  # trang MAHB là danh sách tin, không có câu mô tả quản trị
    rec["lead_developer"] = field_text(pages, r"(Malaysia Airports Holdings Berhad|Malaysia Airports)")
    rec["economic_zone_name"] = field_text(pages, r"(Digital Free Trade Zone)")
    rec["commercial_re"] = field_presence(pages, [
        "cargo", "logistics", "aerospace", "MRO", "retail", "hotel", "industrial", "warehouse"])
    rec["basic_amenities"] = field_presence(pages, ["retail", "hotel", "convention", "arena"])
    rec["highlight_amenities"] = field_presence(pages, [
        "Aerospace Park", "ASEAN pavilion", "indoor arena", "convention centre",
        "Sepang International Circuit"])
    rec["cvp_product"] = field_presence(pages, [
        "cargo", "logistics", "aerospace", "MRO", "industrial", "warehouse"])
    rec["cvp_service"] = field_presence(pages, ["free trade zone", "customs", "e-commerce", "fulfilment"])
    rec["cvp_experience"] = field_presence(pages, ["MICE", "convention", "arena", "retail", "leisure"])
    rec["cvp_convenience"] = field_collect(pages, [
        r"KLIA Ekspres[^.]{15,}\.",
        r"air, sea and land connectivity[^.]*\.",
    ])
    rec["rail_connections"] = field_collect(pages, [
        r"KL Sentral[^.]{15,}\.",
        r"Express Rail Link[^.]{15,}\.",
    ])
    rec["cvp_brand"] = field_presence(pages, [
        "Malaysia Airports", "Alibaba", "Khazanah", "AirAsia"])
    rec["sustainability"] = field_presence(pages, ["sustainability", "green", "carbon", "solar"])


CASE_BUILDERS = {
    "schiphol": build_schiphol,
    "incheon": build_incheon,
    "taoyuan": build_taoyuan,
    "western_sydney": build_western_sydney,
    "dubai_south": build_dubai_south,
    "changi": build_changi,
    "hong_kong": build_hong_kong,
    "frankfurt": build_frankfurt,
    "dfw": build_dfw,
    "kuala_lumpur": build_kuala_lumpur,
}


def extract(name: str) -> dict:
    pages = load_pages(name)
    ident = REGISTRY.get(name, {"case_name": name})
    rec: dict = dict(ident)
    builder = CASE_BUILDERS.get(name)
    if builder is None:
        raise SystemExit(
            f"Chưa có bộ pattern cho case '{name}'.\n"
            f"Pha 3-4 của SKILL.md: thêm entry REGISTRY['{name}'] và hàm build_{name}() "
            f"vào CASE_BUILDERS (pattern phải bám ngôn ngữ website của case đó).")
    builder(pages, rec)
    _blank(rec)          # bù các trường builder không gán -> bộ cột ổn định giữa case
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
