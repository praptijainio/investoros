"""
InvestorOS — Main runner.
Usage:
  python run.py setup         # One-time: add new columns, create new sheets
  python run.py enrich        # Pull RSS + YouTube, update activity feed
  python run.py pitch         # Start a pitch practice session (archetype mode)
  python run.py pitch fund    # Start a pitch session for a specific fund
"""
import sys

def main():
    command = sys.argv[1] if len(sys.argv) > 1 else "help"

    if command == "setup":
        print("=== InvestorOS Setup ===")
        from scripts.csv_client import ensure_columns_exist, ensure_partners_file, ensure_activity_file
        print("Adding new columns to master.csv...")
        ensure_columns_exist()
        print("Creating partners.csv...")
        ensure_partners_file()
        print("Creating activity_feed.csv...")
        ensure_activity_file()
        print("\nSetup complete.")

    elif command == "enrich":
        print("=== InvestorOS Enrichment ===")
        from scripts.rss_fetcher import run_rss_enrichment
        from scripts.youtube_fetcher import run_youtube_enrichment
        run_rss_enrichment()
        run_youtube_enrichment()
        print("\nEnrichment complete. Check data/activity_feed.csv for results.")

    elif command == "enrich-rss":
        from scripts.rss_fetcher import run_rss_enrichment
        run_rss_enrichment()

    elif command == "enrich-youtube":
        from scripts.youtube_fetcher import run_youtube_enrichment
        run_youtube_enrichment()

    elif command == "enrich-yt":
        from scripts.youtube_enricher import run_youtube_enrichment as run_yt
        target = sys.argv[2] if len(sys.argv) > 2 else None
        run_yt(target_fund=target)

    elif command == "research":
        print("=== Fund Researcher ===")
        if len(sys.argv) < 3:
            print("Usage: python3 run.py research \"Fund Name\"")
        else:
            from scripts.fund_researcher import research_fund
            fund_name = sys.argv[2]
            force = "--force" in sys.argv
            research_fund(fund_name, force=force)

    elif command == "research-all":
        print("=== Fund Researcher — All Prominent Funds ===")
        force = "--force" in sys.argv
        from scripts.fund_researcher import research_all_prominent_funds
        research_all_prominent_funds(force=force)

    elif command == "pitch":
        from scripts.pitch_trainer import run_pitch_session
        mode = sys.argv[2] if len(sys.argv) > 2 else "archetype"
        fund_name = sys.argv[3] if len(sys.argv) > 3 else None
        run_pitch_session(mode=mode, fund_name=fund_name)

    elif command == "list-funds":
        from scripts.pitch_trainer import list_available_funds
        funds = list_available_funds()
        print(f"\n{len(funds)} funds available for pitch simulation:")
        for f in funds:
            print(f"  - {f}")

    else:
        print(__doc__)

if __name__ == "__main__":
    main()
