# SKILL — Pipeline một case aerotropolis: `refer_file` → trang HTML

> Meta-skill cấp repo. Ba skill con đã có mô tả **từng khối**
> ([`agent_extractor/SKILL.md`](agent_extractor/SKILL.md) · [`html/SKILL.md`](html/SKILL.md));
> file này mô tả **toàn tuyến**: từ lúc đã có bảng nguồn `refer_file/<case>.txt`
> cho tới khi mở được `html/<case>.html`.
>
> Đọc kèm: [`features/ws1_airport/feature_spec.md`](features/ws1_airport/feature_spec.md)
> (mục "Schema thực thi v2") — đó là hợp đồng về tên trường.

## Điều kiện vào / ra

| | Nội dung |
|---|---|
| **Vào** | `refer_file/aerotropolis.txt` — danh mục case ứng viên · `features/ws1_airport/feature_spec.md` — bộ trường cần phủ · *(sinh ở Pha −1)* `refer_file/<case>.txt` — bảng markdown, mỗi dòng 1 nguồn, có link `[tên](url)` và cột ghi chú ngay sau link · `html/vi_text.json` — bản dịch tiếng Việt (biên soạn ở Pha 6b) |
| **Ra** | `html/<case>.html` + `html/index.html` — trang 2 slide tiếng Việt, tự chứa, mở bằng `file://` |
| **Phụ phẩm** | `raw/<case>/pages/*` · `raw/<case>/manifest.json` · `raw/<case>/crawl_log.csv` · `features/<case>_airport_city.json` · `features/airport_city_benchmark.{csv,jsonl}` · `html/assets/<case>/*` |

Toàn tuyến 9 pha. **Pha −1 là nghiên cứu nguồn** (chọn case, tìm link, viết bảng).
**Pha 0–2 là cơ khí** (chạy lệnh, đọc log). **Pha 3–5 là phần agent phải suy nghĩ**
(viết regex bám ngôn ngữ của website case đó). **Pha 6–8 là trình bày + nghiệm thu.**

```
refer_file/aerotropolis.txt  +  features/ws1_airport/feature_spec.md
   │ [Pha −1] chọn case chưa làm → tìm nguồn phủ đủ trường → viết bảng
   ▼
refer_file/<case>.txt
   │ [Pha 0] kiểm định dạng bảng
   │ [Pha 1] crawl_sources.py ──▶ raw/<case>/pages/*.txt + manifest + crawl_log
   │ [Pha 2] nghiệm thu raw (đọc log, xử lý trang fail)
   │ [Pha 3] khai báo REGISTRY[<case>]
   │ [Pha 4] đọc .txt thật → viết/chỉnh pattern trích xuất
   │ [Pha 5] extract_airport_city.py ──▶ <case>_airport_city.json (+ benchmark)
   │ [Pha 6] tổng quát hoá lời văn trong build_html.py (bỏ câu riêng Schiphol)
   │ [Pha 7] harvest_images.py ──▶ assets/<case>/
   │ [Pha 8] build_html.py ──▶ html/<case>.html   +   checklist nghiệm thu
   ▼
```

---

## Pha −1 — Dựng `refer_file/<case>.txt`

**Mục tiêu tìm kiếm không phải "tìm ít trang nói về dự án", mà là _phủ đủ bộ trường
trong_** [`features/ws1_airport/feature_spec.md`](features/ws1_airport/feature_spec.md).
Spec là đề bài; mỗi nguồn đưa vào bảng phải trả lời được ít nhất một nhóm trường.
Trường không nguồn nào nói ⇒ sẽ là `null` ở Pha 5 — đó là kết quả hợp lệ, nhưng
phải là do **nguồn thật sự không công bố**, không phải do lười tìm.

### −1.1 Chọn case & chống trùng *(làm TRƯỚC khi tìm kiếm)*

Danh mục ứng viên: [`refer_file/aerotropolis.txt`](refer_file/aerotropolis.txt)
(tên · quốc gia · sân bay trung tâm · đặc điểm). Case đã làm nằm ở **ba nơi** và
phải khớp nhau — kiểm cả ba, đừng chỉ nhìn thư mục `refer_file/`:

```bash
python - <<'EOF'
import json, re, sys; from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
done = {p.stem.lower() for p in Path("refer_file").glob("*.txt")} - {"aerotropolis"}
reg = re.findall(r'^\s{4}"([a-z_0-9]+)":\s*\{',
     Path("agent_extractor/ws1_airport/extract_airport_city.py").read_text(encoding="utf-8"), re.M)
b = Path("raw_data/output/ws1_airport/features/airport_city_benchmark.jsonl")
names = [json.loads(l)["case_name"] for l in b.read_text(encoding="utf-8").splitlines() if l.strip()] if b.exists() else []
print("refer_file:", sorted(done), "\nREGISTRY  :", reg, "\nbenchmark :", names)
for r in Path("refer_file/aerotropolis.txt").read_text(encoding="utf-8").splitlines():
    if not r.startswith("|") or "**" not in r: continue
    c = [x.strip() for x in r.split("|")]; name = c[2].replace("**","")
    key = re.split(r"[/–-]", name)[0].strip().lower().split()[0]
    print(f"  [{'ĐÃ LÀM' if any(key in d or d in key for d in done) else '  --  '}] {name[:46]:48} {c[3]}")
EOF
```

Lệch nhau nghĩa là có case làm dở (vd có `refer_file` nhưng chưa có `REGISTRY`) —
xử lý case dở đó trước khi mở case mới. Case mới thì **thêm dòng vào
`aerotropolis.txt`** trước, để lần sau vẫn chống trùng được.

`<case>` = một từ, không dấu, `snake_case`, dùng **xuyên suốt 4 lệnh** của pipeline
(`incheon`, `taoyuan`, `western_sydney`). Đặt tên file `refer_file/<case>.txt` đúng
bằng `<case>`.

### −1.2 Bản đồ trường → loại trang cần tìm

Dùng bảng này làm danh sách săn nguồn. Cột "truy vấn mẫu" ghép thêm tên dự án.

