# SKILL — Pipeline benchmark khu đô thị sân bay

> Meta-skill cấp repo: mô tả **toàn tuyến** từ một danh sách chỉ có tên khu cho tới
> cổng tra cứu HTML. Hai skill con mô tả từng khối:
> [`agent_extractor/SKILL.md`](agent_extractor/SKILL.md) (spec → extractor) ·
> [`html/SKILL.md`](html/SKILL.md) (feature → trang web).
>
> Hợp đồng về tên trường nằm ở [`features/ws1_airport/schema.json`](features/ws1_airport/schema.json).

## Điều kiện vào / ra

| | Nội dung |
|---|---|
| **Vào** | `refer_file/aerotropolis.txt` — bảng markdown liệt kê tên khu, quốc gia, sân bay. **Không cần URL.** |
| **Ra** | `html/index.html` — cổng tra cứu tự chứa; `features/airport_city_benchmark.{csv,jsonl}` — bảng benchmark |
| **Phụ phẩm** | `refer_file/{cases,sources}.csv|.xlsx` · `raw/<case>/` · `features/<case>_airport_city.json` · `features/coverage_{report,summary}.csv` |

## Sáu bước

```
aerotropolis.txt ──▶ discover ──▶ registry ──▶ crawl ──▶ extract ──▶ validate ──▶ web
                    (LLM+web)    (CSV/xlsx)  (Playwright) (LLM)     (kiểm+báo cáo)
```

```bash
CLAUDE_PROXY_MODEL=claude-opus-5 ./code_proxy/start.sh --timeout 900   # terminal 1
export ANTHROPIC_BASE_URL=http://127.0.0.1:11439                       # terminal 2
python scripts/run_ws.py ws1_airport
```

| Bước | Script | Việc chính | Thời gian |
|---|---|---|---|
| discover | `scripts/discover_sources.py` | LLM dùng `web_search`/`web_fetch` tìm ~20 URL/khu, probe URL sống, gán `target_fields` + `priority` | ~11 phút/khu |
| registry | `scripts/build_source_registry.py` | Gộp nguồn (bảng `.txt` → `sources.csv` cũ → `manifest.json`), chuẩn hoá `idx`, join trạng thái crawl | vài giây |
| crawl | `raw_data/crawler/crawl_sources.py` | Render Chromium, bóc PDF bằng PyMuPDF, **append-only** | ~1 phút/khu |
| extract | `agent_extractor/ws1_airport/extract_llm.py` | Nén raw thành dossier rồi hỏi model 2 lượt, trả 75 trường + provenance | ~3 phút/khu |
| validate | `scripts/validate_features.py` | Kiểm kiểu theo schema, kiểm khoá trùng, xuất coverage report | vài giây |
| web | `html/build_portal.py` | Nhúng toàn bộ vào một HTML tự chứa | vài giây |

## Phần agent phải suy nghĩ

Bốn bước ngoài rìa (registry, crawl, validate, web) là cơ khí — chạy lệnh, đọc log.
Chất lượng dữ liệu quyết định ở hai bước gọi model.

### discover — tuyển nguồn

Thứ tự ưu tiên đã mã hoá trong prompt: trang chính thức của khu/authority → trang
sân bay (facts & figures, annual report) → cơ quan quy hoạch (master plan, vốn đầu
tư) → trang chuyên đề (logistics park, FTZ, tuyến đường sắt) → Wikipedia/báo cáo tư
vấn (chỉ để đối chiếu).

Model **chỉ được trả URL đã thực mở bằng web_search/web_fetch**; script probe lại
từng URL trước khi ghi (giữ 403/429 vì Playwright thường qua được).

### extract — điền trường

Raw thô ~3,9 triệu ký tự, không nhét vừa prompt. `llm_prep.py` nén còn ~66k/lượt:
bỏ dòng boilerplate lặp trên ≥40% số trang, chấm điểm block theo `kw` trong schema +
mật độ số liệu + vị trí đầu trang, chia hạn ngạch **đều cho mọi trang** (chia theo
trang chứ không theo thứ tự, nếu không các trang cuối bị bỏ trắng).

Mỗi trang mang mã `[Snn]`; model bắt buộc dẫn mã đó cho từng giá trị.

## Bài học chống lỗi dữ liệu

