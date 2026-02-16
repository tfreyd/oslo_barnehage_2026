const fs = require('fs');

function slugify(text) {
  return text
    .toLowerCase()
    .replace(/[æøå]/g, e => ({'æ':'a','ø':'o','å':'a'}[e]))
    .replace(/[^\w\s-]/g, '')
    .replace(/\s+/g, '-')
    .replace(/-+/g, '-')
    .trim();
}

function parseCSV(text) {
  const lines = text.split('\n');
  const result = [];
  let headers = [];
  
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    if (!line) continue;
    
    const cols = [];
    let current = '';
    let inQuotes = false;
    
    for (let j = 0; j < line.length; j++) {
      const char = line[j];
      if (char === '"') {
        inQuotes = !inQuotes;
      } else if (char === ',' && !inQuotes) {
        cols.push(current.trim());
        current = '';
      } else {
        current += char;
      }
    }
    cols.push(current.trim());
    result.push(cols);
  }
  return result;
}

// Read CSV
const csv = fs.readFileSync('barnehage_spots_2026.csv', 'utf8');
const rows = parseCSV(csv);
const header = rows[0];
const barnehageIdx = header.indexOf('barnehage');

// Add new column
header.push('barnehagefakta_url');

// Get unique barnehages
const barnehager = new Set();
for (let i = 1; i < rows.length; i++) {
  const name = rows[i][barnehageIdx];
  if (name) barnehager.add(name);
}

// Generate URLs
const urlMap = {};
for (const name of barnehager) {
  const slug = slugify(name);
  urlMap[name] = `https://barnehagefakta.no/barnehage/${slug}`;
}

// Write new CSV
const newRows = [header];
for (let i = 1; i < rows.length; i++) {
  const row = rows[i];
  const name = row[barnehageIdx];
  row.push(urlMap[name] || '');
  newRows.push(row);
}

const newCSV = newRows.map(row => row.join(',')).join('\n');
fs.writeFileSync('barnehage_spots_2026_with_fakta.csv', newCSV);

console.log(`Processed ${rows.length - 1} rows`);
console.log(`\nSample URLs:`);
Object.entries(urlMap).slice(0, 5).forEach(([k,v]) => console.log(`${k} -> ${v}`));

// Check a few URLs
console.log(`\nVerifying sample URLs...`);
const sampleUrls = Object.values(urlMap).slice(0, 3);
console.log(sampleUrls);
