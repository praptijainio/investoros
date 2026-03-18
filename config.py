# InvestorOS Configuration
import os

# Local CSV file paths (all inside the data/ folder)
MASTER_CSV   = "data/master.csv"
PARTNERS_CSV = "data/partners.csv"
ACTIVITY_CSV = "data/activity_feed.csv"

# YouTube Data API key (optional)
YOUTUBE_API_KEY = ""

# Gemini API key — reads from env/Streamlit secrets, falls back to local value
try:
    import streamlit as st
    GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", ""))
except Exception:
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")

# RSS feeds to monitor
RSS_FEEDS = [
    "https://inc42.com/feed/",
    "https://inc42.com/buzz/feed/",
    "https://yourstory.com/feed",
    "https://techcrunch.com/tag/india/feed/",
]

# How many days back to pull news
NEWS_LOOKBACK_DAYS = 30
