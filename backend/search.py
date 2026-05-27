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
FUZZY_CANDIDATE_LIMIT = 20
FINAL_RESULT_LIMIT = 10
MATCH_TYPE_ORDER = [
    "iata_exact",
    "city_group_match",
    "city_exact",
    "region_match",
    "fuzzy_match",
]


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
        result_limit = min(max(1, limit), FINAL_RESULT_LIMIT)

        if not raw_query:
            return self._response(query, [])

        candidates_by_iata: dict[str, dict] = {}
        seen_iata: set[str] = set()

        # Step 1: exact IATA is an O(1) set lookup.
        # Step 2: city group is an O(1) dict lookup against preloaded JSON.
        # Step 3: city/region exact matches are O(1) dict lookups.
        # Step 4: fuzzy search is always attempted and merged with all prior
        # candidates instead of acting as a fallback.
        if uppercase_query in self.city_group_by_code:
            group = self.city_group_by_code[uppercase_query]
            self._add_iata_candidates(
                candidates_by_iata,
                seen_iata,
                group["airports"],
                "city_group_match",
            )

        if uppercase_query in self.iata_codes:
            self._add_iata_candidate(
                candidates_by_iata,
                seen_iata,
                uppercase_query,
                "iata_exact",
            )

        city_iata_codes = self.airports_by_city.get(normalized_query, [])
        if city_iata_codes:
            self._add_iata_candidates(
                candidates_by_iata,
                seen_iata,
                city_iata_codes,
                "city_exact",
            )

        region_iata_codes = self.airports_by_region.get(normalized_query, [])
        if region_iata_codes:
            self._add_iata_candidates(
                candidates_by_iata,
                seen_iata,
                region_iata_codes,
                "region_match",
            )

        fuzzy_documents = self._fuzzy_documents(normalized_query)
        self._add_document_candidates(
            candidates_by_iata,
            seen_iata,
            fuzzy_documents,
            "fuzzy_match",
        )

        sorted_candidates = sorted(
            candidates_by_iata.values(),
            key=lambda candidate: candidate["document"].get("priority", 0),
            reverse=True,
        )
        results = [
            self._format_airport(candidate["document"], candidate["match_types"])
            for candidate in sorted_candidates[:result_limit]
        ]

        return self._response(query, results)

    def _add_iata_candidates(
        self,
        candidates_by_iata: dict[str, dict],
        seen_iata: set[str],
        iata_codes: list[str],
        match_type: str,
    ) -> None:
        for iata_code in iata_codes:
            self._add_iata_candidate(candidates_by_iata, seen_iata, iata_code, match_type)

    def _add_iata_candidate(
        self,
        candidates_by_iata: dict[str, dict],
        seen_iata: set[str],
        iata_code: str,
        match_type: str,
    ) -> None:
        document = self.airport_by_iata.get(iata_code)
        if document is None:
            return

        self._add_document_candidate(candidates_by_iata, seen_iata, document, match_type)

    def _add_document_candidates(
        self,
        candidates_by_iata: dict[str, dict],
        seen_iata: set[str],
        documents: list[dict],
        match_type: str,
    ) -> None:
        for document in documents:
            self._add_document_candidate(candidates_by_iata, seen_iata, document, match_type)

    def _add_document_candidate(
        self,
        candidates_by_iata: dict[str, dict],
        seen_iata: set[str],
        document: dict,
        match_type: str,
    ) -> None:
        iata = document.get("iata")
        if not iata:
            return

        # DSA requirement: use a dict keyed by IATA plus a seen set for O(1)
        # deduplication while merging candidates from every search strategy.
        if iata not in seen_iata:
            seen_iata.add(iata)
            candidates_by_iata[iata] = {
                "document": self.airport_by_iata.get(iata, document),
                "match_types": set(),
            }
        else:
            existing_document = candidates_by_iata[iata]["document"]
            if document.get("priority", 0) > existing_document.get("priority", 0):
                candidates_by_iata[iata]["document"] = document

        candidates_by_iata[iata]["match_types"].add(match_type)

    def _fuzzy_documents(self, normalized_query: str) -> list[dict]:
        fuzzy_documents: list[dict] = []

        try:
            fuzzy_documents = self.typesense.fuzzy_search(
                normalized_query,
                FUZZY_CANDIDATE_LIMIT,
            )
        except (HTTPError, URLError, TimeoutError, OSError):
            fuzzy_documents = []

        fallback_iata_codes = self._local_fuzzy_iata_codes(normalized_query)
        fallback_documents = [
            self.airport_by_iata[iata_code]
            for iata_code in fallback_iata_codes
            if iata_code in self.airport_by_iata
        ]

        return fuzzy_documents + fallback_documents

    def _local_fuzzy_iata_codes(self, normalized_query: str) -> list[str]:
        search_token_iata_codes = self.airports_by_search_token.get(normalized_query, [])
        if search_token_iata_codes:
            return search_token_iata_codes

        search_prefix_iata_codes = self._search_by_prefixes(normalized_query)
        return self._sort_iata_codes_by_priority(list(dict.fromkeys(search_prefix_iata_codes)))

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

    def _format_airport(self, document: dict, match_types: set[str] | list[str]) -> dict:
        iata = document["iata"]
        city = document.get("city") or ""
        region = document.get("region")
        ordered_match_types = [
            match_type for match_type in MATCH_TYPE_ORDER if match_type in match_types
        ]

        return {
            "iata": iata,
            "name": document.get("name") or "",
            "city": city,
            "display_name": self._display_name(document),
            "country": document.get("country") or "",
            "country_code": document.get("country_code") or "",
            "region": region,
            "type": document.get("type") or "",
            "priority": int(document.get("priority", 0)),
            "match_types": ordered_match_types,
            "is_multi_airport_city": False,
            "sub_airports": [],
        }

    def _display_name(self, document: dict) -> str:
        iata = document.get("iata") or ""
        city = document.get("city") or ""
        region = document.get("region")

        if region and normalize_query(region) != normalize_query(city):
            return f"{region} / {city} ({iata})"

        return f"{city} ({iata})"

    def _response(self, query: str, results: list[dict]) -> dict:
        search_types = [
            match_type
            for match_type in MATCH_TYPE_ORDER
            if any(match_type in result["match_types"] for result in results)
        ]

        return {
            "query": query,
            "results": results,
            "total": len(results),
            "search_types": search_types,
        }


search_service = AirportSearch()


def startup() -> None:
    search_service.startup()


def health_status() -> str:
    return "connected" if search_service.connected else "disconnected"


def search_airports(query: str, limit: int = 10) -> dict:
    return search_service.search(query, limit)
