# MAG Data Crawler

Pipeline crawl dữ liệu web theo mô hình **feature-driven** để **benchmark các Khu
đô thị Sân bay (airport city / aerotropolis)** trên thế giới, phục vụ đối chiếu
với dự án **Gia Bình Airport City (GBAC)**.

Bạn định nghĩa *cần lấy trường gì* (Features); một *Agent Extractor* đọc định
nghĩa đó như một skill và **sinh ra file Python** để trích xuất; *Raw Data* lo
phần crawl web; cuối cùng khối *HTML* dệt dữ liệu thành **trang hồ sơ 2-slide
tiếng Việt, tự chứa** (mở bằng double-click, không cần server).

## Luồng Core Crawler

```
Research (Domain)
      │  người dùng định nghĩa domain + trường cần lấy
      ▼
features/<ws>/feature_spec.md              ← [1] ĐỊNH NGHĨA feature (nguồn sự thật)
      │
      ▼
agent_extractor/SKILL.md (+ <ws>/extractor_skill.md)   ← [2] SKILL: spec → cách extract
      │  (agent học skill, sinh code)
      ▼
agent_extractor/<ws>/extract_*.py          ← FILE.PY được gen ra
      ▲
      │  đọc dữ liệu thô (.txt đã crawl)
raw_data/crawler/crawl_*.py ──crawl web──▶ raw_data/output/<ws>/raw/<case>/
      │
      ▼ (chạy extractor)
raw_data/output/<ws>/features/             ← [3] DATA cuối + provenance từng trường
      │
      ▼
html/SKILL.md → html/build_html.py         ← [4] TRÌNH BÀY: trang hồ sơ tiếng Việt
      │
      ▼
html/<case>.html · html/index.html
```

Ánh xạ với sơ đồ trong `refer_img/image.png`:

| Khối trong sơ đồ        | Thư mục trong repo                         |
|-------------------------|--------------------------------------------|
| Research (Domain)       | `features/<ws>/feature_spec.md`            |
| Crawler Raw (Raw_data)  | `raw_data/crawler/` → `output/<ws>/raw/`   |
| Agent Extractor (skill) | `agent_extractor/SKILL.md` + `<ws>/`       |
| file.py                 | `agent_extractor/<ws>/extract_*.py`        |
| Deploy / feature storage| `raw_data/output/<ws>/features/`           |
| (mở rộng) Trình bày     | `html/SKILL.md` → `html/build_html.py`     |

## Cấu trúc thư mục

```
mag-data-crawler/
├── config/
│   └── sources.yaml                    # nguồn URL dạng file (dùng cho luồng legacy)
├── refer_file/                         # BẢNG NGUỒN đã tuyển tay (input của crawler chính)
│   ├── Schiphol.txt                    # 10 nguồn đợt 1
│   ├── schiphol1.txt                   # 24 nguồn đợt 2 (crawl append)
│   └── aerotropolis1.txt               # danh sách case aerotropolis thế giới
├── refer_img/                          # 2 slide gốc — tham chiếu feature & thiết kế trang
├── features/                           # [1] ĐỊNH NGHĨA feature
│   └── ws1_airport/feature_spec.md     # schema thực thi v2 (42 trường) + khung Group A/B
├── agent_extractor/                    # [2] SKILL + code extractor được gen
│   ├── SKILL.md                        # meta-skill: quy trình đọc spec → gen .py
│   └── ws1_airport/
│       ├── extractor_skill.md
│       ├── extract_airport_city.py     # ★ extractor đang dùng (case study aerotropolis)
│       └── extract_airport.py          # legacy: OpenFlights airports.dat
├── raw_data/                           # [3] crawl web + lưu output
│   ├── crawler/
│   │   ├── base_crawler.py             # HTTP client chung (requests + retry + manifest)
│   │   ├── crawl_sources.py            # ★ crawler chính (Playwright, append, PDF)
│   │   ├── crawl_aerotropolis.py       # crawl HTML tĩnh theo CSV danh sách case
│   │   ├── crawl_aerotropolis_pw.py    # Playwright: thu ảnh + screenshot full-page
│   │   └── crawl_airport.py            # legacy: tải file theo config/sources.yaml
│   └── output/ws1_airport/
│       ├── raw/<case>/                 # pages/*.html|.txt|.png|.pdf + manifest.json + crawl_log.csv
│       └── features/                   # <case>_airport_city.json + benchmark.{csv,jsonl}
├── html/                               # [4] lớp trình bày
│   ├── SKILL.md                        # skill dựng trang hồ sơ
│   ├── harvest_images.py               # thu + nén ảnh minh hoạ → assets/<case>/
│   ├── build_html.py                   # dệt lời văn tiếng Việt → trang tự chứa
│   └── assets/<case>/                  # *.jpg + images.json
└── scripts/
    └── run_ws.py                       # orchestrator (hiện mới map luồng legacy)
```

## Cài đặt

```bash
cd mag-data-crawler
python -m pip install -r requirements.txt
# Luồng chính cần thêm 3 gói chưa có trong requirements.txt:
python -m pip install playwright pymupdf Pillow
python -m playwright install chromium
```

## Chạy luồng chính — hồ sơ 1 aerotropolis (ví dụ Schiphol)

Bốn bước, chạy tuần tự:

