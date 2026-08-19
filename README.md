# MAG Data Crawler

Pipeline crawl dữ liệu web theo mô hình **feature-driven** để **benchmark các Khu
đô thị Sân bay (airport city / aerotropolis)** trên thế giới, phục vụ đối chiếu
với dự án **Gia Bình Airport City (GBAC)**.

Bạn định nghĩa *cần lấy trường gì* (Features); crawler lo phần lấy raw từ web;
một *extractor LLM* đọc raw và điền trường kèm nguồn; cuối cùng khối *HTML* dệt
dữ liệu thành **cổng tra cứu tự chứa** (mở bằng double-click, không cần server).

## Luồng pipeline

```
refer_file/aerotropolis.txt             ← [0] ĐẦU VÀO DUY NHẤT: danh sách TÊN aerotropolis
        │                                    (không có URL — chỉ tên, quốc gia, sân bay)
        ▼
scripts/discover_sources.py             ← [1] LLM TRA WEB tìm nguồn cho từng khu
        │  gọi model kèm web_search / web_fetch, probe URL rồi ghi vào registry
        ▼
refer_file/sources.csv (+ cases.csv, .xlsx)   ← [2] DANH SÁCH NGUỒN tập trung
        │  scripts/build_source_registry.py chuẩn hoá + join trạng thái crawl
        ▼
raw_data/crawler/crawl_sources.py       ← [3] CRAWL (Playwright, append-only, bóc PDF)
        ▼
raw_data/output/ws1_airport/raw/<case>/pages/*.{html,txt,png}  +  manifest.json
        ▼
agent_extractor/ws1_airport/llm_prep.py ← [4a] nén raw 3,9M ký tự → dossier ~66k/case
agent_extractor/ws1_airport/extract_llm.py ← [4b] LLM điền 75 trường + provenance
        │       (gọi model qua code_proxy → Claude Code CLI, KHÔNG cần API key)
        ▼
raw_data/output/ws1_airport/features/<case>_airport_city.json
        │  record + provenance(source_url, snippet, confidence) + missing(lý do)
        │  + narrative: lời văn tiếng Việt từng nhóm (viết từ record, không thêm dữ kiện)
        ▼
scripts/validate_features.py            ← [5] kiểm kiểu + gộp benchmark + coverage report
        ▼
html/build_portal.py                    ← [6] CỔNG TRA CỨU: tìm kiếm + modal chi tiết
        ▼
html/index.html
```

Chạy cả 7 bước bằng một lệnh:

```bash
python scripts/run_ws.py ws1_airport
python scripts/run_ws.py ws1_airport --steps extract,validate,web
python scripts/run_ws.py ws1_airport --steps crawl --cases incheon,changi
```

## Cài đặt

```bash
cd mag-data-crawler
python -m pip install -r requirements.txt
python -m playwright install chromium
```

Hai bước `discover` và `extract` gọi model qua [`code_proxy/`](code_proxy/README.md) — một HTTP
server localhost nói Anthropic Messages API nhưng bên dưới chạy `claude --print`,
nên dùng phiên đăng nhập Claude Code sẵn có, **không cần `ANTHROPIC_API_KEY`**:

```bash
claude auth status                                            # phải thấy "loggedIn": true

# terminal 1
CLAUDE_PROXY_MODEL=claude-opus-5 ./code_proxy/start.sh --timeout 900
# terminal 2
export ANTHROPIC_BASE_URL=http://127.0.0.1:11439
```

## Chạy từng bước

```bash
# [1] LLM tra web tìm nguồn (đầu vào: refer_file/aerotropolis.txt)
python scripts/discover_sources.py --missing        # chỉ case chưa có nguồn nào
python scripts/discover_sources.py --all --want 25  # bổ sung thêm cho mọi case
python scripts/discover_sources.py --case taoyuan --dry-run

# [2] chuẩn hoá registry + join trạng thái crawl từ manifest
python scripts/build_source_registry.py
#     --rev HEAD để lấy lại bảng .txt đã xoá khỏi working tree

# [3] crawl 1 case (mặc định đọc refer_file/sources.csv, lọc theo --name)
python raw_data/crawler/crawl_sources.py --name incheon
#     cờ: --fresh (crawl lại từ đầu) · --shots (chụp ảnh trang) · --headful · --timeout N
#         --input refer_file/incheon.txt (dùng bảng .txt thay cho registry)

# [4] trích feature bằng LLM (2 lượt/case: dữ kiện cứng + phân tích CVP)
python agent_extractor/ws1_airport/extract_llm.py --case incheon
python agent_extractor/ws1_airport/extract_llm.py --all
python agent_extractor/ws1_airport/extract_llm.py --all --dry-run        # chỉ in cỡ prompt
python agent_extractor/ws1_airport/extract_llm.py --all --narrative-only # chỉ viết lại lời văn

# xem trước dossier mà LLM sẽ đọc
python agent_extractor/ws1_airport/llm_prep.py --case incheon --out /tmp/incheon.md

# [5] validate + gộp bảng + báo cáo độ phủ
python scripts/validate_features.py

# [6] dựng cổng tra cứu (thêm --no-images cho file nhẹ)
python html/build_portal.py
```

