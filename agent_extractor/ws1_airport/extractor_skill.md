# Extractor Skill — WS1 Airport

Skill riêng cho workstream airport. Kế thừa quy trình chung ở
[`../SKILL.md`](../SKILL.md), bổ sung mapping cụ thể của OpenFlights.

## Input

- Spec: `features/ws1_airport/feature_spec.md`
- Raw: `raw_data/output/ws1_airport/raw/airports.dat` (CSV **không header**,
  encoding UTF-8, sentinel giá trị rỗng là chuỗi `\N`).
- Manifest: `raw_data/output/ws1_airport/raw/manifest.json` (provenance).

## Mapping cột (OpenFlights idx → feature)

| feature        | idx | transform                        |
|----------------|-----|----------------------------------|
| `airport_name` | 1   | strip                            |
| `city`         | 2   | strip; `\N`→null                 |
| `country`      | 3   | strip                            |
| `iata`         | 4   | upper; `\N`/len≠3 → loại dòng    |
| `icao`         | 5   | upper; `\N`→null                 |
| `latitude`     | 6   | float                            |
| `longitude`    | 7   | float                            |
| `altitude_ft`  | 8   | int                              |
| `tz_name`      | 11  | strip; `\N`→null                 |
| `passengers`   | —   | null (chưa có nguồn) — TODO      |

## Scope filter

- Loại dòng có `iata == "\N"` hoặc độ dài `iata` khác 3.

## Validate

- `iata`, `latitude`, `longitude`, `airport_name`, `country` không null.
- `iata` là khoá duy nhất — nếu trùng, giữ dòng đầu và log cảnh báo.
- `latitude ∈ [-90, 90]`, `longitude ∈ [-180, 180]`.

## Output

- `raw_data/output/ws1_airport/features/airports.csv`
- `raw_data/output/ws1_airport/features/airports.jsonl`

→ Code sinh ra: [`extract_airport.py`](extract_airport.py).
