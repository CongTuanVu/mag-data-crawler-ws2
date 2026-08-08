"""Sinh trang web tĩnh (phong cách SLIDE, LỜI VĂN TIẾNG VIỆT) cho 1 aerotropolis.

Đọc <case>_airport_city.json (record + provenance) -> dệt dữ liệu thành các đoạn
văn tiếng Việt mạch lạc (không phải chip/keyword), nhúng vào 1 file HTML tự chứa.

Số được format kiểu Việt (66,8 triệu; 2.787 ha) và thuật ngữ EN được dịch qua
từ điển VI. Trường thiếu -> tự bỏ mệnh đề tương ứng (không bịa).

Chạy:
    python html/build_html.py                 # mặc định schiphol
    python html/build_html.py --name schiphol
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FEATURES = ROOT / "raw_data" / "output" / "ws1_airport" / "features"

TEMPLATE = r"""<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__ — Hồ sơ Khu đô thị Sân bay</title>
<style>
  :root{
    --navy:#1f3864; --navy2:#2e5496; --blue:#1f4e79;
    --yellow:#fff2cc; --yellowln:#e6d28a;
    --green:#eaf3e2; --greenln:#a9d08e; --beige:#fdefe4;
    --ink:#20303f; --muted:#5b6b85; --line:#cfd7e6; --line2:#e6ebf3; --teal:#2e7d6b;
  }
  *{box-sizing:border-box}
  body{margin:0;background:#c9d0da;color:var(--ink);
       font-family:"Segoe UI",Arial,Helvetica,sans-serif;line-height:1.6;padding:26px 14px}
  a{color:var(--navy2);text-decoration:none} a:hover{text-decoration:underline}
  .slide{max-width:1120px;margin:0 auto 22px;background:#fff;border:1px solid #b9c2d2;
     border-radius:6px;box-shadow:0 12px 40px rgba(20,35,70,.28);overflow:hidden}
  .titlebar{background:linear-gradient(100deg,var(--navy),var(--navy2));color:#fff;
     padding:16px 26px;display:flex;justify-content:space-between;align-items:center;gap:16px}
  .titlebar .tt{font-size:23px;font-weight:800}
  .titlebar .tt .hl{background:#ffd966;color:#3a2c00;padding:1px 8px;border-radius:4px;
     font-size:14px;font-weight:700;margin-left:8px;vertical-align:middle}
  .titlebar .tag{font-size:11px;letter-spacing:.15em;font-weight:700;color:#cfe2ff;
     border:1px solid #6f92c7;border-radius:999px;padding:5px 12px;white-space:nowrap}
  .subbar{background:#eef2f8;border-bottom:1px solid var(--line);padding:9px 26px;
     display:flex;flex-wrap:wrap;gap:6px 20px;font-size:13.5px;color:#33405c}
  .subbar b{color:var(--navy)} .subbar .pill{background:#dbe6f5;border-radius:999px;padding:1px 10px;font-size:12px;font-weight:700;color:var(--navy)}
  .grid{display:grid;grid-template-columns:172px 1fr}
  .lab{background:var(--yellow);border-right:1px solid var(--yellowln);border-bottom:1px solid var(--line2);
     font-weight:700;color:var(--navy);padding:15px 16px;font-size:14px;display:flex;align-items:flex-start}
  .cell{border-bottom:1px solid var(--line2);padding:15px 22px;font-size:14.5px;color:var(--ink)}
  .cell p{margin:0 0 9px} .cell p:last-child{margin-bottom:0}
  .cell b{color:var(--navy)}
  .row-green .cell{background:var(--green)} .row-green .lab{background:#eef6e6;border-right-color:var(--greenln)}
  .row-beige .cell{background:var(--beige)} .row-beige .lab{background:#fdeee2;border-right-color:#f0c9ad}
  .lead{font-size:15.5px}
  .kpis{display:grid;grid-template-columns:repeat(auto-fill,minmax(118px,1fr));gap:9px;margin-top:12px}
  .kpi{border:1px solid var(--line);border-top:3px solid var(--teal);border-radius:6px;padding:9px 11px;background:#fbfdff}
  .kpi .v{font-size:19px;font-weight:800;color:var(--navy);line-height:1.1}
  .kpi .u{font-size:11px;color:var(--muted)} .kpi .l{font-size:11.5px;color:#3a4763;margin-top:4px}
  .src{font-size:11px;color:#9aa7be;text-decoration:none}
  .quote{border-left:3px solid var(--teal);background:#f3f8f6;padding:8px 13px;border-radius:0 8px 8px 0;
     font-style:italic;color:#37475d;font-size:13.5px;margin:8px 0 0}
  .foot{padding:12px 26px;border-top:2px solid var(--navy);background:#f6f8fc;font-size:12px;color:var(--muted);font-style:italic}
  .foot b{color:var(--navy);font-style:normal}
  details.prov{max-width:1120px;margin:0 auto 20px;background:#fff;border:1px solid #b9c2d2;border-radius:6px;padding:6px 18px 14px}
  details.prov summary{cursor:pointer;font-weight:700;color:var(--navy);padding:8px 0}
  .src-row{display:flex;gap:9px;align-items:baseline;font-size:12.5px;padding:5px 0;border-top:1px solid var(--line2)}
  .src-row .n{color:var(--muted);min-width:20px} .src-row .keys{color:var(--muted);font-size:11.5px}
  @media(max-width:640px){.grid{grid-template-columns:1fr}.lab{border-right:none}.titlebar .tag{display:none}}
</style>
</head>
<body>
<div class="slide">
  <div class="titlebar">
    <div class="tt"><span id="title"></span><span class="hl">Hồ sơ Khu đô thị Sân bay</span></div>
    <div class="tag">PHÂN TÍCH AEROTROPOLIS · BENCHMARK</div>
  </div>
  <div class="subbar" id="subbar"></div>
  <div class="grid">
    <div class="lab">Giới thiệu</div>          <div class="cell lead" id="intro"></div>
    <div class="lab">Vị trí & lịch sử</div>    <div class="cell" id="loc"></div>
    <div class="lab">Quy mô</div>              <div class="cell" id="scale"></div>
    <div class="lab">Định vị</div>             <div class="cell" id="positioning"></div>
    <div class="lab">Quy hoạch & phân khu</div><div class="cell" id="planning"></div>
    <div class="lab row-green">Tầm nhìn & bền vững</div><div class="cell row-green" id="vision"></div>
  </div>
  <div class="foot" id="footer"></div>
</div>

<div class="slide">
  <div class="titlebar">
    <div class="tt"><span id="title2"></span><span class="hl">Phân tích CVP</span></div>
    <div class="tag">ĐỀ XUẤT GIÁ TRỊ KHÁCH HÀNG (CVP)</div>
  </div>
  <div class="subbar">Sáu trụ cột giá trị: Sản phẩm · Giá · Dịch vụ · Trải nghiệm · Thuận tiện · Thương hiệu</div>
  <div class="grid">
    <div class="lab">Sản phẩm</div>          <div class="cell" id="cvp_product"></div>
    <div class="lab row-beige">Giá</div>      <div class="cell row-beige" id="cvp_price"></div>
    <div class="lab">Dịch vụ</div>            <div class="cell" id="cvp_service"></div>
    <div class="lab row-green">Trải nghiệm</div><div class="cell row-green" id="cvp_experience"></div>
    <div class="lab">Thuận tiện</div>         <div class="cell" id="cvp_convenience"></div>
    <div class="lab row-beige">Thương hiệu</div><div class="cell row-beige" id="cvp_brand"></div>
  </div>
  <div class="foot" id="footer2"></div>
</div>

<details class="prov"><summary>Nguồn dữ liệu chi tiết (provenance)</summary><div id="sources"></div></details>

<script>
const DATA = __DATA__;
const GENERATED = "__GENERATED__";
const rec = DATA.record, prov = DATA.provenance || {};
const FLAGS = {"Hà Lan":"🇳🇱","Hàn Quốc":"🇰🇷","Trung Quốc":"🇨🇳","Việt Nam":"🇻🇳","Singapore":"🇸🇬","Đức":"🇩🇪","UAE":"🇦🇪","Nhật Bản":"🇯🇵"};

/* ---- Từ điển dịch thuật ngữ EN -> VI ---- */
const VI = {
  cornerstone:{"Aviation":"Hàng không","Consumer Products & Services":"Sản phẩm & Dịch vụ tiêu dùng","Real Estate":"Bất động sản"},
  commercial:{"logistics":"hậu cần (logistics)","cargo":"kho vận hàng hoá","office":"văn phòng","real estate":"bất động sản","retail":"bán lẻ","hotel":"khách sạn","World Trade Center":"World Trade Center (WTC)","The Base":"toà The Base"},
  amenity:{"meeting":"phòng họp","sports":"khu thể thao","restaurants":"nhà hàng","catering":"dịch vụ ẩm thực","child care":"trông trẻ","childcare":"trông trẻ","shops":"cửa hàng","Schiphol Plaza":"trung tâm mua sắm Schiphol Plaza","café":"quán cà phê","fitness":"phòng tập"},
  highlight:{"World Trade Center":"World Trade Center (WTC)","WTC":"WTC","Hilton Hotel":"khách sạn Hilton","Sheraton Hotel":"khách sạn Sheraton","The Base":"toà The Base","The Outlook":"toà The Outlook","BREEAM":"công trình đạt chuẩn BREEAM"},
  subzone:{"Schiphol Central Business District":"Khu trung tâm thương mại (CBD)","Schiphol East":"Schiphol East","Schiphol Southeast":"Schiphol Southeast","Schiphol Business District":"Khu Thương mại Schiphol"},
  service:{"Spot":"nền tảng cộng đồng Spot","Leasing Managers":"đội ngũ cho thuê (Leasing Managers)","area director":"quản trị khu vực (area director)","flexible real estate":"giải pháp bất động sản linh hoạt"},
  vision:{"Quality of Network":"Mạng lưới","Quality of Life":"Cuộc sống","Quality of Service":"Dịch vụ","Quality of Work":"Công việc"},
  sustain:{"BREEAM":"chứng chỉ BREEAM","circular":"kinh tế tuần hoàn","most sustainable":"bền vững hàng đầu","biodiversity":"đa dạng sinh học","CO2":"giảm phát thải CO₂"},
  product:{"office":"văn phòng","commercial space":"mặt bằng thương mại","development":"quỹ đất phát triển","logistics":"hậu cần","cargo":"kho vận","retail":"bán lẻ","real estate":"bất động sản"},
};

const dedupe = a => { const s=new Set(),o=[]; for(const x of a||[]){const k=String(x).toLowerCase(); if(!s.has(k)){s.add(k);o.push(x);}} return o; };
const tr = (v,m) => (m && m[v]) ? m[v] : v;
const trList = (arr,m) => dedupe(arr).map(v=>tr(v,m));
const joinVi = a => !a.length?"":(a.length===1?a[0]:a.slice(0,-1).join(", ")+" và "+a[a.length-1]);
const fmtVi = n => (typeof n==="number") ? n.toLocaleString("de-DE") : n;
const b = s => `<b>${s}</b>`;
const has = k => rec[k]!=null && !(Array.isArray(rec[k]) && !rec[k].length);
const src = k => { const p=prov[k]; const u=p&&(p.source_url||(p.source_urls&&p.source_urls[0])); return u?` <a class="src" href="${u}" target="_blank" title="Nguồn">ⓘ</a>`:""; };
const P = html => `<p>${html}</p>`;
const set = (id,html) => document.getElementById(id).innerHTML = html || "<p>—</p>";

/* ---- Header ---- */
document.getElementById("title").textContent = rec.case_name || "";
document.getElementById("title2").textContent = rec.case_name || "";
document.getElementById("subbar").innerHTML =
  `<div>${FLAGS[rec.country]||""} <b>${rec.country||""}</b></div>` +
  `<div>${rec.is_target?'<span class="pill">DỰ ÁN MỤC TIÊU</span>':'<span class="pill">CASE THAM CHIẾU</span>'}</div>` +
  (rec.official_website?`<div>🔗 <a href="${rec.official_website}" target="_blank">${rec.official_website.replace(/^https?:\/\//,'')}</a></div>`:"");

/* ---- Giới thiệu ---- */
let intro = `${b(rec.case_name||"")}${rec.aerotropolis?` (còn gọi ${rec.aerotropolis.split('/').pop().trim()})`:""} là khu đô thị sân bay của ${b(rec.country||"")}`;
if(has("airport_name")) intro += `, phát triển quanh ${b("sân bay "+rec.airport_name)}`;
if(has("reference_city")) intro += ` và gắn liền với vùng đô thị ${b(rec.reference_city)}`;
intro += ".";
if(has("founded_year")) intro += ` Hình thành từ năm ${b(rec.founded_year)} trên vùng đất khai hoang Haarlemmermeer, sau hơn một thế kỷ nơi đây đã trở thành một trong những sân bay hàng đầu châu Âu và là hình mẫu kinh điển của mô hình ${b("AirportCity")}${src("founded_year")}.`;
set("intro", P(intro));

/* ---- Vị trí & lịch sử ---- */
let loc = `Khu đô thị nằm ngay cạnh nhà ga hành khách, thuộc vùng đô thị ${b(rec.reference_city||"")}. `;
loc += `Sân bay khởi đầu là một sân bay quân sự năm ${b(rec.founded_year||"")}, nhanh chóng mở rộng thành cảng hàng không dân dụng và phát triển liên tục hơn 100 năm tới nay.`;
set("loc", P(loc));

/* ---- Quy mô (lời văn + KPI) ---- */
let scale = `Về quy mô khai thác, sân bay đón ${b(fmtVi(rec.passengers_million)+" triệu")} lượt khách và ${b(fmtVi(rec.cargo_million_tonnes)+" triệu tấn")} hàng hoá mỗi năm qua ${b(fmtVi(rec.air_movements))} lượt cất/hạ cánh, kết nối ${b(fmtVi(rec.destinations)+" điểm đến")} của ${b(fmtVi(rec.airlines)+" hãng bay")}; khách trung chuyển chiếm ${b(fmtVi(rec.transfer_pct)+"%")}.${src("passengers_million")} `;
scale += `Toàn khu rộng ${b(fmtVi(rec.airport_area_ha)+" ha")} — lớn hơn nhiều thành phố Hà Lan — là nơi làm việc của khoảng ${b(fmtVi(rec.employees)+" người")} thuộc gần ${b(fmtVi(rec.num_companies_airport)+" doanh nghiệp")}.${src("airport_area_ha")}`;
const KPI = [["passengers_million","Hành khách","triệu/năm"],["cargo_million_tonnes","Hàng hoá","triệu tấn/năm"],["air_movements","Cất/hạ cánh","lượt/năm"],["destinations","Điểm đến","điểm"],["airlines","Hãng bay","hãng"],["transfer_pct","Trung chuyển","%"],["airport_area_ha","Diện tích","ha"],["employees","Lao động","người"],["num_office_buildings","Toà văn phòng","toà"]];
let kpiHtml = '<div class="kpis">';
for(const [k,l,u] of KPI){ if(!has(k)) continue; kpiHtml += `<div class="kpi"><div class="v">${fmtVi(rec[k])}</div><div class="u">${u}</div><div class="l">${l}</div></div>`; }
kpiHtml += "</div>";
set("scale", P(scale)+kpiHtml);

/* ---- Định vị ---- */
let pos = `Schiphol được định vị theo mô hình ${b("AirportCity")}`;
if(has("planning_concept")) pos += ` — nơi hành khách, hãng bay và doanh nghiệp có thể tiếp cận mọi dịch vụ suốt 24 giờ mỗi ngày`;
pos += ".";
if(has("cornerstones")) pos += ` Mô hình đứng trên ${b("ba trụ cột")} bổ trợ lẫn nhau: ${joinVi(trList(rec.cornerstones,VI.cornerstone).map(b))}.${src("cornerstones")}`;
set("positioning", P(pos));

/* ---- Quy hoạch & phân khu ---- */
let plan = "";
if(has("subzones")) plan += `Khu vực được tổ chức thành nhiều phân khu chức năng, nổi bật là ${joinVi(trList(rec.subzones,VI.subzone).map(b))}.${src("subzones")} `;
const parks=[];
if(has("logistics_park_ha")) parks.push(`${b("Schiphol Logistics Park")} (~${fmtVi(rec.logistics_park_ha)} ha)`);
if(has("trade_park_ha")) parks.push(`${b("Schiphol Trade Park")} (~${fmtVi(rec.trade_park_ha)} ha)`);
if(parks.length) plan += `Ở cấp vùng, hệ sinh thái mở rộng với ${joinVi(parks)} — các khu hậu cần - kinh doanh phát triển theo từng giai đoạn ở phía nam Hoofddorp.${src("trade_park_ha")}`;
set("planning", plan?P(plan):"");

/* ---- Tầm nhìn & bền vững ---- */
let vis = "";
if(has("vision_label")){
  vis += `Định hướng dài hạn được gói trong ${b(rec.vision_label)}`;
  if(has("vision_qualities")) vis += `, xoay quanh bốn chất lượng cốt lõi: ${joinVi(trList(rec.vision_qualities,VI.vision).map(b))}`;
  if(has("aviation_policy")) vis += `, trong khuôn khổ ${b(rec.aviation_policy)} của Hà Lan`;
  vis += `.${src("vision_qualities")} `;
}
if(has("sustainability")) vis += `Về phát triển bền vững, khu hậu cần theo đuổi ${joinVi(trList(rec.sustainability,VI.sustain))}, hướng tới trở thành khu logistics bền vững hàng đầu.${src("sustainability")}`;
set("vision", vis?P(vis):"");

/* ===== Slide B — CVP (lời văn) ===== */
let pr = "";
if(has("cvp_product")) pr += `Sản phẩm bất động sản thương mại tập trung vào ${joinVi(trList(rec.cvp_product,VI.product).map(b))}. `;
if(has("num_office_buildings")||has("num_companies_realestate"))
  pr += `Toàn khu có khoảng ${b(fmtVi(rec.num_office_buildings)+" toà")} văn phòng cho hơn ${b(fmtVi(rec.num_companies_realestate)+" doanh nghiệp")} thuê; nơi đây gần như không phát triển nhà ở mà thuần về thương mại - văn phòng.${src("num_office_buildings")}`;
set("cvp_product", pr?P(pr):"");

let price = "";
if(has("office_rent_eur_m2_year")){ const r=rec.office_rent_eur_m2_year;
  price += `Giá chào thuê văn phòng dao động khoảng ${b("€"+fmtVi(r.min)+"–€"+fmtVi(r.max)+"/m²/năm")} (chưa gồm VAT), tuỳ vị trí toà nhà và phân khu.${src("office_rent_eur_m2_year")} `; }
if(has("cvp_price")) price += `Ở cấp tập đoàn, nguồn thu đến từ nhiều dòng: phí hàng không và phí hành khách, phí nhượng quyền bán lẻ - ẩm thực, quảng cáo, bãi đỗ, cùng tiền thuê và cho thuê bất động sản.${src("cvp_price")}`;
set("cvp_price", price?P(price):"");

let sv = "";
if(has("cvp_service")) sv += `Schiphol Real Estate đóng vai trò ${b("quản trị khu vực (area director)")} — không chỉ cho thuê mà còn phát triển và vận hành toàn khu, cung cấp giải pháp bất động sản linh hoạt. Cộng đồng doanh nghiệp được kết nối qua ${b("nền tảng Spot")} (sự kiện, hội thảo, thể thao) cùng đội ngũ Leasing Managers hỗ trợ trực tiếp.${src("cvp_service")}`;
set("cvp_service", sv?P(sv):"");

let ex = "";
if(has("cvp_experience")) ex += `Trải nghiệm tại chỗ phong phú với ${joinVi(trList(rec.cvp_experience,Object.assign({},VI.amenity,VI.highlight)))}; lưu trú có các khách sạn cao cấp kết nối trực tiếp nhà ga.${src("cvp_experience")}`;
set("cvp_experience", ex?P(ex):"");

let cv = "";
if(has("cvp_convenience")) cv += `Khả năng kết nối là thế mạnh nổi bật: tiếp cận bằng cả ${b("ô tô, xe buýt, tàu hoả và máy bay")}, liền kề các cao tốc ${b("A4/A5/A9/A10")}; chỉ 2–8 phút tới nhà ga NS và sảnh sân bay, tàu cao tốc đi ${b("Paris")} chạy 9 chuyến mỗi ngày.${src("cvp_convenience")} `;
if(has("rail_connections")) cv += `Đường sắt NS nối trực tiếp ${b("Amsterdam")} và ${b("Rotterdam")} (Intercity direct).${src("rail_connections")}`;
set("cvp_convenience", cv?P(cv):"");

let br = "";
if(has("cvp_brand")) br += `Dự án do ${b("Royal Schiphol Group")} sở hữu và dẫn dắt, với ${b("Schiphol Real Estate")} là đơn vị phát triển - quản trị khu vực; hệ sinh thái quy tụ nhiều thương hiệu và đối tác quốc tế lớn.${src("cvp_brand")}`;
set("cvp_brand", br?P(br):"");

/* ---- Footer + nguồn ---- */
const hostOf = u => u.replace(/^https?:\/\//,'').split('/')[0];
const urlMap = {};
for(const [k,p] of Object.entries(prov)){ const urls=p.source_urls||(p.source_url?[p.source_url]:[]); for(const u of urls){ (urlMap[u]=urlMap[u]||[]).push(k); } }
const hosts = dedupe(Object.keys(urlMap).map(hostOf));
const footTxt = `<b>Nguồn:</b> ${hosts.join(", ")} — tổng hợp & biên soạn tự động bởi pipeline <b>mag-data-crawler</b> (${rec._pages_used||"?"} trang đã crawl). Sinh lúc ${GENERATED}.`;
document.getElementById("footer").innerHTML = footTxt;
document.getElementById("footer2").innerHTML = footTxt;
const sources = document.getElementById("sources");
Object.entries(urlMap).forEach(([u,keys],i)=>{
  const d=document.createElement("div"); d.className="src-row";
  d.innerHTML=`<span class="n">${i+1}.</span><div><a href="${u}" target="_blank">${u.replace(/^https?:\/\//,'')}</a><div class="keys">→ ${dedupe(keys).join(", ")}</div></div>`;
  sources.appendChild(d);
});
</script>
</body>
</html>
"""


def main() -> None:
    ap = argparse.ArgumentParser(description="Sinh trang web tĩnh (lời văn tiếng Việt) cho 1 aerotropolis")
    ap.add_argument("--name", default="schiphol")
    ap.add_argument("--json", type=Path)
    args = ap.parse_args()

    json_path = args.json or (FEATURES / f"{args.name}_airport_city.json")
    if not json_path.exists():
        raise SystemExit(f"Không thấy JSON: {json_path}")

    data = json.loads(json_path.read_text(encoding="utf-8"))
    title = data.get("record", {}).get("case_name", args.name)
    html = (TEMPLATE
            .replace("__DATA__", json.dumps(data, ensure_ascii=False))
            .replace("__GENERATED__", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))
            .replace("__TITLE__", title))

    (HERE / f"{args.name}.html").write_text(html, encoding="utf-8")
    (HERE / "index.html").write_text(html, encoding="utf-8")
    print(f"[ok] đọc {json_path.name}")
    print(f"[ok] -> {HERE / 'index.html'}  (mở bằng trình duyệt)")


if __name__ == "__main__":
    main()
