# MAG Data Crawler

Pipeline crawl dữ liệu từ web theo mô hình **feature-driven**: bạn định nghĩa
*cần lấy trường gì* (Features), một *Agent Extractor* đọc định nghĩa đó như một
skill và **sinh ra file Python** để trích xuất, còn *Raw Data* lo phần crawl web
và lưu output theo từng workstream.

## Luồng Core Crawler

```
Research (Domain)
      │  người dùng định nghĩa domain + trường cần lấy
      ▼
features/<workstream>/feature_spec.md      ← ĐỊNH NGHĨA feature (nguồn sự thật)
      │
      ▼
agent_extractor/<workstream>/extractor_skill.md   ← SKILL: cách đọc spec → cách extract
      │  (agent học skill, sinh code)
      ▼
agent_extractor/<workstream>/extract_*.py  ← FILE.PY được gen ra
      ▲
      │  đọc dữ liệu thô
raw_data/crawler/crawl_*.py  ──crawl web──▶ raw_data/output/<workstream>/raw/
      │
      ▼ (chạy extractor)
raw_data/output/<workstream>/features/     ← DATA cuối, đã chuẩn hoá theo feature_spec
```

Ánh xạ với sơ đồ trong `refer_img/image.png`:

| Khối trong sơ đồ        | Thư mục trong repo                         |
|-------------------------|--------------------------------------------|
| Research (Domain)       | `features/<ws>/feature_spec.md`            |
| Crawler Raw (Raw_data)  | `raw_data/crawler/` → `output/<ws>/raw/`   |
| Agent Extractor (skill) | `agent_extractor/<ws>/extractor_skill.md`  |
| file.py                 | `agent_extractor/<ws>/extract_*.py`        |
| Deploy / feature storage| `raw_data/output/<ws>/features/`           |

## Cấu trúc thư mục

```
mag-data-crawler/
├── config/
│   └── sources.yaml                # khai báo nguồn URL cho mỗi workstream
├── features/                       # [1] ĐỊNH NGHĨA feature
│   ├── README.md
│   └── ws1_airport/
│       └── feature_spec.md         # mô tả các trường cần lấy của WS airport
├── agent_extractor/                # [2] SKILL + code extractor được gen
│   ├── README.md
│   ├── SKILL.md                    # meta-skill: quy trình đọc spec → gen .py
│   └── ws1_airport/
│       ├── extractor_skill.md      # skill riêng cho WS airport
│       └── extract_airport.py      # file.py agent gen ra (ví dụ chạy thật)
├── raw_data/                       # [3] crawl web + lưu output
│   ├── README.md
│   ├── crawler/
│   │   ├── base_crawler.py         # HTTP client dùng chung (requests + retry)
│   │   └── crawl_airport.py        # crawl raw cho WS airport
│   └── output/
│       └── ws1_airport/
│           ├── raw/                # HTML/CSV/JSON thô + manifest provenance
│           └── features/           # data đã extract theo feature_spec
└── scripts/
    └── run_ws.py                   # orchestrator: crawl → extract cho 1 workstream
```

## Chạy thử workstream airport (end-to-end)

```bash
cd mag-data-crawler
python -m pip install -r requirements.txt

# chạy toàn bộ: crawl raw rồi extract theo feature
python scripts/run_ws.py ws1_airport

# hoặc chạy từng bước
python raw_data/crawler/crawl_airport.py
python agent_extractor/ws1_airport/extract_airport.py
```

Kết quả:

- `raw_data/output/ws1_airport/raw/airports.dat` + `manifest.json` (provenance)
- `raw_data/output/ws1_airport/features/airports.csv` và `airports.jsonl`

## Thêm một workstream mới

1. Tạo `features/<ws>/feature_spec.md` mô tả các trường (dùng template WS airport).
2. Khai báo nguồn trong `config/sources.yaml`.
3. Tạo `agent_extractor/<ws>/extractor_skill.md` (copy skill, chỉnh mapping).
4. Để agent đọc `agent_extractor/SKILL.md` + spec → sinh `extract_<ws>.py`.
5. Viết `raw_data/crawler/crawl_<ws>.py` dựa trên `base_crawler.py`.
6. `python scripts/run_ws.py <ws>`.

## Nguyên tắc dữ liệu

- **Raw là bất biến (append-only).** Không sửa đè file trong `output/<ws>/raw/`.
  Mỗi lần crawl ghi kèm `manifest.json` có `source_url` và `accessed_at`.
- **Mỗi giá trị phải truy được nguồn.** Feature output giữ cột `source_name`,
  `source_url`, `accessed_at`.
- **Không bịa số.** Trường nào nguồn không có thì để trống + đánh dấu, không suy đoán.
- Crawl hợp pháp: tôn trọng `robots.txt`, không vượt auth/paywall.
