# SKILL — Sinh trang Hồ sơ Aerotropolis (web tĩnh, lời văn tiếng Việt)

> Skill dựng lớp trình bày cuối của pipeline. Agent đọc skill này +
> `<case>_airport_city.json` (record + provenance) + `features/ws1_airport/feature_spec.md`
> để **sinh/điều chỉnh `html/build_html.py`** → xuất trang hồ sơ 2-slide tiếng Việt.

## Mục tiêu

Input:
- `raw_data/output/ws1_airport/features/<case>_airport_city.json` — gồm `record`
  (giá trị các trường) và `provenance` (nguồn từng trường).
- `features/ws1_airport/feature_spec.md` — định nghĩa trường (mục "Schema thực thi v2").
- Tham chiếu thiết kế: 2 slide gốc trong `refer_img/` (bố cục, màu, footer nguồn).

Output:
- `html/build_html.py` — generator đọc JSON → nhúng data → ghi `html/<case>.html`
  và `html/index.html` (bản mới nhất).
- Trang HTML **tự chứa** (data nhúng inline): mở double-click là chạy, không cần server.

Lệnh chạy:
```bash
python html/build_html.py --name <case>     # vd: schiphol
```

## Nguyên tắc thiết kế (bám slide gốc trong refer_img/)

- Nền sáng; **thanh tiêu đề navy**; **cột nhãn tiêu chí màu vàng** bên trái;
  hàng nội dung viền mảnh; hàng nhấn nền **xanh nhạt / beige** xen kẽ (như Slide B).
- 2 slide: **Slide A – Tổng quan**, **Slide B – Phân tích CVP** (6 trụ).
- KPI dạng ô số (viền teal) cho các chỉ số; footer "Nguồn:" italic.

## Quy trình dựng (7 bước)

1. **Đọc JSON.** Lấy `record` + `provenance`. Đặt `has(k)` = trường có giá trị
   (khác null, list rỗng).
2. **Ánh xạ trường → mục** (xem bảng dưới). Mỗi mục là 1 ô trong lưới nhãn|nội dung.
3. **Dịch thuật ngữ** EN→VI qua từ điển `VI` (cornerstone, commercial, amenity,
   subzone, service, vision, sustain, product). Token ngoài từ điển → giữ nguyên.
4. **Format số kiểu Việt**: `toLocaleString("de-DE")` → dấu chấm hàng nghìn, phẩy
   thập phân (66,8 · 2.787 · 473.815). Đơn vị viết kèm bằng tiếng Việt.
5. **Dệt lời văn (prose)**, KHÔNG dùng chip/keyword rời. Mỗi mục là câu/đoạn hoàn
   chỉnh; **in đậm** số liệu và thuật ngữ chốt. Dùng `joinVi` để nối danh sách
   ("A, B và C").
6. **Bỏ mệnh đề khi thiếu dữ liệu.** `has(k)` false → không viết mệnh đề đó (không
   bịa). Nhờ vậy generator tái dùng cho case khác.
7. **Provenance + nhúng + ghi.** Gắn `ⓘ` (link nguồn) cuối các đoạn có nguồn; liệt
   kê nguồn ở `<details>`; nhúng `const DATA = {...}` vào template; ghi `index.html`.

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

- **Self-contained**: data nhúng inline (không `fetch`), mở file:// chạy được.
- **Tái dùng**: chỉ đọc từ JSON; muốn thêm case chỉ cần chạy lại `--name <case>`.
  Định danh (case_name/country/airport…) đến từ `REGISTRY` trong extractor.
- **Không cần API/LLM**: toàn bộ prose dệt bằng template + từ điển VI.
- **Provenance minh bạch**: mỗi đoạn có nguồn gắn `ⓘ`; mục nguồn liệt kê URL → trường.

## Mở rộng

- **Thêm ngôn ngữ/thuật ngữ**: bổ sung cặp EN→VI vào từ điển `VI`.
- **Thêm mục mới**: thêm 1 hàng `lab|cell` trong template + 1 khối dệt câu trong
  JS (nhớ `has()` guard + `src()` provenance).
- **Nhiều case**: dựng thêm trang so sánh từ `airport_city_benchmark.jsonl`.

Code tham chiếu hoàn chỉnh: [`build_html.py`](build_html.py).
