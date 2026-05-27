# ✈ Fly Fairly Airport Search Engine

An end-to-end airport search system for an online travel agency, built to handle real-world destination queries across codes, cities, regions, aliases, scripts, and misspellings.

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-API-009688?logo=fastapi&logoColor=white)
![Typesense](https://img.shields.io/badge/Typesense-Search-D6249F)
![React](https://img.shields.io/badge/React-Vite-61DAFB?logo=react&logoColor=111827)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)

Fly Fairly combines a React interface, a FastAPI service, Typesense-backed retrieval, and an offline enrichment pipeline. It supports typo-tolerant and multilingual search, region discovery, tourism aliases, multi-airport cities, and ranking-based disambiguation.

## Architecture

```text
User Query
    ↓
React Frontend (Vite)
    ↓ debounced 300 ms
FastAPI Backend
    ↓ 5-tier search logic
Typesense Search Engine
    ↓ ranked results
React UI with Airport Detail Panel
```

### Data Pipeline

The offline pipeline prepares and enriches source data before it is indexed into Typesense.

```text
airports.csv + countries.csv + regions.csv
    ↓ filter_airports.py      (keep IATA-coded operating airports)
    ↓ enrich_countries.py     (add country names)
    ↓ enrich_regions.py       (add region/state names)
    ↓ enrich_aliases.py       (add multilingual aliases
                               from GeoNames 18M rows)
    ↓ build_region_mapping.py (region -> airports map)
    ↓ build_city_groups.py    (multi-airport city groups)
    ↓ index_airports.py       (push to Typesense)
    ✓ 8,805 airports indexed
```

## Features

- ✈ **IATA exact match** for codes such as `JFK`, `DEL`, and `LHR`.
- 🏙 **Multi-airport city grouping** such as `LON` → `LHR`, `LGW`, and `STN`.
- 🗺 **Region and state search** for destinations such as Hawaii, Ontario, and Florida.
- 🌴 **Tourism alias search** such as Bali → `DPS` and Brussels → `BRU`.
- ⌨ **Typo tolerance** such as `Londn` → London and `deli` → Delhi.
- 🌏 **Multi-language support** for queries such as `東京`, `서울`, `دبي`, and `Москва`.
- 🔤 **Accent-insensitive search** so `Sao Paulo` and `São Paulo` resolve consistently.
- 🇬🇧 **Disambiguation** that prioritizes London, United Kingdom over similarly named locations.
- ⚡ **Rate limiting** with remaining-request and reset-time information.
- 🌙 **Dark and light themes** with system-preference initialization.
- 📍 **Airport detail panel** with metadata and a Google Maps link.
- 📊 **Real-time stats API** backed by the indexed collection.

## Tech Stack

| Layer | Technology | Why |
| --- | --- | --- |
| Backend | Python + FastAPI | Async-ready, fast, and clean API development |
| Search | Typesense | Fast self-hosted retrieval with typo tolerance |
| Frontend | React + Vite | Component-based UI with a rapid development workflow |
| Data | OurAirports + GeoNames | Open, reliable, global airport and place-name data |
| Container | Docker Compose | Straightforward local Typesense setup |

## Project Structure

```text
fly-fairly/
├── backend/
│   ├── main.py
│   ├── search.py
│   ├── download_data.py
│   ├── filter_airports.py
│   ├── enrich_countries.py
│   ├── enrich_regions.py
│   ├── enrich_aliases.py
│   ├── build_region_mapping.py
│   ├── build_city_groups.py
│   ├── index_airports.py
│   ├── docker-compose.yml
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── App.jsx
│       └── components/
│           ├── SearchBox.jsx
│           ├── ResultCard.jsx
│           ├── AirportDetail.jsx
│           ├── TestPanel.jsx
│           └── ThemeToggle.jsx
├── data/
│   ├── airports.csv
│   ├── countries.csv
│   ├── regions.csv
│   ├── alternateNames.txt
│   ├── cities15000.txt
│   └── airports.dat
├── test_search.py
└── README.md
```

## Prerequisites

- Python 3.10+
- Node.js 18+
- Docker and Docker Compose

## Setup and Run

The commands below assume the repository already contains the source files under `data/`, as checked into this project. To download fresh source files instead, run `python backend/download_data.py` once from the repository root before starting the pipeline.

### 1. Enter the backend folder

All pipeline, service, and Docker commands run from `backend/`.

```bash
cd backend/
```

### 2. Create a Python virtual environment

Create an isolated environment for the API and data-processing dependencies.

```bash
python -m venv venv
```

### 3. Activate the virtual environment

On macOS or Linux:

```bash
source venv/bin/activate
```

On Windows:

```powershell
venv\Scripts\activate
```

### 4. Install backend dependencies

```bash
pip3 install -r requirements.txt
```

### 5. Run the offline data pipeline

Run these scripts in this exact order to produce the enriched index documents and lookup maps.

```bash
python filter_airports.py
python enrich_countries.py
python enrich_regions.py
python enrich_aliases.py
python build_region_mapping.py
python build_city_groups.py
```

> `enrich_aliases.py` processes approximately 18 million GeoNames alternate-name rows and typically takes 2 to 3 minutes to complete.

### 6. Start Typesense with Docker Compose

The Compose definition is located in `backend/`, so run this while still in that directory.

```bash
docker-compose up -d
```

### 7. Index airports into Typesense

```bash
python index_airports.py
```

### 8. Start the backend API

```bash
./venv/bin/uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API is now available at `http://localhost:8000`.

### 9. Start the frontend

In a new terminal, from the repository root:

```bash
cd frontend/
npm install
npm run dev
```

### 10. Open the application

Visit [http://localhost:5173](http://localhost:5173) in a browser.

## API Endpoints

| Method | Endpoint | Description | Rate Limit |
| --- | --- | --- | --- |
| `GET` | `/search?q={query}&limit={limit}` | Search airports; `limit` is accepted from 1 to 100 and responses are capped at 10 results | 30/minute |
| `GET` | `/stats` | Return live indexed-collection statistics | 20/minute |
| `GET` | `/health` | Check API and Typesense status | 10/minute |

Every successful endpoint response includes a `rate_limit` block. Rate-limited responses return HTTP `429` with the same block and retry information.

```json
{
  "rate_limit": {
    "limit": 30,
    "remaining": 27,
    "reset_timestamp": 1717000000,
    "retry_after_remaining": 23
  }
}
```

## Running Tests

All 12 assignment edge cases are covered in `test_search.py`. The tests call the live API, so Typesense must be indexed and the backend server must be running before executing them.

From the repository root:

```bash
backend/venv/bin/python -m pytest -s test_search.py -q
```

Expected covered cases:

```text
✓ Hawaii -> HNL, OGG, KOA, LIH
✓ Bali -> DPS first, no BPN in top 3
✓ Florida -> no Chilean airports in top 5
✓ Manama -> BAH
✓ TUL -> Tulsa airport
✓ Brussels -> BRU
✓ Londn -> London airports
✓ LON -> grouped city containing LHR
✓ London -> LHR above YXU and LOZ
✓ 東京 -> HND and NRT
✓ Sao Paulo -> same as São Paulo
✓ BAH -> Bahrain airport
FINAL SCORE: 12/12
```

## Data Pipeline Details

### Input Sources

| File | Rows | Purpose |
| --- | ---: | --- |
| `airports.csv` | 85,476 | Raw global airport data from OurAirports |
| `countries.csv` | 249 | Country-name metadata |
| `regions.csv` | 3,982 | Region and state metadata |
| `cities15000.txt` | 33,742 | GeoNames city population data |
| `alternateNames.txt` | 18,978,835 | Multilingual alternate place names |
| `airports.dat` | 7,698 | Backup airport enrichment input |

### Generated Index Metrics

| Metric | Count |
| --- | ---: |
| Indexed IATA-coded airports | 8,805 |
| Country metadata rows | 249 |
| Region metadata rows | 3,982 |
| Multi-airport city groups | 358 |
| Regions mapped to airports | 2,097 |

Live document, country, region, capital, and alias coverage statistics are also exposed through `GET /stats`.

## Search Logic

Search combines five retrieval strategies in one response:

1. **Exact IATA code match** for queries such as `JFK`, `DEL`, or `LHR`.
2. **Multi-airport city code match** for grouped destinations such as `LON`, `NYC`, or `TYO`.
3. **Exact city or region match** for queries such as `Hawaii` or `Brussels`.
4. **Typesense fuzzy search** for aliases, multilingual text, prefixes, and typos such as `Londn` or `東京`.
5. **Local prefix-backed city matching** to resolve partial or expanded variants such as `deli` → Delhi.

Candidates from the strategies are merged and deduplicated by IATA code, then ranked with direct-match boosts, city-group handling, and the stored airport priority score.

### Priority Scoring

| Signal | Score |
| --- | ---: |
| `large_airport` base score | 90 |
| `medium_airport` base score | 70 |
| `small_airport` base score | 50 |
| City population greater than 1 million | +10 |
| City population greater than 500,000 | +5 |
| Capital city | +5 |
| Maximum stored priority | 100 |

## Edge Cases Handled

| Query | Expected Result | Problem Class |
| --- | --- | --- |
| `Hawaii` | `HNL`, `OGG`, `KOA`, `LIH` | State/region search |
| `Bali` | `DPS` first | Tourism alias |
| `LON` | Group containing `LHR`, `LGW`, `STN`, `LCY`, `LTN` | Multi-airport city |
| `London` | London, UK airports rank first | Disambiguation |
| `Londn` | London airports | Typo tolerance |
| `東京` | `HND`, `NRT` | Japanese-script search |
| `서울` | `ICN`, `GMP` | Korean-script search |
| `Sao Paulo` | Same results as `São Paulo` | Accent insensitive |
| `TUL` | Tulsa airport | IATA reverse lookup |
| `Florida` | Florida airports without Chilean false matches at the top | Region disambiguation |
| `Manama` | `BAH` | City-to-airport search |
| `Brussels` | `BRU` | Alias versus municipality |

## LLM Usage

Built with Claude as an AI pair programmer. Claude was used iteratively, through a series of focused prompts that each addressed one problem at a time rather than through a single large prompt. Key decisions such as the filtering strategy, alias enrichment approach, data-structure optimizations, and search-tier design were made manually after evaluating Claude's suggestions. See the approach memo for the full prompt iteration log, including incorrect suggestions that were identified and corrected.

## License

This project is licensed under the MIT License.