| Nhóm trường trong spec | Loại trang cần có | Truy vấn mẫu | ⭐ |
|---|---|---|---|
| `passengers_million` · `cargo_million_tonnes` · `air_movements` · `destinations` · `airlines` · `transfer_pct` | **Trang số liệu chính chủ**: "Facts & Figures", "At a Glance", "Statistics", báo cáo thường niên | `<sân bay> facts and figures statistics` | ⭐⭐⭐⭐⭐ |
| đối chiếu chéo các KPI trên | Wikipedia trang sân bay (infobox có số sạch, dễ regex) | `<sân bay> wikipedia` | ⭐⭐⭐⭐ |
| `positioning` · `planning_concept` · `cornerstones` · `subzones` · `area_km2` | Trang **quy hoạch / masterplan / about the project** của chủ đầu tư hoặc cơ quan quy hoạch | `<dự án> master plan precincts zones` | ⭐⭐⭐⭐⭐ |
| `investor_governance` · `lead_developer` · `brand_partners` | Trang **cơ quan quản lý / ban quản lý dự án** ("About us", "Authority") | `<dự án> development authority about` | ⭐⭐⭐⭐⭐ |
| `total_investment_usd` · `jobs_created` · `development_context` | **Thông cáo chính phủ** (chính phủ, bộ, chính quyền bang/thành phố) | `<dự án> investment billion jobs government` | ⭐⭐⭐⭐⭐ |
| `economic_zone_name` · `economic_zone_year` · `logistics_park_ha` | Trang **đặc khu / khu phi thuế quan / logistics park** | `<dự án> free trade zone logistics park` | ⭐⭐⭐⭐ |
| `commercial_re` · `num_office_buildings` · `num_companies_realestate` · `office_rent_eur_m2_year` · `cvp_price` | Trang **bất động sản / cho thuê / offering** | `<dự án> real estate office space for lease` | ⭐⭐⭐⭐ |
| `residential_product_desc` · `basic_amenities` · `highlight_amenities` · `cvp_experience` | Trang **tiện ích / khu ở / dự án điểm nhấn** | `<dự án> housing amenities facilities` | ⭐⭐⭐⭐ |
| `rail_connections` · `metro_lines` · `cvp_convenience` · `connection_modes` | Trang **đơn vị vận hành đường sắt/metro** hoặc trang hướng dẫn đi lại | `<sân bay> airport rail link metro travel time` | ⭐⭐⭐⭐⭐ |
| `vision_label` · `vision_qualities` · `sustainability` · `aviation_policy` | Trang **tầm nhìn / chiến lược / ESG** | `<dự án> vision strategy ESG sustainability` | ⭐⭐⭐⭐ |
| `founded_year` · `airport_build_period` · `urban_build_period` | Trang **lịch sử** hoặc mốc khai trương | `<sân bay> history opened timeline` | ⭐⭐⭐ |
| `reference_city` · bối cảnh đô thị | Trang **chính quyền thành phố tham chiếu** | `<thành phố> official english site` | ⭐⭐⭐ |

