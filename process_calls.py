#!/usr/bin/env python3
"""
Main entry point for processing sales calls.

Usage:
    python process_calls.py                        # Process with defaults from .env
    python process_calls.py --days 30              # Override lookback days
    python process_calls.py --limit 10             # Process first 10 calls only
    python process_calls.py --reset --limit 5      # Reset DB and process 5 calls
"""

import argparse
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.core import Config, GongClient, LLMClient
from src.data import Database, init_database, Repository
from src.services.call_processor import CallProcessor


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Process sales calls from Gong")
    parser.add_argument(
        "--days",
        type=int,
        help="Number of days to look back (default: from GONG_LOOKBACK_DAYS in .env)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of calls to process (e.g., --limit 10 for first 10 calls)",
    )
    parser.add_argument(
        "--segment",
        type=str,
        help="Filter by sales rep segment (e.g., --segment enterprise)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset database before processing (WARNING: deletes all data)",
    )
    parser.add_argument(
        "--db-path",
        help="Path to SQLite database (default: from .env SQLITE_DB_PATH or 'introspect.db')",
    )

    args = parser.parse_args()

    # Initialize configuration
    print("🔧 Initializing configuration...")
    config = Config()

    # Validate configuration
    if not config.validate():
        print("\n❌ Configuration incomplete. Please check your .env file.")
        print("\nRequired variables:")
        print("  - GONG_ACCESS_KEY")
        print("  - GONG_SECRET_KEY")
        print("  - LLM_API_KEY")
        return 1

    print(f"   ✓ Config loaded")
    print(f"   ✓ Gong API URL: {config.GONG_API_URL}")
    print(f"   ✓ Internal Domain: {config.INTERNAL_DOMAIN}")
    print(f"   ✓ Lookback Days: {config.GONG_LOOKBACK_DAYS}")
    print(f"   ✓ LLM Provider: {config.LLM_PROVIDER}")
    print(f"   ✓ LLM Model: {config.LLM_MODEL}")

    # Determine lookback days (CLI arg > .env)
    lookback_days = args.days if args.days is not None else config.GONG_LOOKBACK_DAYS

    # Determine database path (CLI arg > .env > default)
    db_path = args.db_path or config.SQLITE_DB_PATH

    # Initialize database
    print(f"🗄️  Initializing database at {db_path}...")
    db = init_database(db_path, reset=args.reset)
    repository = Repository(db.conn)

    # Initialize clients
    print("\n🌐 Initializing Gong client...")
    try:
        gong_client = GongClient(
            access_key=config.GONG_ACCESS_KEY,
            secret_key=config.GONG_SECRET_KEY,
            api_url=config.GONG_API_URL,
            internal_domain=config.INTERNAL_DOMAIN,
            lookback_days=lookback_days,
        )
        print("   ✓ Gong client initialized")
    except Exception as e:
        print(f"   ❌ Failed to initialize Gong client: {e}")
        return 1

    print("\n🤖 Initializing LLM client...")
    try:
        llm_client = LLMClient(
            anthropic_api_key=config.LLM_API_KEY,
            model=config.LLM_MODEL,
        )
        print("   ✓ LLM client initialized")
    except Exception as e:
        print(f"   ❌ Failed to initialize LLM client: {e}")
        return 1

    # Initialize processor
    print("⚙️  Initializing call processor...")
    processor = CallProcessor(
        gong_client=gong_client,
        llm_client=llm_client,
        repository=repository,
        internal_domain=config.INTERNAL_DOMAIN,
    )

    # Process calls
    print("\n" + "=" * 70)
    print(f"📞 Processing calls from last {lookback_days} days")
    if args.segment:
        print(f"   Segment filter: {args.segment}")
    if args.limit:
        print(f"   Limit: {args.limit} calls")
    print("=" * 70)

    try:
        processor.process_recent_calls(days=lookback_days, limit=args.limit, segment=args.segment)
    except Exception as e:
        print(f"\n❌ Processing failed: {e}")
        import traceback
        traceback.print_exc()
        db.close()
        return 1

    # Show summary
    print("\n" + "=" * 70)
    print("📊 DATABASE SUMMARY")
    print("=" * 70)
    counts = db.get_table_counts()
    for table, count in sorted(counts.items()):
        if count > 0:
            print(f"  {table}: {count}")

    db.close()
    print("\n✅ Done!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
