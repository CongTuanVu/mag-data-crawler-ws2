# SKILL — Sinh trang Hồ sơ Aerotropolis (web tĩnh, lời văn tiếng Việt)

> Skill dựng lớp trình bày cuối của pipeline. Agent đọc skill này +
> `<case>_airport_city.json` (record + provenance) + `features/ws1_airport/feature_spec.md`
> để **sinh/điều chỉnh `html/build_html.py`** → xuất trang hồ sơ 2-slide tiếng Việt.

## Mục tiêu

Input:
- `raw_data/output/ws1_airport/features/<case>_airport_city.json` — gồm `record`
  (giá trị các trường) và `provenance` (nguồn từng trường).
- `features/ws1_airport/feature_spec.md` — định nghĩa trường (mục "Schema thực thi v2").
- `raw_data/output/ws1_airport/raw/<case>/pages/*.html` — để **thu ảnh minh hoạ**.
- `html/assets/<case>/images.json` — bản đồ ảnh đã thu (do `harvest_images.py` sinh).
- Tham chiếu thiết kế: 2 slide gốc trong `refer_img/` (bố cục, màu, ảnh có caption, footer nguồn).

Output:
- `html/harvest_images.py` — thu + nén ảnh đại diện → `html/assets/<case>/*.jpg` + `images.json`.
- `html/build_html.py` — generator đọc JSON + ảnh → **nhúng data & ảnh base64** → ghi
  `html/<case>.html` và `html/index.html` (bản mới nhất).
- Trang HTML **tự chứa** (data + ảnh nhúng inline): mở double-click là chạy, không cần server.

Lệnh chạy (2 bước — thu ảnh trước, dựng trang sau):
```bash
python html/harvest_images.py --name <case>   # thu ảnh -> assets/<case>/
python html/build_html.py     --name <case>   # dựng trang (tự nhúng ảnh nếu có)
```
> `build_html.py` chạy được cả khi chưa có ảnh (bỏ qua phần ảnh); ảnh là lớp tăng cường.

## Nguyên tắc thiết kế (bám slide gốc trong refer_img/)

- Nền sáng; **thanh tiêu đề navy**; **cột nhãn tiêu chí màu vàng** bên trái;
  hàng nội dung viền mảnh; hàng nhấn nền **xanh nhạt / beige** xen kẽ (như Slide B).
- 2 slide: **Slide A – Tổng quan**, **Slide B – Phân tích CVP** (6 trụ).
- KPI dạng ô số (viền teal) cho các chỉ số; footer "Nguồn:" italic.

## Quy trình dựng (8 bước)

1. **Đọc JSON.** Lấy `record` + `provenance`. Đặt `has(k)` = trường có giá trị
   (khác null, list rỗng).
2. **Ánh xạ trường → mục** (xem bảng dưới). Mỗi mục là 1 ô trong lưới nhãn|nội dung.
3. **Dịch thuật ngữ** EN→VI qua từ điển `VI` (cornerstone, commercial, amenity,
   highlight, subzone, service, brand, vision, sustain, product). Token ngoài từ
   điển → giữ nguyên. Từ điển này chỉ dịch **token rời** trong các list.
3b. **Dịch câu văn** qua [`vi_text.json`](vi_text.json) — xem mục dưới. Trường nào
   khai ở đó thì hiển thị bản tiếng Việt, không khai thì hiện nguyên văn nguồn.
4. **Format số kiểu Việt**: `toLocaleString("de-DE")` → dấu chấm hàng nghìn, phẩy
   thập phân (66,8 · 2.787 · 473.815). Đơn vị viết kèm bằng tiếng Việt.
5. **Dệt lời văn (prose)**, KHÔNG dùng chip/keyword rời. Mỗi mục là câu/đoạn hoàn
   chỉnh; **in đậm** số liệu và thuật ngữ chốt. Dùng `joinVi` để nối danh sách
   ("A, B và C").
6. **Bỏ mệnh đề khi thiếu dữ liệu.** `has(k)` false → không viết mệnh đề đó (không
   bịa). **Mọi khối đã bọc `has()` đầy đủ**, kể cả `loc` và `scale` — hai khối này
   trước đây dệt câu không guard nên case thiếu trường in ra `null` giữa câu; nay
   ghép từng mệnh đề bằng mảng + `joinVi`, thiếu trường thì câu tự ngắn lại.
   Thêm mệnh đề mới thì **luôn** bọc `has()`.
