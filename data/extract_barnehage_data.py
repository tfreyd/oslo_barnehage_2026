#!/usr/bin/env python3
import csv
import html
import io
import json
import re
import subprocess
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from difflib import SequenceMatcher
from pathlib import Path
from urllib import parse, request

PDF_PATTERN = "Forventet-ledig-kapasitet-2026-*.pdf"
CSV_OUTPUT = Path("barnehage_spots_2026.csv")
MAP_OUTPUT = Path("barnehage_spots_2026_map.html")

BYDEL_NAME_MAP = {
    "Alna": "Alna",
    "Bjerke": "Bjerke",
    "Frogner": "Frogner",
    "Gamle-Oslo": "Gamle Oslo",
    "Grorud": "Grorud",
    "Grunerlokka": "Grünerløkka",
    "Nordre-Aker": "Nordre Aker",
    "Nordstrand": "Nordstrand",
    "Ostensjo": "Østensjø",
    "Sagene": "Sagene",
    "Sondre-Nordstrand": "Søndre Nordstrand",
    "St.-Hanshaugen": "St. Hanshaugen",
    "Stovner": "Stovner",
    "Ullern": "Ullern",
    "Vestre-Aker": "Vestre Aker",
}

BYDEL_COLORS = {
    "Alna": "#1f77b4",
    "Bjerke": "#ff7f0e",
    "Frogner": "#2ca02c",
    "Gamle Oslo": "#d62728",
    "Grorud": "#9467bd",
    "Grünerløkka": "#8c564b",
    "Nordre Aker": "#e377c2",
    "Nordstrand": "#7f7f7f",
    "Østensjø": "#bcbd22",
    "Sagene": "#17becf",
    "Søndre Nordstrand": "#1b9e77",
    "St. Hanshaugen": "#d95f02",
    "Stovner": "#7570b3",
    "Ullern": "#e7298a",
    "Vestre Aker": "#66a61e",
}

BYDEL_TAG_MAP = {
    "Alna": 888,
    "Bjerke": 893,
    "Frogner": 897,
    "Gamle Oslo": 901,
    "Grorud": 905,
    "Grünerløkka": 911,
    "Nordre Aker": 915,
    "Nordstrand": 919,
    "Sagene": 923,
    "St. Hanshaugen": 927,
    "Stovner": 931,
    "Søndre Nordstrand": 935,
    "Ullern": 939,
    "Vestre Aker": 943,
    "Østensjø": 948,
}

# NOTE: These are read-only public API keys for Oslo Kommune's public data
# They are intended for client-side use and are not sensitive credentials
ALGOLIA_APP_ID = "NJ4QX1MFJ2"
ALGOLIA_API_KEY = "4ce897d2ad7bca6a9fbcac2888b35801"
ALGOLIA_INDEX = "prod_oslo_kommune_no"


def normalize_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def parse_pdf_rows(pdf_path: Path):
    tsv = subprocess.check_output(["pdftotext", "-tsv", str(pdf_path), "-"], text=True)
    parsed = list(csv.DictReader(io.StringIO(tsv), delimiter="\t"))

    words = []
    for row in parsed:
        if row["level"] != "5":
            continue
        txt = row["text"]
        if not txt or txt == "###PAGE###":
            continue
        words.append(
            {
                "page": int(row["page_num"]),
                "left": float(row["left"]),
                "top": float(row["top"]),
                "text": txt,
            }
        )

    records = []
    for page in sorted({w["page"] for w in words}):
        page_words = [w for w in words if w["page"] == page]

        by_top = {}
        for w in page_words:
            by_top.setdefault(round(w["top"], 2), []).append(w)

        anchors = []
        for y, ws in by_top.items():
            small = [w for w in ws if 430 <= w["left"] < 560 and re.fullmatch(r"\d+", w["text"])]
            big = [w for w in ws if 640 <= w["left"] < 760 and re.fullmatch(r"\d+", w["text"])]
            if small and big:
                anchors.append((y, int(max(small, key=lambda x: x["left"])["text"]), int(max(big, key=lambda x: x["left"])["text"])))

        anchors.sort()
        name_tokens = [w for w in page_words if 150 <= w["left"] < 430]

        for i, (y, small, big) in enumerate(anchors):
            lower_mid = (anchors[i - 1][0] + y) / 2 if i > 0 else float("-inf")
            upper_mid = (y + anchors[i + 1][0]) / 2 if i + 1 < len(anchors) else float("inf")

            lower = max(lower_mid, y - 12.2)
            upper = min(upper_mid, y + 12.2)

            tokens = [w for w in name_tokens if lower < w["top"] <= upper]
            tokens.sort(key=lambda t: (t["top"], t["left"]))
            name = normalize_spaces(" ".join(t["text"] for t in tokens))

            if name:
                records.append({"barnehage": name, "small": small, "big": big})

    return records