**Quy tắc chấm sao** — sao quyết định điều kiện chốt Pha 2 ("mọi nguồn ⭐⭐⭐⭐⭐ đều
phải crawl ok"), nên đừng rải sao bừa:

- ⭐⭐⭐⭐⭐ — **nguồn chuẩn duy nhất** cho một nhóm trường. Chết là phải tìm thay thế
  trước khi đi tiếp. Đây cũng là trang sẽ được trỏ bằng `prefer=` ở Pha 4.
- ⭐⭐⭐⭐ — nguồn tốt, có thể đối chiếu chéo hoặc bổ sung.
- ⭐⭐⭐ — nền/bối cảnh. Chết thì chấp nhận được.

**Ngưỡng phủ:** mỗi nhóm trường ≥ 1 nguồn; tổng thường **18–21 nguồn**. Ít hơn ~12
thì gần như chắc chắn sẽ thủng nhiều trường ở Pha 5.

### −1.3 Ưu tiên & tránh nguồn

- **Bản EN của trang chính chủ** trước tiên (§ 4.4). Trang song ngữ thường có
  `/en/`, `/eng/`, `english.` — thử đổi tiền tố trước khi bỏ cuộc.
- **Ưu tiên trang có số nằm trong câu văn**, tránh trang mà số chỉ hiện trong biểu
  đồ hoặc bảng dựng bằng JS — extractor chỉ đọc `.txt`, không đọc được canvas.
- **PDF được** (crawler bóc bằng PyMuPDF) — hợp cho precinct plan, báo cáo thường niên.
- **Không** dùng nguồn sau paywall/đăng nhập (vi phạm contract "crawl hợp pháp").
- Anchor `[tên]` phải **ngắn và không trùng nhau sau khi cắt 50 ký tự** — nó thành
  tên file. Đừng để hai dòng cùng mở đầu bằng một chuỗi dài giống nhau.

### −1.4 Thử nguồn sống TRƯỚC khi chốt bảng

Lỗi hay gặp nhất là chốt xong bảng mới phát hiện site chặn bot — mất cả một vòng
crawl. Thử trước bằng chính crawler, dưới một tên case tạm:

```bash
# file tạm chỉ chứa các URL nghi ngờ, đúng định dạng bảng
python raw_data/crawler/crawl_sources.py --name _probe --input <file tạm> --no-shots --timeout 60
rm -rf raw_data/output/ws1_airport/raw/_probe
```

| Kết quả | Nghĩa | Xử lý |
|---|---|---|
| `200` + vài nghìn ký tự | Dùng được | Đưa vào bảng |
| `200` nhưng < 1.500 ký tự | Nội dung dựng bằng JS sau khi tải | Tăng `--timeout`, hoặc tìm subpage tĩnh |
| `403` | Chặn bot ở tầng CDN | Thử `--headful`; **không được thì đổi nguồn khác cùng nội dung** |
| `ERR_HTTP2_PROTOCOL_ERROR` | Site không chịu HTTP/2 của Chromium | Đổi nguồn |

Đã gặp thật: `taoyuan-aerotropolis.com`, `topics.amcham.com.tw`, `wsiairport.com.au`
chặn 403 kể cả `--headful`; `westernsydneyairport.gov.au` và `infrastructure.gov.au`
lỗi HTTP/2. Cả bốn đều phải thay bằng nguồn khác cùng nội dung.

### −1.5 Viết bảng

Header 3 dòng tự do (tên case · đặc thù · ghi chú nguồn chặn), rồi bảng 5 cột:

```
Case: <Tên đầy đủ> (<Quốc gia>) — sân bay <Tên sân bay>
Đặc thù: <1–2 câu: mô hình quản trị, cấu trúc phân khu — thứ khiến case này khác các case khác>
Nguồn đã fetch xác minh <ngày>. Ghi chú: <site nào cần Playwright / bị chặn / đã thay>

| #      | Website / nguồn | Tiêu chí trong benchmark | Có thể lấy dữ liệu gì? | Mức độ ưu tiên |
| ------ | --------------- | ------------------------ | ---------------------- | -------------- |
| **1**  | [Anchor ngắn](https://…) | **Nhóm trường** | `field_a`, `field_b`: giá trị kỳ vọng cụ thể… | ⭐⭐⭐⭐⭐ |
```

Hai cột quyết định chất lượng cả pipeline:

- **Cột 3 "Tiêu chí"** = ô ngay sau ô chứa link ⇒ parser lấy làm `purpose`. Không
  được rỗng.
- **Cột 4 "Có thể lấy dữ liệu gì?"** — ghi **tên trường trong spec + giá trị kỳ vọng
  đã đọc được từ trang**. Pha 4 dùng cột này làm danh sách việc, Pha 5 dùng nó để
  phán đoán trường `null` nào là chính đáng. Ghi `logistics_park_ha: 45 ha` hữu ích
  gấp nhiều lần ghi "thông tin logistics".

Ghi giá trị kỳ vọng có nghĩa là **phải mở trang ra đọc trước khi đưa vào bảng** —
đúng tinh thần "không đoán" của Pha 4. Không đọc thì sẽ đưa vào những trang nghe
tên có vẻ đúng nhưng không chứa số nào.

**Chốt Pha −1 khi:** mọi nhóm trường ở bảng −1.2 có ≥1 nguồn, mọi nguồn ⭐⭐⭐⭐⭐ đã
thử sống, và mỗi dòng đều có cột 4 ghi tên trường cụ thể. Rồi sang Pha 0.

---

## Pha 0 — Kiểm định dạng `refer_file`

**Mục đích:** bảo đảm parser đọc được trước khi mở trình duyệt (crawl tốn vài phút/trang).

Parser là `parse_input()` trong [`raw_data/crawler/crawl_sources.py:61`](raw_data/crawler/crawl_sources.py#L61).
Luật thực tế của nó:

1. Duyệt **từng dòng**; dòng nào không khớp `[text](http…)` thì **bỏ qua** — nên
   header, dòng kẻ `|---|`, ghi chú tự do đều an toàn.
2. `anchor` = text trong `[...]` → dùng làm **slug tên file** (`slugify`: hạ chữ
   thường, ký tự lạ → `_`, cắt 50 ký tự). ⇒ anchor phải **ngắn, không trùng nhau**.
3. `purpose` = **ô ngay sau ô chứa link**, đã bỏ `**` và backtick.
4. URL bị **strip tham số `utm_*`** (`clean_url`) trước khi so trùng.
5. File `.csv` cũng đọc được: cần cột `website_url`/`url`, tuỳ chọn `name`, `purpose`.

**Kiểm nhanh (không crawl):**

```bash
python - <<'EOF'
import re, sys; from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
rows = []
for line in Path("refer_file/<case>.txt").read_text(encoding="utf-8").splitlines():
    m = LINK.search(line)
    if not m: continue
    cells = [c.strip() for c in line.split("|")]
    i = next((i for i, c in enumerate(cells) if "](" in c), None)
    purpose = re.sub(r"\*\*|`", "", cells[i+1]).strip() if i is not None and i+1 < len(cells) else ""
    rows.append((m.group(1), m.group(2), purpose))
print("rows:", len(rows), "| unique url:", len({r[1] for r in rows}))
for a, u, p in rows:
    if not p: print("  [THIẾU purpose]", a)
EOF
```

**Chốt pha 0 khi:** số dòng đúng như bảng, không URL trùng, không dòng thiếu
`purpose`, anchor không trùng nhau.

---

## Pha 1 — Crawl nguồn

```bash
python raw_data/crawler/crawl_sources.py --name <case> --input refer_file/<case>.txt
```

Cờ: `--fresh` (bỏ data cũ, crawl lại từ đầu) · `--no-shots` (không chụp ảnh, nhanh
hơn ~30%) · `--headful` (mở trình duyệt để xem) · `--timeout N` (mặc định 40s).

**Cần biết về hành vi:**

- **Mặc định APPEND.** Có `manifest.json` rồi thì chỉ crawl URL mới, đánh số tiếp
  từ `idx` lớn nhất. Bổ sung nguồn = thêm dòng vào `refer_file` rồi chạy lại lệnh
  cũ — data cũ giữ nguyên. Đây là cách Schiphol đi từ 10 → 29 nguồn.
- **Chỉ dùng `--fresh` khi** đổi hẳn danh sách nguồn hoặc nghi ngờ bản crawl cũ hỏng.
  `--fresh` **không xoá file cũ trong `pages/`**, chỉ ghi lại manifest từ đầu — file
  mồ côi của lần trước vẫn nằm đó và **extractor vẫn đọc** (nó `glob("*.txt")`, không
  đọc manifest để lọc). Muốn sạch thì xoá tay thư mục `raw/<case>/` trước.
- Mỗi nguồn sinh 3 file: `.html` (đã render) · `.txt` (text sạch — **extractor chỉ
  đọc file này**) · `.png` (screenshot full-page).
- PDF: tải bằng `ctx.request.get`, bóc text bằng PyMuPDF, lưu `.pdf` + `.txt`, **không
  có screenshot**.
- Trang render bằng Chromium thật, cuộn 4 lần × 2200px để kích lazy-load, chờ
  `networkidle` tối đa 8s.

**Phụ thuộc** (thiếu là crash ngay): `playwright` + `python -m playwright install chromium`,
`pymupdf`, `beautifulsoup4`. Ba gói đầu **chưa có trong `requirements.txt`**.

---

## Pha 2 — Nghiệm thu raw

Đọc `raw_data/output/ws1_airport/raw/<case>/crawl_log.csv`. Cột đáng nhìn:
`status`, `http_status`, `chars`, `error`.

```bash
python - <<'EOF'
import csv, sys; from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
rows = list(csv.DictReader(Path("raw_data/output/ws1_airport/raw/<case>/crawl_log.csv").open(encoding="utf-8")))
ok = [r for r in rows if r["status"] == "ok"]
print(f"tổng {len(rows)} | ok {len(ok)} | tổng ký tự {sum(int(r['chars'] or 0) for r in ok):,}")
for r in rows:
    if r["status"] != "ok" or int(r["chars"] or 0) < 1500:
        print(f"  ⚠ #{r['idx']:>2} {r['status']:<10} {r['chars']:>7} ký tự  {r['anchor'][:40]}  {r['error'][:60]}")
EOF
```

**Ngưỡng phán đoán:**

| Triệu chứng | Nghĩa là | Xử lý |
|---|---|---|
| `status=ok` nhưng `chars` < 1.500 | Trang JS nặng, render chưa kịp / bị tường cookie | Tăng `--timeout 60`; nếu vẫn thấp thì tìm URL thay thế (bản in, subpage tĩnh) |
| `http_error` 403 | Chặn bot | Thử lại `--headful`; không được thì đổi nguồn khác cùng nội dung |
| `timeout` | Mạng hoặc trang treo | Chạy lại (append sẽ chỉ lấy trang thiếu) |
| `error` bắt đầu bằng `shot:` | Chỉ lỗi screenshot | **Bỏ qua** — `.txt` vẫn có, extractor không cần ảnh |

**Quy tắc: không sửa file trong `raw/`.** Muốn đổi nội dung thì đổi nguồn rồi crawl lại.

**Chốt pha 2 khi:** tỷ lệ ok ≥ ~85% và **mọi nguồn đánh ⭐⭐⭐⭐⭐ trong `refer_file`
đều ok**. Một nguồn ⭐⭐⭐ chết thì chấp nhận được; nguồn "Facts & Figures" chết thì phải
tìm thay thế trước khi sang pha 3, vì đó là nguồn chuẩn cho các chỉ số headline.

---

## Pha 3 — Khai báo định danh case

Trong [`agent_extractor/ws1_airport/extract_airport_city.py:34`](agent_extractor/ws1_airport/extract_airport_city.py#L34),
thêm một entry vào `REGISTRY`:

```python
"<case>": {
    "case_name":        "...",   # tên hiển thị, cũng là KHOÁ trong benchmark.jsonl
    "aerotropolis":     "...",   # tên đầy đủ / tên gọi khác
    "country":          "...",   # TIẾNG VIỆT — phải khớp key trong FLAGS của build_html.py
    "is_target":        False,   # True chỉ dành cho Gia Binh Airport City
    "airport_name":     "...",
    "reference_city":   "...",
    "official_website": "https://...",
},
```

Lý do các trường này nằm ở đây chứ không trích từ text: chúng là **quyết định của
người phân tích** (gọi case là gì, lấy thành phố nào làm tham chiếu), không phải dữ
liệu website tuyên bố.

**Bẫy:** `country` viết tiếng Việt và phải có trong `FLAGS` ở
[`build_html.py:138`](html/build_html.py#L138) (`Hà Lan`, `Hàn Quốc`, `Trung Quốc`,
`Việt Nam`, `Singapore`, `Đức`, `UAE`, `Nhật Bản`, `Đài Loan`, `Úc`). Nước ngoài danh
sách → thiếu cờ, phải bổ sung vào `FLAGS`.

Cùng lúc, thêm hàm `build_<case>(pages, rec)` và đăng ký vào `CASE_BUILDERS` ở cuối
[`extract_airport_city.py`](agent_extractor/ws1_airport/extract_airport_city.py) — mỗi
case có **bộ pattern riêng**, không dùng chung. Thiếu builder thì extractor dừng và
in đúng việc phải làm, thay vì lặng lẽ ra record rỗng.

---

## Pha 4 — Viết pattern trích xuất *(pha tốn công nhất)*

Bộ pattern hiện có **bám sát cách hành văn của schiphol.nl** và gần như không tự
chuyển sang case khác. Ví dụ `r"began life in (\d{4})"` chỉ đúng với trang lịch sử
Schiphol; `r"(\d+)\s+business buildings"` chỉ đúng với Schiphol Real Estate.

### 4.1 Đọc dữ liệu thật trước khi viết regex

**Không đoán.** Với mỗi trường cần lấy, grep trong `.txt` đã crawl để xem câu gốc:

```bash
# ví dụ: tìm câu chứa số hành khách
grep -rn -i -E "million passengers|passengers in 20|旅客" raw_data/output/ws1_airport/raw/<case>/pages/*.txt | head -20
```

Đọc **cột "Có thể lấy dữ liệu gì?" trong `refer_file/<case>.txt`** — nó đã ghi sẵn
trường nào nằm ở trang nào và giá trị kỳ vọng. Dùng nó làm danh sách việc.

### 4.2 Chọn helper đúng loại

| Helper | Trả về | Dùng cho |
|---|---|---|
| `field_num(pages, pat, cast, unit, prefer)` | 1 số + provenance | KPI đơn trị: `passengers_million`, `airport_area_ha`, `founded_year` |
| `field_text(pages, pat, group)` | 1 chuỗi | Câu mô tả: `planning_concept`, `cvp_price`, `aviation_policy` |
| `field_range(pages, pat, unit)` | `{min,max,count}` | Dải giá trị rải rác nhiều trang: `office_rent_eur_m2_year` |
| `field_presence(pages, tokens)` | list token **có xuất hiện** | Danh sách kiểm: `subzones`, `basic_amenities`, `cvp_brand`, `sustainability` |
| `field_collect(pages, patterns)` | list **câu khớp** | Mô tả nhiều vế: `cvp_convenience`, `rail_connections` |

Khác biệt then chốt: `field_presence` trả về **chính token bạn liệt kê** (sạch, dễ
dịch sang tiếng Việt ở tầng HTML); `field_collect` trả về **nguyên câu trong trang**
(giàu thông tin nhưng dài).

### 4.3 Ba quy tắc chống lỗi đã rút ra từ case Schiphol

1. **`prefer=` cho chỉ số trùng.** Cùng một chỉ số xuất hiện ở nhiều trang với số
   khác nhau (marketing "over 300" vs Facts & Figures "301"). Truyền
   `prefer="<mảnh tên file trang chuẩn>"` để `_search` xếp trang đó lên đầu.
   Áp dụng cho toàn bộ nhóm headline: passengers, cargo, movements, destinations,
   airlines, transfer.
2. **Neo ngữ nghĩa, đừng bắt số trần.** `r"€\s*([\d.,]+)\s*per\s*m"` sẽ nuốt cả
   "Service costs €65/m²". Phải neo bằng từ mở đầu: `r"(?:Starting at|From)\s*€…"`.
3. **Không tìm thấy → để `None`.** Không đặt giá trị mặc định, không suy từ case
   khác. `residential_product_desc` của Schiphol là `None` và điều đó đúng.

### 4.4 Chiến lược ngôn ngữ — trích nguyên văn, dịch ở tầng hiển thị

**Luật cốt lõi: KHÔNG dịch rồi mới trích.** Extractor luôn bắt **nguyên văn tại
nguồn** và cất vào `record` + `snippet`; đó là bằng chứng để đối soát. Bản tiếng
Việt nằm ở [`html/vi_text.json`](html/vi_text.json) và chỉ áp ở tầng hiển thị
(chi tiết: [`html/SKILL.md` § Lớp dịch](html/SKILL.md)). Dịch trước rồi regex sẽ
làm `snippet` không còn khớp trang nguồn.

Chọn nguồn: Incheon/Taoyuan có trang song ngữ → ưu tiên URL bản EN trong
`refer_file`. Nếu chỉ có bản bản địa, hai lựa chọn: (a) tìm nguồn EN tương đương,
(b) viết pattern theo tiếng bản địa và ghi chú trong `snippet`.

Hai loại chuỗi cần dịch, hai chỗ khác nhau:

| Loại | Ví dụ | Dịch ở đâu |
|---|---|---|
| **Token rời** trong list (`subzones`, `cvp_service`, `sustainability`, `cvp_brand`…) | `"free-trade zone"`, `"RE100"` | từ điển `VI.*` trong [`build_html.py`](html/build_html.py) |
| **Câu/đoạn văn** (`planning_concept`, `location_desc`, `investor_governance`, `cvp_convenience`…) | cả câu tiếng Anh | [`html/vi_text.json`](html/vi_text.json), khoá theo `<case>` |

Mảng dịch phải **cùng số phần tử** với mảng gốc; lệch thì `vi()` tự trả về bản gốc
(chống lệch cặp câu sau khi sửa regex ở Pha 4).

### 4.5 Nếu case cần trường mới

Thêm trường = sửa **3 nơi**, đúng thứ tự:
1. `features/ws1_airport/feature_spec.md` — khai báo name/type/nguồn (spec là nguồn sự thật).
2. `extract_airport_city.py` — gán `rec["<field>"] = ...`.
3. `html/build_html.py` — thêm mệnh đề dệt câu, **có `has()` guard và `src()`**.

---

## Pha 5 — Chạy extractor & đối soát

```bash
python agent_extractor/ws1_airport/extract_airport_city.py --name <case>
```

Xuất 3 thứ: `<case>_airport_city.json` (record + provenance),
append 1 dòng vào `airport_city_benchmark.jsonl` (**khoá `case_name`** — trùng thì
ghi đè dòng cũ), và dựng lại `airport_city_benchmark.csv` từ toàn bộ jsonl.

Cuối lệnh in báo cáo coverage: số trang đã đọc, số trường điền được, **danh sách
trường null**.

**Đối soát bắt buộc — 3 bước, không bỏ:**

1. **Trường null có chính đáng không?** Đối chiếu danh sách null với cột ghi chú
   trong `refer_file`. Trường mà `refer_file` nói "trang này có" nhưng lại null ⇒
   regex sai, quay lại pha 4. Trường thật sự không nguồn nào nêu ⇒ null là đúng.
2. **Số có khớp nguồn không?** Mở JSON, với mỗi KPI đọc `provenance.<field>.snippet`
   — đó là câu gốc. Snippet không chứa con số đã trích ⇒ regex bắt nhầm vị trí.
3. **Đơn vị có đúng không?** `passengers_million` phải là **triệu** (66.8), không
   phải 66.800.000. `_ha` phải là hecta, không phải m² hay km².

```bash
python - <<'EOF'
import json, sys; from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
d = json.loads(Path("raw_data/output/ws1_airport/features/<case>_airport_city.json").read_text(encoding="utf-8"))
rec, prov = d["record"], d["provenance"]
for k, v in rec.items():
    if k.startswith("_") or v in (None, [], ""): continue
    p = prov.get(k, {})
    print(f"{k:26} = {str(v)[:48]:50} ← {(p.get('snippet') or p.get('source_file') or '(registry)')[:70]}")
print("\nNULL:", [k for k, v in rec.items() if not k.startswith('_') and v in (None, [], '')])
EOF
```

**Chốt pha 5 khi:** mọi trường non-null đều có snippet chứng minh, và mọi trường
null đều giải thích được.

---

## Pha 6 — Tổng quát hoá lời văn *(ĐÃ XONG — chỉ kiểm lại khi thêm trường mới)*

[`build_html.py`](html/build_html.py) **đã hết câu hardcode riêng Schiphol** (làm khi
thêm 3 case incheon/taoyuan/western_sydney). Toàn bộ prose ở cả 2 slide giờ dệt từ
`record`, mỗi mệnh đề bọc `has()`. Các câu từng hardcode đã thay bằng:

| Mệnh đề | Nguồn dữ liệu thay thế |
|---|---|
| Giới thiệu / lịch sử | `founded_year` + `positioning` (bỏ hẳn Haarlemmermeer, "sân bay quân sự") |
| Vị trí | `reference_city` · `distance_to_city_km` · `location_desc` · `airport_build_period` · `urban_build_period` · `development_context` |
| Quy mô | từng KPI có `has()` riêng, ghép bằng `joinVi` — case thiếu KPI thì câu tự ngắn lại, không in `null` |
| Định vị | `rec.positioning` · `rec.planning_concept` · `rec.cornerstones` (số trụ lấy từ `.length`) |
| Park vùng | `logistics_park_name` / `trade_park_name` (null ⇒ dùng chữ chung), bỏ "phía nam Hoofddorp" |
| CVP Giá / Dịch vụ / Trải nghiệm / Thuận tiện / Thương hiệu | `cvp_*` + `price_vs_reference` · `sales_scheme` · `smart_city` · `experience_desc` · `connection_modes` · `metro_lines` · `investor_governance` · `lead_developer` · `brand_partners` |

Nguyên tắc giữ nguyên: **mỗi mệnh đề phải bắt nguồn từ một trường trong `record`**.
Không có trường ⇒ không có câu. Sau khi sửa, **luôn chạy lại `--name schiphol`** để
chắc trang cũ không vỡ (bản hiện tại: 43 trường điền / 1 null).

### 6b. Dịch sang tiếng Việt *(làm sau khi chốt Pha 5)*

Trang phải **thuần tiếng Việt**, trừ danh từ riêng. Hai việc:

1. **Token rời** → bổ sung cặp EN→VI vào từ điển `VI` trong `build_html.py`
   (`cornerstone` · `commercial` · `amenity` · `highlight` · `subzone` · `service` ·
   `brand` · `vision` · `sustain` · `product`).
2. **Câu văn** → thêm khoá `<case>` vào [`html/vi_text.json`](html/vi_text.json),
   mỗi trường một bản dịch (list phải cùng số phần tử với list gốc).

Chỉ dịch sau khi Pha 5 đã chốt — regex còn đổi thì bản dịch sẽ lệch với `record`.

**Kiểm bằng máy, không đọc bằng mắt** — render rồi quét chuỗi Latin dài:

```bash
python - <<'EOF'
import re, sys; from pathlib import Path
from playwright.sync_api import sync_playwright
sys.stdout.reconfigure(encoding="utf-8")
VN = "àáâãèéêìíòóôõùúăđĩũơưạảấầẩẫậắằẳẵặẹẻẽềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹý"
SEC = ["intro","loc","scale","positioning","planning","vision",
       "cvp_product","cvp_price","cvp_service","cvp_experience","cvp_convenience","cvp_brand"]
with sync_playwright() as pw:
    b = pw.chromium.launch(); pg = b.new_page()
    pg.goto(Path("html/<case>.html").resolve().as_uri()); pg.wait_for_timeout(500)
    for s in SEC:
        t = " ".join(pg.inner_text("#"+s).split())
        for m in re.finditer(r"(?:\b[A-Za-z][A-Za-z'’\-]*\b[ ,]+){4,}[A-Za-z][A-Za-z'’\-]*", t):
            if not any(c in m.group(0).lower() for c in VN): print(f"[{s}] {m.group(0)[:120]}")
    b.close()
EOF
```

Kết quả mong đợi: **không in gì**, hoặc chỉ in cụm danh từ riêng (`Schiphol East`,
`Western Parkland City`, `St Marys`) — những cụm này giữ nguyên là đúng.

Từ điển `VI` ([`:141`](html/build_html.py#L141)) cũng cần bổ sung cặp EN→VI cho
token mới của case (`subzone`, `amenity`, `service`, `sustain`…). Token không có
trong từ điển thì **giữ nguyên tiếng Anh** — không lỗi, chỉ kém mượt.

---

## Pha 7 — Thu ảnh minh hoạ *(3 bước: kiểm kê → curate → NHÌN)*

Bốn mục ảnh, mỗi mục có **yêu cầu ngữ cảnh riêng** — ảnh phải nói đúng nội dung ô
mà nó nằm trong, không phải "một tấm ảnh đẹp bất kỳ":

| `section` | Vị trí trên trang | Ảnh phải là |
|---|---|---|
| `hero` | full-width dưới subbar | toàn cảnh / ảnh trên không / công trình biểu tượng |
| `planning` | ô "Quy hoạch & phân khu" | **bản đồ phân khu, masterplan, sơ đồ sử dụng đất** |
| `vision` | ô "Tầm nhìn & bền vững" | phối cảnh tương lai, công trình xanh, hạ tầng bền vững |
| `experience` | ô "Trải nghiệm" | tiện ích, công viên, nhà ga, không gian công cộng |

⚠️ **`og:image` gần như luôn SAI ngữ cảnh.** Đó là ảnh chia sẻ mạng xã hội — logo
hoặc ảnh thương hiệu chung của cả website. Bản curate đầu tiên của repo này chỉ
dựa vào `og:image` và ra: hero của Taoyuan là **icon SDG #11**, mục Tầm nhìn của
Western Sydney là **logo NSW Government**, còn hero và vision của Incheon là **cùng
một file**.

### 7.1 Kiểm kê ảnh thật *(bắt buộc — cùng tinh thần "grep trước" của Pha 4)*

```bash
python html/harvest_images.py --name <case> --inspect
python html/harvest_images.py --name <case> --inspect --section planning
```

In ra mọi ảnh của mọi trang đã crawl kèm **URL · `alt` · chữ quanh ảnh · điểm ưu
tiên** theo từ khoá của từng mục (`SECTION_HINTS`). `alt` là tín hiệu mạnh nhất —
kể cả khi là tiếng Hàn/Trung: `경제권역 지도` = "bản đồ vùng kinh tế", `捷運路線圖`
= "sơ đồ tuyến MRT".

### 7.2 Curate — chỉ đích danh ảnh, đừng chỉ chỉ trang

`CURATION["<case>"]` trong [`html/harvest_images.py`](html/harvest_images.py) nhận
tuple **4 phần tử**, phần tử thứ 4 (`want`) là chuỗi con của URL **hoặc** `alt` để
khoá đúng tấm ảnh cần:

```python
"<case>": [
    ("hero",       "<slug trang>", "Chú thích tiếng Việt…", "<mảnh url hoặc alt>"),
    ("planning",   "<slug trang>", "…",                     "city%20spaces%20map"),
    ("vision",     "<slug trang>", "…",                     "Disaster Prevention Retention Basin 1"),
    ("experience", "<slug trang>", "…",                     "metro_pic"),
],
```

Bỏ trống `want` ⇒ rơi về `og:image` ⇒ gần như chắc chắn sai. Hai mục lấy trùng một
ảnh thì script in `[warn] TRÙNG ảnh với mục '<x>'`.

```bash
python html/harvest_images.py --name <case>
```

### 7.3 NHÌN ảnh đã tải *(bước hay bị bỏ — và là bước bắt lỗi nhiều nhất)*

`alt` đúng vẫn có thể ra ảnh sai. Phải mở `html/assets/<case>/{hero,planning,vision,experience}.jpg`
lên xem. Ba lỗi chỉ lộ ra khi nhìn, không lộ qua `alt`:

- Ảnh là **icon/infographic** chứ không phải ảnh thật (SDG icon, logo cơ quan).
- Ảnh **đúng nội dung nhưng sai mục** — vd `complex-city-view1` của Incheon `alt`
  ghi "ảnh tổng quan" nhưng thực chất là **bản đồ quy hoạch đánh số phân khu** ⇒
  thuộc về `planning`, không phải `hero`.
- Ảnh là **infographic đặc chữ Hán/Hàn** — người đọc Việt không dùng được, đổi
  sang ảnh/phối cảnh thực tế.

Cơ chế kỹ thuật (og:image → fallback → `urljoin` → resize → `images.json`) mô tả ở
[`html/SKILL.md` § Ảnh minh hoạ](html/SKILL.md) — không lặp lại ở đây.

Trang skip thì in `[skip]`, tải lỗi in `[fail]` — **không chặn pipeline**, chỉ mất ảnh
đó. `upload.wikimedia.org` hay trả **429** (chặn tốc độ) ⇒ ưu tiên ảnh từ chính
website của dự án.

⚠️ `harvest_images.py` **gọi mạng** (tải ảnh từ CDN gốc). Đây là ngoại lệ duy nhất
so với quy tắc "sau khi crawl thì offline".

---

## Pha 8 — Dựng trang & nghiệm thu

```bash
python html/build_html.py --name <case>
```

Ghi `html/<case>.html` **và ghi đè `html/index.html`** (index luôn là bản dựng gần
nhất).

Cách trang được dựng — thiết kế bám slide gốc, bảng ánh xạ trường → mục trình bày,
7 bước dệt prose, từ điển `VI`, cơ chế nhúng base64 — xem
[`html/SKILL.md`](html/SKILL.md). Pha này chỉ lo **nghiệm thu**.

### Checklist nghiệm thu (mở file trong trình duyệt)

- [ ] Tiêu đề, cờ quốc gia, pill "CASE THAM CHIẾU"/"DỰ ÁN MỤC TIÊU", link website — đúng.
- [ ] **Không còn câu nào nhắc Schiphol/Hà Lan** trong trang của case khác *(pha 6)*.
- [ ] **Không còn câu tiếng Anh trong prose** — chạy script quét ở Pha 6b *(chỉ được
      còn danh từ riêng)*.
- [ ] Rê chuột vào vài `ⓘ`: tooltip hiện **nguyên văn câu nguồn** (bản dịch vẫn kiểm chứng được).
- [ ] Số trong prose **khớp** số trong ô KPI, và khớp `record` trong JSON.
- [ ] Định dạng số kiểu Việt: `66,8` · `2.787` · `473.815`.
- [ ] Không ô nào hiện `—` mà lẽ ra có dữ liệu; ô `—` phải tương ứng trường null thật.
- [ ] Bấm thử vài `ⓘ` — mở đúng trang nguồn.
- [ ] `<details>` "Nguồn dữ liệu chi tiết" liệt kê đủ domain đã dùng.
- [ ] **Mở từng ảnh trong `html/assets/<case>/` ra xem** — đúng mục, không phải
      icon/logo/infographic ngoại ngữ, 4 ảnh khác nhau *(pha 7.3)*.
- [ ] Ảnh "Quy hoạch & phân khu" **là bản đồ/masterplan**, không phải ảnh chung chung.
- [ ] Caption khớp đúng thứ đang thấy trong ảnh; link "nguồn" chạy.
- [ ] Thu hẹp cửa sổ < 640px: lưới đổ về 1 cột, không tràn ngang.
- [ ] Dòng benchmark của case đã có trong `airport_city_benchmark.csv`.

---

## Hợp đồng (contract) — áp cho mọi pha

- **Không bịa.** Nguồn không nêu → `null` → HTML im lặng bỏ mệnh đề. Không suy từ
  case khác, không lấy số "cho có".
- **Dịch là tầng hiển thị, không phải tầng dữ liệu.** `record` luôn giữ nguyên văn
  nguồn; bản tiếng Việt ở `html/vi_text.json`. Bản dịch không được thêm dữ kiện mà
  nguồn không nêu — nếu thấy cần thêm, đó là dấu hiệu thiếu một trường ở Pha 4.
- **Raw bất biến.** Không sửa file trong `raw/`. Sai thì đổi nguồn và crawl lại.
- **Extractor không gọi mạng, idempotent.** Chạy 2 lần trên cùng raw phải ra cùng output.
- **Tên trường theo spec.** Không tự đổi tên cột; muốn đổi thì sửa `feature_spec.md` trước.
- **Ưu tiên nguồn chuẩn.** Chỉ số trùng → `prefer=` trỏ trang chính chủ/mới nhất.
- **Truy được nguồn.** Mọi giá trị trích ra phải có `source_url` + `snippet`.
- **Crawl hợp pháp.** Tôn trọng `robots.txt`, không vượt auth/paywall.

## Bảng lỗi thường gặp

| Hiện tượng | Nguyên nhân | Xử lý |
|---|---|---|
| `Không tách được URL nào từ …` | `refer_file` sai định dạng link | Quay lại pha 0 |
| Làm xong mới phát hiện case đã có | Bỏ qua bước chống trùng | Pha −1.1 — kiểm cả 3 nơi: `refer_file/`, `REGISTRY`, benchmark |
| Pha 5 thủng hàng loạt trường dù regex đúng | `refer_file` không phủ đủ nhóm trường của spec | Pha −1.2 — bổ sung nguồn rồi crawl lại (append giữ data cũ) |
| Cột 4 chỉ ghi chung chung ("thông tin quy hoạch") | Đưa nguồn vào bảng mà chưa mở trang ra đọc | Pha −1.5 — ghi tên trường + giá trị kỳ vọng |
| `Chưa có raw cho '<case>'` | Chưa crawl, hoặc `--name` khác nhau giữa 2 lệnh | Dùng đúng một `<case>` xuyên suốt 4 lệnh |
| `Chưa curate ảnh cho '<case>'` | Thiếu `CURATION[<case>]` | Pha 7 |
| `Không thấy JSON: …` | Chưa chạy extractor | Pha 5 |
| `Chưa có bộ pattern cho case '<case>'` | Thiếu `build_<case>` trong `CASE_BUILDERS` | Pha 3 + 4 |
| Extractor điền rất ít trường | Pattern chưa bám ngôn ngữ của case | Pha 4 — grep `.txt` thật rồi viết lại regex |
| Số đúng chữ số nhưng sai giá trị (vd ra `0` thay vì `70`) | Trang render số đếm **tách từng chữ số** trên các dòng riêng (airport.kr) | Neo pattern vào nhãn phía sau và cho `\s` vào trong nhóm số; `field_num` đã tự bỏ mọi khoảng trắng |
| Số đúng nhưng sai đơn vị (m² vs ha vs km²) | Nguồn công bố đơn vị khác spec | Truyền `factor=` cho `field_num` (bảng quy đổi ở `feature_spec.md` §7) |
| `harvest_images` báo `No scheme supplied` | Trang trả ảnh đường dẫn tương đối | Đã xử lý bằng `urljoin` với URL trang gốc |
| Ảnh thu về là icon menu vài trăm byte | Trang không có `og:image`, fallback bắt nhầm ảnh giao diện | Dùng `--inspect` rồi khoá ảnh bằng `want` *(Pha 7.1–7.2)* |
| Ảnh là logo cơ quan / icon SDG / ảnh thương hiệu | Curate không có `want` nên lấy `og:image` (ảnh chia sẻ MXH) | Pha 7.2 — luôn điền `want` |
| Hai mục hiện cùng một ảnh | Hai entry trỏ cùng `og:image` của một site | Script in `[warn] TRÙNG` — đổi `want`/`slug` |
| Ảnh đúng nội dung nhưng nằm sai ô | Chọn theo `alt` mà không mở ảnh ra xem | Pha 7.3 — nhìn rồi hoán mục |
| `429 Too Many Requests` khi tải ảnh | `upload.wikimedia.org` chặn tốc độ | Đổi sang ảnh từ website chính chủ của dự án |
| Câu trích cụt ngay tại con số (vd `exceeding NT$2.`) | Pattern dùng `[^.]+\.` nên dừng ở dấu chấm **thập phân** | Dùng hằng `SENT` trong extractor (`(?:[^.]|\.(?=\d))*\.`) |
| Trường text nuốt cả khối menu / chữ tiếng Hàn, tiếng Trung | Pattern neo vào **tên riêng trần** — tên đó còn nằm trong menu & footer | Neo vào **một câu hoàn chỉnh** chứa động từ, đừng neo tên tổ chức |
| Trang vẫn hiện câu tiếng Anh | Chưa khai trong `vi_text.json` / từ điển `VI` | Pha 6b |
| Bản dịch list lệch câu so với nguồn | Mảng trong `vi_text.json` khác số phần tử với list gốc | `vi()` tự fallback về bản gốc — sửa lại cho đủ phần tử |
| Trang HTML thiếu cờ quốc gia | `country` chưa có trong `FLAGS` | Thêm vào `FLAGS` ở `build_html.py` |
| Số trong trang sai đơn vị | `cast`/`unit` sai ở `field_num` | Sửa pha 4, chạy lại pha 5 + 8 |
| `ModuleNotFoundError: playwright / pymupdf / PIL` | 3 gói thiếu trong `requirements.txt` | `pip install playwright pymupdf Pillow` + `python -m playwright install chromium` |

## Chạy lại toàn tuyến (khi đã ổn định)

> Pha −1 và 6b là việc **biên soạn**, không có lệnh — làm một lần rồi giữ trong
> `refer_file/<case>.txt` và `html/vi_text.json`. Bốn lệnh dưới đây tái lập được
> toàn bộ output từ hai file đó.

```bash
python raw_data/crawler/crawl_sources.py --name <case> --input refer_file/<case>.txt
python agent_extractor/ws1_airport/extract_airport_city.py --name <case>
python html/harvest_images.py --name <case>
python html/build_html.py --name <case>
```

> [`scripts/run_ws.py`](scripts/run_ws.py) **chưa gói 4 lệnh này** — `PIPELINES` mới
> map luồng legacy (OpenFlights). Muốn một lệnh duy nhất thì thêm entry
> `ws1_airport_case` nhận tham số `--name` và gọi tuần tự 4 script trên.

## Mở rộng

- **Trang so sánh nhiều case:** dữ liệu đã sẵn ở `airport_city_benchmark.jsonl`
  (mỗi case 1 dòng, cùng bộ cột). Dựng thêm generator đọc jsonl → bảng đối chiếu,
  bám đúng bộ trường của [`feature_spec.md`](features/ws1_airport/feature_spec.md).
- **Case mục tiêu GBAC:** `is_target=True`; nhiều trường sẽ null vì dự án chưa công
  bố — đó là kết quả hợp lệ và chính là thông tin cần thấy khi đối sánh.
- **Case còn trong danh mục:** [`refer_file/aerotropolis.txt`](refer_file/aerotropolis.txt)
  còn 6 case chưa làm — Dubai South · Changi · Hong Kong · Dallas–Fort Worth ·
  Frankfurt · Kuala Lumpur Aeropolis. Mỗi case bắt đầu lại từ Pha −1.
