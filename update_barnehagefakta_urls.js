#!/usr/bin/env node
const fs = require("fs");
const { execFileSync } = require("child_process");

const CSV_PATH = "barnehage_spots_2026.csv";
const DATA_JS_PATH = "barnehage_data.js";
const SEARCH_API_BASE = "https://sok.udir.no/_api/search/query";

function parseCsv(text) {
  const rows = [];
  let row = [];
  let cell = "";
  let inQuotes = false;

  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    const next = text[i + 1];

    if (ch === '"') {
      if (inQuotes && next === '"') {
        cell += '"';
        i += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }

    if (ch === "," && !inQuotes) {
      row.push(cell);
      cell = "";
      continue;
    }

    if ((ch === "\n" || ch === "\r") && !inQuotes) {
      if (ch === "\r" && next === "\n") i += 1;
      row.push(cell);
      cell = "";
      if (row.length > 1 || row[0] !== "") rows.push(row);
      row = [];
      continue;
    }

    cell += ch;
  }

  if (cell.length || row.length) {
    row.push(cell);
    rows.push(row);
  }
  return rows;
}

function quoteCsv(value) {
  const str = String(value == null ? "" : value);
  if (/[",\n\r]/.test(str)) return `"${str.replace(/"/g, '""')}"`;
  return str;
}

function toCsv(rows) {
  return `${rows.map((r) => r.map(quoteCsv).join(",")).join("\n")}\n`;
}

function normalizeMatchText(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[æøå]/g, (c) => ({ "æ": "ae", "ø": "o", "å": "aa" }[c]))
    .replace(/[^a-z0-9]/g, "");
}

function normalizeAddress(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[æøå]/g, (c) => ({ "æ": "ae", "ø": "o", "å": "aa" }[c]))
    .replace(/[.,]/g, " ")
    .replace(/\s+/g, " ")
    .replace(/(\d)\s+([a-z])/g, "$1$2")
    .trim();
}

function slugify(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[æøå]/g, (c) => ({ "æ": "a", "ø": "o", "å": "a" }[c]))
    .replace(/[^\w\s-]/g, "")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-")
    .trim();
}

function scoreNameMatch(a, b) {
  const x = normalizeMatchText(a);
  const y = normalizeMatchText(b);
  if (!x || !y) return 0;
  if (x === y) return 3;
  if (x.includes(y) || y.includes(x)) return 2;
  return 1;
}

function distanceDeg(latA, lonA, latB, lonB) {
  return Math.sqrt((latA - latB) ** 2 + (lonA - lonB) ** 2);
}

function extractAddressParts(addressRaw) {
  const parts = String(addressRaw || "").split(",");
  const line = normalizeAddress(parts[0] || "");
  const postnrMatch = String(addressRaw || "").match(/\b\d{4}\b/);
  const postnr = postnrMatch ? postnrMatch[0] : "";
  return { line, postnr };
}

function buildQueryUrl(queryText, rowLimit = 10) {
  const params = new URLSearchParams({
    selectproperties: "'Title,BarnehagefaktaOrgnummer,BarnehagefaktaFylkesnavn,BarnehagefaktaKommunenavn,BarnehagefaktaBesoksAdresseAdresselinje,BarnehagefaktaBesoksAdressePoststed,BarnehagefaktaBesoksAdressePostnummer,BarnehagefaktaEierform,BarnehagefaktaAntallBarn,BarnehagefaktaAlder,BarnehagefaktaKoordinatLatDecimal,BarnehagefaktaKoordinatLngDecimal'",
    refiners: "'BarnehagefaktaFylkesnummerOgFylkesnavn,BarnehagefaktaFylkesnummerOgKommunenavn(filter=1000/1/*),BarnehagefaktaEierform,BarnehagefaktaPedagogiskProfil,BarnehagefaktaBarnehageType,BarnehagefaktaAlder,BarnehagefaktaAntallBarnInteger(discretize=manual/26/51/76/101)'",
    properties: "'SourceName:Barnehagefakta,SourceLevel:SPSite'",
    startrow: "0",
    rowlimit: String(rowLimit),
    clienttype: "'AllResultsQuery'",
    culture: "1044",
    trimduplicates: "false",
    sortlist: "'Rank:descending'",
    querytext: `'${queryText}'`,
    QueryTemplatePropertiesUrl: "'spfile://webroot/queryparametertemplate-Barnehagefakta.xml'",
  });
  return `${SEARCH_API_BASE}?${params.toString()}`;
}

function fetchJson(url) {
  let lastErr = null;
  for (let attempt = 1; attempt <= 10; attempt++) {
    try {
      const out = execFileSync("curl", ["-sS", "-H", "accept: application/json;odata=verbose", url], {
        encoding: "utf8",
        maxBuffer: 20 * 1024 * 1024,
      });
      return JSON.parse(out);
    } catch (err) {
      lastErr = err;
      execFileSync("sleep", [attempt < 4 ? "1" : "2"]);
    }
  }
  throw new Error(`Request failed: ${url} (${lastErr && lastErr.message ? lastErr.message : String(lastErr)})`);
}

function cellMap(row) {
  const cells = (row && row.Cells && (row.Cells.results || row.Cells)) || [];
  const map = {};
  for (const c of cells) {
    if (c && c.Key) map[c.Key] = c.Value;
  }
  return map;
}

function parseCandidates(payload) {
  const q = (payload && payload.d && payload.d.query) || payload;
  const rows =
    (q && q.PrimaryQueryResult && q.PrimaryQueryResult.RelevantResults && q.PrimaryQueryResult.RelevantResults.Table && q.PrimaryQueryResult.RelevantResults.Table.Rows && (q.PrimaryQueryResult.RelevantResults.Table.Rows.results || q.PrimaryQueryResult.RelevantResults.Table.Rows)) ||
    [];

  return rows
    .map((r) => cellMap(r))
    .map((m) => ({
      title: String(m.Title || ""),
      orgnr: String(m.BarnehagefaktaOrgnummer || ""),
      line: String(m.BarnehagefaktaBesoksAdresseAdresselinje || ""),
      poststed: String(m.BarnehagefaktaBesoksAdressePoststed || ""),
      postnr: String(m.BarnehagefaktaBesoksAdressePostnummer || ""),
      lat: Number(m.BarnehagefaktaKoordinatLatDecimal),
      lon: Number(m.BarnehagefaktaKoordinatLngDecimal),
    }))
    .filter((c) => c.orgnr && c.title);
}

function coordPass(row, candidate) {
  const lat = Number(row.latitude);
  const lon = Number(row.longitude);
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return true;
  if (!Number.isFinite(candidate.lat) || !Number.isFinite(candidate.lon)) return true;
  return distanceDeg(lat, lon, candidate.lat, candidate.lon) < 0.01;
}

function chooseBestCandidate(row, candidates) {
  if (!candidates.length) return null;
  const { line, postnr } = extractAddressParts(row.address);

  const scored = candidates.map((c) => {
    const cLine = normalizeAddress(c.line);
    const cPostnr = String(c.postnr || "");

    let addressScore = 0;
    if (line && cLine) {
      if (line === cLine && postnr && cPostnr && postnr === cPostnr) addressScore = 3;
      else if (line === cLine) addressScore = 2;
      else if (line.includes(cLine) || cLine.includes(line)) addressScore = 1;
    }

    const nameScore = scoreNameMatch(row.barnehage, c.title);
    return { c, addressScore, nameScore };
  });

  scored.sort((a, b) => {
    if (b.addressScore !== a.addressScore) return b.addressScore - a.addressScore;
    return b.nameScore - a.nameScore;
  });

  for (const s of scored) {
    if (coordPass(row, s.c)) return s.c;
  }
  return null;
}

function buildFaktaUrl(candidate) {
  return `https://barnehagefakta.no/barnehage/${candidate.orgnr}/${slugify(candidate.title)}`;
}

function generateDataJs(rows, header) {
  const objects = rows.map((r) => {
    const obj = {};
    header.forEach((key, i) => {
      const raw = r[i] == null ? "" : String(r[i]);
      if (["spot_litenavdeling", "spot_storavdeling", "latitude", "longitude", "match_score", "name_match_score"].includes(key)) {
        const num = Number(raw);
        obj[key] = Number.isFinite(num) ? num : raw;
      } else {
        obj[key] = raw;
      }
    });
    return obj;
  });
  return `window.BARNEHAGE_ROWS = ${JSON.stringify(objects)};\n`;
}

function buildAddressQueries(row) {
  const raw = String(row.address || "").trim();
  if (!raw) return [];
  const line = String(raw.split(",")[0] || "").trim();
  const postnr = (raw.match(/\b\d{4}\b/) || [""])[0];
  const out = [];
  if (raw) out.push(raw);
  if (line && postnr) out.push(`${line} ${postnr}`);
  if (line) out.push(line);
  return [...new Set(out)];
}

async function main() {
  const csvText = fs.readFileSync(CSV_PATH, "utf8");
  const csvRows = parseCsv(csvText);
  if (!csvRows.length) throw new Error("CSV is empty");

  const header = csvRows[0].slice();
  const body = csvRows.slice(1);
  const h = Object.fromEntries(header.map((k, i) => [k, i]));

  if (!("barnehagefakta_url" in h)) header.push("barnehagefakta_url");

  const index = Object.fromEntries(header.map((k, i) => [k, i]));
  const rows = body.map((r) => {
    const next = header.map((_, i) => (r[i] == null ? "" : r[i]));
    return {
      cells: next,
      barnehage: next[index.barnehage] || "",
      address: next[index.address] || "",
      latitude: next[index.latitude] || "",
      longitude: next[index.longitude] || "",
    };
  });

  const queryCache = new Map();
  let apiCalls = 0;
  let matchedByAddress = 0;
  let matchedByName = 0;
  let unmatched = 0;

  for (let i = 0; i < rows.length; i++) {
    const row = rows[i];
    let candidates = [];
    const addrQueries = buildAddressQueries(row);

    for (const q of addrQueries) {
      const key = `a:${q}`;
      if (!queryCache.has(key)) {
        const url = buildQueryUrl(q, 10);
        queryCache.set(key, parseCandidates(fetchJson(url)));
        apiCalls += 1;
        execFileSync("sleep", ["0.1"]);
      }
      candidates = candidates.concat(queryCache.get(key));
    }

    if (!candidates.length) {
      const nameQuery = String(row.barnehage || "").trim();
      if (nameQuery) {
        const key = `n:${nameQuery}`;
        if (!queryCache.has(key)) {
          const url = buildQueryUrl(nameQuery, 10);
          queryCache.set(key, parseCandidates(fetchJson(url)));
          apiCalls += 1;
          execFileSync("sleep", ["0.1"]);
        }
        candidates = candidates.concat(queryCache.get(key));
      }
    }

    const uniq = [];
    const seen = new Set();
    for (const c of candidates) {
      const k = c.orgnr;
      if (!seen.has(k)) {
        seen.add(k);
        uniq.push(c);
      }
    }

    const best = chooseBestCandidate(row, uniq);
    if (!best) {
      row.cells[index.barnehagefakta_url] = "";
      unmatched += 1;
    } else {
      row.cells[index.barnehagefakta_url] = buildFaktaUrl(best);
      const hasAddressHit = addrQueries.length > 0 && uniq.some((c) => extractAddressParts(row.address).line && normalizeAddress(c.line) === extractAddressParts(row.address).line);
      if (hasAddressHit) matchedByAddress += 1;
      else matchedByName += 1;
    }

    if ((i + 1) % 50 === 0 || i + 1 === rows.length) {
      console.log(`Processed ${i + 1}/${rows.length} (apiCalls=${apiCalls})`);
    }
  }

  const outputRows = [header, ...rows.map((r) => r.cells)];
  fs.writeFileSync(CSV_PATH, toCsv(outputRows), "utf8");
  fs.writeFileSync(DATA_JS_PATH, generateDataJs(rows.map((r) => r.cells), header), "utf8");

  console.log(`Updated ${CSV_PATH} and ${DATA_JS_PATH}`);
  console.log(`Rows: ${rows.length}`);
  console.log(`API calls: ${apiCalls} (cached queries: ${queryCache.size})`);
  console.log(`Matched by address-first flow: ${matchedByAddress}`);
  console.log(`Matched by name fallback: ${matchedByName}`);
  console.log(`Unmatched: ${unmatched}`);
}

main().catch((err) => {
  console.error(err && err.message ? err.message : err);
  process.exit(1);
});