def strip_diacritics_keep_norwegian(s: str) -> str:
    return (
        s.replace("æ", "ae")
        .replace("ø", "o")
        .replace("å", "a")
        .replace("Æ", "ae")
        .replace("Ø", "o")
        .replace("Å", "a")
    )


def norm_name(s: str) -> str:
    s = s.lower()
    s = s.replace("&", " og ")
    s = strip_diacritics_keep_norwegian(s)
    s = s.replace("barnehave", "barnehage")
    s = re.sub(r"\bbhg\b", "barnehage", s)
    s = re.sub(r"\bbh\b", "barnehage", s)
    s = re.sub(r"[^a-z0-9\s-]", " ", s)
    s = s.replace("-", " ")
    s = normalize_spaces(s)
    return s


def norm_name_loose(s: str) -> str:
    s = norm_name(s)
    tokens = [
        t
        for t in s.split()
        if t not in {"barnehage", "private", "privat", "as", "sa", "ba", "oslo", "i"}
    ]
    return " ".join(tokens)


def bydel_name_from_pdf(pdf_path: Path) -> str:
    stem = pdf_path.stem.replace("Forventet-ledig-kapasitet-2026-", "")
    return BYDEL_NAME_MAP.get(stem, stem.replace("-", " "))


def algolia_query(params: str):
    url = f"https://{ALGOLIA_APP_ID}-dsn.algolia.net/1/indexes/{ALGOLIA_INDEX}/query"
    payload = json.dumps({"params": params}).encode("utf-8")
    req = request.Request(
        url,
        data=payload,
        headers={
            "x-algolia-api-key": ALGOLIA_API_KEY,
            "x-algolia-application-id": ALGOLIA_APP_ID,
            "content-type": "application/json",
        },
        method="POST",
    )
    with request.urlopen(req, timeout=60) as resp:
        data = json.load(resp)
    return data


def fetch_algolia_kindergartens():
    params = "query=&hitsPerPage=1000&filters=tags:502&attributesToRetrieve=name,meta,card_data,tags"
    return algolia_query(params)["hits"]


def build_candidate_index(hits):
    candidates = []
    for hit in hits:
        meta = hit.get("meta") or {}
        url = meta.get("url")
        name = hit.get("name", "")
        if not url or "/barnehage/finn-barnehage-i-oslo/" not in url:
            continue
        candidates.append(
            {
                "name": name,
                "url": url,
                "address": (hit.get("card_data") or {}).get("address", ""),
                "tags": set(hit.get("tags") or []),
                "norm": norm_name(name),
                "norm_loose": norm_name_loose(name),
            }
        )

    exact = {}
    loose = {}
    for c in candidates:
        exact.setdefault(c["norm"], []).append(c)
        loose.setdefault(c["norm_loose"], []).append(c)
    return candidates, exact, loose


def score_match(a: str, b: str) -> float:
    seq = SequenceMatcher(None, a, b).ratio()
    a_tokens = set(a.split())
    b_tokens = set(b.split())
    overlap = len(a_tokens & b_tokens) / max(1, len(a_tokens | b_tokens))
    return 0.65 * seq + 0.35 * overlap


def choose_best(name: str, candidates):
    n = norm_name(name)
    best = None
    best_score = -1.0
    for c in candidates:
        s = score_match(n, c["norm"])
        if s > best_score:
            best_score = s
            best = c
    return best, best_score


def filter_by_bydel(candidates, bydel: str):
    tag = BYDEL_TAG_MAP.get(bydel)
    if not tag:
        return candidates
    scoped = [c for c in candidates if tag in c["tags"]]
    return scoped if scoped else candidates


def match_barnehage(name: str, bydel: str, exact_idx, loose_idx, candidates):
    scoped_candidates = filter_by_bydel(candidates, bydel)
    n = norm_name(name)
    n_loose = norm_name_loose(name)

    if n in exact_idx:
        group = filter_by_bydel(exact_idx[n], bydel)
        if len(group) == 1:
            return group[0], 1.0
        best, sc = choose_best(name, group)
        return best, sc

    if n_loose and n_loose in loose_idx:
        group = filter_by_bydel(loose_idx[n_loose], bydel)
        if len(group) == 1:
            return group[0], 0.97
        best, sc = choose_best(name, group)
        return best, sc

    best, sc = choose_best(name, scoped_candidates)
    return best, sc


