from pathlib import Path

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parent.parent
AIRPORTS_PATH = ROOT_DIR / "data" / "filtered_airports.csv"
COUNTRIES_PATH = ROOT_DIR / "data" / "countries.csv"
OUTPUT_PATH = ROOT_DIR / "data" / "enriched_airports.csv"


def main() -> None:
    airports = pd.read_csv(AIRPORTS_PATH, dtype=str, keep_default_na=False)
    countries = pd.read_csv(COUNTRIES_PATH, dtype=str, keep_default_na=False)

    country_names = countries[["code", "name"]].rename(columns={"name": "country_name"})
    enriched_airports = airports.merge(
        country_names,
        how="left",
        left_on="iso_country",
        right_on="code",
    )
    enriched_airports = enriched_airports.drop(columns=["code"])

    matched_count = int(enriched_airports["country_name"].fillna("").str.strip().ne("").sum())
    unmatched_count = len(enriched_airports) - matched_count

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    enriched_airports.to_csv(OUTPUT_PATH, index=False)

    print("Country enrichment complete")
    print(f"Input airports file: {AIRPORTS_PATH}")
    print(f"Input countries file: {COUNTRIES_PATH}")
    print(f"Output file: {OUTPUT_PATH}")
    print()
    print(f"Airports with country name: {matched_count}")
    print(f"Airports without country match: {unmatched_count}")


if __name__ == "__main__":
    main()
