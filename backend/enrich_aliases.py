from collections import defaultdict
from pathlib import Path
import json

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parent.parent
AIRPORTS_PATH = ROOT_DIR / "data" / "enriched_airports.csv"
CITIES_PATH = ROOT_DIR / "data" / "cities15000.txt"
ALTERNATE_NAMES_PATH = ROOT_DIR / "data" / "alternateNames.txt"
OUTPUT_PATH = ROOT_DIR / "data" / "enriched_airports.csv"

CITIES_COLUMNS = [
    "geonameid",
    "name",
    "asciiname",
    "alternatenames",
    "latitude",
    "longitude",
    "feature_class",
    "feature_code",
    "country_code",
    "cc2",
    "admin1_code",
    "admin2_code",
    "admin3_code",
    "admin4_code",
    "population",
    "elevation",
    "dem",
    "timezone",
    "modification_date",
]

ALTERNATE_NAMES_COLUMNS = [
    "alternateNameId",
    "geonameid",
    "isolanguage",
    "alternateName",
    "isPreferredName",
    "isShortName",
    "isColloquial",
    "isHistoric",
]

VALID_LANGUAGE_CODES = {"en", "zh", "ja", "ar", "ko", "ru", "fr", "es", "de"}
ALTERNATE_NAMES_CHUNK_SIZE = 500_000

BASE_PRIORITY_BY_AIRPORT_TYPE = {
    "large_airport": 90,
    "medium_airport": 70,
    "small_airport": 50,
}


def city_key(city_name: str, country_code: str) -> tuple[str, str]:
    return (str(city_name).strip(), str(country_code).strip())


def alias_key(alias: str) -> str:
    return str(alias).strip().casefold()


def build_city_lookup(cities: pd.DataFrame) -> dict[tuple[str, str], dict[str, object]]:
    city_lookup: dict[tuple[str, str], dict[str, object]] = {}

    for city in cities.itertuples(index=False):
        city_record = {
            "geonameid": city.geonameid,
            "population": int(city.population),
            "feature_code": city.feature_code,
        }

        for key in {
            city_key(city.name, city.country_code),
            city_key(city.asciiname, city.country_code),
        }:
            existing_city = city_lookup.get(key)
            if existing_city is None or city_record["population"] > existing_city["population"]:
                city_lookup[key] = city_record

    return city_lookup


def match_airports_to_cities(
    airports: pd.DataFrame,
    city_lookup: dict[tuple[str, str], dict[str, object]],
) -> tuple[list[str | None], list[int | None], list[bool]]:
    geonameids: list[str | None] = []
    populations: list[int | None] = []
    is_capitals: list[bool] = []

    for municipality, country_code in zip(airports["municipality"], airports["iso_country"]):
        matched_city = city_lookup.get(city_key(municipality, country_code))

        if matched_city is None:
            geonameids.append(None)
            populations.append(None)
            is_capitals.append(False)
            continue

        geonameids.append(str(matched_city["geonameid"]))
        populations.append(int(matched_city["population"]))
        is_capitals.append(matched_city["feature_code"] == "PPLC")

    return geonameids, populations, is_capitals


def build_alias_lookup(matched_geonameids: set[str]) -> dict[str, list[str]]:
    aliases_by_geonameid: dict[str, list[str]] = defaultdict(list)
    seen_aliases_by_geonameid: dict[str, set[str]] = defaultdict(set)

    chunks = pd.read_csv(
        ALTERNATE_NAMES_PATH,
        sep="\t",
        header=None,
        names=ALTERNATE_NAMES_COLUMNS,
        dtype=str,
        keep_default_na=False,
        usecols=["geonameid", "isolanguage", "alternateName", "isHistoric"],
        chunksize=ALTERNATE_NAMES_CHUNK_SIZE,
    )

    for chunk in chunks:
        # DSA optimization: filter languages with set membership before adding
        # rows to the alias dict. This keeps memory proportional to useful
        # aliases instead of all 18M alternateNames rows.
        # 1. Filter geonameids  — kills most rows immediately (~18M → few thousand)
        chunk = chunk.loc[chunk["geonameid"].isin(matched_geonameids)]
        # 2. Filter languages   — now working on tiny subset
        chunk = chunk.loc[chunk["isolanguage"].isin(VALID_LANGUAGE_CODES)]
        # 3. Filter historic    — smaller set
        chunk = chunk.loc[chunk["isHistoric"].ne("1")]
        # 4. Filter empty names — final cleanup
        chunk = chunk.loc[chunk["alternateName"].str.strip().ne("")]

        for geonameid, alternate_name in zip(chunk["geonameid"], chunk["alternateName"]):
            normalized_alias = alias_key(alternate_name)
            # DSA optimization: use a per-city set for O(1) duplicate checks
            # while preserving insertion order in the alias list.
            if normalized_alias not in seen_aliases_by_geonameid[geonameid]:
                seen_aliases_by_geonameid[geonameid].add(normalized_alias)
                aliases_by_geonameid[geonameid].append(alternate_name)

    return dict(aliases_by_geonameid)


