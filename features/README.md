# Features — Định nghĩa dữ liệu cần lấy

Đây là **nguồn sự thật (source of truth)** cho biết mỗi workstream cần thu thập
những trường nào. Agent Extractor đọc các file ở đây để biết phải sinh code
trích xuất ra cột gì, kiểu gì, từ nguồn nào.

## Quy tắc

- Mỗi **workstream** = 1 thư mục con: `features/<workstream>/`.
- Trong mỗi thư mục có **ít nhất 1 file `.md`** mô tả các trường (đặt tên
  `feature_spec.md`).
- Mỗi feature khai báo tối thiểu: `name`, `type`, `required`, `source`,
  `description`. Nếu cần biến đổi thì thêm `transform`.

## Bảng feature chuẩn (dùng trong feature_spec.md)

| Cột        | Ý nghĩa                                                        |
|------------|---------------------------------------------------------------|
| `name`     | Tên cột output (snake_case, tiếng Anh)                         |
| `type`     | `string` \| `int` \| `float` \| `bool` \| `date`              |
| `required` | `yes` nếu bắt buộc phải có; `no` nếu có thể trống              |
| `source`   | Nguồn/cột thô lấy ra (vd cột index trong CSV, selector HTML)   |
| `transform`| Chuẩn hoá cần làm (vd cast float, strip, uppercase)           |
| `description` | Giải thích ngắn                                            |

Mỗi feature output luôn kèm 3 cột provenance (extractor tự thêm):
`source_name`, `source_url`, `accessed_at`.

## Workstream hiện có

- [`ws1_airport/`](ws1_airport/feature_spec.md) — vị trí & thông tin sân bay
  (long/lat, IATA/ICAO, thành phố, quốc gia, số hành khách).
