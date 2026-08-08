# SKILL — Sinh Extractor từ Feature Spec

> Meta-skill dùng chung cho mọi workstream. Agent đọc skill này + file
> `features/<ws>/feature_spec.md` để **sinh ra `extract_<ws>.py`**.

## Mục tiêu

Input:
- `features/<ws>/feature_spec.md` — bảng feature (name/type/required/source/transform).
- `config/sources.yaml` — nguồn thô và định dạng (`csv`/`json`/`html`).
- File thô đã crawl trong `raw_data/output/<ws>/raw/`.

Output:
- `agent_extractor/<ws>/extract_<ws>.py` — script chạy độc lập, đọc raw → ghi
  `raw_data/output/<ws>/features/<name>.csv` và `.jsonl`.

## Quy trình sinh code (7 bước)

1. **Đọc spec.** Lấy danh sách feature: `name`, `type`, `required`, `source`,
   `transform`. Ghi lại khoá (key) và bộ lọc scope.
2. **Xác định reader theo `type` nguồn:**
   - `csv` → `pandas.read_csv` (chú ý header/không header, encoding, quote).
   - `json` → `json.load` rồi chuẩn hoá bằng `pandas.json_normalize`.
   - `html` → `BeautifulSoup(...).select(selector)` hoặc `pandas.read_html`.
3. **Map từng feature:** từ cột/selector thô ở `source` → cột output `name`.
4. **Áp transform:** cast type (`int`/`float`/`date`), `strip`, `upper`, loại
   sentinel rỗng (vd `\N`, `""`, `NaN`).
5. **Áp bộ lọc scope** (vd chỉ giữ dòng có IATA hợp lệ).
6. **Thêm provenance:** 3 cột `source_name`, `source_url`, `accessed_at` lấy từ
   `config/sources.yaml` và `manifest.json` của lần crawl.
7. **Kiểm tra & ghi:**
   - required != null; key không rỗng, không trùng.
   - Ghi cả `.csv` (UTF-8) và `.jsonl`.
   - Log số dòng in/out và số dòng bị loại (kèm lý do).

## Ràng buộc (contract)

- **Không bịa dữ liệu.** Thiếu nguồn cho một feature → để trống + comment TODO,
  không suy đoán.
- **Không gọi mạng** trong extractor. Nếu raw chưa có → báo lỗi rõ ràng, hướng
  dẫn chạy crawler trước.
- **Idempotent.** Chạy lại trên cùng raw phải cho cùng output.
- **Bám tên trong spec.** Không tự đổi tên cột.

## Bộ khung code chuẩn (template)

```python
from pathlib import Path
import pandas as pd

WS = "<ws>"
ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "raw_data" / "output" / WS / "raw"
OUT = ROOT / "raw_data" / "output" / WS / "features"

def load_provenance() -> dict:
    # đọc manifest.json trong RAW để lấy source_url, accessed_at
    ...

def extract() -> pd.DataFrame:
    # 1-5: đọc raw, map feature, transform, filter
    ...

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    df = extract()
    # 6: thêm provenance ; 7: validate + ghi csv/jsonl
    ...

if __name__ == "__main__":
    main()
```

Ví dụ hoàn chỉnh đã sinh cho workstream airport:
[`ws1_airport/extract_airport.py`](ws1_airport/extract_airport.py).
