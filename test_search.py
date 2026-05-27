"""Live API regression tests for Fly Fairly airport search assignment cases.

Run with:
    pytest -s test_search.py
"""

from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen
import json
import os

import pytest


SEARCH_API = os.environ.get("FLY_FAIRLY_SEARCH_API", "http://localhost:8000/search")
TOTAL_CASES = 12
CASE_RESULTS: list[tuple[str, bool]] = []


@pytest.fixture(scope="session", autouse=True)
def score_report():
    yield
    score = sum(passed for _, passed in CASE_RESULTS)
    print(f"\nFINAL SCORE: {score}/{TOTAL_CASES}")


def search(query: str, limit: int = 10) -> dict:
    url = f"{SEARCH_API}?{urlencode({'q': query, 'limit': limit})}"
    try:
        with urlopen(url, timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        body = error.read().decode("utf-8")
        raise AssertionError(f"API returned HTTP {error.code} for {query!r}: {body}") from error
    except URLError as error:
        raise AssertionError(f"Could not connect to live search API for {query!r}: {error}") from error


def iata_codes(payload: dict, top: int | None = None) -> list[str]:
    results = payload.get("results", [])
    if top is not None:
        results = results[:top]
    return [result.get("iata") for result in results]


def record(case_name: str, check) -> None:
    try:
        check()
    except AssertionError as error:
        CASE_RESULTS.append((case_name, False))
        print(f"FAIL: {case_name} - {error}")
        raise

    CASE_RESULTS.append((case_name, True))
    print(f"PASS: {case_name}")


def test_hawaii_returns_major_hawaiian_airports():
    def check():
        codes = set(iata_codes(search("Hawaii")))
        required = {"HNL", "OGG", "KOA", "LIH"}
        assert required <= codes, f"missing {sorted(required - codes)}; got {sorted(codes)}"

    record("Hawaii -> HNL, OGG, KOA, LIH", check)


def test_bali_prioritizes_dps_without_bpn_noise():
    def check():
        codes = iata_codes(search("Bali"))
        assert codes, "returned no results"
        assert codes[0] == "DPS", f"top result was {codes[0]}, expected DPS"
        assert "BPN" not in codes[:3], f"BPN appeared in top 3: {codes[:3]}"

    record("Bali -> DPS first, no BPN in top 3", check)


def test_florida_top_five_have_no_chilean_airports():
    def check():
        results = search("Florida").get("results", [])[:5]
        chilean = [result.get("iata") for result in results if result.get("country_code") == "CL"]
        assert not chilean, f"Chilean airports appeared in top 5: {chilean}"

    record("Florida -> no Chilean airports in top 5", check)


def test_manama_returns_bah():
    def check():
        codes = iata_codes(search("Manama"))
        assert "BAH" in codes, f"BAH not returned; got {codes}"

    record("Manama -> BAH", check)


def test_tul_returns_tulsa_airport():
    def check():
        results = search("TUL").get("results", [])
        matches = [
            result
            for result in results
            if result.get("iata") == "TUL"
            and "tulsa" in f"{result.get('name', '')} {result.get('city', '')}".lower()
        ]
        assert matches, f"Tulsa airport TUL not returned; got {iata_codes({'results': results})}"

    record("TUL -> Tulsa airport", check)


def test_brussels_returns_bru():
    def check():
        codes = iata_codes(search("Brussels"))
        assert "BRU" in codes, f"BRU not returned; got {codes}"

    record("Brussels -> BRU", check)


def test_londn_typo_returns_london_airports():
    def check():
        codes = set(iata_codes(search("Londn")))
        required = {"LHR", "LGW"}
        assert required <= codes, f"missing London airports {sorted(required - codes)}; got {sorted(codes)}"

    record("Londn -> London airports", check)


def test_lon_returns_multi_airport_group_with_lhr():
    def check():
        results = search("LON").get("results", [])
        grouped_results = [result for result in results if result.get("is_multi_airport_city") is True]
        assert grouped_results, "no multi-airport city result returned"
        sub_codes = {
            airport.get("iata")
            for result in grouped_results
            for airport in result.get("sub_airports", [])
        }
        assert "LHR" in sub_codes, f"LHR missing from grouped sub-airports; got {sorted(sub_codes)}"

    record("LON -> grouped city containing LHR", check)


def test_london_ranks_lhr_above_canadian_and_kentucky_noise():
    def check():
        codes = iata_codes(search("London"))
        assert "LHR" in codes, f"LHR not returned; got {codes}"
        lhr_position = codes.index("LHR")
        incorrectly_ranked = [
            code for code in ("YXU", "LOZ") if code in codes and codes.index(code) < lhr_position
        ]
        assert not incorrectly_ranked, f"{incorrectly_ranked} ranked above LHR; got {codes}"

    record("London -> LHR above YXU and LOZ", check)


def test_tokyo_japanese_script_returns_hnd_and_nrt():
    def check():
        codes = set(iata_codes(search("東京")))
        required = {"HND", "NRT"}
        assert required <= codes, f"missing {sorted(required - codes)}; got {sorted(codes)}"

    record("東京 -> HND and NRT", check)


def test_sao_paulo_accent_insensitive_results_are_equal():
    def check():
        ascii_codes = iata_codes(search("Sao Paulo"))
        accented_codes = iata_codes(search("São Paulo"))
        assert ascii_codes == accented_codes, (
            f"results differed: Sao Paulo={ascii_codes}, São Paulo={accented_codes}"
        )

    record("Sao Paulo -> same as São Paulo", check)


def test_bah_returns_bahrain_airport():
    def check():
        results = search("BAH").get("results", [])
        matches = [
            result
            for result in results
            if result.get("iata") == "BAH" and result.get("country") == "Bahrain"
        ]
        assert matches, f"Bahrain airport BAH not returned; got {iata_codes({'results': results})}"

    record("BAH -> Bahrain airport", check)
