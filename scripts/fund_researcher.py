"""
Fund Researcher — builds a rich context profile for a fund using:
  - Fund website scraping
  - DuckDuckGo search (no API key) for recent news, investments, founder opinions
  - YouTube summary (already in master.csv)
  - Gemini synthesis into a structured profile

Profiles saved to: data/fund_profiles/{slug}.json

Usage:
  python3 run.py research "Blume Ventures"       # one fund
  python3 run.py research-all                    # all 20 prominent funds
"""
import os, sys, json, re, time
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
import requests
from bs4 import BeautifulSoup
from google import genai

PROFILES_DIR = "data/fund_profiles"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}


# ── Utilities ─────────────────────────────────────────────────────────────────

def fund_slug(name):
    return re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')

def profile_path(name):
    os.makedirs(PROFILES_DIR, exist_ok=True)
    return os.path.join(PROFILES_DIR, f"{fund_slug(name)}.json")

def load_profile(name):
    path = profile_path(name)
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None

def save_profile(name, profile):
    with open(profile_path(name), 'w') as f:
        json.dump(profile, f, indent=2)


# ── Web scraping ──────────────────────────────────────────────────────────────

def scrape_url(url, max_chars=4000):
    """Scrape plain text from a URL. Returns None on failure."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=12)
        if r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, 'html.parser')
        # Remove nav, footer, script, style
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True)
        # Collapse whitespace
        text = re.sub(r'\s+', ' ', text)
        return text[:max_chars]
    except Exception:
        return None


def ddg_search(query, num=5):
    """DuckDuckGo HTML search — no API key needed."""
    try:
        url = f"https://html.duckduckgo.com/html/?q={requests.utils.quote(query)}"
        r = requests.get(url, headers=HEADERS, timeout=12)
        soup = BeautifulSoup(r.text, 'html.parser')
        results = []
        for result in soup.select('.result__body')[:num]:
            title = result.select_one('.result__title')
            snippet = result.select_one('.result__snippet')
            results.append({
                'title': title.get_text(strip=True) if title else '',
                'snippet': snippet.get_text(strip=True) if snippet else '',
            })
        return results
    except Exception:
        return []


def collect_raw_data(fund_name, website_url=None):
    """
    Pull raw text from multiple sources for a fund.
    Returns a dict of {source: text}.
    """
    sources = {}
    print(f"  Collecting data for {fund_name}...")

    # 1. Fund website
    if website_url:
        print(f"    Scraping website: {website_url}")
        text = scrape_url(website_url)
        if text:
            sources["website"] = text
            # Try /portfolio, /team, /about subpages
            for path in ["/portfolio", "/team", "/about", "/thesis"]:
                sub = scrape_url(website_url.rstrip('/') + path, max_chars=2000)
                if sub:
                    sources[f"website_{path.strip('/')}"] = sub
                    time.sleep(0.5)

    # 2. Recent news about the fund
    print(f"    Searching recent news...")
    news = ddg_search(f"{fund_name} venture capital India investments 2024 2025", num=6)
    if news:
        sources["recent_news"] = "\n".join(
            f"- {r['title']}: {r['snippet']}" for r in news if r['snippet']
        )

    # 3. What founders say about them
    print(f"    Searching founder opinions...")
    founder_mentions = ddg_search(f"\"{fund_name}\" founder experience portfolio startup India", num=5)
    if founder_mentions:
        sources["founder_opinions"] = "\n".join(
            f"- {r['title']}: {r['snippet']}" for r in founder_mentions if r['snippet']
        )

    # 4. What other VCs / press say
    print(f"    Searching press coverage...")
    press = ddg_search(f"{fund_name} India fund thesis focus investments Inc42 YourStory TechCrunch", num=5)
    if press:
        sources["press"] = "\n".join(
            f"- {r['title']}: {r['snippet']}" for r in press if r['snippet']
        )

    # 5. Their partners / GPs on Twitter/LinkedIn (search for quotes)
    print(f"    Searching partner viewpoints...")
    partner_views = ddg_search(f"{fund_name} partner GP what we look for in startups", num=4)
    if partner_views:
        sources["partner_views"] = "\n".join(
            f"- {r['title']}: {r['snippet']}" for r in partner_views if r['snippet']
        )

    return sources


# ── Gemini synthesis ──────────────────────────────────────────────────────────

SYNTHESIS_PROMPT = """
You are building a detailed investor profile for a VC pitch simulator.
Based on all the raw data below, produce a JSON object with exactly these fields:

