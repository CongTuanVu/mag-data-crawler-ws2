"""Extractor cho WS1 Airport.

FILE.PY được sinh từ:
  - features/ws1_airport/feature_spec.md
  - agent_extractor/ws1_airport/extractor_skill.md
  - agent_extractor/SKILL.md (quy trình chung)

Đọc raw OpenFlights (airports.dat) -> chuẩn hoá theo feature_spec ->
ghi raw_data/output/ws1_airport/features/airports.{csv,jsonl}.

Không gọi mạng. Chạy crawl_airport.py trước để có raw.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

WS = "ws1_airport"
ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "raw_data" / "output" / WS / "raw"
OUT_DIR = ROOT / "raw_data" / "output" / WS / "features"
RAW_FILE = RAW_DIR / "airports.dat"
MANIFEST = RAW_DIR / "manifest.json"

# Thứ tự cột OpenFlights (không header).
OPENFLIGHTS_COLS = [
    "airport_id", "airport_name", "city", "country", "iata", "icao",
    "latitude", "longitude", "altitude_ft", "tz_offset", "dst",
    "tz_name", "type", "source",
]
NA = "\\N"  # sentinel rỗng của OpenFlights


def _clean(value: object) -> object:
    """Chuẩn hoá sentinel rỗng -> None, strip chuỗi."""
    if value is None:
        return None
    s = str(value).strip()
    if s == "" or s == NA:
        return None
    return s


def load_provenance() -> dict:
    if MANIFEST.exists():
        data = json.loads(MANIFEST.read_text(encoding="utf-8"))
        src = (data.get("sources") or [{}])[0]
        return {
            "source_name": src.get("name", "OpenFlights Airports Database"),
            "source_url": src.get("url", ""),
            "accessed_at": data.get("accessed_at", ""),
        }
    return {"source_name": "OpenFlights Airports Database", "source_url": "", "accessed_at": ""}


def extract() -> pd.DataFrame:
    if not RAW_FILE.exists():
        raise FileNotFoundError(
            f"Chưa có raw: {RAW_FILE}\n"
            f"Chạy trước: python raw_data/crawler/crawl_airport.py"
        )

    # OpenFlights: CSV không header, quote kép, encoding utf-8.
    raw = pd.read_csv(
        RAW_FILE, header=None, names=OPENFLIGHTS_COLS,
        keep_default_na=False, dtype=str, encoding="utf-8",
    )
    n_in = len(raw)

    df = pd.DataFrame()
    df["airport_name"] = raw["airport_name"].map(_clean)
    df["iata"] = raw["iata"].map(lambda v: (_clean(v) or "").upper() or None)
    df["icao"] = raw["icao"].map(lambda v: (_clean(v) or "").upper() or None)
    df["city"] = raw["city"].map(_clean)
    df["country"] = raw["country"].map(_clean)
    df["latitude"] = pd.to_numeric(raw["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(raw["longitude"], errors="coerce")
    df["altitude_ft"] = pd.to_numeric(raw["altitude_ft"], errors="coerce").astype("Int64")
    df["tz_name"] = raw["tz_name"].map(_clean)
    df["passengers"] = pd.NA  # TODO: cần nguồn thứ hai (vd Wikipedia). Không bịa số.

    # --- Scope filter: chỉ giữ IATA hợp lệ (3 ký tự) ---
    valid_iata = df["iata"].notna() & (df["iata"].str.len() == 3)
    df = df[valid_iata].copy()

    # --- Validate ---
    df = df.dropna(subset=["airport_name", "country", "latitude", "longitude"])
    df = df[(df["latitude"].between(-90, 90)) & (df["longitude"].between(-180, 180))]
    dup = df["iata"].duplicated(keep="first").sum()
    if dup:
        print(f"[warn] {dup} IATA trùng -> giữ dòng đầu")
    df = df.drop_duplicates(subset=["iata"], keep="first").reset_index(drop=True)

    print(f"[extract] in={n_in} -> out={len(df)} (loại {n_in - len(df)} dòng)")
    return df


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    df = extract()

    prov = load_provenance()
    for col, val in prov.items():
        df[col] = val

    csv_path = OUT_DIR / "airports.csv"
    jsonl_path = OUT_DIR / "airports.jsonl"
    df.to_csv(csv_path, index=False, encoding="utf-8")
    with jsonl_path.open("w", encoding="utf-8") as f:
        for rec in df.to_dict(orient="records"):
            f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")

    print(f"[ok] {len(df)} bản ghi -> {csv_path}")
    print(f"[ok] {len(df)} bản ghi -> {jsonl_path}")


if __name__ == "__main__":
    main()
