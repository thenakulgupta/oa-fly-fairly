#!/bin/sh
set -eu

python - <<'PY'
import os
import time
from urllib.error import URLError
from urllib.request import urlopen

host = os.environ.get("TYPESENSE_HOST", "typesense")
port = os.environ.get("TYPESENSE_PORT", "8108")
health_url = f"http://{host}:{port}/health"

for attempt in range(60):
    try:
        with urlopen(health_url, timeout=2):
            break
    except (URLError, TimeoutError, OSError):
        print(f"Waiting for Typesense at {health_url} ({attempt + 1}/60)")
        time.sleep(1)
else:
    raise RuntimeError(f"Typesense did not become ready at {health_url}")
PY

python backend/download_data.py

python filter_airports.py
python enrich_countries.py
python enrich_regions.py
python enrich_aliases.py
python build_region_mapping.py
python build_city_groups.py
python backend/index_airports.py

exec uvicorn backend.main:app --host 0.0.0.0 --port "${PORT:-3004}"