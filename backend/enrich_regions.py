from pathlib import Path

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parent.parent
AIRPORTS_PATH = ROOT_DIR / "data" / "enriched_airports.csv"
REGIONS_PATH = ROOT_DIR / "data" / "regions.csv"
OUTPUT_PATH = ROOT_DIR / "data" / "enriched_airports.csv"


def main() -> None:
    airports = pd.read_csv(AIRPORTS_PATH, dtype=str, keep_default_na=False)
    regions = pd.read_csv(REGIONS_PATH, dtype=str, keep_default_na=False)

    if "region_name" in airports.columns:
        airports = airports.drop(columns=["region_name"])

    region_names = regions[["code", "name"]].rename(columns={"name": "region_name"})
    enriched_airports = airports.merge(
        region_names,
        how="left",
        left_on="iso_region",
        right_on="code",
    )
    enriched_airports = enriched_airports.drop(columns=["code"])

    matched_count = int(enriched_airports["region_name"].fillna("").str.strip().ne("").sum())
    unmatched_count = len(enriched_airports) - matched_count

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    enriched_airports.to_csv(OUTPUT_PATH, index=False)

    examples = enriched_airports[["iso_region", "region_name"]].head(5)

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
