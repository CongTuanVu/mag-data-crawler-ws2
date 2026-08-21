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
      + aerotropolis_done.txt                (không có URL — chỉ tên, quốc gia, sân bay)
        │                                    khu đã xong chuyển sang _done cho gọn hàng đợi;
        │                                    cả hai file đều được đọc như một danh sách
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

Chạy toàn bộ bằng một lệnh:

```bash
./run_all.sh                    # mọi khu chưa có dữ liệu, 4 luồng song song
JOBS=8 ./run_all.sh             # 8 luồng (phải nâng LLM_PROXY_MAX_CONCURRENCY cho khớp)
./run_all.sh zhengzhou delhi    # chỉ vài khu chỉ định
FRESH=1 ./run_all.sh            # làm lại cả những khu đã có feature
```

`run_all.sh` tự khởi động proxy nếu chưa chạy, chia nhóm cho `scripts/run_batch.sh`,
chờ xong rồi chạy registry → validate → build_portal. Ngắt giữa chừng chạy lại là
tiếp tục, không làm lại phần đã xong.

> **JOBS phải ≤ `LLM_PROXY_MAX_CONCURRENCY`.** Vượt trần thì Claude API trả `429
> usage_limit` hàng loạt và discover/extract hỏng im lặng — log chỉ hiện "không tìm
> được nguồn nào". Đã xảy ra ở lần chạy 8 luồng với proxy đặt 4.

Hoặc gọi orchestrator theo từng bước:

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
# [1] LLM tra web tìm nguồn (đầu vào: refer_file/aerotropolis{,_done}.txt)
python scripts/discover_sources.py --missing        # chỉ case chưa có nguồn nào
python scripts/discover_sources.py --all --want 25  # bổ sung thêm cho mọi case
python scripts/discover_sources.py --case taoyuan --dry-run
#     --focus passengers_million,area_km2,employees,subzones
#         nhắm vào các trường còn trống: prompt nêu thẳng cụm từ mà trang nguồn hay
#         dùng (kể cả tiếng bản địa: 占地面积, 就业人数) và bắt model tra riêng từng trường

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

Ảnh minh hoạ cho thẻ trên cổng tra cứu (chạy trước bước [6]):

```bash
python html/harvest_images.py --name incheon        # -> html/assets/incheon/
python html/harvest_images.py --name incheon --inspect   # xem ứng viên trước khi curate tay
#     --min-width 560   bề rộng ảnh GỐC tối thiểu; nhỏ hơn thì thử ứng viên khác
#     --max-width 1100  bề rộng sau khi thu nhỏ để nhúng vào trang
```

Mỗi khu lấy 4 ảnh: `hero`, `planning`, `vision`, `experience`. Khu nào có trong bảng
`CURATION` (đầu `harvest_images.py`) thì dùng ảnh curate tay; khu chưa có thì script
**tự chấm điểm ứng viên và chọn**, nên khu mới crawl về là có ảnh ngay.

Bộ lọc chất lượng: sàn cứng 400px, tỷ lệ khung hình trong khoảng 1:3–3.5:1 (loại icon,
logo, dải trang trí), và mỗi mục giữ 6 ứng viên để lùi khi ảnh đầu tải hỏng — 403 chặn
hotlink, 404 media đã dời, hoặc URL hoá ra là API chứ không phải ảnh.

**Cạm bẫy Wikimedia:** URL ảnh Wikipedia là thumbnail theo đường dẫn (`/250px-Ten.jpg`).
Script nâng lên `1280px` nhưng **tuyệt đối không lấy file gốc trên Commons** — nhiều tấm
10–80MB, mà `timeout` của `requests` chỉ tính khoảng lặng giữa hai gói tin nên tải file
lớn qua đường bị bóp nhịp là treo vô hạn định. Wikimedia cũng phạt 429 tới 105 giây, nên
script giãn nhịp 2,5s giữa hai request tới host này.

## Danh sách nguồn: `refer_file/`

Đầu vào bắt buộc chỉ là `aerotropolis.txt` — danh sách tên khu, **không có URL**.
Nguồn crawl do `discover_sources.py` (LLM tra web) sinh ra, rồi
`build_source_registry.py` chuẩn hoá và join với `manifest.json` để biết URL nào
đã crawl được:

