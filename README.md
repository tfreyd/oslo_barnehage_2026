# Oslo Barnehage 2026

Interactive local app to explore available kindergarten spots in Oslo for 2026.

## What is in this repo

- `barnehage_filter_app.html`: main filter app (map + searchable result cards).
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

From the repository root:

```bash
python3 data/extract_barnehage_data.py
```

This regenerates data outputs used by the app.
