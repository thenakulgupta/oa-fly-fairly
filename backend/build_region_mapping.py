from collections import defaultdict
from pathlib import Path
import json

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parent.parent
AIRPORTS_PATH = ROOT_DIR / "data" / "enriched_airports.csv"
OUTPUT_PATH = ROOT_DIR / "data" / "region_mapping.json"

SANITY_CHECK_REGIONS = ["Hawaii", "Ontario", "Florida", "California", "Texas"]


def main() -> None:
    airports = pd.read_csv(
        AIRPORTS_PATH,
        dtype={"iata_code": str, "region_name": str, "iso_region": str, "priority": int},
        keep_default_na=False,
        usecols=["iata_code", "region_name", "iso_region", "priority"],
    )

    # DSA optimization: prebuild an O(1) priority lookup keyed by IATA code so
    # sorting each region does not scan the dataframe repeatedly.
    priority_by_iata = dict(zip(airports["iata_code"], airports["priority"]))

    # DSA optimization: group airports in one O(n) pass with defaultdict(list)
    # instead of filtering/scanning the dataframe once per region.
    airports_by_region: dict[str, list[str]] = defaultdict(list)
    for airport in airports.itertuples(index=False):
        region_name = airport.region_name.strip()
        iata_code = airport.iata_code.strip()

        if (
            not region_name
            or region_name == "(unassigned)"
            or not iata_code
        ):
            continue

        airports_by_region[region_name].append(iata_code)

    region_mapping = {
        region_name: sorted(
            iata_codes,
            key=lambda iata_code: priority_by_iata.get(iata_code, 0),
            reverse=True,
        )
        for region_name, iata_codes in sorted(airports_by_region.items())
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as output_file:
        json.dump(region_mapping, output_file, ensure_ascii=False, indent=2)
        output_file.write("\n")

    top_regions = sorted(
        region_mapping.items(),
        key=lambda item: len(item[1]),
        reverse=True,
    )[:5]

    print("Region mapping build complete")
    print(f"Input airports file: {AIRPORTS_PATH}")
    print(f"Output file: {OUTPUT_PATH}")
    print()
    print(f"Total number of regions mapped: {len(region_mapping)}")
    print()
    print("Top 5 regions with most airports:")
    for region_name, iata_codes in top_regions:
        print(f"- {region_name}: {len(iata_codes)} airports")
    print()
    print("Sanity check regions:")
    for region_name in SANITY_CHECK_REGIONS:
        print(f"- {region_name}: {region_mapping.get(region_name, [])}")


if __name__ == "__main__":
    main()
