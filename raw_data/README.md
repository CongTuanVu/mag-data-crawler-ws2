# Raw Data — Crawl web & lưu output

Khối này lo phần **lấy dữ liệu thô về** và **chứa toàn bộ output** theo workstream.

```
raw_data/
├── crawler/
│   └── crawl_<ws>.py       # crawl raw cho từng workstream
└── output/
    └── <ws>/
        ├── raw/            # file thô đúng như tải về + manifest.json (provenance)
        └── features/       # data đã chạy qua extractor (csv/jsonl)
```

## Quy tắc

- **`raw/` là bất biến, append-only.** Không sửa đè. Mỗi lần crawl ghi kèm
  `manifest.json` gồm `source_url` và `accessed_at`.
- Crawler **chỉ tải & lưu thô**, không parse feature. Việc trích xuất thuộc
  `agent_extractor/`.
- Tôn trọng `robots.txt`, đặt `User-Agent` rõ ràng, có `sleep` giữa request.
  Không vượt auth/paywall.

## Chạy

```bash
python raw_data/crawler/crawl_sources.py --name <case>   # -> output/ws1_airport/raw/<case>/
```

Sau đó chạy extractor tương ứng để sinh `output/<ws>/features/`.