7. **Provenance + nhúng + ghi.** Gắn `ⓘ` (link nguồn) cuối các đoạn có nguồn; liệt
   kê nguồn ở `<details>`; nhúng `const DATA = {...}` vào template; ghi `index.html`.
8. **Kiểm còn tiếng Anh.** Render bằng Playwright, quét text hiển thị tìm chuỗi ≥5
   từ Latin liên tiếp không dấu — còn thì bổ sung `vi_text.json`/từ điển `VI`.

## Lớp dịch `vi_text.json`

Extractor cố tình giữ **nguyên văn nguồn** trong `record` (đó là bằng chứng truy
nguồn). Bản tiếng Việt là **nội dung biên soạn**, tách riêng ra file này:

```jsonc
{ "<case>": {
    "planning_concept": "…bản tiếng Việt…",       // trường text: chuỗi
    "cvp_convenience":  ["…", "…"]                 // trường list: mảng CÙNG SỐ PHẦN TỬ
} }
```

Cơ chế trong template: `vi(k)` trả bản dịch nếu có, **fallback về `rec[k]`** nếu
chưa dịch **hoặc nếu mảng dịch lệch số phần tử với mảng gốc** (chống lệch cặp câu
sau khi regex đổi). `has(k)` vẫn kiểm trên `rec`, nên bản dịch không bao giờ tự
sinh ra mệnh đề mà nguồn không có.

Truy nguồn vẫn nguyên: `title` của mỗi `ⓘ` chứa **nguyên văn snippet tại nguồn**,
và `record`/benchmark CSV vẫn lưu bản gốc.

**Quy ước dịch:** tên tổ chức/địa danh giữ dạng đọc được cho người Việt, viết tắt
quen thuộc giữ nguyên (`IFEZ`, `IIAC`, `AMRF`, `NSW`). Không dịch tên phân khu là
địa danh (`Songdo`, `Badgerys Creek`, `St Marys`).

⚠️ **Không dịch rồi mới trích.** Luôn trích từ text gốc đã crawl, dịch ở tầng hiển
thị. Dịch trước rồi regex sẽ mất `snippet` khớp nguồn.

## Ảnh minh hoạ (harvest_images.py)

Mỗi mục trọng điểm có 1 ảnh đại diện lấy từ chính trang đã crawl — để trang "có
hình như slide", không phải chỉ chữ.

Quy trình thu ảnh:
1. **Kiểm kê**: `--inspect` liệt kê MỌI ảnh của mọi trang kèm `alt`, chữ quanh ảnh
   và điểm ưu tiên theo `SECTION_HINTS` của từng mục.
2. **Curate** map `mục → (slug, caption, want)` trong `CURATION[<case>]`. `want` là
   chuỗi con của URL/`alt` khoá đúng tấm ảnh cần.
3. Với mỗi mục: đọc `pages/<slug>.html`; có `want` thì lấy ảnh khớp, không thì rơi
   về **`og:image`** (fallback cuối: ảnh `<img>` lớn đầu tiên, loại icon/logo/sprite).
   URL tương đối được `urljoin` với URL trang gốc. Hai mục trùng ảnh → in `[warn]`.
4. **Tải → resize** về bề rộng ≤ 820px → **nén JPEG q80** (giảm nặng).
5. Lưu `html/assets/<case>/<mục>.jpg` và ghi `images.json`:
   `{mục: {file, source_image, page_url, caption, bytes}}`.
6. **Mở ảnh ra nhìn.** `alt` đúng vẫn có thể ra icon, logo, hay ảnh thuộc mục khác.

> **`og:image` là ảnh chia sẻ mạng xã hội, không phải ảnh minh hoạ.** Curate chỉ
> dựa vào nó thì mục "Quy hoạch & phân khu" sẽ ra logo công ty thay vì bản đồ phân
> khu. Luôn điền `want`. Chi tiết & các lỗi đã gặp: [`../SKILL.md` Pha 7](../SKILL.md).

Khi dựng trang, `build_html.py`:
- Đọc `images.json`, **base64-hoá** từng jpg → `data:image/jpeg;base64,...` (giữ
  self-contained).
- **Hero**: ảnh `hero` chạy full-width ngay dưới thanh phụ của Slide A.
- **Ảnh theo mục**: chèn `<figure>` (ảnh + caption + link "nguồn") vào ô tương ứng
  qua `figureFor(section)`.