Bốn lớp bảo vệ dưới đây sinh ra từ lỗi thật đã gặp — đừng gỡ khi refactor.

| Lỗi | Ví dụ thật | Lớp chặn |
|---|---|---|
| Lấy **công suất/dự báo** làm số thực tế | Dubai South "capacity for up to 260 million passengers" → 260 tr khách/năm | Quy tắc 8 trong `SYSTEM_RULES`: cấm "capacity for", "when complete", "by 2030"; trả null kèm lý do |
| Lấy **sai phạm vi** diện tích | Schiphol 350 ha (Trade Park) → `area_km2 = 3,5` cho cả khu đô thị | Quy tắc 9 + hàm `cross_check()` đối chiếu `area_km2` với `*_park_ha` |
| Baseline sai **tự củng cố** qua các lần chạy | `baseline_record()` đọc chính file output nên vòng sau xác nhận lại lỗi vòng trước | Đọc `features/_deterministic/<case>.json` (bản regex gốc), không đọc output LLM — **thư mục này đã bị xoá, xem ghi chú cuối README** |
| Model **không bác được** giá trị cũ sai | Giữ nguyên `sustainability = ['green']` do regex bịa | Cho phép trả `reason: "BASELINE_SAI: …"` → xoá hẳn giá trị thay vì giữ |

Nguyên tắc chung: **thà trống còn hơn sai**. Trường không có bằng chứng phải vào khối
`missing` kèm lý do đọc được — lý do đó hiện thẳng trên trang web, nên nó là một phần
sản phẩm chứ không phải log nội bộ.

## Thêm một khu mới

```bash
# 1. thêm 1 dòng vào refer_file/aerotropolis.txt:
#    | 11 | Tên khu | Quốc gia | Sân bay trung tâm | ghi chú |
# 2. chạy toàn tuyến cho riêng khu đó
python scripts/run_ws.py ws1_airport --cases <case_id>
```

`case_id` sinh tự động từ tên (bỏ dấu, bỏ chữ "aerotropolis"/"airport city"); xem lại
trong `refer_file/cases.csv`. Muốn định danh chuẩn hơn (tên tiếng Việt, website chính
thức) thì thêm case vào
[`features/ws1_airport/cases_registry.json`](features/ws1_airport/cases_registry.json).

## Thêm một trường mới

Sửa [`features/ws1_airport/schema.json`](features/ws1_airport/schema.json) rồi chạy
lại `extract → validate → web`. Prompt, validator và trang web đều đọc từ file này.
Nhớ khai `kw` — không có từ khoá thì `llm_prep.py` không giữ lại đoạn chứa dữ kiện,
và model sẽ không bao giờ thấy bằng chứng để điền.

## Nghiệm thu

```bash
python scripts/validate_features.py       # 0 lỗi kiểu; đọc bảng độ phủ
python html/build_portal.py               # mở html/index.html
```

- `coverage_summary.csv` — độ phủ từng khu; cột `from_baseline` cao nghĩa là LLM chưa
  xác minh được nhiều, cần bổ sung nguồn (chạy lại `discover`).
- `coverage_report.csv` — soi từng trường: giá trị, nguồn, confidence, lý do thiếu.
- Trường trống ở **mọi** khu (in ra cuối bản validate) là dấu hiệu nguồn hiện tại
  không công bố loại dữ liệu đó, không phải lỗi extractor.

## Sự cố thường gặp

| Hiện tượng | Nguyên nhân | Cách xử lý |
|---|---|---|
| `extract` báo lỗi kết nối | Chưa chạy `code_proxy` | Khởi động proxy, đặt `ANTHROPIC_BASE_URL` |
| Model trả JSON hỏng | Prompt dài, model kèm lời dẫn | Đã tự retry 3 lần và bóc JSON cân ngoặc; xem `_llm_log/<case>_<pass>.json` |
| Độ phủ tụt sau khi chạy lại | Đúng như thiết kế — giá trị sai bị loại | Đọc `warnings` trong `_meta`, kiểm `BASELINE_SAI` |
| Crawl ra trang rỗng | Trang chặn bot hoặc render chậm | `--timeout 60`, `--headful` để xem, hoặc bỏ URL khỏi `sources.csv` |
| Repo phình dung lượng | Screenshot `.png` trong raw | Mặc định đã tắt; chỉ bật `--shots` khi cần bằng chứng thị giác |
