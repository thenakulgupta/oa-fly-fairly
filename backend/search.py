from collections import defaultdict
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import json
import unicodedata


ROOT_DIR = Path(__file__).resolve().parent.parent
AIRPORT_INDEX_PATH = ROOT_DIR / "data" / "airports_index.json"
CITY_GROUPS_PATH = ROOT_DIR / "data" / "city_groups.json"
AIRPORT_TO_CITY_GROUP_PATH = ROOT_DIR / "data" / "airport_to_city_group.json"
REGION_MAPPING_PATH = ROOT_DIR / "data" / "region_mapping.json"

TYPESENSE_HOST = "localhost"
TYPESENSE_PORT = 8108
TYPESENSE_PROTOCOL = "http"
TYPESENSE_API_KEY = "xyz123"
COLLECTION_NAME = "airports"


def normalize_query(query: str) -> str:
    normalized = unicodedata.normalize("NFKD", query.strip())
    without_accents = "".join(
        character for character in normalized if unicodedata.category(character) != "Mn"
    )
    return without_accents.lower()


def load_json(path: Path):
    with path.open(encoding="utf-8") as input_file:
        return json.load(input_file)


class TypesenseHttpClient:
    def __init__(self) -> None:
        self.base_url = f"{TYPESENSE_PROTOCOL}://{TYPESENSE_HOST}:{TYPESENSE_PORT}"

    def request(
        self,
        method: str,
        path: str,
        payload: object | None = None,
    ) -> dict:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            f"{self.base_url}{path}",
            data=body,
            method=method,
            headers={
                "X-TYPESENSE-API-KEY": TYPESENSE_API_KEY,
                "Content-Type": "application/json",
            },
        )

        with urlopen(request, timeout=5) as response:
            response_body = response.read().decode("utf-8")
            return json.loads(response_body) if response_body else {}

    def health(self) -> bool:
        try:
            response = self.request("GET", "/health")
        except (HTTPError, URLError, TimeoutError, OSError):
            return False

        return response.get("ok") is True

    def fuzzy_search(self, query: str, limit: int) -> list[dict]:
        params = urlencode(
            {
                "q": query,
                "query_by": "search_text",
                "num_typos": 2,
                "sort_by": "priority:desc",
                "per_page": limit,
            }
        )
        response = self.request(
            "GET",
            f"/collections/{COLLECTION_NAME}/documents/search?{params}",
        )
        return [hit["document"] for hit in response.get("hits", [])]