Bốn `section` cố định — `build_html.py` gọi `figureFor()` đúng theo tên này:

| section | mục hiển thị | ảnh phải là |
|---------|--------------|-------------|
| `hero` | banner full-width đầu Slide A | toàn cảnh / ảnh trên không / công trình biểu tượng |
| `planning` | Quy hoạch & phân khu | **bản đồ phân khu / masterplan / sơ đồ sử dụng đất** |
| `vision` | Tầm nhìn & bền vững | phối cảnh tương lai, hạ tầng xanh |
| `experience` | Trải nghiệm (Slide B) | tiện ích, công viên, nhà ga, không gian công cộng |

## Ánh xạ trường → mục trình bày

| Slide | Mục (nhãn) | Trường dùng |
|-------|-----------|-------------|
| A | Giới thiệu | case_name, aerotropolis, country, airport_name, reference_city, founded_year |
| A | Vị trí & lịch sử | reference_city, founded_year |
| A | Quy mô (văn + KPI) | passengers_million, cargo_million_tonnes, air_movements, destinations, airlines, transfer_pct, airport_area_ha, employees, num_companies_airport, num_office_buildings |
| A | Định vị | positioning, planning_concept, cornerstones |
| A | Quy hoạch & phân khu | subzones, logistics_park_ha, trade_park_ha |
| A | Tầm nhìn & bền vững | vision_label, vision_qualities, aviation_policy, sustainability |
| B | Sản phẩm | cvp_product, num_office_buildings, num_companies_realestate |
| B | Giá | office_rent_eur_m2_year, cvp_price |
| B | Dịch vụ | cvp_service |
| B | Trải nghiệm | cvp_experience |
| B | Thuận tiện | cvp_convenience, rail_connections |
| B | Thương hiệu | cvp_brand |

## Quy tắc lời văn

- **Tiếng Việt, có văn phong**; giữ tên riêng/thương hiệu tiếng Anh (Schiphol,
  AirportCity, WTC, BREEAM…).
- Câu dẫn dắt tự nhiên; **in đậm** con số & thuật ngữ then chốt.
- Không thêm nhận định vượt nguồn; số liệu phải khớp `record` (đã có provenance).
- Trường null → im lặng bỏ qua (vd `residential_product_desc` không xuất hiện).

## Ràng buộc (contract)

- **Self-contained**: data + **ảnh (base64)** nhúng inline (không `fetch`), mở file:// chạy được.
- **Tái dùng — có điều kiện.** Generator chỉ đọc từ JSON + `images.json`, không
  hardcode đường dẫn theo case; nhưng **lời văn thì chưa trung tính**: một số mệnh
  đề còn nhắc thẳng Schiphol/Hà Lan/Haarlemmermeer/Hoofddorp, và 2 khối thiếu
  `has()` guard (xem bước 6). Vì vậy `--name <case>` **chạy được ngay nhưng chưa
  cho ra trang đúng** với case mới: phải làm Pha 6 trong [`SKILL.md`](../SKILL.md)
  gốc repo (tổng quát hoá 6 vị trí hardcode) rồi mới dựng trang thật. Định danh
  (case_name/country/airport…) đến từ `REGISTRY` trong extractor.
- **Không cần API/LLM**: toàn bộ prose dệt bằng template + từ điển VI.
- **Provenance minh bạch**: mỗi đoạn có nguồn gắn `ⓘ`; mỗi ảnh có caption + link "nguồn".
- **Ảnh là tuỳ chọn**: thiếu `images.json` thì trang vẫn dựng bình thường (không ảnh).

## Mở rộng

- **Thêm ngôn ngữ/thuật ngữ**: bổ sung cặp EN→VI vào từ điển `VI`.
- **Thêm mục mới**: thêm 1 hàng `lab|cell` trong template + 1 khối dệt câu trong
  JS (nhớ `has()` guard + `src()` provenance).
- **Thêm/đổi ảnh**: sửa `CURATION[<case>]` trong `harvest_images.py` (mục → slug
  trang), chạy lại harvest; muốn ảnh vào ô mới thì gọi `figureFor("<section>")`
  tại ô đó trong `build_html.py`.
- **Nhiều case**: dựng thêm trang so sánh từ `airport_city_benchmark.jsonl`.

Code tham chiếu: [`harvest_images.py`](harvest_images.py) (thu ảnh) · [`build_html.py`](build_html.py) (dựng trang).
