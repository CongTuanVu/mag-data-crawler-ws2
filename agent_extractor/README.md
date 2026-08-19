# Agent Extractor — Skill sinh code trích xuất

Khối này biến **định nghĩa feature** (ở `features/<ws>/feature_spec.md`) thành
**code Python trích xuất** (`extract_<ws>.py`). Mỗi workstream có một thư mục
con chứa file skill `.md`; agent đọc skill đó để hiểu cách map từ dữ liệu thô
sang các feature, rồi sinh ra file `.py`.

```
agent_extractor/
├── SKILL.md                      # meta-skill: quy trình chung để sinh extractor
└── <workstream>/
    ├── llm_prep.py               # nén raw đã crawl thành dossier cho model
    ├── extract_llm.py            # OUTPUT chính: điền feature bằng LLM + provenance
    └── extract_airport_city.py   # bản deterministic (regex) — baseline đối chiếu
```

## Nguyên tắc

- File `.md` là **đầu vào để học** (skill), file `.py` là **đầu ra**.
- Extractor chỉ đọc từ `raw_data/output/<ws>/raw/`, ghi ra
  `raw_data/output/<ws>/features/`. Không tự gọi mạng — việc crawl thuộc
  `raw_data/crawler/`.
- Extractor phải bám đúng `feature_spec.md`: đúng tên cột, đúng type, đúng
  transform, và luôn thêm 3 cột provenance.

Xem [`SKILL.md`](SKILL.md) để biết quy trình sinh code.

## Hai thế hệ extractor cho ws1_airport

| | `extract_airport_city.py` (regex) | `extract_llm.py` (LLM) |
|---|---|---|
| Cách hoạt động | 1133 dòng regex + từ khoá bám theo cách hành văn từng website | Đọc hiểu dossier đã nén từ raw, model trả JSON theo `schema.json` |
| Độ phủ 75 trường | ~43% trung bình | ~79% trung bình |
| Trường định tính (`brand_desc`, `connectivity_desc`, `has_*`…) | không lấy được | lấy được |
| Case mới | phải viết thêm regex riêng | chạy được ngay, không sửa code |
| Chi phí | miễn phí, tức thì | ~90 giây/case qua `code_proxy` |
| Vai trò hiện tại | **baseline đối chiếu** — giá trị LLM không xác minh được thì giữ bản này (`source=baseline`) | **đường chính** |

Bản regex được backup sang `raw_data/output/ws1_airport/features/_deterministic/`
trước khi LLM ghi đè, nên luôn so lại được hai thế hệ.

Chống bịa dữ liệu trong `extract_llm.py`:

- model không có mạng, chỉ thấy dossier trích từ raw đã crawl;
- mỗi giá trị phải dẫn mã nguồn `[Snn]`, mã lạ bị hạ `confidence` + gắn cờ
  `unverified_source`;
- trường không có bằng chứng phải trả `null` kèm lý do, ghi vào khối `missing`;
- `scripts/validate_features.py` kiểm kiểu dữ liệu và xuất `coverage_report.csv`
  để soi lại từng trường.
