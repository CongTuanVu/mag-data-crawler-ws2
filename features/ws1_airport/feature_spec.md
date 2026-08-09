# Feature Spec — WS1 Airport City (KĐT Sân bay)

Domain: **Khu đô thị sân bay (airport city / aerotropolis)**. Mục tiêu: chuẩn hoá
bộ tiêu chí benchmark các case study KĐT sân bay trên thế giới để đối chiếu với
dự án **Gia Bình Airport City (GBAC)**.

- **Đơn vị quan sát (1 bản ghi):** một *case study KĐT sân bay* (hoặc một phân
  khu). Ví dụ: `Incheon – Yeongjong`, `Incheon – Songdo`, `Tianfu Airport City`,
  `Hongqiao CBD`, `Aranya`, `Gia Binh Airport City`.
- Nguồn feature: 2 slide phân tích trong `refer_img/` (xem mục Nguồn).

## Nguồn dữ liệu (raw)

| Slide | Vị trí gốc | Tiêu đề | Nguồn ghi trên slide |
|-------|-----------|---------|----------------------|
| A | PDF `OMRE CMI_...Chairman Present.pdf` **trang 59** (= `Screenshot ...211929.png`) | Tổng quan các KĐT Sân bay nghiên cứu | CBRE Vietnam, GLG, Trung tâm Nghiên cứu thị trường & Am hiểu khách hàng One Mount Group — T5/2026 |
| B | PDF **trang 29** (= `Screenshot ...212021.png`) | Incheon tập trung CVP Sản phẩm & Dịch vụ; Hongqiao/Tianfu chú trọng CVP Thuận tiện & Trải nghiệm | GLG, Decision Lab, One Mount Group — T6/2026 |

> Raw thực tế cần crawl: báo cáo/slide nghiên cứu, trang dự án, CBRE/JLL, tin quy
> hoạch. Đây là dữ liệu **benchmark định tính + một số chỉ số**, không phải một CSV
> đơn. Mỗi giá trị phải giữ `source_name`, `source_url`, `accessed_at`.

## Khung phân loại feature

- **Group A – Định danh & Tổng quan** (từ Slide A).
- **Group B – Phân tích CVP** (từ Slide B): 6 trụ CVP = Sản phẩm, Giá, Dịch vụ,
  Trải nghiệm, Thuận tiện, Thương hiệu.

---

## Schema thực thi (web extraction) — v2 · CHỐT

> Đây là **schema mà pipeline đang sinh thật**: `crawl_sources.py` crawl website
> chính thức → `extract_airport_city.py` (deterministic, không LLM) → record +
> provenance. Mỗi trường kèm `source_url`, `source_file`, `snippet`, `confidence`.
> Cột "ví dụ" lấy từ case **Schiphol Airport City** (39 trường có dữ liệu / 28 trang).
> Group A/B bên dưới là khung khái niệm gốc từ 2 slide (giữ để đối chiếu benchmark).

### 1) Định danh
| name | type | nguồn | ví dụ (Schiphol) |
|------|------|-------|------------------|
| `case_name` | string | registry | Schiphol Airport City |
| `aerotropolis` | string | registry | Schiphol Airport City / Amsterdam Aerotropolis |
| `country` | string | registry | Hà Lan |
| `is_target` | bool | registry | false |
| `airport_name` | string | registry | Amsterdam Airport Schiphol |
| `reference_city` | string | registry | Amsterdam |
| `official_website` | string | registry | https://www.schiphol.nl |

### 2) Định vị & khái niệm
| name | type | nguồn | ví dụ |
|------|------|-------|-------|
| `positioning` | string | business-model | AirportCity |
| `planning_concept` | string | business-model | "…developed as an AirportCity where travellers, airlines and businesses…" |
| `cornerstones` | list | business-model | Aviation; Consumer Products & Services; Real Estate |
| `subzones` | list | real-estate | Central Business District; Schiphol East; Schiphol Southeast |

