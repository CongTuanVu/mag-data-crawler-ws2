# SKILL — Lớp trình bày: feature → cổng tra cứu HTML

> Skill con của [`SKILL.md`](../SKILL.md). Mô tả khối cuối pipeline: biến
> `features/<case>_airport_city.json` thành một trang web tra cứu tự chứa.

## Vào / ra

| | Nội dung |
|---|---|
| **Vào** | `features/ws1_airport/schema.json` (nhóm, nhãn, đơn vị) · `raw_data/output/ws1_airport/features/*_airport_city.json` · `html/assets/<case>/images.json` (tuỳ chọn) |
| **Ra** | `html/index.html` — một file, mở bằng `file://` chạy được, không cần server |

```bash
python html/harvest_images.py --name <case>   # tuỳ chọn: thu ảnh minh hoạ
python html/build_portal.py                   # dựng trang (thêm --no-images cho bản nhẹ)
```

## Trang có gì

- **Thanh thống kê**: số khu, số quốc gia, số trường/khu, độ phủ trung bình, tổng hành khách.
- **Tìm kiếm tức thời** trên toàn bộ giá trị của record (gõ `/` để nhảy vào ô tìm),
  lọc theo quốc gia, sắp xếp theo độ phủ / hành khách / diện tích / tên.
- **Lưới thẻ**: ảnh hero, 4 KPI, chip phân khu, thanh độ phủ dữ liệu.
- **Modal chi tiết** khi bấm vào thẻ, mở ở tab **📋 Hồ sơ**: bố cục nhãn vàng bên
  trái | lời văn tiếng Việt bên phải, xen dải KPI ở mục "Chỉ số quy mô", ảnh hero có
  caption, footer ghi số trang đã crawl và model đã dùng — giữ đúng bố cục bản hồ sơ in.
- Tab **Chi tiết trường** (và tab từng nhóm) trả về dạng tra cứu: 75 dòng
  trường–giá trị kèm badge tin cậy, link nguồn, trích dẫn gốc.
- Đóng bằng `Esc` hoặc bấm nền.

## Lời văn đến từ đâu

Đoạn văn mỗi mục **không dệt bằng template trong JS** mà do bước extract sinh ra:
`narrate()` trong [`extract_llm.py`](../agent_extractor/ws1_airport/extract_llm.py) chạy
sau khi record đã chốt và **chỉ nhìn thấy record đó** (không nhìn dossier), nên không
thể đưa vào dữ kiện chưa qua trích xuất và chưa có provenance. `check_narrative()` soi
lại mọi con số trong lời văn: số nào không truy được về record thì ghi cảnh báo.

Model đánh dấu `**giá trị**`; trang đổi thành `<b>` sau khi đã escape HTML. Mỗi mục
kết bằng một dòng ⓘ liệt kê nguồn của các trường trong mục.

Viết lại lời văn mà không trích lại (nhanh, ~40 giây/khu):

```bash
python agent_extractor/ws1_airport/extract_llm.py --all --narrative-only
```

## Ba thứ luôn hiện cùng một giá trị

Đây là điểm khác biệt của trang này so với một bảng dữ liệu thường — người đọc phải
kiểm chứng được ngay tại chỗ:

| Thành phần | Lấy từ | Vì sao cần |
|---|---|---|
| Badge tin cậy | `provenance[field].confidence` | phân biệt số nguồn nêu thẳng với số phải suy ra |
| Link nguồn | `provenance[field].source_url` | bấm ra đúng trang đã crawl |
| Trích dẫn gốc | `provenance[field].snippet` | **giữ nguyên ngôn ngữ nguồn**, không dịch — đó là bằng chứng |

Trường thiếu không bị giấu đi: hiện mờ kèm lý do lấy từ khối `missing`, ví dụ *"Nguồn
chỉ nêu service costs €65/m²/năm cho Avioport; không có tỷ giá EUR-USD trong tài liệu
để quy đổi sang USD/m²/tháng"*. Lý do đó là một phần sản phẩm, không phải log nội bộ.

## Ngôn ngữ hiển thị

Việc dịch làm ở **bước extract**, không phải ở đây — xem quy tắc 11 trong
`SYSTEM_RULES` của [`extract_llm.py`](../agent_extractor/ws1_airport/extract_llm.py):
giá trị chữ trả về tiếng Việt, giữ nguyên tên riêng (tổ chức, phân khu, công trình,
viết tắt) dạng "tên gốc (giải nghĩa)", `snippet` giữ nguyên văn.

Nhãn trường, tên nhóm và đơn vị lấy từ `schema.json`; sửa nhãn thì sửa ở đó, đừng
hardcode trong `build_portal.py`.

## Ràng buộc kỹ thuật

- **Tự chứa**: dữ liệu nhúng dạng JSON, ảnh nhúng base64 (`data:` URI). Không request
  ra ngoài, mở bằng `file://` phải chạy đủ chức năng.
- **Escape**: mọi giá trị đi qua `esc()` trước khi vào HTML — dữ liệu là văn bản crawl
  từ web, có thể chứa `<`, `&`.
- **Ảnh**: `images.json` là dict theo slot (`hero`, `planning`, `experience`,
  `vision`); trang lấy `hero` trước, không có thì lấy slot bất kỳ, không có nữa thì
  dùng nền gradient. Bỏ file ảnh > 900KB để trang không phình.
- **Theme**: có sẵn biến màu cho `prefers-color-scheme: dark`.

## Nghiệm thu

Kiểm tra bằng Playwright thay vì mở mắt nhìn — bắt được lỗi JS im lặng:

```python
pg.goto("file:///…/html/index.html")
pg.fill("#q", "free trade zone")          # tìm kiếm lọc đúng số thẻ?
pg.click(".card")                          # modal mở?
pg.locator("table.f .src a").count()       # có link nguồn?
pg.keyboard.press("Escape")                # đóng được?
```

Checklist: 10 thẻ hiện đủ · sắp xếp mặc định là độ phủ giảm dần · modal đủ 75 dòng ·
không lỗi `pageerror` · nhãn và giá trị đều tiếng Việt (trừ tên riêng và `snippet`).
