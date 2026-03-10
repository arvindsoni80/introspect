#!/usr/bin/env python3
"""Test fetching calls from Gong using GONG_LOOKBACK_DAYS."""

import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core import Config, GongClient
from src.data import Database, Repository


def main():
    print("📞 Testing Gong Call Fetching with Lookback Period\n")
    print("=" * 70)

    # Load config
    print("\n1. Loading configuration...")
    config = Config()

    if not config.validate():
        print("\n❌ Configuration incomplete. Check your .env file.")
        return

    print(f"   ✓ Config loaded")
    print(f"   ✓ Gong API URL: {config.GONG_API_URL}")
    print(f"   ✓ Lookback Days: {config.GONG_LOOKBACK_DAYS}")
    print(f"   ✓ Internal Domain: {config.INTERNAL_DOMAIN}")

    # Load sales reps from database
    print("\n2. Loading sales reps from database...")
    db_path = config.SQLITE_DB_PATH
    print(f"   Database: {db_path}")

    db = Database(db_path)
    db.connect()
    repo = Repository(db.conn)

    sales_reps = repo.list_sales_reps(active_only=True)
    db.close()

    if not sales_reps:
        print("   ⚠️  No sales reps found in database")
        print("   Run: python load_sales_reps.py first")
        return

    print(f"   ✓ Found {len(sales_reps)} active sales reps:")
    sales_rep_emails = []
    for rep in sorted(sales_reps, key=lambda r: r.email):
        print(f"      • {rep.email} ({rep.segment})")
        sales_rep_emails.append(rep.email)

    # Initialize Gong client
    print("\n3. Initializing Gong client...")
    try:
        gong_client = GongClient(
            access_key=config.GONG_ACCESS_KEY,
            secret_key=config.GONG_SECRET_KEY,
            api_url=config.GONG_API_URL,
            internal_domain=config.INTERNAL_DOMAIN,
            lookback_days=config.GONG_LOOKBACK_DAYS,
        )
        print("   ✓ Gong client initialized")
    except Exception as e:
        print(f"   ❌ Failed to initialize Gong client: {e}")
        return

    # Fetch calls for sales reps (only calls with external participants)
    print(f"\n4. Fetching calls for sales reps (last {config.GONG_LOOKBACK_DAYS} days)...")
    print("   📌 Note: Only fetching calls WITH external participants")
    print("   (This may take a few seconds...)")

    try:
        calls = gong_client.get_calls_for_sales_reps(sales_rep_emails)
        print(f"   ✓ Fetched {len(calls)} calls with external participants")
    except Exception as e:
        print(f"   ❌ Failed to fetch calls: {e}")
        import traceback
        traceback.print_exc()
        return

    if not calls:
        print(f"\n⚠️  No calls found in the last {config.GONG_LOOKBACK_DAYS} days")
        print("   Possible reasons:")
        print("   - No calls with external participants in this period")
        print("   - Sales rep emails don't match Gong user IDs")
        print(f"   - Try increasing GONG_LOOKBACK_DAYS (currently {config.GONG_LOOKBACK_DAYS})")
        return

    # Analyze calls
    print("\n" + "=" * 70)
    print("CALL ANALYSIS")
    print("=" * 70)

    # Group by sales rep
    calls_by_rep = {}
    for call in calls:
        rep_email = call.get("sales_rep_email", "unknown")
        if rep_email not in calls_by_rep:
            calls_by_rep[rep_email] = []
        calls_by_rep[rep_email].append(call)

    print(f"\n📊 Calls by Sales Rep:")
    for rep_email in sorted(calls_by_rep.keys()):
        call_list = calls_by_rep[rep_email]
        print(f"\n   {rep_email}: {len(call_list)} calls")

        for call in call_list[:3]:  # Show first 3
            meta = call.get("metaData", {})
            title = meta.get("title", "Untitled")
            started = meta.get("started", "")

            if started:
                try:
                    call_date = datetime.fromisoformat(started.replace("Z", "+00:00"))
                    date_str = call_date.strftime("%Y-%m-%d %H:%M")
                except:
                    date_str = started
            else:
                date_str = "unknown date"

            # Get participants
            participants = call.get("parties", [])
            external_count = sum(1 for p in participants
                               if p.get("affiliation") in ("External", "Unknown"))

            print(f"      • {title[:50]}")
            print(f"        Date: {date_str}, External participants: {external_count}")

        if len(call_list) > 3:
            print(f"      ... and {len(call_list) - 3} more calls")

    # Final summary
    print("\n" + "=" * 70)
    print("✅ SUMMARY")
    print("=" * 70)
    print(f"\nPeriod: Last {config.GONG_LOOKBACK_DAYS} days")
    print(f"\nTotal calls fetched: {len(calls)}")
    print(f"  (Only calls with external participants)")
    print(f"\nSales reps in DB: {len(sales_reps)}")
    print(f"Sales reps with calls: {len(calls_by_rep)}")

    # Show reps without calls
    reps_without_calls = set(sales_rep_emails) - set(calls_by_rep.keys())
    if reps_without_calls:
        print(f"\n⚠️  Sales reps with NO calls found:")
        for email in sorted(reps_without_calls):
            print(f"   • {email}")

    print("\n✨ Next steps:")
    print("   1. If data looks good, test classification:")
    print("      python test_classification.py")
    print("   2. Then process calls into database:")
    print("      python process_calls.py --reset --limit 5")
    print()


if __name__ == "__main__":
    main()