### 3) Chỉ số quy mô (KPI)
| name | type | đơn vị | nguồn | ví dụ |
|------|------|--------|-------|-------|
| `passengers_million` | float | triệu/năm | Facts & Figures | 66.8 |
| `cargo_million_tonnes` | float | triệu tấn/năm | Facts & Figures | 1.49 |
| `air_movements` | int | lượt/năm | Facts & Figures | 473,815 |
| `destinations` | int | điểm | Facts & Figures | 301 |
| `airlines` | int | hãng | Facts & Figures | 120 |
| `transfer_pct` | float | % | Facts & Figures | 36.3 |
| `airport_area_ha` | float | ha | Airport Facts | 2,787 |
| `employees` | int | người | Airport Facts | 68,000 |
| `num_companies_airport` | int | công ty | Airport Facts | 800 |
| `num_companies_realestate` | int | công ty | Real Estate | 450 |
| `num_office_buildings` | int | toà | Real Estate | 35 |

> Chỉ số headline (passengers/cargo/movements/destinations/airlines/transfer) **ưu
> tiên trang "Facts & Figures"** khi nhiều trang cho số khác nhau (chống lấy nhầm
> số marketing/cũ).

### 4) Sản phẩm, BĐS & Tiện ích
| name | type | nguồn | ví dụ |
|------|------|-------|-------|
| `commercial_re` | list | business-district | logistics; cargo; office; retail; hotel; WTC; The Base |
| `residential_product_desc` | string\|null | — | null (Schiphol thiên business/office) |
| `basic_amenities` | list | facilities | meeting; sports; restaurants; child care; shops; Schiphol Plaza |
| `highlight_amenities` | list | real-estate | WTC; Hilton Hotel; Sheraton Hotel; The Base; BREEAM |

### 5) Phân tích CVP (6 trụ)
| name | type | nguồn | ví dụ |
|------|------|-------|-------|
| `cvp_product` | list | real-estate | office; commercial space; development; logistics; retail |
| `cvp_price` | string | business-model | mô hình doanh thu (airport charges, concession, property rents…) |
| `office_rent_eur_m2_year` | obj `{min,max,count}` | total-offering | €130–€280/m²/năm (13 chào giá, excl. VAT) |
| `cvp_price_note` | string | — | Giá chào thuê văn phòng; đơn giá tuỳ toà & phân khu |
| `cvp_service` | list | real-estate | Spot; Leasing Managers; area director; flexible real estate |
| `cvp_experience` | list | facilities | restaurants; sports; meeting; Schiphol Plaza; Hilton; Sheraton |
| `cvp_convenience` | list | airport-facts | đa phương thức (car/bus/train/plane); cao tốc A4/A5/A9/A10; tàu Paris 9 chuyến/ngày |
| `rail_connections` | list | NS | Amsterdam↔Schiphol (Intercity direct); Schiphol↔Rotterdam |
| `cvp_brand` | list | real-estate | Royal Schiphol Group; Schiphol Real Estate |

### 6) Bổ sung (lịch sử · tầm nhìn · park vùng · bền vững)
| name | type | nguồn | ví dụ |
|------|------|-------|-------|
| `founded_year` | int | airport-history | 1916 |
| `vision_label` | string | strategic-qualities | Vision 2050 |
| `vision_qualities` | list | strategic-qualities | Quality of Network/Life/Service/Work |
| `aviation_policy` | string | strategy | Aviation Policy Memorandum 2020-2050 |
| `logistics_park_ha` | float | SADC – SLP facts | 43 |
| `logistics_park_name` | string\|null | trang park | Schiphol Logistics Park |
| `trade_park_ha` | float | SADC – Trade Park | 350 |
| `trade_park_name` | string\|null | trang park | Schiphol Trade Park |
| `sustainability` | list | SADC sustainability | BREEAM; circular; most sustainable; biodiversity; CO2 |

> `*_park_name` tách khỏi `*_park_ha` để `build_html.py` không phải hardcode tên park
> riêng của Schiphol; case không có tên park thì null và HTML dùng chữ chung.

### 7) Quy đổi đơn vị tại nguồn

Nhiều website công bố ở đơn vị khác spec. `field_num(..., factor=)` quy đổi ngay khi
trích, để `record` luôn đúng đơn vị đã khai báo:

| Case | Nguồn ghi | Trường | factor |
|---|---|---|---|
| Incheon | `2,093,000 square meters` | `logistics_park_ha` | `1e-4` |
| Taoyuan | `4,564 hectares` | `area_km2` | `0.01` |
| Taoyuan | `47,795,969` khách | `passengers_million` | `1e-6` |
| Western Sydney | `11,200 hectares` | `area_km2` | `0.01` |

