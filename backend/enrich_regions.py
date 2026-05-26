from pathlib import Path

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parent.parent
AIRPORTS_PATH = ROOT_DIR / "data" / "enriched_airports.csv"
REGIONS_PATH = ROOT_DIR / "data" / "regions.csv"
OUTPUT_PATH = ROOT_DIR / "data" / "enriched_airports.csv"


def main() -> None:
    airports = pd.read_csv(AIRPORTS_PATH, dtype=str, keep_default_na=False)
    regions = pd.read_csv(
        REGIONS_PATH,
        dtype=str,
        keep_default_na=False,
        usecols=["code", "name"],
    )

    if "region_name" in airports.columns:
        airports = airports.drop(columns=["region_name"])

    # DSA optimization: use regions.code as a hash lookup table for O(n + m)
    # enrichment. This avoids merge overhead and avoids using non-unique
    # local_code values.
    region_name_by_code = regions.drop_duplicates("code").set_index("code")["name"]
    airports["region_name"] = airports["iso_region"].map(region_name_by_code)

    matched_count = int(airports["region_name"].fillna("").str.strip().ne("").sum())
    unmatched_count = len(airports) - matched_count

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    airports.to_csv(OUTPUT_PATH, index=False)

    examples = airports[["iso_region", "region_name"]].head(5)

    print("Region enrichment complete")
    print(f"Input airports file: {AIRPORTS_PATH}")
    print(f"Input regions file: {REGIONS_PATH}")
    print(f"Output file: {OUTPUT_PATH}")
    print()
    print(f"Airports with region name: {matched_count}")
    print(f"Airports with null region: {unmatched_count}")
    print()
    print("Example rows:")
    print(examples.to_string(index=False))


if __name__ == "__main__":
    main()