```bash
# 1. Crawl các nguồn đã tuyển (render JS, lưu html/txt/png, bóc PDF). Mặc định APPEND.
python raw_data/crawler/crawl_sources.py --name schiphol --input refer_file/schiphol1.txt

# 2. Trích xuất feature theo feature_spec (deterministic, không gọi LLM/mạng)
python agent_extractor/ws1_airport/extract_airport_city.py --name schiphol

# 3. Thu ảnh minh hoạ từ chính các trang đã crawl (tuỳ chọn)
python html/harvest_images.py --name schiphol

# 4. Dựng trang hồ sơ tiếng Việt (tự nhúng ảnh nếu có)
python html/build_html.py --name schiphol
```

Cờ hữu ích của `crawl_sources.py`: `--fresh` (bỏ data cũ, crawl lại từ đầu),
`--no-shots` (không chụp screenshot), `--headful` (xem trình duyệt chạy),
`--timeout N`.

Kết quả:

- `raw_data/output/ws1_airport/raw/schiphol/` — `pages/` (html + txt + png),
  `manifest.json`, `crawl_log.csv`
- `raw_data/output/ws1_airport/features/schiphol_airport_city.json` — `record`
  (42 trường) + `provenance` (nguồn từng trường)
- `raw_data/output/ws1_airport/features/airport_city_benchmark.{csv,jsonl}` —
  bảng benchmark, mỗi case 1 dòng
- `html/schiphol.html` và `html/index.html` — trang tự chứa (data + ảnh base64)

### Trạng thái hiện tại

Đã chạy hoàn chỉnh **1 case: Schiphol** — 29 nguồn (27 ok) qua 2 đợt crawl
append, 28 trang text → **42 trường, 41 có dữ liệu** (chỉ
`residential_product_desc` null) → trang hồ sơ. Số liệu chốt: **66,8 triệu** hành
khách · **473.815** lượt bay · **2.787 ha** · **68.000** lao động · thuê văn
phòng **€130–280/m²/năm**.

## Luồng legacy (dataset dạng file)

Vẫn giữ để crawl các nguồn là *file dữ liệu* (CSV/JSON) khai báo trong
`config/sources.yaml` — hiện chỉ có OpenFlights `airports.dat`:

```bash
python scripts/run_ws.py ws1_airport          # crawl_airport.py → extract_airport.py
python scripts/run_ws.py ws1_airport --crawl-only
python scripts/run_ws.py ws1_airport --extract-only
```

> `scripts/run_ws.py` **mới map luồng legacy**, chưa gọi 4 bước của luồng chính.
> Với case-study aerotropolis, gõ tay 4 lệnh ở mục trên.

## Thêm một case aerotropolis mới

1. Soạn bảng nguồn `refer_file/<case>.txt` (markdown, mỗi dòng 1 link `[tên](url)`
   + cột "dùng để lấy gì") hoặc `.csv` có cột `url`/`website_url`.
2. Crawl: `python raw_data/crawler/crawl_sources.py --name <case> --input refer_file/<case>.txt`.
3. Thêm định danh case vào `REGISTRY` trong
   [`extract_airport_city.py`](agent_extractor/ws1_airport/extract_airport_city.py)
   (`case_name`, `country`, `airport_name`, `reference_city`, `official_website`, `is_target`).
4. Chỉnh/bổ sung regex trích xuất cho cách hành văn của website case đó
   (bộ pattern hiện tại bám sát website Schiphol, **không tự chuyển sang case khác**).
5. Thêm `CURATION["<case>"]` trong [`harvest_images.py`](html/harvest_images.py)
   (map `mục → slug trang nguồn → caption`), rồi chạy harvest + build.

## Thêm một workstream mới

1. Tạo `features/<ws>/feature_spec.md` mô tả các trường (dùng WS airport làm mẫu).
2. Khai báo nguồn: `config/sources.yaml` (nguồn dạng file) hoặc bảng nguồn trong
   `refer_file/` (nguồn dạng website).
3. Tạo `agent_extractor/<ws>/extractor_skill.md` (copy skill, chỉnh mapping).
4. Để agent đọc `agent_extractor/SKILL.md` + spec → sinh `extract_<ws>.py`.
5. Viết `raw_data/crawler/crawl_<ws>.py` dựa trên `base_crawler.py`, hoặc tái dùng
   `crawl_sources.py` nếu nguồn là danh sách URL.
6. Thêm 1 entry vào `PIPELINES` trong `scripts/run_ws.py`.

## Nguyên tắc dữ liệu

- **Raw là bất biến (append-only).** Không sửa đè file trong `output/<ws>/raw/`.
  Mỗi lần crawl ghi kèm `manifest.json` có `url` và `accessed_at`; crawl lại mặc
  định **gộp thêm** (bỏ URL trùng, đánh số tiếp), giữ nguyên data cũ.
- **Mỗi giá trị phải truy được nguồn.** Extractor ghi `source_url`, `source_file`,
  `snippet` (câu gốc) và `confidence` cho từng trường; trang HTML gắn `ⓘ` link
  nguồn ở cuối mỗi đoạn có dữ liệu.
- **Không bịa số.** Trường nguồn không nêu → `null`; extractor để trống, trang
  HTML tự bỏ mệnh đề tương ứng (vd `residential_product_desc` không xuất hiện).
- **Ưu tiên nguồn chuẩn khi xung đột.** Chỉ số headline lấy từ trang "Facts &
  Figures" (tham số `prefer=`) để tránh số marketing/cũ (vd "over 300" → **301**);
  giá thuê chỉ bắt dòng mở đầu `Starting at`/`From` để loại "Service costs €65/m²".
- **Extractor không gọi mạng, idempotent.** Chạy lại trên cùng raw cho cùng output.
- Crawl hợp pháp: tôn trọng `robots.txt`, không vượt auth/paywall.