### Quy tắc chống lỗi đã áp dụng
- **Ưu tiên nguồn chuẩn** cho chỉ số trùng (headline → "Facts & Figures 2025", tránh "over 300" marketing).
- **Loại nhiễu ngữ nghĩa**: giá thuê chỉ bắt dòng mở đầu `Starting at`/`From` (loại "Service costs €65/m²").
- **Append, không ghi đè**: crawl bổ sung giữ nguồn cũ (giữ số 66.8M/301/2787 khi thêm 24 nguồn mới).
- **Không bịa**: trường nguồn không nêu → null (vd `residential_product_desc`).

---

## Group A — Định danh & Tổng quan

| name                     | type   | required | source (Slide A – dòng) | transform / đơn vị            | description |
|--------------------------|--------|----------|-------------------------|-------------------------------|-------------|
| `case_name`              | string | yes      | tiêu đề cột             | strip                         | Tên KĐT/phân khu (khoá) |
| `country`                | string | yes      | suy ra từ cột           | —                             | Quốc gia (Hàn Quốc, Trung Quốc, Việt Nam) |
| `is_target`              | bool   | yes      | —                       | GBAC = true                   | Có phải dự án mục tiêu (GBAC) không |
| `airport_name`           | string | no       | Vị trí/tiêu đề          | strip                         | Sân bay gắn với KĐT (Incheon, Tianfu, Hongqiao, Gia Bình…) |
| `location_desc`          | string | yes      | Vị trí                  | strip                         | Mô tả vị trí gốc |
| `reference_city`         | string | no       | Vị trí                  | strip                         | Thành phố tham chiếu (Seoul, Thành Đô, Thượng Hải, Hà Nội) |
| `distance_to_city_km`    | float  | no       | Vị trí                  | số, km                        | Khoảng cách tới trung tâm tham chiếu |
| `area_km2`               | float  | no       | Quy mô                  | số, km²                       | Quy mô diện tích |
| `airport_build_period`   | string | no       | Thời gian xây dựng      | dạng `YYYY-YYYY` hoặc `-nay`  | Giai đoạn xây sân bay |
| `urban_build_period`     | string | no       | Thời gian xây dựng      | dạng `YYYY-nay`               | Giai đoạn xây KĐT |
| `development_context`    | string | no       | Bối cảnh phát triển     | strip                         | Bối cảnh/động lực phát triển |
| `investor_governance`    | string | no       | Chủ đầu tư / Quản trị   | strip                         | Mô hình chủ đầu tư & quản trị |
| `gov_led_ratio_pct`      | float  | no       | Chủ đầu tư / Quản trị   | %, 0–100                      | Tỷ lệ nhà nước dẫn dắt (nếu nêu) |
| `private_ratio_pct`      | float  | no       | Chủ đầu tư / Quản trị   | %, 0–100                      | Tỷ lệ tư nhân thực thi (nếu nêu) |
| `total_investment_usd`   | string | no       | Tổng mức đầu tư         | giữ nguyên văn + số tỷ USD    | Tổng mức đầu tư (thường theo khu/giai đoạn) |
| `positioning`            | string | no       | Quy hoạch, định vị      | strip                         | Định vị (vd Aviation & Tourism Hub, Smart City & Bio Hub) |
| `subzones`               | list   | no       | Phân khu                | tách theo `;`                 | Danh sách phân khu chức năng |
| `planning_concept`       | string | no       | Quy hoạch               | strip                         | Ý tưởng quy hoạch (bàn cờ, urban park, mảng xanh là xương sống…) |

## Group B — Phân tích CVP

### B1. Sản phẩm (Product)

