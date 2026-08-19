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

## Hai lớp định nghĩa

| File | Dành cho | Nội dung |
|---|---|---|
| `feature_spec.md` | người đọc | mô tả trường, nguồn slide gốc, quy tắc chống lỗi, seed case |
| `schema.json` | code | 75 trường máy đọc: `name`, `type`, `label`, `unit`, `desc`, `kw` |

`schema.json` là thứ **code thực sự đọc**: `llm_prep.py` dùng `kw` để lọc đoạn
liên quan trong raw, `extract_llm.py` dựng bảng trường trong prompt từ đó,
`validate_features.py` kiểm kiểu theo `type`, `build_portal.py` render nhãn theo
`label`/`group`. Thêm hoặc sửa trường thì sửa ở đây, không hardcode nơi khác.

## Workstream hiện có

- [`ws1_airport/`](ws1_airport/feature_spec.md) — khu đô thị sân bay
  (aerotropolis): định danh, KPI quy mô, đầu tư & quản trị, 6 trụ CVP, tầm nhìn
  & bền vững. 75 trường, xem [`schema.json`](ws1_airport/schema.json).
