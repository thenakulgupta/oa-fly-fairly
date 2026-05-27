from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import json
import os

import pandas as pd


ROOT_DIR = Path(__file__).resolve().parent.parent
AIRPORTS_PATH = ROOT_DIR / "data" / "enriched_airports.csv"
CITY_GROUPS_PATH = ROOT_DIR / "data" / "city_groups.json"
AIRPORT_TO_CITY_GROUP_PATH = ROOT_DIR / "data" / "airport_to_city_group.json"
REGION_MAPPING_PATH = ROOT_DIR / "data" / "region_mapping.json"
OUTPUT_PATH = ROOT_DIR / "data" / "airports_index.json"

TYPESENSE_HOST = os.environ.get("TYPESENSE_HOST", "localhost")
TYPESENSE_PORT = int(os.environ.get("TYPESENSE_PORT", "8108"))
TYPESENSE_PROTOCOL = os.environ.get("TYPESENSE_PROTOCOL", "http")
TYPESENSE_API_KEY = os.environ.get(
    "TYPESENSE_API_KEY",
    "nakulgupta-1076787674878372323dsff",
)
COLLECTION_NAME = "airports"
BATCH_SIZE = 100
PROGRESS_INTERVAL = 500

AIRPORT_SCHEMA = {
    "name": COLLECTION_NAME,
    "fields": [
        {"name": "id", "type": "string"},
        {"name": "iata", "type": "string", "facet": False},
        {"name": "name", "type": "string"},
        {"name": "city", "type": "string"},
        {"name": "city_aliases", "type": "string[]"},
        {"name": "keywords", "type": "string[]"},
        {"name": "country", "type": "string"},
        {"name": "country_code", "type": "string", "facet": True},
        {"name": "region", "type": "string", "facet": True, "optional": True},
        {"name": "region_aliases", "type": "string[]"},
        {"name": "multi_airport_city", "type": "string", "optional": True},
        {"name": "type", "type": "string", "facet": True},
        {"name": "priority", "type": "int32"},
        {"name": "latitude", "type": "float", "optional": True},
        {"name": "longitude", "type": "float", "optional": True},
        {"name": "is_capital", "type": "bool", "optional": True},
        {"name": "city_population", "type": "int64", "optional": True},
        {"name": "search_text", "type": "string"},
    ],
    "default_sorting_field": "priority",
}


def clean_text(value: object) -> str:
    return str(value).strip()


def optional_text(value: object) -> str | None:
    text = clean_text(value)
    return text or None


def optional_float(value: object) -> float | None:
    text = clean_text(value)
    if not text:
        return None

    try:
        return float(text)
    except ValueError:
        return None


def optional_int(value: object) -> int | None:
    text = clean_text(value)
    if not text:
        return None

    try:
        return int(float(text))
    except ValueError:
        return None


def parse_bool(value: object) -> bool:
    return clean_text(value).casefold() in {"true", "1", "yes", "y"}


def parse_aliases(raw_aliases: object) -> list[str]:
    try:
        aliases = json.loads(clean_text(raw_aliases) or "[]")
    except json.JSONDecodeError:
        aliases = []

    deduped_aliases: list[str] = []
    seen_aliases: set[str] = set()

    for alias in aliases:
        alias_text = clean_text(alias)
        alias_key = alias_text.casefold()

        if not alias_text or alias_key in seen_aliases:
            continue

        seen_aliases.add(alias_key)
        deduped_aliases.append(alias_text)

    return deduped_aliases


def parse_keywords(raw_keywords: object) -> list[str]:
    keywords: list[str] = []
    seen_keywords: set[str] = set()

    for keyword in clean_text(raw_keywords).split(","):
        keyword_text = keyword.strip()
        keyword_key = keyword_text.casefold()

        # DSA optimization: airport-supplied keyword deduplication is O(1)
        # per entry while retaining source order for deterministic documents.
        if not keyword_text or keyword_key in seen_keywords:
            continue

        seen_keywords.add(keyword_key)
        keywords.append(keyword_text)

    return keywords


def build_search_text(parts: list[object]) -> str:
    tokens: list[str] = []
    seen_tokens: set[str] = set()

    for part in parts:
        if part is None:
            continue

        values = part if isinstance(part, list) else [part]
        for value in values:
            for token in clean_text(value).lower().split():
                # DSA optimization: use a set for O(1) token deduplication
                # while preserving first-seen order in the final search string.
                if token and token not in seen_tokens:
                    seen_tokens.add(token)
                    tokens.append(token)

    return " ".join(tokens)


def load_json_file(path: Path) -> dict:
    with path.open(encoding="utf-8") as input_file:
        return json.load(input_file)


def build_city_group_lookup(
    city_groups: dict[str, dict],
    airport_to_city_group: dict[str, str],
) -> dict[str, str]:
    # DSA optimization: precompute IATA -> city group code in O(n), validating
    # against city_groups once so every airport document gets O(1) lookup.
    city_group_by_iata: dict[str, str] = {}

    for iata_code, city_group_code in airport_to_city_group.items():
        if city_group_code not in city_groups:
            raise ValueError(f"Missing city group for code {city_group_code}")

        city_group_by_iata[iata_code] = city_group_code

    return city_group_by_iata