{{
  "fund_name": "{fund_name}",
  "thesis_summary": "2-3 sentence summary of what they invest in and why",
  "focus_areas": ["area1", "area2", ...],
  "stage": "e.g. Pre-seed to Series A",
  "check_size": "e.g. $500K - $3M",
  "key_partners": ["Name (known for X)", ...],
  "recent_investments": ["Company (sector)", ...],
  "what_they_talk_about": "What themes, topics, and priorities come up in their content",
  "what_they_prioritize_in_founders": "What they explicitly say they look for",
  "typical_questions_they_ask": ["Question 1", "Question 2", ...],
  "what_founders_say_about_them": "How do portfolio founders describe working with them",
  "what_others_say_about_them": "What press, other VCs, or industry says about this fund",
  "red_flags_for_this_fund": "What types of pitches or founders they are known to pass on",
  "yt_summary": "{yt_summary}"
}}

Return ONLY the JSON. No explanation, no markdown fences.

RAW DATA:
{raw_data}
"""

def synthesize_profile(client, fund_name, sources, yt_summary=""):
    """Use Gemini to synthesize raw data into a structured fund profile."""
    raw_data = ""
    for source, text in sources.items():
        raw_data += f"\n\n=== {source.upper()} ===\n{text}"

    if not raw_data.strip():
        print(f"  No data collected for {fund_name}. Skipping synthesis.")
        return None

    prompt = SYNTHESIS_PROMPT.format(
        fund_name=fund_name,
        yt_summary=yt_summary,
        raw_data=raw_data[:12000]  # stay within token limits
    )

    try:
        response = client.models.generate_content(
            model="gemini-flash-latest",
            contents=prompt
        )
        text = response.text.strip()
        # Strip markdown fences if Gemini adds them
        text = re.sub(r'^```json\s*', '', text)
        text = re.sub(r'\s*```$', '', text)
        profile = json.loads(text)
        return profile
    except json.JSONDecodeError as e:
        print(f"  JSON parse error: {e}")
        return None
    except Exception as e:
        print(f"  Gemini error: {e}")
        return None


# ── Main runner ───────────────────────────────────────────────────────────────

def research_fund(fund_name, website_url=None, force=False):
    """
    Research a single fund and save profile to data/fund_profiles/.
    Skip if profile already exists (unless force=True).
    """
    if not config.GEMINI_API_KEY:
        print("No Gemini API key in config.py.")
        return None

    if not force and os.path.exists(profile_path(fund_name)):
        print(f"  Profile already exists for {fund_name}. Use force=True to refresh.")
        return load_profile(fund_name)

    # Auto-lookup website if not provided
    if not website_url:
        try:
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from data.fund_websites import FUND_WEBSITES
            website_url = FUND_WEBSITES.get(fund_name)
        except ImportError:
            pass

    # Get YT summary from master.csv if available
    yt_summary = ""
    try:
        from scripts.csv_client import get_all_funds
        funds = get_all_funds()
        fund_row = next((f for f in funds if f.get("Fund Name", "").strip().lower() == fund_name.strip().lower()), None)
        if fund_row:
            yt_summary = fund_row.get("YT Summary", "")
    except Exception:
        pass

    client = genai.Client(api_key=config.GEMINI_API_KEY)

    # Collect raw data
    sources = collect_raw_data(fund_name, website_url)

    # Synthesize with Gemini
    print(f"  Synthesizing profile with Gemini...")
    profile = synthesize_profile(client, fund_name, sources, yt_summary)

    if profile:
        from datetime import datetime
        profile["last_updated"] = datetime.now().strftime("%Y-%m-%d")
        save_profile(fund_name, profile)
        print(f"  Profile saved: {profile_path(fund_name)}")
    else:
        print(f"  Failed to build profile for {fund_name}.")

    return profile


def research_all_prominent_funds(force=False):
    """Research all 20 prominent funds from FUND_WEBSITES."""
    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from data.fund_websites import FUND_WEBSITES
    except ImportError:
        print("data/fund_websites.py not found.")
        return

    print(f"\n[Fund Researcher] Building profiles for {len(FUND_WEBSITES)} funds...\n")
    for i, (fund_name, website) in enumerate(FUND_WEBSITES.items()):
        print(f"[{i+1}/{len(FUND_WEBSITES)}] {fund_name}")
        research_fund(fund_name, website_url=website, force=force)
        time.sleep(2)  # polite rate limiting between funds
        print()

    print("\n[Fund Researcher] Done.")
