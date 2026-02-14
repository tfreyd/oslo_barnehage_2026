# Oslo Barnehage 2026

Interactive local app to explore available kindergarten spots in Oslo for 2026.

## What is in this repo

- `barnehage_filter_app.html`: main filter app (map + searchable result cards).
- `barnehage_app.js`: application JavaScript code.
- `barnehage_data.js`: JS dataset loaded by the app.
- `barnehage_spots_2026.csv`: extracted dataset in CSV format.
- `barnehage_spots_2026_map.html`: map-focused HTML export.
- `data/`: source PDFs and extraction script.
  - `data/extract_barnehage_data.py`

## Run locally

Open the app directly:

- `barnehage_filter_app.html`

Or serve the folder with a simple local server (recommended):

```bash
python3 -m http.server 8000
```

Then open:

- `http://localhost:8000/barnehage_filter_app.html`

## Update data

### Setup (first time only)

The data extraction script requires API credentials. Copy the example environment file and fill in your API keys:

```bash
cp .env.example .env
```

Edit `.env` and add your Algolia API credentials:
```
ALGOLIA_APP_ID=your_app_id_here
ALGOLIA_API_KEY=your_api_key_here
ALGOLIA_INDEX=prod_oslo_kommune_no
```

**Note:** These are read-only public API keys for Oslo Kommune's public data. Contact Oslo Kommune if you need access.

### Running the extraction

From the repository root:

```bash
python3 data/extract_barnehage_data.py
```

This regenerates data outputs used by the app.