| File | Nội dung |
|---|---|
| `refer_file/aerotropolis.txt` | **đầu vào gốc — hàng đợi**: khu CHƯA có feature, chỉ tên + quốc gia + sân bay |
| `refer_file/aerotropolis_done.txt` | khu ĐÃ có feature, cùng định dạng bảng, giữ nguyên số thứ tự gốc |
| `refer_file/cases.csv` | 1 dòng / case: định danh, website chính thức, số nguồn, số trang đã crawl |
| `refer_file/sources.csv` | 1 dòng / URL: `case_id`, `url`, `purpose`, `target_fields`, `has_images`, `priority`, trạng thái crawl |
| `refer_file/sources.xlsx` | cùng nội dung, 2 sheet — bản cho người biên tập |
| `refer_file/_discovered/<case>.csv` | nguồn do discover tìm được, mỗi case một file (tránh ghi đè khi chạy song song) |

Hai file `.txt` là **một danh sách duy nhất bị cắt đôi cho gọn**: `parse_case_list()`
đọc cả hai. Sửa để chỉ đọc một file là registry và trang web mất sạch phần khu đã xong.

Cột `origin` cho biết nguồn đến từ đâu: `llm` (discover tra web), `curated` (người
tuyển tay trong bảng `.txt`), `manifest` (URL đã crawl nhưng không có trong registry).
Cột `has_images` đánh dấu trang có ảnh minh hoạ dùng được (≥800px, không phải logo).

Thêm nguồn: hoặc chạy `discover_sources.py` để LLM tự tìm, hoặc mở `sources.csv`
(`.xlsx`) thêm dòng `case_id` + `url` rồi chạy lại crawl → extract.

Thêm **khu mới**: thêm một dòng vào `refer_file/aerotropolis.txt` (tên, quốc gia,
sân bay), rồi `python scripts/run_ws.py ws1_airport` — discover sẽ tự tìm nguồn cho nó.

## Cấu trúc thư mục