Ảnh minh hoạ cho thẻ trên cổng tra cứu (tuỳ chọn, chạy trước bước [6]):

```bash
python html/harvest_images.py --name incheon      # -> html/assets/incheon/
```

## Danh sách nguồn: `refer_file/`

Đầu vào bắt buộc chỉ là `aerotropolis.txt` — danh sách tên khu, **không có URL**.
Nguồn crawl do `discover_sources.py` (LLM tra web) sinh ra, rồi
`build_source_registry.py` chuẩn hoá và join với `manifest.json` để biết URL nào
đã crawl được:

| File | Nội dung |
|---|---|
| `refer_file/cases.csv` | 1 dòng / case: định danh, website chính thức, số nguồn, số trang đã crawl |
| `refer_file/sources.csv` | 1 dòng / URL: `case_id`, `url`, `purpose`, `target_fields`, `priority`, trạng thái crawl |
| `refer_file/sources.xlsx` | cùng nội dung, 2 sheet — bản cho người biên tập |
| `refer_file/aerotropolis.txt` | **đầu vào gốc**: 10 aerotropolis, chỉ tên + quốc gia + sân bay |

Cột `origin` cho biết nguồn đến từ đâu: `llm` (discover tra web), `curated` (người
tuyển tay trong bảng `.txt`), `manifest` (URL đã crawl nhưng không có trong registry).

Thêm nguồn: hoặc chạy `discover_sources.py` để LLM tự tìm, hoặc mở `sources.csv`
(`.xlsx`) thêm dòng `case_id` + `url` rồi chạy lại crawl → extract.

Thêm **khu mới**: thêm một dòng vào `refer_file/aerotropolis.txt` (tên, quốc gia,
sân bay), rồi `python scripts/run_ws.py ws1_airport` — discover sẽ tự tìm nguồn cho nó.

## Cấu trúc thư mục

```
mag-data-crawler/
├── code_proxy/                         # HTTP proxy: Messages API -> claude CLI (không cần API key)
├── refer_file/
│   ├── aerotropolis.txt                # ★ ĐẦU VÀO GỐC: danh sách tên aerotropolis
│   └── cases.csv · sources.csv · sources.xlsx   # registry nguồn (sinh ra)
├── refer_img/                          # 2 slide gốc — tham chiếu feature & thiết kế trang
├── features/ws1_airport/
│   ├── feature_spec.md                 # [1] định nghĩa feature dạng văn bản
│   └── schema.json                     # ★ 75 trường máy đọc: nhóm, kiểu, đơn vị, keyword lọc
├── agent_extractor/
│   ├── SKILL.md                        # meta-skill: spec -> extractor
│   └── ws1_airport/
│       ├── llm_prep.py                 # ★ nén raw -> dossier (bỏ boilerplate, chấm điểm block)
│       ├── extract_llm.py              # ★ extractor LLM: 75 trường + provenance
│       └── extract_airport_city.py     # extractor regex — giữ làm baseline + REGISTRY định danh case
├── raw_data/
│   ├── crawler/crawl_sources.py        # ★ crawler chính (Playwright, append, PDF, đọc registry)
│   └── output/ws1_airport/
│       ├── raw/<case>/                 # pages/*.{html,txt,png} + manifest.json + crawl_log.csv
│       ├── features/                   # <case>_airport_city.json + benchmark + coverage_*
│       │   └── _deterministic/         # bản regex trước khi LLM ghi đè (để đối chiếu)
│       └── _llm_log/                   # phản hồi JSON thô của model, theo case & lượt
├── html/
│   ├── build_portal.py                 # ★ cổng tra cứu: tìm kiếm + modal chi tiết
│   ├── harvest_images.py               # thu + nén ảnh minh hoạ -> assets/<case>/
│   └── index.html                      # ★ output cổng tra cứu
└── scripts/
    ├── discover_sources.py             # ★ LLM tra web tìm URL nguồn (web_search/web_fetch)
    ├── build_source_registry.py        # dựng refer_file/{cases,sources}.csv|.xlsx
    ├── validate_features.py            # validate + benchmark + coverage report
    └── run_ws.py                       # orchestrator 6 bước
```

