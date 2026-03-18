# InvestorOS — Progress Log
**Last updated:** March 18, 2026

---

## Status: Fully unblocked. No Google Cloud credentials needed.

---

## What Changed (March 18, 2026)
- Removed Google Sheets API dependency entirely
- Replaced `sheets_client.py` with `csv_client.py` (reads/writes local CSV files)
- All data now lives in `data/` folder as CSV files
- No credit card, no Google Cloud, no service account required

---

## What's Built
- `run.py` — main entry point
- `config.py` — API keys and CSV file paths
- `scripts/csv_client.py` — local CSV read/write (no credentials needed)
- `scripts/rss_fetcher.py` — Inc42, YourStory, TechCrunch India news enrichment
- `scripts/youtube_fetcher.py` — YouTube enrichment (skips gracefully if no key)
- `scripts/pitch_trainer.py` — Gemini-powered investor persona simulator
- All Python dependencies installed ✓

---

## Next Steps (in order)

### Step 1 — Export your fund database (5 minutes)
1. Open your Google Sheet in the browser
2. File → Download → CSV
3. Rename file to `master.csv`
4. Move to `~/Desktop/InvestorOS/data/master.csv`

### Step 2 — Run setup
```bash
cd ~/Desktop/InvestorOS
python3 run.py setup
```

### Step 3 — Get Gemini API key (for pitch trainer)
- Go to aistudio.google.com → Get API Key (free, Google login only, no card)
- Paste in `config.py` as `GEMINI_API_KEY`

### Step 4 — Run enrichment
```bash
python3 run.py enrich
```

### Step 5 — Test pitch trainer
```bash
python3 run.py pitch
```

---

## Google Sheet
- URL: https://docs.google.com/spreadsheets/d/1NpMthdcx_f0_5z4v-iZJP381UBpoKjCgXCXVkxulZeI/edit
- Still your source of truth — keep editing it in the browser
- Re-export as CSV whenever you add/edit funds
