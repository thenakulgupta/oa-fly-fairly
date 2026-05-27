from collections import defaultdict
from bisect import bisect_left
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import csv
import json
import os
import unicodedata


ROOT_DIR = Path(__file__).resolve().parent.parent
AIRPORT_INDEX_PATH = ROOT_DIR / "data" / "airports_index.json"
CITY_GROUPS_PATH = ROOT_DIR / "data" / "city_groups.json"
AIRPORT_TO_CITY_GROUP_PATH = ROOT_DIR / "data" / "airport_to_city_group.json"
REGION_MAPPING_PATH = ROOT_DIR / "data" / "region_mapping.json"
COUNTRIES_PATH = ROOT_DIR / "data" / "countries.csv"
REGIONS_PATH = ROOT_DIR / "data" / "regions.csv"

TYPESENSE_HOST = os.environ.get("TYPESENSE_HOST", "localhost")
TYPESENSE_PORT = int(os.environ.get("TYPESENSE_PORT", "8108"))
TYPESENSE_PROTOCOL = os.environ.get("TYPESENSE_PROTOCOL", "http")
TYPESENSE_API_KEY = os.environ.get(
    "TYPESENSE_API_KEY",
    "nakulgupta-1076787674878372323dsff",
)
COLLECTION_NAME = "airports"
FUZZY_CANDIDATE_LIMIT = 20
FINAL_RESULT_LIMIT = 10
STATS_PAGE_SIZE = 250
COMMON_QUERY_SUFFIXES = ("a", "e", "h", "i", "n", "o", "s", "u", "y")
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


def count_csv_data_rows(path: Path) -> int:
    with path.open(newline="", encoding="utf-8") as input_file:
        reader = csv.reader(input_file)
        next(reader, None)
        return sum(1 for _ in reader)


def optional_float(value: object) -> float | None:
    if value in (None, ""):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def optional_int(value: object) -> int | None:
    if value in (None, ""):
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def bool_value(value: object) -> bool:
    if isinstance(value, bool):
        return value

    if value in (None, ""):
        return False

    return str(value).casefold() in {"true", "1", "yes", "y"}


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
                "num_typos": "2",
                "prefix": "true",
                "typo_tokens_threshold": 1,
                "min_len_1typo": 3,
                "min_len_2typo": 5,
                "sort_by": "priority:desc",
                "per_page": limit,
            }
        )
        response = self.request(
            "GET",
            f"/collections/{COLLECTION_NAME}/documents/search?{params}",
        )
        return [hit["document"] for hit in response.get("hits", [])]

    def collection_facets(self) -> dict:
        params = urlencode(
            {
                "q": "*",
                "query_by": "search_text",
                "per_page": 1,
                "facet_by": "type,country_code,region",
                "max_facet_values": 10000,
            }
        )
        return self.request(
            "GET",
            f"/collections/{COLLECTION_NAME}/documents/search?{params}",
        )

    def search_documents_page(self, page: int, per_page: int, include_fields: str) -> dict:
        params = urlencode(
            {
                "q": "*",
                "query_by": "search_text",
                "page": page,
                "per_page": per_page,
                "include_fields": include_fields,
            }
        )
        return self.request(
            "GET",
            f"/collections/{COLLECTION_NAME}/documents/search?{params}",
        )

    def count_documents(self, filter_by: str) -> int:
        params = urlencode(
            {
                "q": "*",
                "query_by": "search_text",
                "filter_by": filter_by,
                "per_page": 1,
            }
        )
        response = self.request(
            "GET",
            f"/collections/{COLLECTION_NAME}/documents/search?{params}",
        )
        return int(response.get("found", 0))


