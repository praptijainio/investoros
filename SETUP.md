# InvestorOS — Setup Guide

## What This Does
- Pulls recent news about your 262 funds from Inc42, YourStory, TechCrunch India automatically
- Lets founders (and you) practice pitching to realistic investor personas
- All data stored locally as CSV files — no Google Cloud, no credit card, no API credentials

---

## Step 1 — Export your Google Sheet as CSV

1. Open your Google Sheet in the browser
2. Click **File → Download → Comma Separated Values (.csv)**
3. Rename the downloaded file to exactly: `master.csv`
4. Move it to: `~/Desktop/InvestorOS/data/master.csv`

That's it. The sheet stays in your browser as usual. Scripts will read from this local copy.

---

## Step 2 — Run setup (one-time)

Open Terminal and run:
```bash
cd ~/Desktop/InvestorOS
python3 run.py setup
```

This:
- Adds new enrichment columns to `data/master.csv` (Website, YouTube Channel, etc.)
- Creates `data/partners.csv` (blank, ready for partner-level data)
- Creates `data/activity_feed.csv` (blank, will fill up as you enrich)

---

## Step 3 — Get Gemini API Key (for pitch trainer)

Required only if you want to use the pitch trainer.

1. Go to https://aistudio.google.com
2. Sign in with your Google account
3. Click **Get API Key → Create API Key**
4. Copy the key
5. Open `config.py` and paste it as the value for `GEMINI_API_KEY`

No credit card needed. This is Google AI Studio's free tier.

---

## Step 4 — Run enrichment (pulls latest news)

```bash
python3 run.py enrich
```

This fetches recent articles from Inc42, YourStory, TechCrunch India and matches them
against your fund names. Results are saved to `data/activity_feed.csv`.

Run this weekly. Takes 1-2 minutes.

---

## Daily / Weekly Usage

**Pull latest news:**
```bash
python3 run.py enrich
```

**Practice a pitch (archetype mode):**
```bash
python3 run.py pitch
```
Choose from: Pequoia (large fund), Zelevation (mid-tier), Microfund (micro VC)

**Practice with a specific fund:**
```bash
python3 run.py pitch fund "Blume Ventures"
```

**See all funds available for simulation:**
```bash
python3 run.py list-funds
```

---

## Folder Structure

```
InvestorOS/
├── run.py                  ← main entry point
├── config.py               ← API keys and settings
├── requirements.txt        ← Python dependencies
├── SETUP.md                ← this file
├── scripts/
│   ├── csv_client.py       ← local CSV read/write (no Google API needed)
│   ├── rss_fetcher.py      ← Inc42/YourStory/TechCrunch news
│   ├── youtube_fetcher.py  ← YouTube enrichment (optional, needs API key)
│   └── pitch_trainer.py    ← Gemini-powered investor persona simulator
└── data/
    ├── master.csv          ← YOUR FUND DATABASE (you export this from Sheets)
    ├── partners.csv        ← partner contacts (auto-created)
    └── activity_feed.csv   ← enrichment log (auto-created)
```

---

## Refreshing the Fund Database

When you add/edit funds in Google Sheets, just re-export as CSV and overwrite `data/master.csv`.
Run `python3 run.py setup` again — it skips columns that already exist.
