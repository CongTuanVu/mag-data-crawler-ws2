"""Sinh trang tổng hợp TẤT CẢ khu đô thị sân bay: tìm kiếm + modal chi tiết.

Khác `build_html.py` (mỗi case một trang dài, lời văn tiếng Việt viết tay), trang này
là cổng tra cứu: một file `html/index.html` self-contained chứa toàn bộ record của mọi
case, có ô tìm kiếm tức thời, lọc theo quốc gia, sắp xếp, và bấm vào một khu là mở
modal hiện đủ 75 trường theo nhóm — kèm nguồn, trích dẫn gốc và mức tin cậy.

Dữ liệu vào:
  features/ws1_airport/schema.json                          — nhóm, nhãn, đơn vị
  raw_data/output/ws1_airport/features/<case>_airport_city.json — record + provenance + missing
  html/assets/<case>/images.json                            — ảnh hero (nếu đã harvest)

Chạy:
    python html/build_portal.py
    python html/build_portal.py --out html/index.html --no-images
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

WS = "ws1_airport"
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
FEATURES = ROOT / "raw_data" / "output" / WS / "features"
SCHEMA_PATH = ROOT / "features" / WS / "schema.json"

FLAGS = {"Hàn Quốc": "🇰🇷", "Hà Lan": "🇳🇱", "UAE": "🇦🇪", "Singapore": "🇸🇬",
         "Hong Kong": "🇭🇰", "Mỹ": "🇺🇸", "Đức": "🇩🇪", "Malaysia": "🇲🇾",
         "Đài Loan": "🇹🇼", "Úc": "🇦🇺", "Việt Nam": "🇻🇳"}

# Chỉ số hiện trên mặt thẻ (tên trường, nhãn ngắn, hậu tố).
CARD_KPIS = [("passengers_million", "Khách", "tr"),
             ("area_km2", "Diện tích", "km²"),
             ("employees", "Lao động", ""),
             ("subzones", "Phân khu", "")]


def load_cases(with_images: bool) -> list[dict]:
    cases = []
    for path in sorted(FEATURES.glob("*_airport_city.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        case_id = path.name.replace("_airport_city.json", "")
        rec = data.get("record", data)
        hero = ""
        if with_images:
            hero = load_hero(case_id)
        cases.append({"case_id": case_id, "record": rec,
                      "provenance": data.get("provenance", {}),
                      "missing": data.get("missing", {}),
                      "narrative": data.get("narrative", {}),
                      "meta": data.get("_meta", {}),
                      "hero": hero})
    return cases


def load_hero(case_id: str) -> str:
    """Ảnh đại diện -> data URI (trang phải chạy được khi mở bằng file://)."""
    d = HERE / "assets" / case_id
    manifest = d / "images.json"
    if not manifest.exists():
        return ""
    try:
        items = json.loads(manifest.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return ""
    if isinstance(items, dict):
        # {"hero": {...}, "planning": {...}} — ưu tiên slot hero, sau đó tới slot bất kỳ
        items = ([items["hero"]] if isinstance(items.get("hero"), dict) else []) + \
                [v for k, v in items.items() if k != "hero" and isinstance(v, dict)]
    for item in items if isinstance(items, list) else []:
        name = item.get("file") if isinstance(item, dict) else item
        if not name:
            continue
        p = d / Path(str(name)).name
        if p.exists() and p.stat().st_size < 900_000:
            ext = p.suffix.lstrip(".").lower() or "jpeg"
            mime = "jpeg" if ext in ("jpg", "jpeg") else ext
            return f"data:image/{mime};base64," + base64.b64encode(p.read_bytes()).decode()
    return ""


TEMPLATE = """<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Khu đô thị sân bay — Cổng tra cứu benchmark</title>
<meta name="generator" content="mag-data-crawler / build_portal.py">
<style>
:root{
  --navy:#1f3864; --navy2:#2e5496; --ink:#1c2b3a; --muted:#5b6b85;
  --line:#d7dee9; --line2:#eaeff6; --bg:#eef1f6; --card:#fff;
  --yellow:#fff2cc; --yellowln:#e6d28a; --green:#f2f8ec; --green2:#eef6e6; --greenln:#a9d08e;
  --teal:#2e7d6b; --amber:#b8860b; --red:#b23c3c;
}
@media (prefers-color-scheme: dark){
  :root{--ink:#e8edf5; --muted:#9aa9c0; --line:#33405c; --line2:#26314a;
        --bg:#141b2b; --card:#1b2436; --yellow:#3a3520; --yellowln:#5a5230; --green:#1d2a22;
        --green2:#22301f; --greenln:#3f5f3a; --teal:#5fbfa4; --amber:#e0b451; --red:#e08585;}
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);line-height:1.55;
     font-family:"Segoe UI",-apple-system,BlinkMacSystemFont,Arial,Helvetica,sans-serif}
a{color:var(--navy2)}
header.top{background:linear-gradient(105deg,var(--navy),var(--navy2));color:#fff;padding:26px 20px 22px}
.wrap{max-width:1220px;margin:0 auto}
header.top h1{margin:0 0 6px;font-size:26px;font-weight:800;letter-spacing:.2px}
header.top p{margin:0;color:#cfe0f7;font-size:14px}
.stats{display:flex;flex-wrap:wrap;gap:10px;margin-top:16px}
.stat{background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.22);
      border-radius:8px;padding:7px 13px;font-size:13px}
.stat b{font-size:17px;display:block;line-height:1.25}
.toolbar{position:sticky;top:0;z-index:20;background:var(--card);border-bottom:1px solid var(--line);
         padding:12px 20px;box-shadow:0 2px 10px rgba(20,35,70,.06)}
.toolbar .wrap{display:flex;flex-wrap:wrap;gap:10px;align-items:center}
#q{flex:1 1 300px;min-width:220px;padding:10px 14px;font-size:15px;color:var(--ink);
   border:1px solid var(--line);border-radius:8px;background:var(--bg)}
#q:focus{outline:2px solid var(--navy2);outline-offset:1px}
select{padding:9px 11px;border:1px solid var(--line);border-radius:8px;background:var(--bg);
       color:var(--ink);font-size:14px}
.count{color:var(--muted);font-size:13px;margin-left:auto}
main{padding:22px 20px 60px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden;
      cursor:pointer;transition:transform .13s,box-shadow .13s;display:flex;flex-direction:column}
.card:hover,.card:focus-visible{transform:translateY(-3px);box-shadow:0 12px 28px rgba(20,35,70,.16);
      outline:none;border-color:var(--navy2)}
.card .thumb{height:118px;background:linear-gradient(120deg,var(--navy),var(--navy2));
      background-size:cover;background-position:center;display:flex;align-items:flex-end}
.card .thumb span{background:rgba(12,22,44,.62);color:#fff;font-size:12px;padding:4px 10px;
      border-radius:0 8px 0 0;font-weight:600}
.card .body{padding:13px 15px 15px;flex:1;display:flex;flex-direction:column;gap:9px}
.card h3{margin:0;font-size:16.5px;font-weight:750;color:var(--navy2)}
.card .sub{color:var(--muted);font-size:12.5px;margin:-4px 0 0}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:7px;margin-top:2px}
.kpi{background:var(--line2);border-radius:7px;padding:6px 7px;text-align:center}
.kpi b{display:block;font-size:14px;color:var(--navy2)}
.kpi span{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.02em;
      display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.chips{display:flex;flex-wrap:wrap;gap:5px}
.chip{background:var(--yellow);color:#5a4300;border-radius:999px;padding:2px 9px;font-size:11.5px}
.cov{margin-top:auto;display:flex;align-items:center;gap:8px;font-size:11.5px;color:var(--muted)}
.bar{flex:1;height:5px;background:var(--line2);border-radius:3px;overflow:hidden}
.bar i{display:block;height:100%;background:var(--teal)}
.empty{padding:50px 10px;text-align:center;color:var(--muted)}
/* modal */
.back{position:fixed;inset:0;background:rgba(10,18,36,.62);backdrop-filter:blur(3px);
      display:none;z-index:50;padding:26px 14px;overflow:auto}
.back.on{display:block}
.modal{max-width:980px;margin:0 auto;background:var(--card);border-radius:14px;overflow:hidden;
       box-shadow:0 26px 70px rgba(6,14,32,.5)}
.mhead{background:linear-gradient(105deg,var(--navy),var(--navy2));color:#fff;padding:18px 24px;
       display:flex;justify-content:space-between;gap:16px;align-items:flex-start;
       position:sticky;top:0;z-index:2}
.mhead h2{margin:0 0 3px;font-size:21px}
.mhead .msub{color:#cfe0f7;font-size:13px}
.x{background:rgba(255,255,255,.16);border:0;color:#fff;font-size:20px;line-height:1;
   width:34px;height:34px;border-radius:8px;cursor:pointer;flex:none}
.x:hover{background:rgba(255,255,255,.3)}
.tabs{display:flex;flex-wrap:wrap;gap:5px;padding:11px 20px;border-bottom:1px solid var(--line);
      background:var(--bg);position:sticky;top:69px;z-index:1}
.tab{border:1px solid var(--line);background:var(--card);color:var(--muted);border-radius:999px;
     padding:5px 12px;font-size:12.5px;cursor:pointer}
.tab.on{background:var(--navy2);border-color:var(--navy2);color:#fff;font-weight:600}
.mbody{padding:6px 24px 26px}
.sec{padding-top:18px}
.sec h4{margin:0 0 9px;font-size:15px;color:var(--navy2);display:flex;align-items:center;gap:8px}
.sec h4 em{font-style:normal;color:var(--muted);font-size:12px;font-weight:400}
/* hồ sơ: nhãn vàng bên trái | lời văn bên phải (giữ bố cục bản in cũ) */
.hero{margin:0;border-bottom:1px solid var(--line)}
.hero img{display:block;width:100%;max-height:270px;object-fit:cover}
.hero figcaption{padding:6px 24px;font-size:12px;color:var(--muted);font-style:italic;background:var(--bg)}
.rows{display:grid;grid-template-columns:186px 1fr}
.rows .lab{background:var(--yellow);color:var(--navy);font-weight:700;font-size:13.5px;
     padding:15px 16px;border-right:1px solid var(--yellowln);border-bottom:1px solid var(--line2)}
/* min-width:0 bắt buộc: nếu không, link nguồn dài sẽ nong cột 1fr và tràn khỏi modal */
.rows .cell{padding:15px 22px;border-bottom:1px solid var(--line2);font-size:14.5px;
     min-width:0;overflow-wrap:anywhere}
.rows .r2 .lab{background:var(--green2);border-right-color:var(--greenln)}
.rows .r2 .cell{background:var(--green)}
.rows .cell b{color:var(--navy2)}
.rows .cell .none{color:var(--muted)}
.srcline{margin-top:9px;font-size:12px;color:var(--muted);display:flex;flex-wrap:wrap;gap:4px 12px}
.srcline a{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:100%}
.kpirow{display:grid;grid-template-columns:repeat(auto-fit,minmax(104px,1fr));gap:8px;margin-top:12px}
.kpibox{border:1px solid var(--line);border-top:3px solid var(--teal);border-radius:6px;
     padding:8px 10px;background:var(--card)}
.kpibox b{display:block;font-size:17px;color:var(--navy2);line-height:1.25}
.kpibox b i{font-style:normal;font-size:10.5px;font-weight:600;color:var(--muted)}
.kpibox span{font-size:11.5px;color:var(--muted);display:block;margin-top:1px}
.foot{padding:14px 24px 4px;font-size:12px;color:var(--muted);border-top:2px solid var(--navy2);
     background:var(--bg);margin-top:18px}
table.f{width:100%;border-collapse:collapse;font-size:14px}
table.f td{border-bottom:1px solid var(--line2);padding:9px 10px;vertical-align:top}
table.f td.k{width:210px;color:var(--muted);font-size:13px}
table.f tr.none td{opacity:.55}
.val{font-weight:600}
.unit{color:var(--muted);font-weight:400;font-size:12.5px}
.badge{font-size:10px;text-transform:uppercase;letter-spacing:.04em;border-radius:4px;
       padding:1px 6px;margin-left:7px;vertical-align:middle;font-weight:700}
.b-high{background:#e3f3ec;color:var(--teal)} .b-medium{background:#fdf3dd;color:var(--amber)}
.b-low{background:#fbe6e6;color:var(--red)} .b-none{background:var(--line2);color:var(--muted)}
.src{display:block;margin-top:4px;font-size:12px;color:var(--muted)}
.src q{font-style:italic}
.miss{font-size:12.5px;color:var(--muted)}
@media (max-width:640px){
  table.f td.k{width:auto;display:block;padding-bottom:0;border:0}
  table.f td:not(.k){display:block;padding-top:2px}
  .tabs{top:0;position:static}
}
</style>
</head>
<body>
<header class="top"><div class="wrap">
  <h1>Khu đô thị sân bay — Cổng tra cứu benchmark</h1>
  <p>Dữ liệu crawl từ nguồn chính thức, trích bằng LLM theo <code>features/ws1_airport/schema.json</code>. Bấm vào một khu để xem chi tiết từng trường kèm nguồn.</p>
  <div class="stats" id="stats"></div>
</div></header>

<div class="toolbar"><div class="wrap">
  <input id="q" type="search" placeholder="Tìm theo tên, quốc gia, sân bay, phân khu, định vị…" autocomplete="off">
  <select id="country"><option value="">Mọi quốc gia</option></select>
  <select id="sort">
    <option value="cov">Sắp xếp: Độ phủ dữ liệu ↓</option>
    <option value="pax">Hành khách ↓</option>
    <option value="area">Diện tích ↓</option>
    <option value="name">Tên A→Z</option>
  </select>
  <span class="count" id="count"></span>
</div></div>

<main><div class="wrap"><div class="grid" id="grid"></div><div class="empty" id="empty" hidden>Không có khu đô thị nào khớp từ khoá.</div></div></main>

<div class="back" id="back" role="dialog" aria-modal="true"><div class="modal" id="modal"></div></div>

<script>
const SCHEMA = __SCHEMA__;
const CASES  = __DATA__;
const FLAGS  = __FLAGS__;
const CARD_KPIS = __KPIS__;

const $ = s => document.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const isEmpty = v => v === null || v === undefined || v === "" ||
                     (Array.isArray(v) && !v.length) || (typeof v === "object" && !Array.isArray(v) && !Object.keys(v).length);

function fmt(v, unit){
  if (isEmpty(v)) return "";
  if (Array.isArray(v)) return v.map(esc).join(" · ");
  if (typeof v === "object") {
    const p = [];
    if (v.min != null) p.push("từ " + v.min);
    if (v.max != null) p.push("đến " + v.max);
    if (v.count != null) p.push("(" + v.count + " chào giá)");
    return p.length ? esc(p.join(" ")) : esc(JSON.stringify(v));
  }
  if (typeof v === "boolean") return v ? "Có" : "Không";
  if (typeof v === "number") return esc(v.toLocaleString("vi-VN"));
  return esc(v);
}
const short = n => n == null ? "—" :
  n >= 1e9 ? (n/1e9).toFixed(1)+" tỷ" : n >= 1e6 ? (n/1e6).toFixed(1)+"tr" :
  n >= 1e3 ? (n/1e3).toFixed(0)+"k" : String(Math.round(n*10)/10);

// gộp mọi giá trị của case thành một chuỗi để tìm kiếm
CASES.forEach(c => {
  const r = c.record;
  c.blob = Object.values(r).map(v => Array.isArray(v) ? v.join(" ") :
           (v && typeof v === "object") ? JSON.stringify(v) : String(v ?? "")).join(" ").toLowerCase();
  c.cov = c.meta && c.meta.coverage_pct != null ? c.meta.coverage_pct :
          Math.round(100 * Object.values(r).filter(v => !isEmpty(v)).length / SCHEMA.nfields);
});

function statBar(){
  const avg = CASES.reduce((s,c)=>s+c.cov,0) / (CASES.length||1);
  const pax = CASES.reduce((s,c)=>s+(c.record.passengers_million||0),0);
  const countries = new Set(CASES.map(c=>c.record.country).filter(Boolean)).size;
  $("#stats").innerHTML = [
    [CASES.length, "khu đô thị sân bay"], [countries, "quốc gia"],
    [SCHEMA.nfields, "trường / khu"], [avg.toFixed(0)+"%", "độ phủ dữ liệu"],
    [pax.toFixed(0)+" tr", "hành khách/năm (cộng dồn)"]
  ].map(([v,l]) => `<div class="stat"><b>${esc(v)}</b>${esc(l)}</div>`).join("");
}

function cardHTML(c, i){
  const r = c.record;
  const flag = FLAGS[r.country] || "🌐";
  const kpis = CARD_KPIS.map(([f,label,suf]) => {
    const v = r[f];
    const txt = isEmpty(v) ? "—" : Array.isArray(v) ? v.length : short(typeof v === "number" ? v : parseFloat(v));
    return `<div class="kpi"><b>${esc(txt)}${txt!=="—"&&suf?" "+esc(suf):""}</b><span>${esc(label)}</span></div>`;
  }).join("");
  const chips = (r.subzones||[]).slice(0,3).map(s=>`<span class="chip">${esc(s)}</span>`).join("")
    + ((r.subzones||[]).length>3 ? `<span class="chip">+${r.subzones.length-3}</span>` : "");
  const thumb = c.hero ? `style="background-image:url('${c.hero}')"` : "";
  return `<article class="card" tabindex="0" data-i="${i}">
    <div class="thumb" ${thumb}><span>${flag} ${esc(r.country||"")}</span></div>
    <div class="body">
      <h3>${esc(r.case_name || c.case_id)}</h3>
      <p class="sub">${esc(r.airport_name||"")}${r.reference_city?" · "+esc(r.reference_city):""}</p>
      <div class="kpis">${kpis}</div>
      <div class="chips">${chips}</div>
      <div class="cov"><span>Độ phủ</span><span class="bar"><i style="width:${c.cov}%"></i></span><b>${c.cov}%</b></div>
    </div></article>`;
}

let view = [];
function render(){
  const q = $("#q").value.trim().toLowerCase();
  const country = $("#country").value, sort = $("#sort").value;
  view = CASES.filter(c => (!country || c.record.country === country) &&
                           (!q || q.split(/\\s+/).every(t => c.blob.includes(t))));
  const num = (c,f) => c.record[f] == null ? -1 : c.record[f];
  view.sort((a,b) => sort === "pax" ? num(b,"passengers_million")-num(a,"passengers_million")
    : sort === "area" ? num(b,"area_km2")-num(a,"area_km2")
    : sort === "cov" ? b.cov-a.cov
    : String(a.record.case_name||"").localeCompare(String(b.record.case_name||""), "vi"));
  $("#grid").innerHTML = view.map((c,i)=>cardHTML(c,i)).join("");
  $("#empty").hidden = view.length > 0;
  $("#count").textContent = `${view.length}/${CASES.length} khu`;
}

function rowHTML(c, f){
  const v = c.record[f.name];
  const p = c.provenance[f.name] || {};
  const label = `<td class="k">${esc(f.label)}${f.unit?` <span class="unit">(${esc(f.unit)})</span>`:""}</td>`;
  if (isEmpty(v)){
    const why = c.missing[f.name] || "không có trong nguồn đã crawl";
    return `<tr class="none">${label}<td><span class="miss">— <span class="badge b-none">thiếu</span> ${esc(why)}</span></td></tr>`;
  }
  const conf = p.confidence || "medium";
  let src = "";
  if (p.source_url) src = `<a href="${esc(p.source_url)}" target="_blank" rel="noopener">${esc(p.source_name || p.source_url)}</a>`;
  else if (p.source === "baseline") src = "trích tự động (regex) — chưa đối chiếu LLM";
  else if (p.source) src = esc(p.source);
  const snip = p.snippet ? ` <q>${esc(p.snippet)}</q>` : "";
  const CONF_VI = {high: "tin cậy cao", medium: "tin cậy vừa", low: "tin cậy thấp"};
  return `<tr>${label}<td><span class="val">${fmt(v, f.unit)}</span>
     <span class="badge b-${esc(conf)}">${esc(CONF_VI[conf] || conf)}</span>
     ${src||snip ? `<span class="src">${src}${snip}</span>` : ""}</td></tr>`;
}

// **in đậm** -> <b>, sau khi đã escape HTML
const bold = s => esc(s).replace(/\\*\\*(.+?)\\*\\*/g, "<b>$1</b>");

// Đơn vị đầy đủ quá dài cho ô KPI hẹp -> rút gọn, giữ nghĩa
const UNIT_SHORT = {"triệu khách/năm":"tr/năm", "triệu tấn/năm":"tr tấn/năm", "lượt/năm":"lượt/năm",
  "điểm đến":"", "hãng":"", "công ty":"", "toà":"", "người":"", "việc làm":"", "km²":"km²", "ha":"ha", "%":"%"};

// KPI hiện thành dải ô trong mục "Chỉ số quy mô", giống bản hồ sơ in
function kpiRow(c){
  const r = c.record;
  const boxes = SCHEMA.groups.find(g=>g.id==="kpi").fields
    .filter(f => !isEmpty(r[f.name]))
    .map(f => {
      const u = f.unit ? (UNIT_SHORT[f.unit] ?? f.unit) : "";
      return `<div class="kpibox"><b>${fmt(r[f.name])}${u?` <i>${esc(u)}</i>`:""}</b>`
           + `<span>${esc(f.label)}</span></div>`;
    });
  return boxes.length ? `<div class="kpirow">${boxes.join("")}</div>` : "";
}

// mỗi mục kết bằng danh sách nguồn của các trường trong mục đó (khỏi lặp ⓘ giữa câu)
function groupSources(c, g){
  const seen = new Map();
  g.fields.forEach(f => {
    const p = c.provenance[f.name];
    if (p && p.source_url && !seen.has(p.source_url)) seen.set(p.source_url, p.source_name || p.source_url);
  });
  if (!seen.size) return "";
  return `<div class="srcline">ⓘ ` + [...seen].map(([u,n]) =>
    `<a href="${esc(u)}" target="_blank" rel="noopener">${esc(n).slice(0,52)}</a>`).join("") + `</div>`;
}

function profileHTML(c){
  const r = c.record, nar = c.narrative || {};
  const rows = SCHEMA.groups.map((g, i) => {
    const filled = g.fields.filter(f => !isEmpty(r[f.name])).length;
    if (!filled) return "";
    const para = nar[g.id]
      ? `<p style="margin:0">${bold(nar[g.id])}</p>`
      : `<p class="none" style="margin:0">Chưa có lời văn tóm tắt — xem tab “Chi tiết trường”.</p>`;
    return `<div class="r${i%2?2:1}" style="display:contents">
      <div class="lab">${g.icon||""} ${esc(g.label)}</div>
      <div class="cell">${para}${g.id==="kpi"?kpiRow(c):""}${groupSources(c,g)}</div></div>`;
  }).join("");
  const hero = c.hero ? `<figure class="hero"><img src="${c.hero}" alt="">
      <figcaption>${esc(r.case_name||c.case_id)} — ảnh minh hoạ thu từ trang nguồn đã crawl</figcaption></figure>` : "";
  const m = c.meta || {};
  const foot = `<div class="foot"><b>Nguồn:</b> ${m.dossier?.pages_total||"?"} trang đã crawl ·
      ${m.fields_filled||0}/${m.fields_total||SCHEMA.nfields} trường có dữ liệu ·
      ${m.high_confidence||0} trường tin cậy cao · ${Object.keys(c.missing||{}).length} trường thiếu kèm lý do.
      Trích tự động bằng ${esc(m.model||"LLM")}${m.generated_at?` lúc ${esc(String(m.generated_at).slice(0,16).replace("T"," "))}`:""}.</div>`;
  return hero + `<div class="rows">${rows}</div>` + foot;
}

function openCase(i){
  const c = view[i]; if (!c) return;
  const r = c.record;
  const secs = SCHEMA.groups.map(g => {
    const filled = g.fields.filter(f => !isEmpty(r[f.name])).length;
    return `<section class="sec" data-g="${esc(g.id)}" hidden>
      <h4>${g.icon||""} ${esc(g.label)} <em>${filled}/${g.fields.length} trường</em></h4>
      <table class="f"><tbody>${g.fields.map(f=>rowHTML(c,f)).join("")}</tbody></table></section>`;
  }).join("");
  const tabs = `<button class="tab on" data-g="profile">📋 Hồ sơ</button>` +
    `<button class="tab" data-g="all">Chi tiết trường</button>` +
    SCHEMA.groups.map(g=>`<button class="tab" data-g="${esc(g.id)}">${g.icon||""} ${esc(g.label)}</button>`).join("");
  const meta = c.meta || {};
  $("#modal").innerHTML = `
    <div class="mhead">
      <div><h2>${esc(r.case_name||c.case_id)}</h2>
        <div class="msub">${FLAGS[r.country]||"🌐"} ${esc(r.country||"")} · ${esc(r.airport_name||"")}
          ${r.official_website?` · <a href="${esc(r.official_website)}" target="_blank" rel="noopener" style="color:#fff">website</a>`:""}
          · độ phủ ${c.cov}%${meta.model?` · model ${esc(meta.model)}`:""}</div></div>
      <button class="x" id="close" aria-label="Đóng">✕</button>
    </div>
    <div class="tabs">${tabs}</div>
    <div class="mbody"><div id="profile">${profileHTML(c)}</div>${secs}</div>`;
  $("#back").classList.add("on");
  document.body.style.overflow = "hidden";
  $("#close").focus();
}

function closeModal(){
  $("#back").classList.remove("on");
  document.body.style.overflow = "";
}

$("#grid").addEventListener("click", e => {
  const card = e.target.closest(".card"); if (card) openCase(+card.dataset.i);
});
$("#grid").addEventListener("keydown", e => {
  if ((e.key === "Enter" || e.key === " ") && e.target.closest(".card")){
    e.preventDefault(); openCase(+e.target.closest(".card").dataset.i);
  }
});
$("#modal").addEventListener("click", e => {
  if (e.target.id === "close") return closeModal();
  const tab = e.target.closest(".tab"); if (!tab) return;
  document.querySelectorAll(".tab").forEach(t => t.classList.toggle("on", t === tab));
  const g = tab.dataset.g;
  $("#profile").hidden = g !== "profile";
  document.querySelectorAll(".sec").forEach(s =>
    s.hidden = g === "profile" || (g !== "all" && s.dataset.g !== g));
});
$("#back").addEventListener("click", e => { if (e.target.id === "back") closeModal(); });
document.addEventListener("keydown", e => {
  if (e.key === "Escape") closeModal();
  if (e.key === "/" && document.activeElement !== $("#q")){ e.preventDefault(); $("#q").focus(); }
});
$("#q").addEventListener("input", render);
$("#country").addEventListener("change", render);
$("#sort").addEventListener("change", render);

[...new Set(CASES.map(c=>c.record.country).filter(Boolean))].sort().forEach(c => {
  const o = document.createElement("option"); o.value = o.textContent = c; $("#country").append(o);
});
statBar(); render();
</script>
</body>
</html>
"""


def main() -> None:
    ap = argparse.ArgumentParser(description="Sinh cổng tra cứu tất cả KĐT sân bay")
    ap.add_argument("--out", type=Path, default=HERE / "index.html")
    ap.add_argument("--no-images", action="store_true", help="bỏ ảnh hero cho file nhẹ")
    args = ap.parse_args()

    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    cases = load_cases(not args.no_images)
    if not cases:
        raise SystemExit(f"Không thấy feature nào trong {FEATURES}")

    slim = {"groups": [{"id": g["id"], "label": g["label"], "icon": g.get("icon", ""),
                        "fields": [{"name": f["name"], "label": f["label"], "type": f["type"],
                                    "unit": f.get("unit", "")} for f in g["fields"]]}
                       for g in schema["groups"]],
            "nfields": sum(len(g["fields"]) for g in schema["groups"])}

    html = (TEMPLATE
            .replace("__SCHEMA__", json.dumps(slim, ensure_ascii=False))
            .replace("__DATA__", json.dumps(cases, ensure_ascii=False))
            .replace("__FLAGS__", json.dumps(FLAGS, ensure_ascii=False))
            .replace("__KPIS__", json.dumps(CARD_KPIS, ensure_ascii=False)))
    args.out.write_text(html, encoding="utf-8")

    def coverage(c: dict) -> float:
        if c["meta"].get("coverage_pct") is not None:
            return float(c["meta"]["coverage_pct"])
        filled = sum(1 for v in c["record"].values() if v not in (None, "", [], {}))
        return 100 * filled / slim["nfields"]

    avg = sum(coverage(c) for c in cases) / len(cases)
    n_hero = sum(1 for c in cases if c["hero"])
    shown = args.out.relative_to(ROOT) if args.out.resolve().is_relative_to(ROOT) else args.out
    print(f"[ok] {shown}  ({args.out.stat().st_size/1024:.0f} KB)")
    print(f"     {len(cases)} case · {slim['nfields']} trường/case · độ phủ TB {avg:.1f}% · {n_hero} ảnh hero")


if __name__ == "__main__":
    main()