def search_kindergarten(name: str, bydel: str):
    query = parse.quote(name)
    tag = BYDEL_TAG_MAP.get(bydel)
    filters = "tags:502"
    if tag:
        filters += f"%20AND%20tags:{tag}"
    params = (
        f"query={query}&hitsPerPage=20&filters={filters}"
        "&attributesToRetrieve=name,meta,card_data,tags"
    )
    hits = algolia_query(params).get("hits", [])
    if not hits:
        return None, 0.0

    candidates, exact_idx, loose_idx = build_candidate_index(hits)
    best, score = match_barnehage(name, bydel, exact_idx, loose_idx, candidates)
    return best, score


def parse_besoksadresse(html: str):
    m = re.search(
        r"Besøksadresse</dt>\s*<dd[^>]*>(.*?)</dd>",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not m:
        return ""
    val = re.sub(r"<br\s*/?>", ", ", m.group(1), flags=re.IGNORECASE)
    val = re.sub(r"<[^>]+>", " ", val)
    return normalize_spaces(val)


def fetch_page_data(url: str):
    html = ""
    for _ in range(3):
        try:
            with request.urlopen(url, timeout=30) as resp:
                html = resp.read().decode("utf-8", errors="ignore")
            break
        except Exception:
            html = ""

    if not html:
        return None, None, ""

    m = re.search(r'&quot;longitude&quot;:&quot;([0-9.\-]+)&quot;,&quot;latitude&quot;:&quot;([0-9.\-]+)&quot;', html)
    lat, lon = None, None
    if m:
        lat, lon = float(m.group(2)), float(m.group(1))

    address = parse_besoksadresse(html)
    return lat, lon, address


def build_map_html(rows):
    pts = [r for r in rows if r["latitude"] is not None and r["longitude"] is not None]
    if not pts:
        center_lat, center_lon = 59.91, 10.75
    else:
        center_lat = sum(r["latitude"] for r in pts) / len(pts)
        center_lon = sum(r["longitude"] for r in pts) / len(pts)

    legend_items = "".join(
        f'<div><span style="display:inline-block;width:12px;height:12px;background:{color};margin-right:8px;border-radius:50%;"></span>{bydel}</div>'
        for bydel, color in BYDEL_COLORS.items()
    )

    points_js = []
    for r in pts:
        name = json.dumps(r["barnehage"], ensure_ascii=False)
        bydel = json.dumps(r["bydel"], ensure_ascii=False)
        url = json.dumps(r["barnehage_url"] or "", ensure_ascii=False)
        popup = (
            f"<b>{html.escape(r['barnehage'])}</b><br>"
            f"Bydel: {html.escape(r['bydel'])}<br>"
            f"Liten avdeling: {html.escape(str(r['spot_litenavdeling']))}<br>"
            f"Stor avdeling: {html.escape(str(r['spot_storavdeling']))}<br>"
        )
        if r["barnehage_url"]:
            popup += f"<a href='{html.escape(r['barnehage_url'])}' target='_blank' rel='noopener'>Barnehage-side</a>"
        popup_js = json.dumps(popup, ensure_ascii=False)
        color = BYDEL_COLORS.get(r["bydel"], "#333333")
        points_js.append(
            f"L.circleMarker([{r['latitude']},{r['longitude']}],{{radius:6,color:'{color}',fillColor:'{color}',fillOpacity:0.85,weight:1}}).addTo(map).bindPopup({popup_js});"
        )

    html = f"""<!DOCTYPE html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />
  <title>Oslo barnehage spots 2026</title>
  <link rel=\"stylesheet\" href=\"https://unpkg.com/leaflet@1.9.4/dist/leaflet.css\" integrity=\"sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=\" crossorigin=\"\"/>
  <style>
    html, body, #map {{ height: 100%; margin: 0; font-family: Arial, sans-serif; }}
    .legend {{ position: absolute; z-index: 1000; right: 12px; top: 12px; background: rgba(255,255,255,0.95); padding: 10px 12px; border-radius: 6px; box-shadow: 0 1px 8px rgba(0,0,0,0.2); max-height: 70vh; overflow:auto; }}
    .legend h4 {{ margin: 0 0 8px 0; font-size: 14px; }}
    .legend div {{ font-size: 12px; margin-bottom: 4px; }}
  </style>
</head>
<body>
  <div id=\"map\"></div>
  <div class=\"legend\"><h4>Bydel</h4>{legend_items}</div>
  <script src=\"https://unpkg.com/leaflet@1.9.4/dist/leaflet.js\" integrity=\"sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=\" crossorigin=\"\"></script>
  <script>
    const map = L.map('map').setView([{center_lat:.6f}, {center_lon:.6f}], 11);
    L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
      maxZoom: 19,
      attribution: '&copy; OpenStreetMap contributors'
    }}).addTo(map);
    {''.join(points_js)}
  </script>
</body>
</html>
"""
    MAP_OUTPUT.write_text(html, encoding="utf-8")


def main():
    pdf_files = sorted(Path(".").glob(PDF_PATTERN))
    if not pdf_files:
        raise SystemExit("No PDF files found.")

    extracted = []
    for pdf in pdf_files:
        bydel = bydel_name_from_pdf(pdf)
        for rec in parse_pdf_rows(pdf):
            extracted.append(
                {
                    "bydel": bydel,
                    "barnehage": rec["barnehage"],
                    "spot_litenavdeling": rec["small"],
                    "spot_storavdeling": rec["big"],
                }
            )

    hits = fetch_algolia_kindergartens()
    candidates, exact_idx, loose_idx = build_candidate_index(hits)

    for row in extracted:
        match, score = match_barnehage(row["barnehage"], row["bydel"], exact_idx, loose_idx, candidates)
        if match and score >= 0.68:
            row["barnehage_url"] = match["url"]
            row["address"] = match["address"]
            row["match_score"] = round(score, 4)
        else:
            row["barnehage_url"] = ""
            row["address"] = ""
            row["match_score"] = round(score if match else 0.0, 4)

    missing_url_rows = [r for r in extracted if not r["barnehage_url"]]
    if missing_url_rows:
        total_missing = len(missing_url_rows)
        for idx, row in enumerate(missing_url_rows, start=1):
            print(
                f"\rURL search fallback [{idx}/{total_missing}] {row['bydel']} | {row['barnehage'][:50]}",
                end="",
                flush=True,
            )
            match, score = search_kindergarten(row["barnehage"], row["bydel"])
            if match and score >= 0.5:
                row["barnehage_url"] = match["url"]
                row["address"] = match["address"]
                row["match_score"] = round(score, 4)
        print()

    unique_urls = sorted({r["barnehage_url"] for r in extracted if r["barnehage_url"]})
    page_data = {}
    total_urls = len(unique_urls)

    def print_progress(done: int, total: int):
        width = 40
        filled = int(width * done / max(1, total))
        bar = "#" * filled + "-" * (width - filled)
        print(f"\rCoordinate scraping [{bar}] {done}/{total}", end="", flush=True)

    print_progress(0, total_urls)
    with ThreadPoolExecutor(max_workers=16) as ex:
        futures = {ex.submit(fetch_page_data, u): u for u in unique_urls}
        completed = 0
        for fut in as_completed(futures):
            u = futures[fut]
            lat, lon, besoksadresse = fut.result()
            page_data[u] = (lat, lon, besoksadresse)
            completed += 1
            print_progress(completed, total_urls)
    print()

    for row in extracted:
        lat, lon, besoksadresse = page_data.get(row["barnehage_url"], (None, None, ""))
        if besoksadresse:
            row["address"] = besoksadresse
        row["latitude"] = lat
        row["longitude"] = lon

    extracted.sort(key=lambda r: (r["bydel"], r["barnehage"].lower()))

    fields = [
        "bydel",
        "barnehage",
        "spot_litenavdeling",
        "spot_storavdeling",
        "barnehage_url",
        "address",
        "latitude",
        "longitude",
        "match_score",
    ]
    with CSV_OUTPUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(extracted)

    build_map_html(extracted)

    total = len(extracted)
    matched = sum(1 for r in extracted if r["barnehage_url"])
    geocoded = sum(1 for r in extracted if r["latitude"] is not None and r["longitude"] is not None)
    print(f"Rows: {total}")
    print(f"Matched URLs: {matched}")
    print(f"Rows with coordinates: {geocoded}")
    print(f"CSV: {CSV_OUTPUT}")
    print(f"Map: {MAP_OUTPUT}")


if __name__ == "__main__":
    main()
