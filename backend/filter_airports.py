from pathlib import Path

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parent.parent
INPUT_PATH = ROOT_DIR / "data" / "airports.csv"
OUTPUT_PATH = ROOT_DIR / "data" / "filtered_airports.csv"

EXCLUDED_TYPES = {"closed", "heliport", "seaplane_base"}


def has_valid_iata(iata_codes: pd.Series) -> pd.Series:
    return iata_codes.fillna("").astype(str).str.strip().ne("")


def main() -> None:
    airports = pd.read_csv(INPUT_PATH, dtype=str, keep_default_na=False)
    total_airports = len(airports)

    airports["iata_code"] = airports["iata_code"].fillna("").astype(str).str.strip()

    valid_iata_mask = has_valid_iata(airports["iata_code"])
    removed_invalid_iata_count = int(total_airports - valid_iata_mask.sum())
    airports_with_iata = airports.loc[valid_iata_mask].copy()

    # DSA optimization: build one hash-count table for airport types in O(n)
    # instead of scanning the dataframe once per removal rule.
    type_counts_after_iata = airports_with_iata["type"].value_counts()
    removed_closed_count = int(type_counts_after_iata.get("closed", 0))
    removed_heliport_count = int(type_counts_after_iata.get("heliport", 0))
    removed_seaplane_base_count = int(type_counts_after_iata.get("seaplane_base", 0))

    # DSA optimization: use set-backed vectorized membership in O(n + k), where
    # k is the number of excluded types, avoiding chained intermediate filters.
    excluded_type_mask = airports_with_iata["type"].isin(EXCLUDED_TYPES)
    filtered_airports = airports_with_iata.loc[excluded_type_mask.eq(False)].copy()

    removed_count = total_airports - len(filtered_airports)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    filtered_airports.to_csv(OUTPUT_PATH, index=False)

    kept_type_counts = filtered_airports["type"].value_counts().sort_index()

    print("Airport filtering complete")
    print(f"Input file: {INPUT_PATH}")
    print(f"Output file: {OUTPUT_PATH}")
    print()
    print(f"Airports kept: {len(filtered_airports)}")
    print(f"Airports removed: {removed_count}")
    print()
    print("Removed per rule:")
    print(f"- Invalid or missing IATA code: {removed_invalid_iata_count}")
    print(f"- Closed type: {removed_closed_count}")
    print(f"- Heliport type: {removed_heliport_count}")
    print(f"- Seaplane base type: {removed_seaplane_base_count}")
    print()
    print("Breakdown by type of kept airports:")
    for airport_type, count in kept_type_counts.items():
        print(f"- {airport_type}: {count}")


if __name__ == "__main__":
    main()
