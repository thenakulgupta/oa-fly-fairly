from pathlib import Path

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parent.parent
INPUT_PATH = ROOT_DIR / "data" / "airports.csv"
OUTPUT_PATH = ROOT_DIR / "data" / "filtered_airports.csv"


def has_valid_iata(series: pd.Series) -> pd.Series:
    return series.fillna("").astype(str).str.strip().ne("")


def main() -> None:
    airports = pd.read_csv(INPUT_PATH, dtype=str, keep_default_na=False)
    total_airports = len(airports)

    airports["iata_code"] = airports["iata_code"].fillna("").astype(str).str.strip()

    valid_iata_mask = has_valid_iata(airports["iata_code"])
    removed_invalid_iata_count = int(len(airports) - valid_iata_mask.sum())

    airports_with_iata = airports.loc[valid_iata_mask].copy()

    removed_closed_count = int(airports_with_iata["type"].eq("closed").sum())
    active_airports = airports_with_iata.loc[airports_with_iata["type"].ne("closed")].copy()

    removed_heliport_count = int(active_airports["type"].eq("heliport").sum())
    non_heliport_airports = active_airports.loc[active_airports["type"].ne("heliport")].copy()

    removed_seaplane_base_count = int(non_heliport_airports["type"].eq("seaplane_base").sum())
    filtered_airports = non_heliport_airports.loc[
        non_heliport_airports["type"].ne("seaplane_base")
    ].copy()

    removed_count = total_airports - len(filtered_airports)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    filtered_airports.to_csv(OUTPUT_PATH, index=False)

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
    for airport_type, count in filtered_airports["type"].value_counts().sort_index().items():
        print(f"- {airport_type}: {count}")


if __name__ == "__main__":
    main()
