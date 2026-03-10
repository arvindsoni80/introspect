#!/usr/bin/env python3
"""Helper script to get call IDs for testing."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core import Config, GongClient
from src.data import Database, Repository


def main():
    print("📋 Fetching Call IDs\n")
    print("=" * 70)

    # Initialize config
    config = Config()

    if not config.validate():
        print("\n❌ Configuration incomplete.")
        return

    # Load sales reps
    print("\n1. Loading sales reps...")
    db = Database(config.SQLITE_DB_PATH)
    db.connect()
    repo = Repository(db.conn)
    sales_reps = repo.list_sales_reps(active_only=True)
    db.close()

    if not sales_reps:
        print("   ⚠️  No sales reps found. Run: python load_sales_reps.py")
        return

    sales_rep_emails = [rep.email for rep in sales_reps]
    print(f"   ✓ Found {len(sales_reps)} sales reps")

    # Initialize Gong client
    print("\n2. Fetching calls...")
    gong_client = GongClient(
        access_key=config.GONG_ACCESS_KEY,
        secret_key=config.GONG_SECRET_KEY,
        api_url=config.GONG_API_URL,
        internal_domain=config.INTERNAL_DOMAIN,
        lookback_days=config.GONG_LOOKBACK_DAYS,
    )

    calls = gong_client.get_calls_for_sales_reps(sales_rep_emails)
    print(f"   ✓ Fetched {len(calls)} calls")

    if not calls:
        print("\n⚠️  No calls found")
        return

    # Display call IDs
    print("\n" + "=" * 70)
    print("CALL IDs (First 20)")
    print("=" * 70)

    for i, call in enumerate(calls[:20], 1):
        meta = call.get("metaData", {})
        call_id = call.get("id") or meta.get("id", "unknown")
        title = meta.get("title", "Untitled")[:50]
        sales_rep = call.get("sales_rep_email", "unknown")

        print(f"{i:2d}. {call_id:20s} | {title:50s} | {sales_rep}")

    # Save to file
    output_file = "call_ids.txt"
    with open(output_file, 'w') as f:
        for call in calls[:20]:
            meta = call.get("metaData", {})
            call_id = call.get("id") or meta.get("id", "unknown")
            if call_id != "unknown":
                f.write(f"{call_id}\n")

    print(f"\n✅ Saved first 20 call IDs to: {output_file}")
    print(f"\nUsage:")
    print(f"   python test_scoring.py --file {output_file}")
    print(f"   python test_scoring.py CALL_ID1 CALL_ID2")
    print()


if __name__ == "__main__":
    main()