```
mag-data-crawler/
├── code_proxy/                         # HTTP proxy: Messages API -> claude CLI (không cần API key)
├── run_all.sh                          # ★ chạy toàn pipeline, chia luồng song song
├── refer_file/
│   ├── aerotropolis.txt                # ★ ĐẦU VÀO GỐC: khu chưa xử lý
│   ├── aerotropolis_done.txt           # ★ khu đã có feature (cùng danh sách, tách ra)
│   ├── _discovered/<case>.csv          # nguồn do discover tìm, mỗi case một file
│   └── cases.csv · sources.csv · sources.xlsx   # registry nguồn (sinh ra)
├── refer_img/                          # slide gốc — tham chiếu feature & thiết kế trang
├── features/ws1_airport/
│   ├── feature_spec.md                 # [1] định nghĩa feature dạng văn bản
│   ├── schema.json                     # ★ 75 trường máy đọc: nhóm, kiểu, đơn vị, keyword lọc
│   └── cases_registry.json             # định danh case đã biết (tên VN, website chính thức)
├── agent_extractor/
│   ├── SKILL.md                        # meta-skill: spec -> extractor
│   └── ws1_airport/
│       ├── llm_prep.py                 # ★ nén raw -> dossier (bỏ boilerplate, chấm điểm block)
│       ├── extract_llm.py              # ★ extractor LLM: 75 trường + provenance
├── raw_data/
│   ├── crawler/crawl_sources.py        # ★ crawler chính (Playwright, append, PDF, đọc registry)
│   └── output/ws1_airport/
│       ├── raw/<case>/                 # pages/*.{html,txt,png} + manifest.json + crawl_log.csv
│       ├── features/                   # <case>_airport_city.json + benchmark + coverage_*
│       └── _llm_log/                   # phản hồi JSON thô của model (không commit, xoá được)
├── html/
│   ├── build_portal.py                 # ★ cổng tra cứu: tìm kiếm + modal chi tiết
│   ├── harvest_images.py               # thu + nén ảnh minh hoạ -> assets/<case>/
│   ├── assets/<case>/                  # hero/planning/vision/experience.jpg + images.json
│   └── index.html                      # ★ output cổng tra cứu
└── scripts/
    ├── discover_sources.py             # ★ LLM tra web tìm URL nguồn (web_search/web_fetch)
    ├── build_source_registry.py        # dựng refer_file/{cases,sources}.csv|.xlsx
    ├── validate_features.py            # validate + benchmark + coverage report
    ├── run_batch.sh                    # chạy trọn pipeline cho MỘT nhóm case (run_all.sh gọi)
    ├── fill_kpi_gaps.sh                # bổ sung 4 chỉ số hay thiếu cho 1 khu
    ├── merge_kpi.py                    # gộp record sau khi extract lại, chống mất dữ liệu
    └── run_ws.py                       # orchestrator theo bước
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

> **Coi chừng tên gần giống nhau.** `match_case_id()` khớp tên khu với registry theo ranh
> giới từ, và ranh giới ở đây loại cả dấu gạch nối — nếu không, *"Frankfurt-Hahn Airport
> City"* (sân bay HHN, cách Frankfurt 120km) sẽ khớp `frankfurt` rồi bị đánh dấu đã xử lý
> theo dữ liệu của sân bay khác. Một registry `case_id` cũng chỉ được cấp cho đúng một
> dòng; dòng thứ hai khớp cùng id sẽ nhận slug riêng (`frankfurt_hahn`).

Muốn định danh chuẩn hơn (tên tiếng Việt, website chính thức) thì thêm case vào
[`features/ws1_airport/cases_registry.json`](features/ws1_airport/cases_registry.json).

## Bổ sung chỉ số còn thiếu cho khu đã chạy

Bốn chỉ số hiện lên mặt thẻ (`passengers_million`, `area_km2`, `employees`, `subzones`)
hay trống nhất. Bổ sung riêng cho một khu:

```bash
./scripts/fill_kpi_gaps.sh doha employees     # discover +10 URL → crawl → extract lại
python scripts/merge_kpi.py --dry-run         # xem sẽ đổi gì
python scripts/merge_kpi.py                   # gộp
```

> **Bắt buộc chạy `merge_kpi.py` sau đó.** `extract_llm.py` dựng lại TOÀN BỘ record mỗi
> lần chạy, mà model không tất định — lượt mới có thể bỏ trống đúng trường lượt trước đã
> trích được. Chạy lại để thêm 4 chỉ số mà mất 6 trường khác thì lợi bất cập hại.
> `merge_kpi.py` so với bản sao lưu và khôi phục mọi trường bị bỏ trống kèm provenance gốc.
> Sao lưu trước khi chạy:
> ```bash
> cp -r raw_data/output/ws1_airport/features raw_data/output/ws1_airport/_features_backup_kpi
> ```

Thực tế đo được: trong 9 khu độ phủ >75%, chỉ **3 khu** điền được trường đích. Sáu khu
còn lại trống vì nguồn **không công bố một con số duy nhất** — ranh giới "airport city"
của Schiphol hay Đại Hưng không cố định. Đó là giới hạn của dữ liệu, thêm nguồn không cứu được.

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
- **Ưu tiên nguồn chuẩn khi xung đột.** Chỉ số headline lấy từ trang thống kê
  chính thức, tránh số marketing kiểu "over 300".
- **"Không có" khác 0.** Nguồn nói *"no commercial passenger service"* thì trường để
  `null` + lý do, KHÔNG điền `0` — vì 0 nghĩa là đã đo được và bằng không, trang web sẽ
  hiện "0 triệu lượt khách/năm" như thể dữ liệu hỏng. Quy tắc 9 trong `SYSTEM_RULES`.
- **Tên hiển thị không được là slug.** `case_name` phải là tên viết cho người đọc
  ("Dubai International Aviation District"), không phải `dubai_aviation_district`.
  Quy tắc 12 trong `SYSTEM_RULES`; `build_portal.py` còn đè thêm một lớp từ `cases.csv`.
- Crawl hợp pháp: tôn trọng `robots.txt`, không vượt auth/paywall.

## Ghi chú

Extractor regex `extract_airport_city.py` đã được gỡ khỏi repo. Phần duy nhất còn
cần từ nó — bảng định danh case — nay nằm ở
[`features/ws1_airport/cases_registry.json`](features/ws1_airport/cases_registry.json),
do `build_source_registry.py` đọc trực tiếp.

Cùng với nó, thư mục `features/_deterministic/` (mốc đối chiếu bản regex) cũng đã bị
xoá. Hệ quả: `llm_prep.baseline_record()` nay rơi xuống nhánh dự phòng là đọc chính
`features/<case>_airport_city.json` — tức output LLM lần trước — nên **lần extract sau
sẽ tự xác nhận lại kết quả cũ thay vì đối chiếu với baseline độc lập**
([`llm_prep.py:186`](agent_extractor/ws1_airport/llm_prep.py#L186)).
Cần mốc độc lập trở lại thì khôi phục thư mục từ git:

```bash
git checkout <commit-trước-khi-xoá> -- raw_data/output/ws1_airport/features/_deterministic
```
