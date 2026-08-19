# SKILL — Sinh Extractor từ Feature Spec

> Meta-skill dùng chung cho mọi workstream. Agent đọc skill này + file
> `features/<ws>/feature_spec.md` để **sinh ra `extract_<ws>.py`**.

## Mục tiêu

Input:
- `features/<ws>/feature_spec.md` — bảng feature (name/type/required/source/transform).
- `refer_file/sources.csv` — danh sách nguồn (URL, purpose, target_fields).
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
   `refer_file/sources.csv` và `manifest.json` của lần crawl.
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

Ví dụ hoàn chỉnh: [`ws1_airport/extract_airport_city.py`](ws1_airport/extract_airport_city.py)
(bản deterministic) và [`ws1_airport/extract_llm.py`](ws1_airport/extract_llm.py) (bản LLM).

---

## Biến thể LLM (dùng khi spec có nhiều trường định tính)

Quy trình 7 bước ở trên sinh extractor **deterministic** — hợp với nguồn có cấu
trúc (CSV/JSON/bảng HTML). Khi nguồn là văn xuôi website và spec có nhiều trường
mô tả (`brand_desc`, `connectivity_desc`, các cờ `has_*`), regex chạm trần rất
sớm; dùng extractor LLM thay thế:

1. **Khai báo trường ở dạng máy đọc** — `features/<ws>/schema.json`: mỗi trường có
   `name`, `type`, `label`, `unit`, `desc`, và `kw` (từ khoá để lọc đoạn liên quan).
2. **Nén raw thành dossier** (`llm_prep.py`): bỏ dòng boilerplate lặp trên nhiều
   trang, chia trang thành block, chấm điểm theo `kw` + mật độ số liệu + vị trí đầu
   trang, giữ block điểm cao trong hạn ngạch chia đều cho mọi trang. Gắn mã `[Snn]`
   cho từng nguồn.
3. **Hỏi model theo lượt** (`extract_llm.py`): tách nhóm trường thành vài lượt để
   prompt ngắn và model bám sát; mỗi lượt yêu cầu trả JSON `{"fields": {...}}`.
4. **Ràng buộc chống bịa**: model không có mạng; mỗi giá trị phải kèm `[Snn]` +
   `snippet` nguyên văn + `confidence`; không có bằng chứng thì trả `null` + `reason`.
5. **Đối chiếu ngược**: mã `[Snn]` phải khớp `manifest.json`, sai thì hạ
   `confidence` và gắn `unverified_source`.
6. **Giữ baseline**: kết quả extractor regex cũ được đưa vào prompt làm mốc và
   backup ra `features/_deterministic/`; trường LLM không xác minh được vẫn giữ giá
   trị cũ với `source=baseline`.
7. **Validate**: `scripts/validate_features.py` kiểm kiểu theo `schema.json`, kiểm
   khoá trùng, xuất `coverage_report.csv` (từng trường) và `coverage_summary.csv`.

Model được gọi qua [`code_proxy/`](../code_proxy/README.md) nên chạy được bằng
phiên Claude Code CLI, không cần `ANTHROPIC_API_KEY`.
