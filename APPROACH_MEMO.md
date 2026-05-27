# Fly Fairly Airport Search Engine: Approach Memo

**Technical assessment submission | Python + FastAPI + Typesense + React**

- **Live demo:** [https://fly-fairly-online-assessment.nakulgupta.in/](https://fly-fairly-online-assessment.nakulgupta.in/)
- **Walkthrough:** [https://drive.google.com/file/d/1kn9Ubj0WqMtCGtDSLVZszZX6hQGda9E9/view?usp=sharing](https://drive.google.com/file/d/1kn9Ubj0WqMtCGtDSLVZszZX6hQGda9E9/view?usp=sharing)
- **LLM Prompt Logs:** [Cursor](https://www.notion.so/Cursor-LLM-Prompts-36c6f02c9bd08016b562f43cd384bc32) | [Research](https://www.notion.so/Research-LLM-Prompts-36c6f02c9bd080f380badbf5acbb382e)

## Problem Framing

I treated airport search as ranking over imperfect geographic data. It must resolve typos (`Londn` -> London), aliases (`Bali` -> `DPS`, not `BPN`), metro codes (`LON` -> `LHR`, `LGW`, `STN`), regions (`Hawaii` -> `HNL`, `OGG`, `KOA`, `LIH`), and ambiguous Londons in the UK, Ontario, and Kentucky. It must accept scripts (`東京`, `서울`, `دبي`), ignore accents (`Sao Paulo` = `São Paulo`), support both `TUL` and Tulsa, and bridge Brussels airport's Zaventem municipality.

**Architecture:** The offline enrichment pipeline runs once, produces `enriched_airports.csv`, and indexes into Typesense. Runtime is FastAPI -> Typesense only: no database and no runtime LLM.

## Data Sources and Preparation

| Source                                     | Treatment                                                                                                                                |
| ------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------- |
| OurAirports `airports.csv` (85,476)        | Valid IATA only; removed closed, heliports, and seaplanes -> **8,805** indexed airports. IATA is the traveler-facing booking identifier. |
| OurAirports countries/regions              | Joined hierarchy for display, region search, and disambiguation.                                                                         |
| GeoNames `cities15000.txt`                 | Joined population and capital status for ranking.                                                                                        |
| GeoNames `alternateNames.txt` (18,978,835) | Streamed aliases in nine languages: `en`, `zh`, `ja`, `ar`, `ko`, `ru`, `fr`, `es`, `de`.                                                |

I chose `cities15000.txt` over `allCountries.zip`: `allCountries` has 12M rows including mountains, rivers, and villages. It was too noisy, so I deleted it.

Data issues I handled:

- `alternateNames.txt`: **7,306,150** blank `isolanguage` rows; I retained useful language-tagged aliases.
- `airports.dat`: `\N` null sentinels required normalization.
- `allCountries.zip`: approximately 12M noisy rows for this scope; removed.
- 249 source country rows become **236 countries/territories** represented after airport filtering.

## Search Approach

I chose **Typesense**: lighter to operate than Elasticsearch, purpose-built for typo retrieval unlike SQLite, and explicit in typo/sorting controls versus MeiliSearch.

| Tier | Retrieval path                                    | Example                    |
| ---: | ------------------------------------------------- | -------------------------- |
|    1 | Exact IATA lookup                                 | `TUL` -> Tulsa             |
|    2 | Multi-airport city-code lookup                    | `LON` -> London area group |
|    3 | Exact city or region lookup                       | `Hawaii`, `Brussels`       |
|    4 | Typesense fuzzy retrieval with `num_typos=2`      | `Londn`, `東京`            |
|    5 | Binary-search prefix match over sorted city terms | `deli` -> Delhi            |

The search text field combines IATA, city, all aliases, name, country, and region as lowercase deduplicated tokens; this is what Typesense searches against.

I run all tiers, deduplicate by IATA, then rank; first-match stopping caused Bali to surface a Cameroon airport instead of `DPS`.

**Priority:** `large=90`, `medium=70`, `small=50`; `+10` if population >1M, `+5` if >500K, `+5` if capital, cap `100`, plus query-match boosts. This additive approach ranks London UK hubs above lower-signal alternatives without hardcoding a winner.

## Tradeoffs

| Decision                                | Chose                  | Over                          | Why                                                                                                                                          |
| --------------------------------------- | ---------------------- | ----------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| cities15000 vs allCountries             | cities15000 (25K rows) | allCountries (12M rows)       | allCountries includes mountains, rivers, villages — adds ranking noise. Smaller dataset is cleaner and faster to process                     |
| Offline enrichment vs runtime LLM       | Offline pipeline       | Runtime LLM at query time     | Autocomplete needs <50ms. Runtime LLM adds 500ms+ latency, network risk, API cost. Aliases baked in at index time                            |
| All tiers run vs first match stops      | All tiers run          | Stop at first match           | First match caused Bali to return Cameroon airport instead of DPS. Collecting all candidates then ranking by priority gives better relevance |
| Dynamic city groups vs IATA metro codes | Derived from data      | Paid IATA metro database      | IATA metro codes (NYC, LON) are behind a paid database. Used highest priority airport iata as group key — free and deterministic             |
| IATA only filter vs ICAO                | IATA only              | IATA + ICAO                   | Simpler, traveler facing identifier. Tradeoff: excludes some valid airports with ICAO but no IATA — worth a product conversation             |
| Typesense self hosted vs cloud search   | Self hosted Typesense  | Elasticsearch, Algolia        | Lighter to operate than Elasticsearch, cheaper than Algolia, purpose built for typo tolerance. Tradeoff: need to manage infra                |
| Prefix binary search vs Levenshtein     | Binary search prefix   | Full Levenshtein distance     | Levenshtein on 8805 airports per query is O(n) with string comparison overhead. Binary search on sorted city names is O(log n)               |
| Single search_text field vs multi field | Single combined field  | Search across multiple fields | Simpler Typesense query, one field to tune. Tradeoff: loses field level boosting granularity                                                 |

## LLM Tools and Prompting

I used **Claude (claude.ai)** for research/reasoning and **Cursor** for implementation, with small iterative prompts followed by testing and manual review.

**Full logs:** [Cursor prompts](https://www.notion.so/Cursor-LLM-Prompts-36c6f02c9bd08016b562f43cd384bc32) | [Research prompts](https://www.notion.so/Research-LLM-Prompts-36c6f02c9bd080f380badbf5acbb382e)

Corrections after evaluating LLM output:

- Removed a redundant `EXCLUDED_LANGUAGE_CODES` filter.
- Removed hardcoded aliases including `東京`; GeoNames supplies them dynamically.
- Reordered the 18.9M-row scan to apply the most selective filter first.
- Replaced first-match stopping after Bali ranked a Cameroon airport above `DPS`.
- Fixed `retry_after_remaining=null` on success; an initial fix covered only HTTP `429`.
- Added binary-search prefix matching when Typesense did not map `deli` to Delhi.

## Build, Buy, or Cut

| Decision             | Choice                                 | Reason                                                                                                   |
| -------------------- | -------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| Search engine        | Typesense (buy)                        | Typo tolerance; self-hosted; fast setup                                                                  |
| Data pipeline        | Built                                  | Airport-specific enrichment and ranking                                                                  |
| Multilingual aliases | GeoNames (buy)                         | Free global human-curated translations                                                                   |
| City group codes     | Derived dynamically                    | Avoid a paid metro-code database                                                                         |
| Runtime LLM          | Cut entirely                           | Autocomplete needs <50 ms; inference adds 500 ms+                                                        |
| Deployment           | AWS EC2 + Docker + GitHub/GitLab CI/CD | Image built on Github Actions. Manual pull and start on EC2. Treated as a real product not a local demo. |
| Rate limiting        | `slowapi` (buy)                        | Direct FastAPI integration                                                                               |
| UI component library | Cut                                    | React + CSS variables sufficed                                                                           |

## Deployment

Deployed on AWS EC2 with Docker at:
https://fly-fairly-online-assessment.nakulgupta.in/

CI/CD via GitHub Actions and GitLab CI:

- Docker image pushed to registry on green build
- EC2: manual pull, add `.env`, `docker-compose up -d`

## Production Evaluation

| Metric                                         | Target or purpose                          |
| ---------------------------------------------- | ------------------------------------------ |
| Zero-result, typo-query, language distribution | Find recall and localization gaps          |
| Missing alias rate                             | Track when known aliases return no results |
| Top-1 accuracy; click position                 | Target mean click position `1.0-1.5`       |
| Latency `p50` / `p99`                          | Target `<50 ms`                            |

I would monitor new airports missing from the index, absent tourism aliases, and stale city-group mappings.

## What I Would Do Differently

- Add phonetic matching (Soundex/Metaphone) for harder typos.
- Learn ranking from clicks; add geo-biasing (for example, lift `DEL` in India).
- Revisit IATA-only eligibility: valid ICAO-only airports need an explicit product decision.
- Push back on the assignment assumption: requiring IATA as a mandatory filter excludes valid airports with ICAO codes and scheduled service, which is worth a product conversation.
