# Agent Extractor — Skill sinh code trích xuất

Khối này biến **định nghĩa feature** (ở `features/<ws>/feature_spec.md`) thành
**code Python trích xuất** (`extract_<ws>.py`). Mỗi workstream có một thư mục
con chứa file skill `.md`; agent đọc skill đó để hiểu cách map từ dữ liệu thô
sang các feature, rồi sinh ra file `.py`.

```
agent_extractor/
├── SKILL.md                      # meta-skill: quy trình chung để sinh extractor
└── <workstream>/
    ├── extractor_skill.md        # skill riêng: mapping cụ thể của workstream
    └── extract_<workstream>.py   # OUTPUT: file.py agent gen ra
```

## Nguyên tắc

- File `.md` là **đầu vào để học** (skill), file `.py` là **đầu ra**.
- Extractor chỉ đọc từ `raw_data/output/<ws>/raw/`, ghi ra
  `raw_data/output/<ws>/features/`. Không tự gọi mạng — việc crawl thuộc
  `raw_data/crawler/`.
- Extractor phải bám đúng `feature_spec.md`: đúng tên cột, đúng type, đúng
  transform, và luôn thêm 3 cột provenance.

Xem [`SKILL.md`](SKILL.md) để biết quy trình sinh code.
