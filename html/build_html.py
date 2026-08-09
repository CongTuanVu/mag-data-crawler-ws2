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
import base64
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
  .hero-img{width:100%;height:238px;object-fit:cover;display:block}
  .hero-cap{font-size:11px;color:var(--muted);padding:5px 26px;background:#f6f8fc;border-bottom:1px solid var(--line);font-style:italic}
  figure.ill{margin:12px 0 0}
  figure.ill img{width:100%;max-height:230px;object-fit:cover;border-radius:8px;border:1px solid var(--line);display:block}
  figure.ill figcaption{font-size:11.5px;color:var(--muted);margin-top:5px;font-style:italic}
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
  <div id="heroimg"></div>
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
const IMAGES = __IMAGES__;
const VITEXT = __VITEXT__;
const GENERATED = "__GENERATED__";
const rec = DATA.record, prov = DATA.provenance || {};

/* ---- Lớp dịch: ưu tiên bản tiếng Việt đã biên soạn, không có thì giữ nguyên văn.
   Bản gốc luôn còn trong `rec`/`prov` và hiện khi rê chuột vào ⓘ. ---- */
const vi = k => {
  const t = VITEXT[k];
  if (t == null) return rec[k];
  if (Array.isArray(rec[k]) && Array.isArray(t) && t.length !== rec[k].length) return rec[k];
  return t;
};
function figureFor(section){
  const im = IMAGES[section]; if(!im) return "";
  const cap = im.caption + (im.page_url?` · <a href="${im.page_url}" target="_blank">nguồn</a>`:"");
  return `<figure class="ill"><img src="${im.datauri}" alt="${im.caption||''}"><figcaption>${cap}</figcaption></figure>`;
}
const FLAGS = {"Hà Lan":"🇳🇱","Hàn Quốc":"🇰🇷","Trung Quốc":"🇨🇳","Việt Nam":"🇻🇳","Singapore":"🇸🇬","Đức":"🇩🇪","UAE":"🇦🇪","Nhật Bản":"🇯🇵","Đài Loan":"🇹🇼","Úc":"🇦🇺"};

/* ---- Từ điển dịch thuật ngữ EN -> VI ---- */
const VI = {
  cornerstone:{"Aviation":"Hàng không","Consumer Products & Services":"Sản phẩm & Dịch vụ tiêu dùng","Real Estate":"Bất động sản",
    "Business/R&D Hub":"Trung tâm kinh doanh & R&D","Tourism/Logistics Hub":"Trung tâm du lịch & hậu cần","Advanced Industry Hub":"Trung tâm công nghiệp tiên tiến","Aviation Support Hub":"Trung tâm dịch vụ hàng không"},
  commercial:{"logistics":"hậu cần (logistics)","cargo":"kho vận hàng hoá","office":"văn phòng","real estate":"bất động sản","retail":"bán lẻ","hotel":"khách sạn","World Trade Center":"World Trade Center (WTC)","The Base":"toà The Base",
    "MRO":"bảo dưỡng - sửa chữa máy bay (MRO)","casino":"casino","resort":"khu nghỉ dưỡng","GDC":"trung tâm phân phối toàn cầu (GDC)","fulfillment center":"trung tâm hoàn tất đơn hàng",
    "free trade zone":"khu phi thuế quan","free-trade zone":"khu phi thuế quan","industrial":"công nghiệp","commercial":"thương mại","residential":"nhà ở","semiconductor":"bán dẫn","warehouse":"kho bãi",
    "advanced manufacturing":"sản xuất tiên tiến","agribusiness":"nông nghiệp công nghệ cao","university":"đại học"},
  amenity:{"meeting":"phòng họp","sports":"khu thể thao","restaurants":"nhà hàng","catering":"dịch vụ ẩm thực","child care":"trông trẻ","childcare":"trông trẻ","shops":"cửa hàng","Schiphol Plaza":"trung tâm mua sắm Schiphol Plaza","café":"quán cà phê","fitness":"phòng tập",
    "Seminar rooms":"phòng hội thảo","sports complex":"tổ hợp thể thao","fitness center":"trung tâm thể hình","business center":"trung tâm thương vụ","banquet hall":"sảnh tiệc",
    "arena":"nhà thi đấu - biểu diễn","water park":"công viên nước","casino":"casino","resort":"khu nghỉ dưỡng",
    "bike paths":"đường xe đạp","park landscapes":"cảnh quan công viên","waterfront plazas":"quảng trường ven nước","community amenities":"tiện ích cộng đồng","recreational corridors":"hành lang nghỉ ngơi","park":"công viên",
    "health facilities":"cơ sở y tế","open space":"không gian mở","Central Park":"công viên trung tâm Central Park","walkable":"đi bộ thuận tiện","cycle":"hạ tầng xe đạp","retail":"bán lẻ","university":"đại học","childcare":"trông trẻ"},
  highlight:{"World Trade Center":"World Trade Center (WTC)","WTC":"WTC","Hilton Hotel":"khách sạn Hilton","Sheraton Hotel":"khách sạn Sheraton","The Base":"toà The Base","The Outlook":"toà The Outlook","BREEAM":"công trình đạt chuẩn BREEAM",
    "15,000-seat performance arena":"nhà thi đấu - biểu diễn 15.000 chỗ","indoor water park":"công viên nước trong nhà","foreigner-only casino":"casino dành cho người nước ngoài","largest hotel ballroom in Korea":"sảnh tiệc khách sạn lớn nhất Hàn Quốc","digital entertainment street":"phố giải trí số",
    "smart streetlights":"đèn đường thông minh","common utility tunnels":"hào kỹ thuật dùng chung","retention ponds":"hồ điều tiết",
    "Advanced Manufacturing Readiness Facility":"Trung tâm sẵn sàng sản xuất tiên tiến (AMRF)","Bradfield Metro Station":"ga metro Bradfield"},
  subzone:{"Schiphol Central Business District":"Khu trung tâm thương mại (CBD)","Schiphol East":"Schiphol East","Schiphol Southeast":"Schiphol Southeast","Schiphol Business District":"Khu Thương mại Schiphol",
    "Songdo International City":"đô thị quốc tế Songdo","Yeongjong International City":"đô thị quốc tế Yeongjong","Cheongna International City":"đô thị quốc tế Cheongna","Airport Logistics Complex":"tổ hợp hậu cần sân bay",
    "industry zone":"khu công nghiệp","free-trade zone":"khu phi thuế quan","commercial zone":"khu thương mại","residence zone":"khu dân cư","Air Cargo Terminal":"nhà ga hàng hoá","International Logistics Center":"trung tâm hậu cần quốc tế","Value-Added Park":"khu gia tăng giá trị",
    "Aerotropolis Core":"lõi Aerotropolis","Badgerys Creek":"phân khu Badgerys Creek","Wianamatta-South Creek":"hành lang Wianamatta - South Creek","Northern Gateway":"cửa ngõ phía Bắc","Agribusiness":"phân khu nông nghiệp công nghệ cao","Bradfield City":"lõi đô thị Bradfield City"},
  service:{"Spot":"nền tảng cộng đồng Spot","Leasing Managers":"đội ngũ cho thuê (Leasing Managers)","area director":"quản trị khu vực (area director)","flexible real estate":"giải pháp bất động sản linh hoạt",
    "Visa-Free Entry":"miễn thị thực nhập cảnh","English as an Official Language":"tiếng Anh là ngôn ngữ chính thức","Regulatory Free Zone":"khu tự do về quy định","customs duty deferment":"hoãn nộp thuế nhập khẩu","low rental fees":"phí thuê thấp",
    "In-Town Check-In":"làm thủ tục bay tại nội đô","customs clearance":"thông quan nhanh","duty":"ưu đãi thuế","BIM":"mô hình thông tin công trình (BIM)","GIS":"hệ thống thông tin địa lý (GIS)","IoT":"kết nối vạn vật (IoT)",
    "Investor Concierge":"hỗ trợ nhà đầu tư một cửa","InvestorLink":"cổng kết nối đầu tư InvestorLink","Planning referrals":"tư vấn thủ tục quy hoạch","Special Infrastructure Contributions":"cơ chế đóng góp hạ tầng"},
  brand:{"Royal Schiphol Group":"Tập đoàn Royal Schiphol Group","Schiphol Real Estate":"Schiphol Real Estate (đơn vị bất động sản)",
    "Incheon International Airport Corporation":"Tổng công ty Cảng hàng không quốc tế Incheon (IIAC)","Incheon Free Economic Zone Authority":"Ban quản lý Đặc khu kinh tế tự do Incheon (IFEZ)","INSPIRE":"tổ hợp giải trí INSPIRE",
    "Taoyuan Aerotropolis":"Ban dự án Taoyuan Aerotropolis","Far Glory":"Tập đoàn Far Glory","AECOM":"AECOM (tư vấn quản lý dự án)","Taoyuan Metro":"Công ty Metro Đào Viên",
    "Bradfield Development Authority":"Cơ quan Phát triển Bradfield","WSA Co":"WSA Co (đơn vị vận hành sân bay)","Investment NSW":"Cơ quan Xúc tiến đầu tư bang NSW","Sydney Metro":"Sydney Metro (chủ đầu tư đường sắt đô thị)"},
  vision:{"Quality of Network":"Mạng lưới","Quality of Life":"Cuộc sống","Quality of Service":"Dịch vụ","Quality of Work":"Công việc",
    "Challenge":"Thách thức","Cooperation":"Hợp tác","Creativity":"Sáng tạo","Integrity":"Chính trực"},
  sustain:{"BREEAM":"chứng chỉ BREEAM","circular":"kinh tế tuần hoàn","most sustainable":"bền vững hàng đầu","biodiversity":"đa dạng sinh học","CO2":"giảm phát thải CO₂",
    "RE100":"cam kết RE100","Green Mobility":"giao thông xanh","Low-Carbon Eco-Friendly Airport":"sân bay sinh thái phát thải thấp","renewable energy":"năng lượng tái tạo",
    "recycled materials":"vật liệu tái chế","circular economy":"kinh tế tuần hoàn","carbon emissions":"cắt giảm phát thải carbon","retention ponds":"hồ điều tiết","smart streetlights":"đèn đường thông minh",
    "sustainability":"phát triển bền vững","open space":"không gian mở","blue-green":"hạ tầng xanh - mặt nước","net zero":"phát thải ròng bằng 0"},
  product:{"office":"văn phòng","commercial space":"mặt bằng thương mại","development":"quỹ đất phát triển","logistics":"hậu cần","cargo":"kho vận","retail":"bán lẻ","real estate":"bất động sản",
    "MRO":"bảo dưỡng - sửa chữa máy bay (MRO)","R&D":"nghiên cứu & phát triển","fulfillment center":"trung tâm hoàn tất đơn hàng","industrial complex":"tổ hợp công nghiệp","business platform":"nền tảng kinh doanh",
    "warehouse":"kho bãi","Value-Added Park":"khu gia tăng giá trị","industry zone":"khu công nghiệp","free-trade zone":"khu phi thuế quan",
    "advanced manufacturing":"sản xuất tiên tiến","commercial":"thương mại","residential":"nhà ở","university":"đại học","industrial":"công nghiệp"},
};

const dedupe = a => { const s=new Set(),o=[]; for(const x of a||[]){const k=String(x).toLowerCase(); if(!s.has(k)){s.add(k);o.push(x);}} return o; };
const tr = (v,m) => (m && m[v]) ? m[v] : v;
const trList = (arr,m) => dedupe(arr).map(v=>tr(v,m));
const joinVi = a => !a.length?"":(a.length===1?a[0]:a.slice(0,-1).join(", ")+" và "+a[a.length-1]);
const fmtVi = n => (typeof n==="number") ? n.toLocaleString("de-DE") : n;
const b = s => `<b>${s}</b>`;
const has = k => rec[k]!=null && !(Array.isArray(rec[k]) && !rec[k].length);
const esc = s => String(s).replace(/&/g,"&amp;").replace(/"/g,"&quot;").replace(/</g,"&lt;");
const src = k => {
  const p=prov[k]; const u=p&&(p.source_url||(p.source_urls&&p.source_urls[0]));
  if(!u) return "";
  // title = câu gốc tại nguồn -> mệnh đề đã dịch vẫn kiểm chứng được ngay trên trang
  const orig = (p && p.snippet) || (VITEXT[k]!=null && !Array.isArray(rec[k]) ? rec[k] : "");
  const tip = orig ? `Nguồn — nguyên văn: ${esc(orig).slice(0,300)}` : "Nguồn";
  return ` <a class="src" href="${u}" target="_blank" title="${tip}">ⓘ</a>`;
};
const P = html => `<p>${html}</p>`;
const set = (id,html) => document.getElementById(id).innerHTML = html || "<p>—</p>";

/* ---- Header ---- */
document.getElementById("title").textContent = rec.case_name || "";
document.getElementById("title2").textContent = rec.case_name || "";
document.getElementById("subbar").innerHTML =
  `<div>${FLAGS[rec.country]||""} <b>${rec.country||""}</b></div>` +
  `<div>${rec.is_target?'<span class="pill">DỰ ÁN MỤC TIÊU</span>':'<span class="pill">CASE THAM CHIẾU</span>'}</div>` +
  (rec.official_website?`<div>🔗 <a href="${rec.official_website}" target="_blank">${rec.official_website.replace(/^https?:\/\//,'')}</a></div>`:"");

/* ---- Ảnh hero ---- */
if(IMAGES.hero){
  document.getElementById("heroimg").innerHTML =
    `<img class="hero-img" src="${IMAGES.hero.datauri}" alt="${IMAGES.hero.caption||''}">`+
    `<div class="hero-cap">${IMAGES.hero.caption||""}${IMAGES.hero.page_url?` · <a href="${IMAGES.hero.page_url}" target="_blank">nguồn</a>`:""}</div>`;
}

/* ---- Giới thiệu ---- */
let intro =`${b(rec.case_name||"")}${rec.aerotropolis?` (còn gọi ${rec.aerotropolis.split('/').pop().trim()})`:""} là khu đô thị sân bay của ${b(rec.country||"")}`;
if(has("airport_name")) intro += `, phát triển quanh ${b("sân bay "+vi("airport_name"))}`;
if(has("reference_city")) intro += ` và gắn liền với vùng đô thị ${b(rec.reference_city)}`;
intro += ".";
if(has("founded_year")) intro += ` Hình thành từ năm ${b(rec.founded_year)}${has("positioning")?`, nơi đây phát triển theo mô hình ${b(vi("positioning"))}`:""}.${src("founded_year")}`;
if(has("history_note")) intro += ` ${rec.history_note}${src("history_note")}`;
set("intro", P(intro));

/* ---- Vị trí & lịch sử ---- */
let loc = "";
if(has("reference_city")) loc += `Khu đô thị nằm liền kề nhà ga hành khách, thuộc vùng đô thị ${b(rec.reference_city)}.`;
/* location_desc thường đã nêu sẵn khoảng cách -> chỉ viết câu này khi không có nó, tránh lặp */
if(has("distance_to_city_km") && !has("location_desc")) loc += ` Cách trung tâm khoảng ${b(fmtVi(rec.distance_to_city_km)+" km")}.${src("distance_to_city_km")}`;
if(has("location_desc")) loc += ` ${vi("location_desc")}${src("location_desc")}`;
if(has("airport_build_period")) loc += ` Sân bay được xây dựng trong giai đoạn ${b(vi("airport_build_period"))}.${src("airport_build_period")}`;
if(has("urban_build_period")) loc += ` Phần đô thị triển khai giai đoạn ${b(vi("urban_build_period"))}.${src("urban_build_period")}`;
if(has("development_context")) loc += ` ${vi("development_context")}${src("development_context")}`;
set("loc", P(loc));

/* ---- Quy mô (lời văn + KPI) ---- */
const opClauses = [];
if(has("passengers_million")) opClauses.push(`đón ${b(fmtVi(rec.passengers_million)+" triệu")} lượt khách`);
if(has("cargo_million_tonnes")) opClauses.push(`${b(fmtVi(rec.cargo_million_tonnes)+" triệu tấn")} hàng hoá`);
if(has("air_movements")) opClauses.push(`${b(fmtVi(rec.air_movements))} lượt cất/hạ cánh`);
if(has("destinations")) opClauses.push(`${b(fmtVi(rec.destinations)+" điểm đến")}`);
if(has("airlines")) opClauses.push(`${b(fmtVi(rec.airlines)+" hãng bay")}`);
let scale = "";
if(opClauses.length) scale += `Về quy mô khai thác mỗi năm, sân bay ${joinVi(opClauses)}.${src("passengers_million")} `;
if(has("transfer_pct")) scale += `Khách trung chuyển chiếm ${b(fmtVi(rec.transfer_pct)+"%")}.${src("transfer_pct")} `;
const sizeClauses = [];
if(has("area_km2")) sizeClauses.push(`quy hoạch trên ${b(fmtVi(rec.area_km2)+" km²")}`);
if(has("airport_area_ha")) sizeClauses.push(`diện tích sân bay ${b(fmtVi(rec.airport_area_ha)+" ha")}`);
if(has("employees")) sizeClauses.push(`khoảng ${b(fmtVi(rec.employees)+" người")} làm việc`);
if(has("num_companies_airport")) sizeClauses.push(`gần ${b(fmtVi(rec.num_companies_airport)+" doanh nghiệp")}`);
if(has("jobs_created")) sizeClauses.push(`mục tiêu ${b(fmtVi(rec.jobs_created)+" việc làm")}`);
if(sizeClauses.length) scale += `Về quy mô đất đai và lao động: ${joinVi(sizeClauses)}.${src("area_km2")||src("airport_area_ha")} `;
if(has("total_investment_usd")) scale += `Tổng mức đầu tư: ${b(vi("total_investment_usd"))}.${src("total_investment_usd")}`;
const KPI = [["passengers_million","Hành khách","triệu/năm"],["cargo_million_tonnes","Hàng hoá","triệu tấn/năm"],["air_movements","Cất/hạ cánh","lượt/năm"],["destinations","Điểm đến","điểm"],["airlines","Hãng bay","hãng"],["transfer_pct","Trung chuyển","%"],["area_km2","Quy mô KĐT","km²"],["airport_area_ha","Diện tích sân bay","ha"],["employees","Lao động","người"],["jobs_created","Việc làm mục tiêu","việc làm"],["num_office_buildings","Toà văn phòng","toà"]];
let kpiHtml = '<div class="kpis">';
for(const [k,l,u] of KPI){ if(!has(k)) continue; kpiHtml += `<div class="kpi"><div class="v">${fmtVi(rec[k])}</div><div class="u">${u}</div><div class="l">${l}</div></div>`; }
kpiHtml += "</div>";
set("scale", P(scale)+kpiHtml);

/* ---- Định vị ---- */
let pos = "";
if(has("positioning")) pos += `${b(rec.case_name||"")} được định vị theo mô hình ${b(vi("positioning"))}.${src("positioning")} `;
if(has("planning_concept")) pos += `${vi("planning_concept")}${src("planning_concept")} `;
if(has("cornerstones")) pos += `Mô hình đứng trên ${b(rec.cornerstones.length+" trụ cột")} bổ trợ lẫn nhau: ${joinVi(trList(rec.cornerstones,VI.cornerstone).map(b))}.${src("cornerstones")}`;
set("positioning", pos?P(pos):"");

/* ---- Quy hoạch & phân khu ---- */
let plan = "";
if(has("subzones")) plan += `Khu vực được tổ chức thành nhiều phân khu chức năng, nổi bật là ${joinVi(trList(rec.subzones,VI.subzone).map(b))}.${src("subzones")} `;
const parks=[];
if(has("logistics_park_ha")) parks.push(`${b(vi("logistics_park_name")||"khu hậu cần")} (~${fmtVi(rec.logistics_park_ha)} ha)`);
if(has("trade_park_ha")) parks.push(`${b(vi("trade_park_name")||"khu thương mại - công nghiệp")} (~${fmtVi(rec.trade_park_ha)} ha)`);
if(parks.length) plan += `Ở cấp vùng, hệ sinh thái mở rộng với ${joinVi(parks)} — các khu hậu cần - kinh doanh phát triển theo từng giai đoạn.${src("logistics_park_ha")||src("trade_park_ha")}`;
if(has("economic_zone_name")) plan += ` Khu vực nằm trong ${b(vi("economic_zone_name"))}${has("economic_zone_year")?` (thành lập ${b(rec.economic_zone_year)})`:""}.${src("economic_zone_name")}`;
set("planning", plan?P(plan):"");
document.getElementById("planning").innerHTML += figureFor("planning");

/* ---- Tầm nhìn & bền vững ---- */
let vis = "";
if(has("vision_label")){
  vis += `Định hướng dài hạn được gói trong ${b(vi("vision_label"))}`;
  if(has("vision_qualities")) vis += `, xoay quanh các giá trị cốt lõi: ${joinVi(trList(rec.vision_qualities,VI.vision).map(b))}`;
  if(has("aviation_policy")) vis += `, trong khuôn khổ ${b(vi("aviation_policy"))}`;
  vis += `.${src("vision_qualities")} `;
}
if(has("sustainability")) vis += `Về phát triển bền vững, dự án theo đuổi ${joinVi(trList(rec.sustainability,VI.sustain))}.${src("sustainability")}`;
set("vision", vis?P(vis):"");
document.getElementById("vision").innerHTML += figureFor("vision");

/* ===== Slide B — CVP (lời văn) ===== */
let pr = "";
if(has("cvp_product")) pr += `Sản phẩm bất động sản thương mại tập trung vào ${joinVi(trList(rec.cvp_product,VI.product).map(b))}. `;
const stock=[];
if(has("num_office_buildings")) stock.push(`${b(fmtVi(rec.num_office_buildings)+" toà")} văn phòng`);
if(has("num_companies_realestate")) stock.push(`hơn ${b(fmtVi(rec.num_companies_realestate)+" doanh nghiệp")} thuê`);
if(stock.length) pr += `Toàn khu có ${joinVi(stock)}.${src("num_office_buildings")||src("num_companies_realestate")} `;
if(has("residential_product_desc")) pr += `Về nhà ở: ${vi("residential_product_desc")}${src("residential_product_desc")}`;
else if(stock.length) pr += `Nguồn công bố không nêu sản phẩm nhà ở cho khu vực này.`;
set("cvp_product", pr?P(pr):"");

let price = "";
if(has("office_rent_eur_m2_year")){ const r=rec.office_rent_eur_m2_year;
  price += `Giá chào thuê văn phòng dao động khoảng ${b("€"+fmtVi(r.min)+"–€"+fmtVi(r.max)+"/m²/năm")} (chưa gồm VAT), tuỳ vị trí toà nhà và phân khu.${src("office_rent_eur_m2_year")} `; }
if(has("cvp_price")) price += `Về mô hình doanh thu: ${vi("cvp_price")}${src("cvp_price")} `;
if(has("price_vs_reference")) price += `Mặt bằng giá so với đô thị tham chiếu: ${b(vi("price_vs_reference"))}.${src("price_vs_reference")} `;
if(has("sales_scheme")) price += `Cơ chế bán/cho thuê: ${vi("sales_scheme")}${src("sales_scheme")}`;
set("cvp_price", price?P(price):"");

let sv = "";
if(has("cvp_service")) sv += `Dịch vụ hỗ trợ nhà đầu tư & doanh nghiệp gồm ${joinVi(trList(rec.cvp_service,VI.service).map(b))}.${src("cvp_service")} `;
if(has("smart_city")) sv += `Về đô thị thông minh: ${vi("smart_city")}${src("smart_city")} `;
if(has("airport_privilege")) sv += `Đặc quyền gắn với sân bay: ${vi("airport_privilege")}${src("airport_privilege")}`;
set("cvp_service", sv?P(sv):"");

let ex = "";
if(has("cvp_experience")) ex += `Trải nghiệm tại chỗ gồm ${joinVi(trList(rec.cvp_experience,Object.assign({},VI.amenity,VI.highlight)))}.${src("cvp_experience")} `;
if(has("experience_desc")) ex += `${vi("experience_desc")}${src("experience_desc")}`;
set("cvp_experience", ex?P(ex):"");
document.getElementById("cvp_experience").innerHTML += figureFor("experience");

let cv = "";
if(has("cvp_convenience")) cv += `Khả năng kết nối: ${joinVi(vi("cvp_convenience"))}${src("cvp_convenience")} `;
if(has("connection_modes")) cv += `Phương thức tiếp cận gồm ${joinVi(vi("connection_modes").map(b))}.${src("connection_modes")} `;
if(has("metro_lines")) cv += `Khu vực được phục vụ bởi ${b(fmtVi(rec.metro_lines)+" tuyến")} metro/đường sắt đô thị.${src("metro_lines")} `;
if(has("rail_connections")) cv += `Kết nối đường sắt: ${joinVi(vi("rail_connections"))}${src("rail_connections")}`;
set("cvp_convenience", cv?P(cv):"");

let br = "";
if(has("investor_governance")) br += `Mô hình chủ đầu tư & quản trị: ${vi("investor_governance")}${src("investor_governance")} `;
if(has("lead_developer")) br += `Bên dẫn dắt là ${b(vi("lead_developer"))}.${src("lead_developer")} `;
if(has("cvp_brand")) br += `Hệ sinh thái thương hiệu quy tụ ${joinVi(trList(rec.cvp_brand,VI.brand).map(b))}.${src("cvp_brand")} `;
if(has("brand_partners")) br += `Đối tác lớn: ${joinVi(dedupe(vi("brand_partners")).map(b))}.${src("brand_partners")}`;
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


def load_images(name: str) -> dict:
    """Đọc html/assets/<name>/images.json -> nhúng ảnh base64 (self-contained)."""
    d = HERE / "assets" / name
    j = d / "images.json"
    if not j.exists():
        return {}
    out = {}
    for section, info in json.loads(j.read_text(encoding="utf-8")).items():
        p = d / info.get("file", "")
        if not p.exists():
            continue
        b64 = base64.b64encode(p.read_bytes()).decode()
        out[section] = {"datauri": f"data:image/jpeg;base64,{b64}",
                        "caption": info.get("caption", ""), "page_url": info.get("page_url", "")}
    return out


def load_vi_text(name: str) -> dict:
    """Đọc html/vi_text.json -> {field: bản tiếng Việt} cho 1 case.

    Đây là nội dung BIÊN SOẠN (người viết), tách khỏi record trích tự động để
    extractor vẫn deterministic và bản gốc vẫn truy được nguồn.
    """
    p = HERE / "vi_text.json"
    if not p.exists():
        return {}
    data = json.loads(p.read_text(encoding="utf-8"))
    return {k: v for k, v in data.get(name, {}).items() if not k.startswith("_")}


def main() -> None:
    ap = argparse.ArgumentParser(description="Sinh trang web tĩnh (lời văn tiếng Việt) cho 1 aerotropolis")
    ap.add_argument("--name", default="schiphol")
    ap.add_argument("--json", type=Path)
    args = ap.parse_args()

    json_path = args.json or (FEATURES / f"{args.name}_airport_city.json")
    if not json_path.exists():
        raise SystemExit(f"Không thấy JSON: {json_path}")

    data = json.loads(json_path.read_text(encoding="utf-8"))
    images = load_images(args.name)
    vitext = load_vi_text(args.name)
    print(f"[vi] {len(vitext)} trường dùng bản dịch tiếng Việt")
    title = data.get("record", {}).get("case_name", args.name)
    html = (TEMPLATE
            .replace("__DATA__", json.dumps(data, ensure_ascii=False))
            .replace("__IMAGES__", json.dumps(images, ensure_ascii=False))
            .replace("__VITEXT__", json.dumps(vitext, ensure_ascii=False))
            .replace("__GENERATED__", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))
            .replace("__TITLE__", title))
    print(f"[img] nhúng {len(images)} ảnh")

    (HERE / f"{args.name}.html").write_text(html, encoding="utf-8")
    (HERE / "index.html").write_text(html, encoding="utf-8")
    print(f"[ok] đọc {json_path.name}")
    print(f"[ok] -> {HERE / 'index.html'}  (mở bằng trình duyệt)")


if __name__ == "__main__":
    main()
