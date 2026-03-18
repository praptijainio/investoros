"""
YouTube Fetcher — finds fund/partner YouTube channels and recent videos.
Uses YouTube Data API v3 (free, generous quota).
"""
from googleapiclient.discovery import build
from datetime import datetime, timedelta
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from scripts.csv_client import get_fund_names, write_activity_rows, update_fund_field

def get_youtube_client():
    return build("youtube", "v3", developerKey=config.YOUTUBE_API_KEY)

def search_fund_channel(youtube, fund_name):
    """Search for a fund's YouTube channel."""
    try:
        response = youtube.search().list(
            q=f"{fund_name} venture capital India",
            type="channel",
            part="snippet",
            maxResults=1
        ).execute()
        items = response.get("items", [])
        if items:
            channel = items[0]
            return {
                "channel_id": channel["id"]["channelId"],
                "channel_title": channel["snippet"]["title"],
                "channel_url": f"https://www.youtube.com/channel/{channel['id']['channelId']}"
            }
    except Exception as e:
        print(f"  YouTube search error for {fund_name}: {e}")
    return None

def get_recent_videos(youtube, channel_id, days=60):
    """Get recent videos from a channel."""
    cutoff = (datetime.utcnow() - timedelta(days=days)).strftime('%Y-%m-%dT%H:%M:%SZ')
    try:
        response = youtube.search().list(
            channelId=channel_id,
            type="video",
            part="snippet",
            order="date",
            publishedAfter=cutoff,
            maxResults=5
        ).execute()
        videos = []
        for item in response.get("items", []):
            snippet = item["snippet"]
            videos.append({
                "title": snippet["title"],
                "published": snippet["publishedAt"][:10],
                "url": f"https://www.youtube.com/watch?v={item['id']['videoId']}",
                "description": snippet.get("description", "")[:200]
            })
        return videos
    except Exception as e:
        print(f"  Error fetching videos for channel {channel_id}: {e}")
        return []

def run_youtube_enrichment(funds_to_check=None):
    """
    For each fund, find their YouTube channel and recent videos.
    Updates the sheet with channel URL + writes activity rows.
    """
    if not config.YOUTUBE_API_KEY:
        print("[YouTube] No API key set in config.py. Skipping.")
        return

    print("\n[YouTube Fetcher] Starting...")
    youtube = get_youtube_client()
    fund_names = funds_to_check or get_fund_names()
    print(f"  Checking {len(fund_names)} funds...")

    new_rows = []

    for fund in fund_names:
        print(f"  Searching: {fund}")
        channel = search_fund_channel(youtube, fund)
        if not channel:
            continue

        # Update channel URL in master sheet
        update_fund_field(fund, "YouTube Channel", channel["channel_url"])

        # Get recent videos
        videos = get_recent_videos(youtube, channel["channel_id"])
        for video in videos:
            new_rows.append([
                video["published"],
                fund,
                "",
                "YouTube",
                video["title"],
                video["url"],
                video["description"]
            ])
        if videos:
            print(f"    Found {len(videos)} recent videos for {fund}")

    write_activity_rows(new_rows)
    print(f"[YouTube Fetcher] Done. {len(new_rows)} video entries added.")

if __name__ == "__main__":
    run_youtube_enrichment()