def calculate_priority(
    airport_type: str,
    city_population: int | None,
    is_capital: bool,
) -> int:
    priority = BASE_PRIORITY_BY_AIRPORT_TYPE.get(airport_type, 0)

    if city_population is not None and city_population > 1_000_000:
        priority += 10

    if city_population is not None and city_population > 500_000:
        priority += 5

    if is_capital:
        priority += 5

    return min(priority, 100)


def main() -> None:
    airports = pd.read_csv(AIRPORTS_PATH, dtype=str, keep_default_na=False)
    cities = pd.read_csv(
        CITIES_PATH,
        sep="\t",
        header=None,
        names=CITIES_COLUMNS,
        dtype={
            "geonameid": str,
            "name": str,
            "asciiname": str,
            "country_code": str,
            "population": int,
            "feature_code": str,
        },
        keep_default_na=False,
        usecols=["geonameid", "name", "asciiname", "country_code", "population", "feature_code"],
    )

    # DSA optimization: build O(1) city lookup dictionaries keyed by
    # (name, country_code) and (asciiname, country_code), avoiding dataframe
    # scans for each airport.
    city_lookup = build_city_lookup(cities)
    geonameids, populations, is_capitals = match_airports_to_cities(airports, city_lookup)

    airports["city_geonameid"] = geonameids
    airports["city_population"] = pd.Series(populations, dtype="Int64")
    airports["is_capital"] = is_capitals

    matched_geonameids = {
        geonameid for geonameid in airports["city_geonameid"].dropna().astype(str) if geonameid
    }

    # DSA optimization: build the alternate-name dict once, keyed by geonameid,
    # then do O(1) alias lookups per airport instead of scanning alternateNames
    # once per airport.
    aliases_by_geonameid = build_alias_lookup(matched_geonameids)
    alternate_alias_count = int(
        airports["city_geonameid"].astype(str).map(aliases_by_geonameid).notna().sum()
    )

    city_aliases = [
        list(aliases_by_geonameid.get(str(geonameid), []))
        for geonameid in airports["city_geonameid"]
    ]
    airports["city_aliases"] = [json.dumps(aliases, ensure_ascii=False) for aliases in city_aliases]

    airports["priority"] = [
        calculate_priority(airport_type, population, is_capital)
        for airport_type, population, is_capital in zip(
            airports["type"],
            populations,
            is_capitals,
        )
    ]

    no_city_match_count = int(airports["city_geonameid"].isna().sum())
    average_alias_count = sum(len(aliases) for aliases in city_aliases) / len(airports)

    output_airports = airports.drop(columns=["city_geonameid"])

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    output_airports.to_csv(OUTPUT_PATH, index=False)

    examples = airports[["iata_code", "municipality", "city_aliases", "priority"]].head(5)
    examples = examples.rename(columns={"iata_code": "iata"})

    print("Alias enrichment complete")
    print(f"Input airports file: {AIRPORTS_PATH}")
    print(f"Input cities file: {CITIES_PATH}")
    print(f"Input alternate names file: {ALTERNATE_NAMES_PATH}")
    print(f"Output file: {OUTPUT_PATH}")
    print()
    print(f"Airports with city aliases from alternateNames.txt: {alternate_alias_count}")
    print(f"Airports with no city match in cities15000.txt: {no_city_match_count}")
    print(f"Average number of aliases per airport: {average_alias_count:.2f}")
    print()
    print("Example rows:")
    print(examples.to_string(index=False))


if __name__ == "__main__":
    main()
