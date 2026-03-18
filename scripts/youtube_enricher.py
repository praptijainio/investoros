"""
YouTube Enricher (no API key needed)
Searches YouTube for each fund's podcast/talk presence,
grabs transcript or description, summarizes with Gemini,
and writes a short summary to master.csv under "YT Summary" column.

Usage:
  python3 run.py enrich-yt              # runs for all funds
  python3 run.py enrich-yt "Blume Ventures"   # single fund
"""
import time
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from scripts.csv_client import get_all_funds, update_fund_field, ensure_columns_exist

import yt_dlp as ytdlp
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound
from google import genai


def search_fund_video(fund_name):
    """Find the most relevant YouTube video for a fund using yt-dlp (no API key needed)."""
    queries = [
        f"{fund_name} venture capital podcast",
        f"{fund_name} VC India investment thesis",
    ]
    skip_words = ["#shorts", "short", "reel", "clip", "trailer"]
    ydl_opts = {"quiet": True, "extract_flat": True, "no_warnings": True}

    for query in queries:
        try:
            with ytdlp.YoutubeDL(ydl_opts) as ydl:
                results = ydl.extract_info(f"ytsearch5:{query}", download=False)
                for entry in results.get("entries", []):
                    title = entry.get("title", "")
                    vid_id = entry.get("id", "")
                    if not vid_id:
                        continue
                    if any(w in title.lower() for w in skip_words):
                        continue
                    return {
                        "id": vid_id,
                        "title": title,
                        "channel": entry.get("channel", ""),
                        "description": entry.get("description", "") or "",
                    }
        except Exception:
            continue
    return None


def get_transcript(video_id, max_chars=3000):
    """Try to get English transcript. Falls back to auto-generated."""
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id, languages=["en", "en-IN"])
        text = " ".join([t["text"] for t in transcript_list])
        return text[:max_chars]
    except (TranscriptsDisabled, NoTranscriptFound):
        return None
    except Exception:
        return None


def summarize_with_gemini(client, fund_name, video_info, transcript):
    """Use Gemini to write a 2-3 line summary of the fund's YouTube presence."""
    if transcript:
        content = f"""
Fund: {fund_name}
Video: {video_info['title']} (by {video_info['channel']})
Transcript excerpt: {transcript}

Write a 2-3 sentence summary of what this fund looks for in investments,
based on what was discussed. Be specific. No fluff. Start with the fund name.
"""
    else:
        content = f"""
Fund: {fund_name}
Video: {video_info['title']} (by {video_info['channel']})
Description: {video_info.get('description', 'N/A')}

Based on the video title and description, write 1-2 sentences about what this fund
likely focuses on. Be specific. Start with the fund name.
"""
    try:
        response = client.models.generate_content(
            model="gemini-flash-latest",
            contents=content
        )
        return response.text.strip()
    except Exception as e:
        return ""


def add_yt_summary_column():
    """Ensure 'YT Summary' and 'YT Video' columns exist in master.csv."""
    funds = get_all_funds()
    if not funds:
        return
    existing = list(funds[0].keys())
    from scripts.csv_client import _write_csv
    changed = False
    for col in ["YT Summary", "YT Video"]:
        if col not in existing:
            existing.append(col)
            for f in funds:
                f[col] = ""
            changed = True
    if changed:
        from scripts.csv_client import MASTER_FILE
        _write_csv(MASTER_FILE, funds, existing)


def run_youtube_enrichment(target_fund=None):
    """
    Main function: for each fund, find YouTube content and write summary to master.csv.
    target_fund: if set, only processes that one fund.
    """
    if not config.GEMINI_API_KEY:
        print("[YT Enricher] No Gemini API key. Add GEMINI_API_KEY to config.py.")
        return

    # Ensure columns exist
    add_yt_summary_column()

    client = genai.Client(api_key=config.GEMINI_API_KEY)
    funds = get_all_funds()

    if target_fund:
        funds = [f for f in funds if f.get("Fund Name", "").strip().lower() == target_fund.strip().lower()]
        if not funds:
            print(f"  Fund not found: {target_fund}")
            return

    print(f"\n[YT Enricher] Processing {len(funds)} funds...")
    done = 0
    skipped = 0

    for i, fund in enumerate(funds):
        fund_name = fund.get("Fund Name", "").strip()
        if not fund_name:
            continue

        # Skip if already has a real summary (not an error placeholder)
        existing = fund.get("YT Summary", "").strip()
        if existing and existing != "No relevant video found":
            skipped += 1
            continue

        print(f"  [{i+1}/{len(funds)}] {fund_name}...")

        video = search_fund_video(fund_name)
        if not video:
            print(f"    No video found.")
            update_fund_field(fund_name, "YT Summary", "No relevant video found")
            continue

        print(f"    Found: {video['title'][:60]}...")
        transcript = get_transcript(video["id"])

        summary = summarize_with_gemini(client, fund_name, video, transcript)
        if summary:
            update_fund_field(fund_name, "YT Summary", summary)
            update_fund_field(fund_name, "YT Video", f"https://youtube.com/watch?v={video['id']}")
            print(f"    Summary written.")
            done += 1
        else:
            print(f"    Could not summarize.")

        # Rate limit: 1 request per second to stay within Gemini free tier
        time.sleep(1)

    print(f"\n[YT Enricher] Done. {done} summaries written, {skipped} already had summaries.")