class AirportSearch:
    def __init__(self) -> None:
        self.typesense = TypesenseHttpClient()
        self.connected = False
        self.airport_by_iata: dict[str, dict] = {}
        self.iata_codes: set[str] = set()
        self.city_group_by_code: dict[str, dict] = {}
        self.city_group_by_iata: dict[str, str] = {}
        self.city_group_by_keyword: dict[str, str] = {}
        self.region_mapping: dict[str, list[str]] = {}
        self.airports_by_city: dict[str, list[str]] = {}
        self.airports_by_region: dict[str, list[str]] = {}
        self.airports_by_search_token: dict[str, list[str]] = {}
        self.airports_by_search_prefix: dict[str, list[str]] = {}
        self.city_prefix_entries: list[tuple[str, str]] = []
        self.total_countries = 0
        self.total_regions = 0

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
        self.city_group_by_keyword = self._build_city_group_keyword_index(city_groups)
        # DSA requirement: keep region mapping in memory for O(1) exact region lookup.
        self.region_mapping = region_mapping
        self.airports_by_city = self._build_city_index(documents)
        self.airports_by_region = self._build_region_index(region_mapping)
        self.airports_by_search_token = self._build_search_token_index(documents)
        self.airports_by_search_prefix = self._build_search_prefix_index(documents)
        self.city_prefix_entries = self._build_city_prefix_entries(documents)
        self.total_countries = count_csv_data_rows(COUNTRIES_PATH)
        self.total_regions = count_csv_data_rows(REGIONS_PATH)
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
                for prefix_length in range(2, len(token) + 1):
                    airports_by_prefix[token[:prefix_length]].append(document["iata"])

        return {
            prefix: self._sort_iata_codes_by_priority(list(dict.fromkeys(iata_codes)))
            for prefix, iata_codes in airports_by_prefix.items()
        }

    def _build_city_prefix_entries(self, documents: list[dict]) -> list[tuple[str, str]]:
        city_entries: set[tuple[str, str]] = set()

        for document in documents:
            for city_term in self._city_terms(document):
                city_entries.add((city_term, document["iata"]))

        # DSA requirement: keep city terms sorted so prefix lookup can jump to
        # the matching range with binary search in O(log n), then scan only
        # matching city-prefix rows instead of all airports.
        return sorted(city_entries)

    def _build_city_group_keyword_index(self, city_groups: dict[str, dict]) -> dict[str, str]:
        groups_by_keyword: dict[str, set[str]] = defaultdict(set)

        for group_code, group in city_groups.items():
            keyword_counts: dict[str, int] = defaultdict(int)
            for iata_code in group["airports"]:
                document = self.airport_by_iata.get(iata_code, {})
                for keyword in set(document.get("keywords") or []):
                    keyword_code = keyword.strip().upper()
                    if len(keyword_code) == 3 and keyword_code.isalpha():
                        keyword_counts[keyword_code] += 1

            for keyword_code, count in keyword_counts.items():
                if count > 1:
                    groups_by_keyword[keyword_code].add(group_code)

        # DSA optimization: map a shared, unambiguous source keyword (such as
        # a metro code) to its city group once for O(1) query-time lookup.
        return {
            keyword: next(iter(group_codes))
            for keyword, group_codes in groups_by_keyword.items()
            if len(group_codes) == 1
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
        query_variants = self._query_variants(normalized_query)
        uppercase_query = raw_query.upper()
        result_limit = min(max(1, limit), FINAL_RESULT_LIMIT)

        if not raw_query:
            return self._response(query, [])

        candidates_by_iata: dict[str, dict] = {}
        seen_iata: set[str] = set()
        matched_city_group_code = None

        # Step 1: exact IATA is an O(1) set lookup.
        # Step 2: city group is an O(1) dict lookup against preloaded JSON.
        # Step 3: city/region exact matches are O(1) dict lookups.
        # Step 4: fuzzy search is always attempted and merged with all prior
        # candidates instead of acting as a fallback.
        if uppercase_query in self.city_group_by_code:
            group = self.city_group_by_code[uppercase_query]
            matched_city_group_code = uppercase_query
            self._add_iata_candidates(
                candidates_by_iata,
                seen_iata,
                group["airports"],
                "city_group_match",
            )
        elif uppercase_query not in self.iata_codes:
            matched_city_group_code = self.city_group_by_keyword.get(uppercase_query)
            if matched_city_group_code:
                self._add_iata_candidates(
                    candidates_by_iata,
                    seen_iata,
                    self.city_group_by_code[matched_city_group_code]["airports"],
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

        city_prefix_iata_codes = self._city_prefix_iata_codes(query_variants)
        if city_prefix_iata_codes:
            self._add_iata_candidates(
                candidates_by_iata,
                seen_iata,
                city_prefix_iata_codes,
                "fuzzy_match",
            )

        fuzzy_documents = self._fuzzy_documents(query_variants)
        self._add_document_candidates(
            candidates_by_iata,
            seen_iata,
            fuzzy_documents,
            "fuzzy_match",
        )

        if any(
            self._direct_match_boost(candidate["document"], normalized_query)
            for candidate in candidates_by_iata.values()
        ):
            candidates_by_iata = {
                iata: candidate
                for iata, candidate in candidates_by_iata.items()
                if self._direct_match_boost(candidate["document"], normalized_query)
                or "iata_exact" in candidate["match_types"]
                or "city_group_match" in candidate["match_types"]
            }

        sorted_candidates = sorted(
            candidates_by_iata.values(),
            key=lambda candidate: self._candidate_sort_key(
                candidate, normalized_query, query_variants
            ),
            reverse=True,
        )
        results = [
            self._format_airport(candidate["document"], candidate["match_types"])
            for candidate in sorted_candidates[:result_limit]
        ]

        if matched_city_group_code and uppercase_query not in self.iata_codes:
            group_iata_codes = set(self.city_group_by_code[matched_city_group_code]["airports"])
            results = [
                self._format_city_group(matched_city_group_code),
                *[result for result in results if result["iata"] not in group_iata_codes],
            ][:result_limit]

        return self._response(query, results)

    def stats(self) -> dict:
        facet_response = self.typesense.collection_facets()
        facet_counts = {
            facet["field_name"]: {
                value["value"]: value["count"]
                for value in facet.get("counts", [])
                if value.get("value")
            }
            for facet in facet_response.get("facet_counts", [])
        }

        return {
            "total_airports": int(facet_response.get("found", 0)),
            "total_countries": len(facet_counts.get("country_code", {})),
            "total_regions": len(facet_counts.get("region", {})),
            "capital_airports": self.typesense.count_documents("is_capital:=true"),
            "by_type": facet_counts.get("type", {}),
            "multi_airport_cities": len(self.city_group_by_code),
            "airports_with_aliases": self._count_airports_with_aliases(
                int(facet_response.get("found", 0))
            ),
        }

    def _count_airports_with_aliases(self, total_airports: int) -> int:
        airports_with_aliases = 0

        for offset in range(0, total_airports, STATS_PAGE_SIZE):
            page = (offset // STATS_PAGE_SIZE) + 1
            response = self.typesense.search_documents_page(
                page=page,
                per_page=STATS_PAGE_SIZE,
                include_fields="city_aliases",
            )

            for hit in response.get("hits", []):
                city_aliases = hit.get("document", {}).get("city_aliases", [])
                if city_aliases:
                    airports_with_aliases += 1

        return airports_with_aliases

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

    def _fuzzy_documents(self, query_variants: list[str]) -> list[dict]:
        fuzzy_documents_by_iata: dict[str, dict] = {}

        for query_variant in query_variants:
            try:
                fuzzy_documents = self.typesense.fuzzy_search(
                    query_variant,
                    FUZZY_CANDIDATE_LIMIT,
                )
            except (HTTPError, URLError, TimeoutError, OSError):
                fuzzy_documents = []

            for document in fuzzy_documents:
                iata = document.get("iata")
                if iata:
                    fuzzy_documents_by_iata[iata] = document

        fallback_iata_codes: list[str] = []
        for query_variant in query_variants:
            fallback_iata_codes.extend(self._local_fuzzy_iata_codes(query_variant))

        fallback_documents = [
            self.airport_by_iata[iata_code]
            for iata_code in dict.fromkeys(fallback_iata_codes)
            if iata_code in self.airport_by_iata
        ]

        reranked_documents = list(fuzzy_documents_by_iata.values()) + fallback_documents
        return sorted(
            reranked_documents,
            key=lambda document: self._document_sort_key(document, query_variants),
            reverse=True,
        )

    def _local_fuzzy_iata_codes(self, normalized_query: str) -> list[str]:
        search_token_iata_codes = self.airports_by_search_token.get(normalized_query, [])
        if search_token_iata_codes and len(normalized_query) >= 4:
            return search_token_iata_codes

        search_prefix_iata_codes = self._search_by_prefixes(normalized_query)
        iata_codes = search_token_iata_codes + search_prefix_iata_codes
        return self._sort_iata_codes_by_priority(list(dict.fromkeys(iata_codes)))

    def _candidate_sort_key(
        self,
        candidate: dict,
        normalized_query: str,
        query_variants: list[str],
    ) -> tuple[int, int, int]:
        document = candidate["document"]
        priority = int(document.get("priority", 0))
        match_types = candidate["match_types"]
        search_step_boost = 1_000 if "iata_exact" in match_types else 0

        if "city_group_match" in match_types:
            search_step_boost += 500

        return (
            priority
            + self._direct_match_boost(document, normalized_query)
            + self._city_match_boost(document, query_variants)
            + search_step_boost,
            priority,
            -len(document.get("name") or ""),
        )

    def _document_sort_key(self, document: dict, query_variants: list[str]) -> tuple[int, int]:
        priority = int(document.get("priority", 0))
        return (
            priority + self._city_match_boost(document, query_variants),
            priority,
        )

    def _city_match_boost(self, document: dict, query_variants: list[str]) -> int:
        city_terms = self._city_terms(document)
        exact_city_match = any(query_variant in city_terms for query_variant in query_variants)
        if exact_city_match:
            return 20

        partial_city_match = any(
            city_term.startswith(query_variant)
            for city_term in city_terms
            for query_variant in query_variants
            if query_variant
        )
        return 10 if partial_city_match else 0

    def _direct_match_boost(self, document: dict, normalized_query: str) -> int:
        if not normalized_query:
            return 0

        if normalize_query(document.get("region") or "") == normalized_query:
            return 300

        if normalized_query in self._city_terms(document):
            return 200

        keywords = {
            normalize_query(keyword) for keyword in document.get("keywords") or []
        }
        if normalized_query in keywords:
            return 250

        if not normalized_query.isascii() and any(
            keyword.startswith(normalized_query) for keyword in keywords
        ):
            return 150

        return 0

    def _query_variants(self, normalized_query: str) -> list[str]:
        variants = [normalized_query]

        if normalized_query:
            variants.extend(f"{normalized_query}{suffix}" for suffix in COMMON_QUERY_SUFFIXES)

            if normalized_query.endswith("i"):
                variants.append(f"{normalized_query[:-1]}hi")

            if normalized_query.endswith("h"):
                variants.append(f"{normalized_query}i")

        # DSA optimization: ordered dict-style dedup keeps query expansion small
        # and makes every downstream lookup run once per unique normalized query.
        return [variant for variant in dict.fromkeys(variants) if variant]

    def _city_prefix_iata_codes(self, query_variants: list[str]) -> list[str]:
        matching_iata_codes: list[str] = []

        for query_variant in query_variants:
            if len(query_variant) < 2:
                continue

            start = bisect_left(self.city_prefix_entries, (query_variant, ""))
            end = bisect_left(self.city_prefix_entries, (f"{query_variant}\U0010ffff", ""))
            matching_iata_codes.extend(
                iata_code for _, iata_code in self.city_prefix_entries[start:end]
            )

        return self._sort_iata_codes_by_priority(list(dict.fromkeys(matching_iata_codes)))

    def _city_terms(self, document: dict) -> set[str]:
        terms: set[str] = set()
        raw_terms = [document.get("city") or "", *(document.get("city_aliases") or [])]

        for raw_term in raw_terms:
            normalized_term = normalize_query(raw_term)
            if not normalized_term:
                continue

            terms.add(normalized_term)
            words = normalized_term.split()
            for index in range(len(words)):
                terms.add(" ".join(words[index:]))

        return terms

    def _search_by_prefixes(self, normalized_query: str) -> list[str]:
        query_tokens = [token for token in normalized_query.split() if len(token) >= 2]
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

    def _format_city_group(self, group_code: str) -> dict:
        group = self.city_group_by_code[group_code]
        sub_documents = [
            self.airport_by_iata[iata]
            for iata in group["airports"]
            if iata in self.airport_by_iata
        ]
        representative = sub_documents[0]
        result = self._format_airport(representative, {"city_group_match"})
        result.update(
            {
                "iata": group_code,
                "name": f"{group['city']} Area Airports",
                "city": group["city"],
                "display_name": group["label"],
                "country_code": group["country_code"],
                "is_multi_airport_city": True,
                "sub_airports": [
                    {
                        "iata": document["iata"],
                        "name": document.get("name") or "",
                        "display_name": (
                            f"{document.get('city') or group['city']} "
                            f"({document['iata']})"
                        ),
                    }
                    for document in sub_documents
                ],
            }
        )
        return result

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
            "latitude": optional_float(document.get("latitude")),
            "longitude": optional_float(document.get("longitude")),
            "is_capital": bool_value(document.get("is_capital")),
            "city_population": optional_int(document.get("city_population")),
            "match_types": ordered_match_types,
            "city_aliases": document.get("city_aliases") or [],
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


def airport_stats() -> dict:
    return search_service.stats()
