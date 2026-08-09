"""Thu ảnh minh hoạ cho trang hồ sơ của 1 aerotropolis.

Với mỗi MỤC trình bày, lấy ảnh đại diện (og:image, fallback ảnh lớn đầu tiên) từ
trang đã crawl tương ứng -> tải -> nén/resize -> lưu html/assets/<case>/<mục>.jpg
và ghi images.json (mục -> file, source_image, page_url, caption).

build_html.py sẽ đọc images.json và nhúng ảnh (base64) vào đúng mục.

Chạy:
    python html/harvest_images.py --name schiphol
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
from pathlib import Path

import requests
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from PIL import Image

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}

# Mục trình bày -> (slug trang nguồn, caption[, want]).
#   want = chuỗi con của URL/alt để chỉ ĐÚNG ảnh cần lấy.
# Bỏ trống `want` sẽ rơi về og:image — gần như luôn là ảnh thương hiệu chung, SAI
# ngữ cảnh mục. Chạy `--inspect` để xem ứng viên thật trước khi điền.
CURATION = {
    "schiphol": [
        ("hero",       "03_schiphol_business_district",        "Khu Thương mại Schiphol (Business District)"),
        ("planning",   "17_sadc_schiphol_logistics_park",      "Ảnh trên không khu hậu cần Schiphol Logistics Park"),
        ("vision",     "29_schiphol_airport_of_the_future",    "Định hướng 'Sân bay của tương lai'"),
        ("experience", "08_schiphol_real_estate_facilities",   "Tiện ích & không gian trải nghiệm tại Schiphol"),
    ],
    "incheon": [
        ("hero",       "08_incheon_airport_esg_management",                    "Nhà ga hành khách sân bay quốc tế Incheon", "esg-intro-strategy1"),
        ("planning",   "01_incheon_airport_development_of_a_complex_city_air_", "Bản đồ quy hoạch Air City: các phân khu IBC-I/II/III, MRO, logistics, sân golf", "complex-city-view1"),
        ("vision",     "01_incheon_airport_development_of_a_complex_city_air_", "Phối cảnh phân khu IBC-III — giai đoạn phát triển tương lai", "complex-city-view3"),
        ("experience", "17_inspire_entertainment_resort_visitkorea",           "Tổ hợp giải trí INSPIRE trên đảo Yeongjong (nằm trong IBC-III)", "3073488_image2"),
    ],
    "taoyuan": [
        ("hero",       "15_aecom_taoyuan_aerotropolis_development",            "Toàn cảnh sân bay Đào Viên và vùng đô thị sân bay bao quanh", "taoyuan-aerotropolis-1-1"),
        ("planning",   "15_aecom_taoyuan_aerotropolis_development",            "Ranh giới quy hoạch Taoyuan Aerotropolis (4.564 ha) trên nền ảnh thực địa", "taoyuan-aerotropolis-2-new"),
        ("vision",     "02_taoyuan_city_gov_sdgs_aerotropolis_development_pro", "Hồ điều tiết phòng chống thiên tai — 5/12 hồ, sức chứa 1,47 triệu tấn nước", "Disaster Prevention Retention Basin 1"),
        ("experience", "12_taoyuan_tourism_ch_nh_quy_n_tp_airport_mrt",        "Sơ đồ tuyến MRT sân bay A1–A21 với dịch vụ check-in nội đô", "metro_pic"),
    ],
    "western_sydney": [
        ("hero",       "06_bradfield_city_what_is_bradfield_city",             "Toàn cảnh Bradfield City — lõi đô thị của Western Sydney Aerotropolis", "about-bradfield-city-h"),
        ("planning",   "07_bradfield_city_trang_ch_nh",                        "Bản đồ phân khu Bradfield City: Enterprise, AMRF, Central Park, University, Commercial", "city%20spaces%20map"),
        ("vision",     "05_nsw_gov_delivering_bradfield_city",                 "Phối cảnh Bradfield City theo Master Plan duyệt 9/2024", "BDA-artist-impres"),
        ("experience", "06_bradfield_city_what_is_bradfield_city",             "Không gian mở và tiện ích công cộng — 1/3 diện tích thành phố", "Food-and-Beverage-venu"),
    ],
    "dubai_south": [
        ("hero",       "01_dubai_south_trang_ch_ch_nh_th_c",                   "Hệ sinh thái hàng không Dubai South bao quanh sân bay Al Maktoum", "Home_4_Home_Page_slider_1"),
        ("planning",   "04_dubai_south_mbr_aerospace_hub",                     "Sơ đồ quy hoạch khu hàng không MBR Aerospace Hub", "Master_Plan"),
        ("vision",     "01_dubai_south_trang_ch_ch_nh_th_c",                   "Tầm nhìn dài hạn dẫn dắt quá trình phát triển Dubai South", "Home_5_Home_Page_slider_1B"),
        ("experience", "07_dubai_south_live_khu_d_n_c",                        "Khu dân cư ven nước The Pulse Beachfront", "The_Pulse_BeachFrount"),
    ],
    "changi": [
        ("hero",       "07_changi_fact_sheet_terminal_5",                      "Phối cảnh trên không Nhà ga T5 và khu Changi East", "terminal-5-aerial"),
        ("planning",   "06_changi_future_developments",                        "Sơ đồ mặt bằng khu phát triển Changi East", "site-plan"),
        ("vision",     "06_changi_future_developments",                        "Nhà ga T5 — bước mở rộng công suất lên 135 triệu khách/năm", "terminal-5:"),
        ("experience", "08_changi_fact_sheet_jewel",                           "Forest Valley trong Jewel Changi Airport", "forest valley"),
    ],
    "hong_kong": [
        ("hero",       "03_hkia_three_runway_system_t_ng_quan_d_n",            "Toàn cảnh hệ ba đường băng trên đảo Chek Lap Kok", "third-runway-panorama"),
        ("planning",   "03_hkia_three_runway_system_t_ng_quan_d_n",            "Sơ đồ hệ ba đường băng và mặt bằng mở rộng sân bay", "3rs_map_en"),
        ("vision",     "02_hkia_vision_mission_airport_authority",             "Tầm nhìn & sứ mệnh của Airport Authority Hong Kong", "vision_and_mission"),
        ("experience", "05_asiaworld_expo_skycity",                            "SKYCITY — lõi thương mại & giải trí nối thẳng AsiaWorld-Expo", "1600x650-skycity"),
    ],
    "frankfurt": [
        ("hero",       "06_skylineatlas_gateway_gardens",                      "Toàn cảnh khu văn phòng Gateway Gardens cạnh sân bay Frankfurt", "gateway-gardens-frankfurt"),
        ("planning",   "05_gateway_gardens_trang_ch_nh_th_c_khu",              "Khu Gateway Gardens (~35 ha) giữa sân bay Frankfurt và nút giao Frankfurter Kreuz", "main-slider/0"),
        ("vision",     "12_fraport_sustainability",                            "Định hướng phát triển bền vững của Fraport", "AM_05_2022"),
        ("experience", "05_gateway_gardens_trang_ch_nh_th_c_khu",              "Không gian làm việc, khách sạn và tiện ích trong Gateway Gardens", "pages/main/3"),
    ],
    "dfw": [
        ("hero",       "05_dfw_nghi_n_c_u_t_c_ng_kinh_t_78_3_t_usd",           "Sân bay DFW về đêm — cửa ngõ hàng không của vùng Bắc Texas", "Roadway_Terminal_D_Night"),
        ("planning",   "07_wikipedia_dallas_fort_worth_international_airport",  "Sơ đồ mặt bằng sân bay DFW (FAA airport diagram) — 5 nhà ga, 7 đường băng", "FAA airport diagram"),
        ("vision",     "07_wikipedia_dallas_fort_worth_international_airport",  "Ảnh trên không DFW — quỹ đất 17.183 acre lớn hơn Manhattan", "aerial photograph of DFW"),
        ("experience", "07_wikipedia_dallas_fort_worth_international_airport",  "Không gian bán lẻ & ẩm thực trong nhà ga DFW", "Gate C35"),
    ],
    "kuala_lumpur": [
        ("hero",       "01_klia_aeropolis_trang_ch_nh_th_c",                   "KLIA Aeropolis — đô thị sân bay thế kỷ 21 quanh KLIA", "bnr-aeropolis-01"),
        ("planning",   "01_klia_aeropolis_trang_ch_nh_th_c",                   "Sơ đồ vị trí và phạm vi 100 km² của KLIA Aeropolis", "klia-map"),
        ("vision",     "04_klia_aeropolis_aerospace_park",                     "Aerospace Park — cụm hàng không vũ trụ và MRO", "header-Aerospace"),
        ("experience", "05_klia_aeropolis_c_m_mice_leisure",                   "Cụm MICE & Leisure: hội nghị, arena, du lịch sự kiện", "mice-overview"),
    ],
}


def page_url_map(case_dir: Path) -> dict:
    man = case_dir / "manifest.json"
    if not man.exists():
        return {}
    data = json.loads(man.read_text(encoding="utf-8"))
    out = {}
    for s in data.get("sources", []):
        out[s.get("slug", "")] = s.get("url", "")
    return out


def pick_image_url(html_path: Path, page_url: str = "") -> str | None:
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8", errors="ignore"), "html.parser")

    def absolutise(u: str) -> str:
        """Nhiều site trả og:image / src dạng '/path/x.jpg' hoặc './x.jpg'.

        requests không nuốt URL thiếu scheme -> phải ghép với URL trang gốc, nếu
        không sẽ mất ảnh của mọi nguồn dùng đường dẫn tương đối (nsw.gov.au,
        taoyuan-metro…).
        """
        return urljoin(page_url, u) if page_url else u

    og = soup.find("meta", attrs={"property": "og:image"})
    if og and og.get("content"):
        return absolutise(og["content"].strip())
    for i in soup.find_all("img"):
        u = (i.get("src") or i.get("data-src") or "").strip()
        if u and any(e in u.lower() for e in (".jpg", ".jpeg", ".png", ".webp")) \
           and not any(x in u.lower() for x in ("icon", "logo", "sprite", "favicon")):
            return absolutise(u)
    return None


# Từ khoá nhận diện ảnh HỢP NGỮ CẢNH cho từng mục trình bày. Dùng để xếp hạng ứng
# viên ở chế độ --inspect; người curate vẫn là người chốt.
SECTION_HINTS = {
    "hero":       ["aerial", "skyline", "panorama", "overview", "birdseye", "bird-eye",
                   "cityscape", "airport", "toancanh", "空拍", "全景"],
    "planning":   ["masterplan", "master-plan", "master_plan", "zoning", "zone", "precinct",
                   "landuse", "land-use", "map", "plan", "layout", "district", "phankhu",
                   "quyhoach", "規劃", "分區", "地圖"],
    "vision":     ["vision", "future", "render", "concept", "impression", "proposed",
                   "artist", "2050", "2030", "tamnhin", "願景"],
    "experience": ["amenity", "facility", "park", "plaza", "retail", "resort", "leisure",
                   "lifestyle", "community", "interior", "terminal", "station", "tiennich"],
}
JUNK = ("icon", "logo", "sprite", "favicon", "avatar", "placeholder", "blank",
        "spacer", "banner-ad", "share", "btn", "button", "arrow", "menu")


def _px(v) -> int:
    try:
        return int(str(v).strip().replace("px", ""))
    except (TypeError, ValueError):
        return 0


def image_candidates(html_path: Path, page_url: str = "") -> list[dict]:
    """Kiểm kê MỌI ảnh của trang kèm tín hiệu để chọn: alt, kích thước, chữ quanh ảnh.

    Có hàm này vì `og:image` gần như luôn là ảnh chia sẻ mạng xã hội (ảnh thương
    hiệu chung), không phải ảnh minh hoạ đúng mục — vd bản đồ phân khu cho mục
    "Quy hoạch & phân khu". Curate phải nhìn danh sách thật rồi mới chọn.
    """
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8", errors="ignore"), "html.parser")
    absol = (lambda u: urljoin(page_url, u)) if page_url else (lambda u: u)
    out: list[dict] = []
    seen: set[str] = set()

    og = soup.find("meta", attrs={"property": "og:image"})
    if og and og.get("content"):
        u = absol(og["content"].strip())
        seen.add(u)
        out.append({"url": u, "alt": "(og:image — ảnh chia sẻ MXH)", "w": 0, "h": 0,
                    "near": "", "is_og": True})

    for i in soup.find_all("img"):
        u = (i.get("src") or i.get("data-src") or i.get("data-original") or "").strip()
        if not u or u.startswith("data:"):
            continue
        u = absol(u)
        if u in seen:
            continue
        seen.add(u)
        # chữ quanh ảnh: figcaption gần nhất, hoặc text của thẻ cha
        near = ""
        fig = i.find_parent("figure")
        if fig and fig.find("figcaption"):
            near = fig.find("figcaption").get_text(" ", strip=True)
        elif i.parent:
            near = i.parent.get_text(" ", strip=True)
        out.append({"url": u, "alt": (i.get("alt") or "").strip(),
                    "w": _px(i.get("width")), "h": _px(i.get("height")),
                    "near": " ".join(near.split())[:110], "is_og": False})
    return out


def score_candidate(c: dict, section: str) -> int:
    """Điểm ưu tiên: khớp từ khoá mục > có alt/caption > không phải ảnh giao diện."""
    hay = f"{c['url']} {c['alt']} {c['near']}".lower()
    s = 0
    for kw in SECTION_HINTS.get(section, []):
        if kw in hay:
            s += 10
    if any(j in c["url"].lower() for j in JUNK):
        s -= 25
    if c["alt"] or c["near"]:
        s += 3
    if c["is_og"]:
        s -= 2          # og:image là phương án chót, không phải phương án đầu
    if max(c["w"], c["h"]) >= 600:
        s += 4
    if 0 < max(c["w"], c["h"]) < 150:
        s -= 12
    if c["url"].lower().endswith(".svg"):
        s -= 8
    return s


def inspect_case(name: str, section_filter: str | None = None) -> None:
    """In bảng ứng viên ảnh cho từng mục — chạy TRƯỚC khi viết CURATION."""
    case_dir = ROOT / "raw_data" / "output" / "ws1_airport" / "raw" / name
    urls = page_url_map(case_dir)
    pages = sorted((case_dir / "pages").glob("*.html"))
    for section in (["hero", "planning", "vision", "experience"]
                    if not section_filter else [section_filter]):
        print(f"\n{'='*78}\nMỤC: {section}   (từ khoá: {', '.join(SECTION_HINTS[section][:6])}…)\n{'='*78}")
        ranked = []
        for p in pages:
            for c in image_candidates(p, urls.get(p.stem, "")):
                sc = score_candidate(c, section)
                if sc > 0:
                    ranked.append((sc, p.stem, c))
        ranked.sort(key=lambda x: -x[0])
        if not ranked:
            print("  (không ứng viên nào khớp từ khoá — dùng --inspect-page để xem toàn bộ)")
        for sc, slug, c in ranked[:8]:
            print(f"  [{sc:>3}] {slug[:46]}")
            print(f"        url : {c['url'][:96]}")
            if c["alt"]:
                print(f"        alt : {c['alt'][:96]}")
            if c["near"]:
                print(f"        near: {c['near'][:96]}")


def upsize_url(url: str, want_w: int = 1400) -> str:
    """Nâng tham số bề rộng trên URL ảnh của các CDN/DAM (scene7, Next.js image…).

    Trang thường nhúng bản thumbnail (`wid=250`) của ĐÚNG tấm ảnh cần; lấy nguyên
    thumbnail thì ảnh vỡ khi hiển thị full-width. Đổi tham số là lấy bản lớn hơn
    của cùng asset, không phải đổi sang ảnh khác.
    """
    def bump(m):
        return f"{m.group(1)}={want_w}" if int(m.group(2)) < want_w else m.group(0)
    url = re.sub(r"\b(wid|w)=(\d+)", bump, url)
    url = re.sub(r"\b(hei|h)=(\d+)", lambda m: "", url).replace("&&", "&").rstrip("&?")
    return url


def fetch_resize(url: str, max_w: int = 820) -> bytes | None:
    r = requests.get(url, headers=HEADERS, timeout=25)
    r.raise_for_status()
    im = Image.open(io.BytesIO(r.content)).convert("RGB")
    if im.width > max_w:
        im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=80, optimize=True)
    return buf.getvalue()


def main() -> None:
    ap = argparse.ArgumentParser(description="Thu ảnh minh hoạ cho trang hồ sơ")
    ap.add_argument("--name", default="schiphol")
    ap.add_argument("--max-width", type=int, default=820)
    ap.add_argument("--inspect", action="store_true",
                    help="kiểm kê ứng viên ảnh theo từng mục (chạy TRƯỚC khi viết CURATION)")
    ap.add_argument("--section", help="chỉ kiểm kê 1 mục: hero|planning|vision|experience")
    args = ap.parse_args()

    if args.inspect:
        inspect_case(args.name, args.section)
        return

    cur = CURATION.get(args.name)
    if not cur:
        raise SystemExit(f"Chưa curate ảnh cho '{args.name}'. Thêm vào CURATION.")

    case_dir = ROOT / "raw_data" / "output" / "ws1_airport" / "raw" / args.name
    pages_dir = case_dir / "pages"
    urls = page_url_map(case_dir)
    out_dir = HERE / "assets" / args.name
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest = {}
    used: dict[str, str] = {}
    for entry in cur:
        # (section, slug, caption) hoặc (section, slug, caption, want)
        section, slug, caption = entry[0], entry[1], entry[2]
        want = entry[3] if len(entry) > 3 else None
        html_path = pages_dir / f"{slug}.html"
        if not html_path.exists():
            print(f"  [skip] {section}: không thấy {html_path.name}")
            continue
        page_url = urls.get(slug, "")
        img_url = None
        if want:
            # Chọn đúng ảnh đã curate (khớp chuỗi con trong url/alt) — chỉ dựa vào
            # og:image thì hầu như luôn ra ảnh thương hiệu, sai ngữ cảnh mục.
            for c in image_candidates(html_path, page_url):
                if want.lower() in c["url"].lower() or want.lower() in c["alt"].lower():
                    img_url = c["url"]
                    break
            if not img_url:
                print(f"  [warn] {section}: không thấy ảnh khớp '{want}' trong {slug} -> quay về og:image")
        if not img_url:
            img_url = pick_image_url(html_path, page_url)
        if not img_url:
            print(f"  [skip] {section}: trang {slug} không có ảnh")
            continue
        if img_url in used:
            print(f"  [warn] {section}: TRÙNG ảnh với mục '{used[img_url]}' — nên đổi slug/want")
        used[img_url] = section
        # Thử bản độ phân giải cao trước; CDN nào không nhận tham số đã sửa
        # (vd Next.js chỉ cho phép vài giá trị `w`) thì quay về URL gốc.
        data = None
        for candidate in dict.fromkeys([upsize_url(img_url), img_url]):
            try:
                data = fetch_resize(candidate, args.max_width)
                break
            except Exception as exc:  # noqa: BLE001
                last_err = exc
        if data is None:
            print(f"  [fail] {section}: {img_url[:60]} -> {last_err}")
            continue
        fname = f"{section}.jpg"
        (out_dir / fname).write_bytes(data)
        manifest[section] = {"file": fname, "source_image": img_url,
                             "page_url": urls.get(slug, ""), "caption": caption,
                             "bytes": len(data)}
        print(f"  [ok] {section}: {len(data):,} bytes <- {img_url[:60]}")

    (out_dir / "images.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[done] {len(manifest)} ảnh -> {out_dir}")


if __name__ == "__main__":
    main()