| name                        | type   | required | source (Slide B – Sản phẩm) | transform / đơn vị | description |
|-----------------------------|--------|----------|------------------------------|--------------------|-------------|
| `commercial_re`             | string | no       | Sản phẩm BĐS thương mại      | strip              | BĐS thương mại (đặc khu kinh tế, KCN, logistics…) |
| `economic_zone_name`        | string | no       | Sản phẩm BĐS thương mại      | strip              | Tên đặc khu/FTZ (IFEZ, Hongqiao Linkong EZ, FTZ Tứ Xuyên) |
| `economic_zone_year`        | int    | no       | Sản phẩm BĐS thương mại      | năm                | Năm thành lập đặc khu |
| `jobs_created`              | int    | no       | Sản phẩm BĐS thương mại      | số việc làm        | Số việc làm tạo ra (vd IFEZ 123.000; Hongqiao 650.000) |
| `residential_product_desc`  | string | no       | Sản phẩm nhà ở               | strip              | Mô tả sản phẩm nhà ở |
| `residential_highrise_pct`  | float  | no       | Sản phẩm nhà ở               | %, 0–100           | Tỷ lệ cao tầng |
| `residential_lowrise_pct`   | float  | no       | Sản phẩm nhà ở               | %, 0–100           | Tỷ lệ thấp tầng |
| `residential_land_pct`      | float  | no       | Sản phẩm nhà ở               | %, 0–100           | Tỷ lệ đất nền |
| `basic_amenities`           | string | no       | Tiện ích cơ bản              | strip              | Tiện ích cơ bản (trường học, công viên, TMDV…) |
| `highlight_amenities`       | string | no       | Tiện ích điểm nhấn           | strip              | Tiện ích điểm nhấn (trường quốc tế, tổ hợp nghỉ dưỡng, công trình nghệ thuật…) |

### B2. Giá (Price)

| name                          | type   | required | source (Slide B – Giá) | transform / đơn vị        | description |
|-------------------------------|--------|----------|-------------------------|---------------------------|-------------|
| `price_vs_reference`          | string | no       | Giá                     | giữ nguyên (vd `~1/3 so với Seoul`) | Mặt bằng giá bán so với trung tâm tham chiếu |
| `living_fee_usd_per_m2_month` | string | no       | Giá                     | dải USD/m²/tháng          | Phí sinh hoạt/duy trì (vd `1.5-2`) |
| `has_urban_service_fee`       | bool   | no       | Giá                     | true/false                | Có phí dịch vụ KĐT hay không |
| `sales_scheme`                | string | no       | Giá                     | strip                     | Cơ chế bán (B2B hãng bay, "thuê trước – mua sau"…) |

### B3. Dịch vụ (Service)

| name                    | type   | required | source (Slide B – Dịch vụ) | transform | description |
|-------------------------|--------|----------|-----------------------------|-----------|-------------|
| `airport_privilege`     | string | no       | Dịch vụ                     | strip     | Đặc quyền sân bay (giảm vé bus/xe tháng, Fast Track, Priority…) |
| `has_airport_privilege` | bool   | no       | Dịch vụ                     | true/false| Có triển khai đặc quyền sân bay không |
| `smart_city`            | string | no       | Dịch vụ                     | strip     | Mức độ tích hợp smart city (IoT, xử lý rác, AI giao thông…) |
| `has_smart_city`        | bool   | no       | Dịch vụ                     | true/false| Có tích hợp smart city không |

### B4. Trải nghiệm (Experience)

| name                | type   | required | source (Slide B – Trải nghiệm) | transform | description |
|---------------------|--------|----------|--------------------------------|-----------|-------------|
| `experience_desc`   | string | no       | Trải nghiệm                    | strip     | Hoạt động trải nghiệm (sự kiện tổ bay, business, music festival, triển lãm, tour cuối tuần…) |

### B5. Thuận tiện (Convenience)

| name                | type   | required | source (Slide B – Thuận tiện) | transform / đơn vị | description |
|---------------------|--------|----------|-------------------------------|--------------------|-------------|
| `connectivity_desc` | string | no       | Thuận tiện                    | strip              | Mô tả khả năng kết nối |
| `connection_modes`  | list   | no       | Thuận tiện                    | tách `;`           | Phương thức kết nối (metro; cao tốc; bus) |
| `metro_lines`       | int    | no       | Thuận tiện                    | số tuyến           | Số tuyến metro (Incheon 1, Hongqiao 3, Tianfu 2) |

### B6. Thương hiệu (Brand)

| name              | type   | required | source (Slide B – Thương hiệu) | transform | description |
|-------------------|--------|----------|--------------------------------|-----------|-------------|
| `brand_desc`      | string | no       | Thương hiệu                    | strip     | Mô hình chủ lực & đối tác thương hiệu |
| `lead_developer`  | string | no       | Thương hiệu                    | strip     | Bên dẫn dắt (nhà nước, Korean LH/POSCO, chính quyền TP…) |
| `brand_partners`  | list   | no       | Thương hiệu                    | tách `;`  | Đối tác lớn (Lotte; Hyundai; Chadwick International…) |

