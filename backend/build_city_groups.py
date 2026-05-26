from collections import defaultdict
from pathlib import Path
import json

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parent.parent
AIRPORTS_PATH = ROOT_DIR / "data" / "enriched_airports.csv"
CITY_GROUPS_PATH = ROOT_DIR / "data" / "city_groups.json"
AIRPORT_TO_CITY_GROUP_PATH = ROOT_DIR / "data" / "airport_to_city_group.json"


def main() -> None:
    airports = pd.read_csv(
        AIRPORTS_PATH,
        dtype={
            "iata_code": str,
            "municipality": str,
            "iso_country": str,
            "priority": int,
        },
        keep_default_na=False,
        usecols=["iata_code", "municipality", "iso_country", "priority"],
    )

    # DSA optimization: prebuild an O(1) priority lookup keyed by IATA code so
    # each group sort does not need to scan the dataframe for airport priority.
    priority_by_iata = dict(zip(airports["iata_code"], airports["priority"]))

    # DSA optimization: group airports by (municipality, iso_country) in one
    # O(n) pass with defaultdict(list), avoiding one dataframe scan per city.
    airports_by_city: dict[tuple[str, str], list[str]] = defaultdict(list)
    for airport in airports.itertuples(index=False):
        municipality = airport.municipality.strip()
        country_code = airport.iso_country.strip()
        iata_code = airport.iata_code.strip()

        if not municipality or not iata_code:
            continue

        airports_by_city[(municipality, country_code)].append(iata_code)

    city_groups: dict[str, dict[str, object]] = {}
    used_city_codes: set[str] = set()

    for (municipality, country_code), iata_codes in sorted(airports_by_city.items()):
        if len(iata_codes) <= 1:
            continue

        sorted_iata_codes = sorted(
            iata_codes,
            key=lambda iata_code: priority_by_iata.get(iata_code, 0),
            reverse=True,
        )
        city_code = sorted_iata_codes[0]

        # DSA optimization: track generated city codes in a set for O(1)
        # conflict checks while keeping codes fully dynamic.
        if city_code in used_city_codes:
            raise ValueError(f"City group code conflict for {city_code}")

        used_city_codes.add(city_code)
        city_groups[city_code] = {
            "city": municipality,
            "country_code": country_code,
            "label": f"{municipality} (All Airports)",
            "airports": sorted_iata_codes,
        }

    # DSA optimization: build the inverted index in one O(n) pass over the
    # grouped airport lists, where n is the total grouped airport count.
    airport_to_city_group: dict[str, str] = {}
    for city_code, group in city_groups.items():
        for iata_code in group["airports"]:
            airport_to_city_group[iata_code] = city_code

    CITY_GROUPS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CITY_GROUPS_PATH.open("w", encoding="utf-8") as output_file:
        json.dump(city_groups, output_file, ensure_ascii=False, indent=2)
        output_file.write("\n")

    with AIRPORT_TO_CITY_GROUP_PATH.open("w", encoding="utf-8") as output_file:
        json.dump(airport_to_city_group, output_file, ensure_ascii=False, indent=2)
        output_file.write("\n")

    top_city_groups = sorted(
        city_groups.items(),
        key=lambda item: len(item[1]["airports"]),
        reverse=True,
    )[:5]

    print("City groups build complete")
    print(f"Input airports file: {AIRPORTS_PATH}")
    print(f"City groups output file: {CITY_GROUPS_PATH}")
    print(f"Airport index output file: {AIRPORT_TO_CITY_GROUP_PATH}")
    print()
    print(f"Total number of multi-airport cities found: {len(city_groups)}")
    print()
    print("City groups:")
    for city_code, group in city_groups.items():
        print(f"- {city_code}: {group['label']} -> {group['airports']}")
    print()
    print("Top 5 cities with most airports:")
    for city_code, group in top_city_groups:
        print(f"- {group['label']} [{city_code}]: {len(group['airports'])} airports")


if __name__ == "__main__":
    main()
