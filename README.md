cd backend/
python download_data.py
python -m venv venv
source venv/bin/activate
pip3 install -r requirements.txt
python filter_airports.py
python enrich_countries.py
python enrich_regions.py
python enrich_aliases.py
python build_region_mapping.py