class AirportSearch:
    def __init__(self) -> None:
        self.typesense = TypesenseHttpClient()
        self.connected = False
        self.airport_by_iata: dict[str, dict] = {}
        self.iata_codes: set[str] = set()
        self.city_group_by_code: dict[str, dict] = {}
        self.city_group_by_iata: dict[str, str] = {}
        self.region_mapping: dict[str, list[str]] = {}
        self.airports_by_city: dict[str, list[str]] = {}
        self.airports_by_region: dict[str, list[str]] = {}
        self.airports_by_search_token: dict[str, list[str]] = {}
        self.airports_by_search_prefix: dict[str, list[str]] = {}

    def startup(self) -> None:
        documents = load_json(AIRPORT_INDEX_PATH)
        city_groups = load_json(CITY_GROUPS_PATH)
        airport_to_city_group = load_json(AIRPORT_TO_CITY_GROUP_PATH)
        region_mapping = load_json(REGION_MAPPING_PATH)

        self.airport_by_iata = {document["iata"]: document for document in documents}
        # DSA requirement: a set gives O(1) exact IATA membership checks.
        self.iata_codes = set(self.airport_by_iata)
        self.city_group_by_code = city_groups
        # DSA requirement: airport_to_city_group is the inverted index that gives
        # O(1) multi-airport city lookup by airport IATA.
        self.city_group_by_iata = dict(airport_to_city_group)
        # DSA requirement: keep region mapping in memory for O(1) exact region lookup.
        self.region_mapping = region_mapping
        self.airports_by_city = self._build_city_index(documents)
        self.airports_by_region = self._build_region_index(region_mapping)
        self.airports_by_search_token = self._build_search_token_index(documents)
        self.airports_by_search_prefix = self._build_search_prefix_index(documents)
        self.connected = self.typesense.health()

    def _build_city_index(self, documents: list[dict]) -> dict[str, list[str]]:
        airports_by_city: dict[str, list[str]] = defaultdict(list)

        for document in documents:
            city_key = normalize_query(document.get("city") or "")
            if city_key:
                airports_by_city[city_key].append(document["iata"])

        return {
            city: self._sort_iata_codes_by_priority(iata_codes)
            for city, iata_codes in airports_by_city.items()
        }

    def _build_region_index(self, region_mapping: dict[str, list[str]]) -> dict[str, list[str]]:
        return {
            normalize_query(region_name): self._sort_iata_codes_by_priority(iata_codes)
            for region_name, iata_codes in region_mapping.items()
            if normalize_query(region_name)
        }

    def _build_search_token_index(self, documents: list[dict]) -> dict[str, list[str]]:
        airports_by_token: dict[str, list[str]] = defaultdict(list)

        for document in documents:
            for token in (document.get("search_text") or "").split():
                normalized_token = normalize_query(token)
                if normalized_token:
                    airports_by_token[normalized_token].append(document["iata"])

        return {
            token: self._sort_iata_codes_by_priority(list(dict.fromkeys(iata_codes)))
            for token, iata_codes in airports_by_token.items()
        }

    def _build_search_prefix_index(self, documents: list[dict]) -> dict[str, list[str]]:
        airports_by_prefix: dict[str, list[str]] = defaultdict(list)

        for document in documents:
            tokens = {
                normalize_query(token)
                for token in (document.get("search_text") or "").split()
                if normalize_query(token)
            }

            for token in tokens:
                for prefix_length in range(3, len(token) + 1):
                    airports_by_prefix[token[:prefix_length]].append(document["iata"])

        return {
            prefix: self._sort_iata_codes_by_priority(list(dict.fromkeys(iata_codes)))
            for prefix, iata_codes in airports_by_prefix.items()
        }

    def _sort_iata_codes_by_priority(self, iata_codes: list[str]) -> list[str]:
        return sorted(
            iata_codes,
            key=lambda iata: self.airport_by_iata.get(iata, {}).get("priority", 0),
            reverse=True,
        )

    def search(self, query: str, limit: int = 10) -> dict:
        raw_query = query.strip()
        normalized_query = normalize_query(raw_query)
        uppercase_query = raw_query.upper()
        limit = max(1, limit)

        if not raw_query:
            return self._response(query, [], None)

        if uppercase_query in self.city_group_by_code:
            return self._response(
                query,
                [self._format_city_group(uppercase_query)],
                "city_group_match",
            )

        if uppercase_query in self.iata_codes:
            return self._response(
                query,
                [self._format_airport(self.airport_by_iata[uppercase_query])],
                "iata_exact",
            )

        city_iata_codes = self.airports_by_city.get(normalized_query, [])
        if city_iata_codes:
            return self._response(
                query,
                self._format_airports(city_iata_codes[:limit]),
                "city_exact",
            )

        region_iata_codes = self.airports_by_region.get(normalized_query, [])
        if region_iata_codes:
            return self._response(
                query,
                self._format_airports(region_iata_codes[:limit]),
                "region_match",
            )

        search_token_iata_codes = self.airports_by_search_token.get(normalized_query, [])
        if search_token_iata_codes:
            return self._response(
                query,
                self._format_airports(search_token_iata_codes[:limit]),
                "fuzzy_match",
            )

        search_prefix_iata_codes = self._search_by_prefixes(normalized_query)
        if search_prefix_iata_codes:
            return self._response(
                query,
                self._format_airports(search_prefix_iata_codes[:limit]),
                "fuzzy_match",
            )

        fuzzy_documents = self.typesense.fuzzy_search(normalized_query, limit)
        fuzzy_documents = sorted(
            fuzzy_documents,
            key=lambda document: document.get("priority", 0),
            reverse=True,
        )
        return self._response(
            query,
            [self._format_airport(document) for document in fuzzy_documents[:limit]],
            "fuzzy_match",
        )

    def _format_airports(self, iata_codes: list[str]) -> list[dict]:
        return [
            self._format_airport(self.airport_by_iata[iata_code])
            for iata_code in iata_codes
            if iata_code in self.airport_by_iata
        ]

    def _search_by_prefixes(self, normalized_query: str) -> list[str]:
        query_tokens = [token for token in normalized_query.split() if len(token) >= 3]
        if not query_tokens:
            return []

        matching_iata_sets = []
        for token in query_tokens:
            iata_codes = self.airports_by_search_prefix.get(token, [])
            if not iata_codes:
                return []
            matching_iata_sets.append(set(iata_codes))

        matching_iata_codes = set.intersection(*matching_iata_sets)
        return self._sort_iata_codes_by_priority(list(matching_iata_codes))

    def _format_airport(self, document: dict) -> dict:
        iata = document["iata"]
        city = document.get("city") or ""
        region = document.get("region")

        return {
            "iata": iata,
            "name": document.get("name") or "",
            "city": city,
            "display_name": self._display_name(document),
            "country": document.get("country") or "",
            "country_code": document.get("country_code") or "",
            "region": region,
            "type": document.get("type") or "",
            "is_multi_airport_city": False,
            "sub_airports": [],
        }

    def _format_city_group(self, city_group_code: str) -> dict:
        group = self.city_group_by_code[city_group_code]
        sub_airports = []

        for iata in group["airports"]:
            document = self.airport_by_iata.get(iata)
            if document is None:
                continue

            sub_airports.append(
                {
                    "iata": iata,
                    "name": document.get("name") or "",
                    "display_name": self._display_name(document),
                }
            )

        primary_document = self.airport_by_iata.get(group["airports"][0], {})

        return {
            "iata": city_group_code,
            "name": f"{group['city']} Area Airports",
            "city": group["city"],
            "display_name": group["label"],
            "country": primary_document.get("country") or "",
            "country_code": group["country_code"],
            "region": primary_document.get("region"),
            "type": "city_group",
            "is_multi_airport_city": True,
            "sub_airports": sub_airports,
        }

    def _display_name(self, document: dict) -> str:
        iata = document.get("iata") or ""
        city = document.get("city") or ""
        region = document.get("region")

        if region and normalize_query(region) != normalize_query(city):
            return f"{region} / {city} ({iata})"

        return f"{city} ({iata})"

    def _response(self, query: str, results: list[dict], search_type: str | None) -> dict:
        return {
            "query": query,
            "results": results,
            "total": len(results),
            "search_type": search_type,
        }


search_service = AirportSearch()


def startup() -> None:
    search_service.startup()


def health_status() -> str:
    return "connected" if search_service.connected else "disconnected"


def search_airports(query: str, limit: int = 10) -> dict:
    return search_service.search(query, limit)