def build_airport_documents(
    airports: pd.DataFrame,
    city_group_by_iata: dict[str, str],
) -> list[dict]:
    documents: list[dict] = []

    for airport in airports.itertuples(index=False):
        iata = clean_text(airport.iata_code)
        city = clean_text(airport.municipality)
        city_aliases = parse_aliases(airport.city_aliases)
        keywords = parse_keywords(airport.keywords)
        country = clean_text(airport.country_name)
        region = optional_text(airport.region_name)
        name = clean_text(airport.name)

        document = {
            "id": iata,
            "iata": iata,
            "name": name,
            "city": city,
            "city_aliases": city_aliases,
            "keywords": keywords,
            "country": country,
            "country_code": clean_text(airport.iso_country),
            "region": region,
            "region_aliases": [],
            "multi_airport_city": city_group_by_iata.get(iata),
            "type": clean_text(airport.type),
            "priority": int(airport.priority),
            "latitude": optional_float(airport.latitude_deg),
            "longitude": optional_float(airport.longitude_deg),
            "is_capital": parse_bool(airport.is_capital),
            "city_population": optional_int(airport.city_population),
            "search_text": build_search_text(
                [iata, city, city_aliases, keywords, name, country, region]
            ),
        }
        documents.append(document)

    return documents


def typesense_url(path: str) -> str:
    return f"{TYPESENSE_PROTOCOL}://{TYPESENSE_HOST}:{TYPESENSE_PORT}{path}"


def typesense_request(
    method: str,
    path: str,
    payload: object | str | None = None,
    content_type: str = "application/json",
) -> tuple[int, str]:
    body: bytes | None = None

    if payload is not None:
        if isinstance(payload, str):
            body = payload.encode("utf-8")
        else:
            body = json.dumps(payload).encode("utf-8")

    request = Request(
        typesense_url(path),
        data=body,
        method=method,
        headers={
            "X-TYPESENSE-API-KEY": TYPESENSE_API_KEY,
            "Content-Type": content_type,
        },
    )

    with urlopen(request, timeout=30) as response:
        return response.status, response.read().decode("utf-8")


def recreate_airports_collection() -> None:
    try:
        typesense_request("DELETE", f"/collections/{COLLECTION_NAME}")
    except HTTPError as error:
        if error.code != 404:
            raise

    typesense_request("POST", "/collections", AIRPORT_SCHEMA)


def chunked(items: list[dict], size: int) -> list[dict]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def import_documents(documents: list[dict]) -> list[dict]:
    failed_documents: list[dict] = []
    indexed_count = 0

    for batch in chunked(documents, BATCH_SIZE):
        import_payload = "\n".join(json.dumps(document, ensure_ascii=False) for document in batch)

        try:
            _, response_body = typesense_request(
                "POST",
                f"/collections/{COLLECTION_NAME}/documents/import?action=upsert",
                import_payload,
                content_type="text/plain",
            )
        except HTTPError as error:
            reason = error.read().decode("utf-8")
            for document in batch:
                failed_documents.append({"id": document["id"], "reason": reason})
            indexed_count += len(batch)
            if indexed_count % PROGRESS_INTERVAL == 0 or indexed_count == len(documents):
                print(f"Indexed {indexed_count}/{len(documents)} documents")
            continue

        for document, result_line in zip(batch, response_body.splitlines()):
            result = json.loads(result_line)
            if not result.get("success", False):
                failed_documents.append(
                    {
                        "id": document["id"],
                        "reason": result.get("error", "Unknown Typesense import error"),
                    }
                )

        indexed_count += len(batch)
        if indexed_count % PROGRESS_INTERVAL == 0 or indexed_count == len(documents):
            print(f"Indexed {indexed_count}/{len(documents)} documents")

    return failed_documents


def main() -> None:
    airports = pd.read_csv(AIRPORTS_PATH, dtype=str, keep_default_na=False)
    city_groups = load_json_file(CITY_GROUPS_PATH)
    airport_to_city_group = load_json_file(AIRPORT_TO_CITY_GROUP_PATH)
    region_mapping = load_json_file(REGION_MAPPING_PATH)

    city_group_by_iata = build_city_group_lookup(city_groups, airport_to_city_group)
    documents = build_airport_documents(airports, city_group_by_iata)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as output_file:
        json.dump(documents, output_file, ensure_ascii=False, indent=2)
        output_file.write("\n")

    print("Saved final airport documents")
    print(f"Output file: {OUTPUT_PATH}")
    print()

    recreate_airports_collection()
    failed_documents = import_documents(documents)

    documents_with_aliases = sum(1 for document in documents if document["city_aliases"])
    documents_with_city_group = sum(1 for document in documents if document["multi_airport_city"])
    documents_with_region = sum(1 for document in documents if document["region"])

    print()
    print("Airport indexing complete")
    print(f"Total documents indexed: {len(documents) - len(failed_documents)}")
    print(f"Documents with city aliases: {documents_with_aliases}")
    print(f"Documents with multi_airport_city set: {documents_with_city_group}")
    print(f"Documents with region set: {documents_with_region}")
    print()
    print("Failed documents:")
    if not failed_documents:
        print("- None")
    else:
        for failure in failed_documents:
            print(f"- {failure}")


if __name__ == "__main__":
    main()
