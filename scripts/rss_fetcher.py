"""
RSS Fetcher — pulls recent news from Inc42, YourStory, TechCrunch India.
Matches articles against fund names and writes to Activity Feed.
"""
import feedparser
import re
from datetime import datetime, timedelta
from dateutil import parser as dateparser
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from scripts.csv_client import get_fund_names, write_activity_rows

def fetch_feed(url):
    """Fetches and parses a single RSS feed."""
    try:
        feed = feedparser.parse(url)
        return feed.entries
    except Exception as e:
        print(f"  Error fetching {url}: {e}")
        return []

def is_recent(entry, days=None):
    """Check if entry is within the lookback window."""
    days = days or config.NEWS_LOOKBACK_DAYS
    cutoff = datetime.now() - timedelta(days=days)
    try:
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            pub = datetime(*entry.published_parsed[:6])
            return pub >= cutoff
    except Exception:
        pass
    return True  # include if can't parse date

def match_funds(text, fund_names):
    """Returns list of fund names mentioned in the text."""
    text_lower = text.lower()
    matched = []
    for fund in fund_names:
        # match fund name or common short versions
        search_name = fund.lower().strip()
        # strip common suffixes for broader matching
        short_name = re.sub(r'\s*(ventures?|capital|partners?|fund|vc|india|investments?)\s*$',
                           '', search_name, flags=re.IGNORECASE).strip()
        if short_name and (short_name in text_lower or search_name in text_lower):
            matched.append(fund)
    return matched

def run_rss_enrichment():
    """
    Main function: fetch all RSS feeds, match against fund names,
    write new activity rows to the sheet.
    """
    print("\n[RSS Fetcher] Starting...")
    fund_names = get_fund_names()
    print(f"  Loaded {len(fund_names)} funds to match against.")

    new_rows = []

    for feed_url in config.RSS_FEEDS:
        source = feed_url.split('/')[2].replace('www.', '')
        print(f"  Fetching: {source}...")
        entries = fetch_feed(feed_url)
        print(f"    Found {len(entries)} entries.")

        for entry in entries:
            if not is_recent(entry):
                continue

            title = getattr(entry, 'title', '')
            summary = getattr(entry, 'summary', '')
            link = getattr(entry, 'link', '')
            full_text = f"{title} {summary}"

            # Try to get published date
            try:
                pub_date = dateparser.parse(entry.get('published', '')).strftime('%Y-%m-%d')
            except Exception:
                pub_date = datetime.now().strftime('%Y-%m-%d')

            matched = match_funds(full_text, fund_names)
            for fund in matched:
                # Clean summary to first 200 chars
                clean_summary = re.sub(r'<[^>]+>', '', summary)[:200].strip()
                new_rows.append([
                    pub_date,
                    fund,
                    "",  # Partner - blank for now (RSS doesn't always name the partner)
                    source,
                    title,
                    link,
                    clean_summary
                ])

    # Deduplicate by URL + fund
    seen = set()
    deduped = []
    for row in new_rows:
        key = (row[1], row[4])  # fund + headline
        if key not in seen:
            seen.add(key)
            deduped.append(row)

    print(f"  Matched {len(deduped)} relevant articles.")
    write_activity_rows(deduped)
    print("[RSS Fetcher] Done.")
    return deduped

if __name__ == "__main__":
    run_rss_enrichment()