---

## Provenance (extractor tự thêm)

`source_name`, `source_url`, `source_slide`, `accessed_at`, `confidence`
(`high`/`medium`/`low` — đặt `low` cho giá trị OCR chưa chắc).

## Seed case studies quan sát được (từ 2 slide)

| case_name              | country     | area_km2 | reference_city | distance_to_city_km | metro_lines | residential_highrise_pct |
|------------------------|-------------|----------|----------------|---------------------|-------------|--------------------------|
| Incheon – Yeongjong    | Hàn Quốc    | 51.18    | Seoul          | 46                  | 1           | 95.5                     |
| Incheon – Songdo       | Hàn Quốc    | 53.4     | Seoul          | 46                  | 1           | 95.5                     |
| Incheon – Cheongna     | Hàn Quốc    | 17.8     | Seoul          | 46                  | 1           | 95.5                     |
| Tianfu Airport City    | Trung Quốc  | ~483     | Thành Đô       | ~50                 | 2           | 100                      |
| Hongqiao CBD           | Trung Quốc  | 151      | Thượng Hải     | ~15                 | 3           | 80 (20 thấp tầng)        |
| Aranya                 | Trung Quốc  | (n/a)    | Bắc Kinh       | (ven biển)          | (n/a)       | (nghỉ dưỡng/second home) |
| Gia Binh Airport City  | Việt Nam ★  | ~50      | Hà Nội         | ~35                 | (n/a)       | (chưa xác định)          |

★ `is_target = true`. GBAC: sân bay 2025–2027; thuộc **Phân khu I-3 Nam Sông Đuống**;
định vị "thành phố công viên" & đổi mới công nghệ; mảng xanh là khung xương sống;
phân khu: khoa học & công nghệ, trung tâm thương mại, lõi năng động, sản xuất thông
minh, hành lang sinh thái nghỉ dưỡng. **Chủ đầu tư:** Nhà nước định hướng, tư nhân
triển khai (**Masterise, Vingroup, Sungroup**).

### Giá trị đã xác minh từ PDF (trang 29 & 59) — `confidence=high`

| case | total_investment_usd (verified) | governance | ghi chú |
|------|----------------------------------|------------|---------|
| Incheon | Toàn khu IFEZ **60–70 tỷ USD**; sân bay Incheon (4 phase) ~**14–15 tỷ USD**, phase đầu ~**4.8 tỷ USD** | Nhà nước dẫn dắt + Korea LH, IH, NSIC thực hiện | GDP Seoul 170 tỷ USD, ~8.000 USD/người (1992) |
| Tianfu | New Area **140 tỷ USD**; sân bay **10.8 tỷ USD**; Airport Economic Zone **40–50 tỷ USD** | Nhà nước định hướng (~70%) & tư nhân (~30%): BQL Thành Đông Tân Khu + Vanke, Longfor | — |
| Hongqiao | District **60–70 tỷ USD**; sân bay **2.2 tỷ USD**; NECC, Transportation Hub | Chính quyền Thượng Hải dẫn dắt + tập đoàn nhà nước | GDP Thượng Hải 200 tỷ USD (2007); nhà ga T2 2007–2010 |
| GBAC | Chưa công bố tổng mức đầu tư; tham chiếu: GDP Hà Nội + Bắc Ninh ~**90 tỷ USD** (≈40–50% các địa phương đối sánh) | Nhà nước định hướng, tư nhân triển khai (Masterise, Vingroup, Sungroup) | Nhận định: GBAC khó tái lập quỹ đạo tăng trưởng KĐT sân bay quốc tế nếu kinh tế địa phương chưa đủ lớn |

> **Còn `confidence=low` / cần xác minh thêm:** một vài chỉ số phái sinh và giá trị
> bị che khuất trong ảnh. **Không bịa số còn thiếu.**

## Output mong muốn

- `raw_data/output/ws1_airport/features/airport_city_benchmark.{csv,jsonl}`
- Cột = toàn bộ `name` ở trên + cột provenance.
- Khoá: `case_name` (không rỗng, không trùng).