## Output dữ liệu

| File | Nội dung |
|---|---|
| `features/<case>_airport_city.json` | `record` (75 trường) · `provenance` từng trường · `missing` kèm lý do · `_meta` (model, độ phủ, cảnh báo) |
| `features/airport_city_benchmark.csv/.jsonl` | bảng phẳng, 1 dòng / case, khoá `case_name` |
| `features/coverage_report.csv` | 1 dòng / (case, trường): có giá trị chưa, nguồn, confidence, lý do thiếu |
| `features/coverage_summary.csv` | 1 dòng / case: % độ phủ, số trường high/medium/low, số lấy từ baseline |
| `html/index.html` | cổng tra cứu tự chứa: tìm kiếm, lọc quốc gia, sắp xếp; bấm 1 khu mở hồ sơ dạng bảng nhãn–lời văn + tab tra cứu 75 trường kèm nguồn |

## Thêm một case aerotropolis mới

1. Thêm 1 dòng vào [`refer_file/aerotropolis.txt`](refer_file/aerotropolis.txt):
   `| 11 | Tên khu | Quốc gia | Sân bay trung tâm | ghi chú |`
2. `python scripts/run_ws.py ws1_airport --cases <case_id>`

`case_id` được sinh tự động từ tên (bỏ dấu, bỏ chữ "aerotropolis"/"airport city");
xem lại bằng `python scripts/build_source_registry.py` rồi đọc `refer_file/cases.csv`.
Không cần viết regex riêng, không cần tự tuyển URL: discover tìm nguồn, extractor
LLM đọc hiểu văn bản.

Muốn định danh chuẩn hơn (tên tiếng Việt, website chính thức) thì thêm case vào
`REGISTRY` trong [`extract_airport_city.py`](agent_extractor/ws1_airport/extract_airport_city.py).

## Thêm một trường mới

Sửa `features/ws1_airport/schema.json` (thêm `name`, `type`, `label`, `unit`,
`desc`, `kw` để lọc đoạn liên quan), rồi chạy lại `extract → validate → web`.
Prompt, validator và trang web đều đọc từ file này — không hardcode ở nơi khác.

## Nguyên tắc dữ liệu

- **Raw là bất biến (append-only).** Không sửa đè file trong `output/<ws>/raw/`.
  Crawl lại mặc định **gộp thêm** (bỏ URL trùng, đánh số tiếp), giữ nguyên data cũ.
- **Mỗi giá trị phải truy được nguồn.** Mỗi trường có `source_url`, `source_file`,
  `snippet` (câu gốc) và `confidence`; trang web hiện đủ ba thứ đó khi bấm vào case.
- **Không bịa số.** Model chỉ thấy dossier trích từ raw đã crawl, không có mạng.
  Trường không có bằng chứng → `null` + lý do trong `missing`, không suy đoán.
- **Mã nguồn được đối chiếu ngược.** LLM phải dẫn mã `[Snn]`; mã không khớp
  `manifest.json` bị hạ `confidence` xuống `low` và gắn cờ `unverified_source`.
- **Không mất dữ liệu cũ.** Bản regex được backup sang `features/_deterministic/`;
  trường LLM không xác minh được vẫn giữ giá trị regex, đánh dấu `source=baseline`.
- **Ưu tiên nguồn chuẩn khi xung đột.** Chỉ số headline lấy từ trang thống kê
  chính thức, tránh số marketing kiểu "over 300".
- Crawl hợp pháp: tôn trọng `robots.txt`, không vượt auth/paywall.

## Ghi chú

`extract_airport_city.py` (1133 dòng regex) không còn nằm trong pipeline nhưng vẫn
được giữ vì hai lý do: `REGISTRY` trong đó là nguồn định danh case cho
`build_source_registry.py`, và bản trích của nó trong
`features/_deterministic/` là mốc đối chiếu để phát hiện LLM trả sai.
