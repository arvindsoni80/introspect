#!/usr/bin/env python3
"""
Backfill call participants data from Gong.

This script fetches call details from Gong to get party/participant information
and stores it in the call_participants table.

Usage:
    python backfill_call_participants.py                # Test with 10 calls
    python backfill_call_participants.py --limit 50     # Test with 50 calls
    python backfill_call_participants.py --all          # Process all calls
"""

import argparse
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core import Config
from src.data import Database, init_database, Repository


async def fetch_and_store_participants(call_ids, repo, gong_client):
    """Fetch call details and store participant info."""
    from src.core.gong_client import AsyncGongClient

    print(f"\n📞 Fetching call details for {len(call_ids)} calls...")

    # Fetch call details with parties
    payload = {
        "filter": {
            "callIds": call_ids
        },
        "contentSelector": {
            "exposedFields": {
                "parties": True,
            }
        }
    }

    data = await gong_client._api_call(
        "/v2/calls/extensive",
        "POST",
        payload=payload,
        paginate=False,
    )

    calls = data.get("calls", [])
    print(f"   ✓ Retrieved {len(calls)} calls from Gong")
    print(f"   🔍 DEBUG: Response top-level keys: {list(data.keys())}")
    print(f"   🔍 DEBUG: Type of calls: {type(calls)}")
    print(f"   🔍 DEBUG: Calls is empty: {len(calls) == 0}")

    if len(calls) == 0:
        print(f"   ⚠️  WARNING: No calls in response!")
        print(f"   🔍 DEBUG: Full response keys and values:")
        import json
        print(json.dumps(data, indent=2)[:2000])
        return 0

    # Store participants for each call
    stored_count = 0
    print(f"\n   🔄 Starting loop through {len(calls)} calls...")
    for i, call in enumerate(calls, 1):
        print(f"\n   🔄 Processing call {i}/{len(calls)}...")

        # Get call_id from metadata (not top-level)
        metadata = call.get("metaData", {}) or call.get("metadata", {})
        call_id = metadata.get("id")
        parties = call.get("parties", [])

        print(f"      🔍 DEBUG: call_id = {call_id}")
        print(f"      🔍 DEBUG: parties count = {len(parties)}")

        if not call_id:
            print(f"      ⚠️  WARNING: No call_id, skipping...")
            continue

        print(f"\n   📋 Call ID: {call_id}")
        print(f"      🔍 DEBUG: Call keys: {list(call.keys())}")
        print(f"      Participants: {len(parties)}")

        if not parties:
            print(f"      ⚠️  WARNING: No parties for this call!")
            continue

        print(f"      🔍 DEBUG: First party keys: {list(parties[0].keys())}")
        print(f"      🔍 DEBUG: First party full data:")
        import json
        print(f"         {json.dumps(parties[0], indent=8)}")

        if parties:
            # Store participants
            print(f"      🔍 DEBUG: Storing {len(parties)} participants...")
            inserted_count = repo.store_call_participants(call_id, parties)
            print(f"      ✓ Inserted {inserted_count} participants with speaker IDs")
            stored_count += 1

            # Verify what was stored
            stored_participants = repo.get_call_participants(call_id)
            print(f"      🔍 DEBUG: Verified {len(stored_participants)} participants in database")

            # Print summary of what was stored
            internal_count = sum(1 for p in parties if p.get('affiliation') == 'Internal')
            external_count = sum(1 for p in parties if p.get('affiliation') == 'External')
            unknown_count = sum(1 for p in parties if p.get('affiliation') == 'Unknown')

            print(f"      ✓ Stored: {internal_count} Internal, {external_count} External, {unknown_count} Unknown")

            # Show sample participants
            for i, party in enumerate(parties[:3], 1):
                name = party.get('name', 'Unknown')
                email = party.get('emailAddress', 'N/A')
                affiliation = party.get('affiliation', 'Unknown')
                speaker_id = party.get('speakerId', 'N/A')
                print(f"         {i}. {name} ({affiliation}) - {email[:30]} [Speaker: {speaker_id}]")

            if len(parties) > 3:
                print(f"         ... and {len(parties) - 3} more")

    return stored_count


async def backfill(limit: int = None, process_all: bool = False):
    """Main backfill logic."""
    print("=" * 80)
    print("BACKFILL CALL PARTICIPANTS")
    print("=" * 80)

    # Initialize configuration
    print("\n🔧 Initializing configuration...")
    config = Config()

    if not config.validate():
        print("\n❌ Configuration incomplete. Please check your .env file.")
        return 1

    print(f"✓ Config loaded")

    # Initialize database
    db_path = config.SQLITE_DB_PATH
    print(f"\n🗄️  Connecting to database: {db_path}")
    db = init_database(db_path, reset=False)
    repo = Repository(db.conn)

    # Check if table exists
    cursor = db.conn.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='call_participants'
    """)

    if not cursor.fetchone():
        print("\n❌ call_participants table does not exist!")
        print("   Run: python migrate_add_participants_table.py")
        db.close()
        return 1

    # Get calls to process
    print("\n📊 Finding calls to process...")

    if process_all:
        query = "SELECT call_id FROM calls ORDER BY call_date DESC"
        cursor = db.conn.execute(query)
        print("   Processing ALL calls")
    else:
        limit_val = limit or 10
        query = f"SELECT call_id FROM calls ORDER BY call_date DESC LIMIT {limit_val}"
        cursor = db.conn.execute(query)
        print(f"   Processing {limit_val} most recent calls (test mode)")

    call_ids = [row['call_id'] for row in cursor.fetchall()]

    if not call_ids:
        print("   ⚠️  No calls found in database")
        db.close()
        return 0

    print(f"   ✓ Found {len(call_ids)} calls to process")

    # Initialize Gong client
    print("\n🌐 Initializing Gong client...")
    from src.core.gong_client import AsyncGongClient

    async with AsyncGongClient(
        access_key=config.GONG_ACCESS_KEY,
        secret_key=config.GONG_SECRET_KEY,
        api_url=config.GONG_API_URL,
        internal_domain=config.INTERNAL_DOMAIN,
    ) as gong_client:
        print("   ✓ Connected to Gong")

        # Process in batches of 50 (Gong API limit)
        batch_size = 50
        total_stored = 0

        for i in range(0, len(call_ids), batch_size):
            batch = call_ids[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (len(call_ids) + batch_size - 1) // batch_size

            print(f"\n{'=' * 80}")
            print(f"BATCH {batch_num}/{total_batches} ({len(batch)} calls)")
            print(f"{'=' * 80}")

            stored = await fetch_and_store_participants(batch, repo, gong_client)
            total_stored += stored

    # Summary
    print("\n" + "=" * 80)
    print("✅ BACKFILL COMPLETE")
    print("=" * 80)
    print(f"\n   Calls processed: {len(call_ids)}")
    print(f"   Participants stored: {total_stored} calls")

    # Show sample query
    print("\n📊 Sample data check:")
    cursor = db.conn.execute("""
        SELECT call_id, COUNT(*) as participant_count
        FROM call_participants
        GROUP BY call_id
        ORDER BY call_id DESC
        LIMIT 5
    """)

    print("\n   Recent calls with participant counts:")
    for row in cursor.fetchall():
        print(f"      {row['call_id']}: {row['participant_count']} participants")

    # Total count
    cursor = db.conn.execute("SELECT COUNT(DISTINCT call_id) as call_count FROM call_participants")
    call_count = cursor.fetchone()['call_count']

    cursor = db.conn.execute("SELECT COUNT(*) as total FROM call_participants")
    total_participants = cursor.fetchone()['total']

    print(f"\n   Total in database:")
    print(f"      Calls with participants: {call_count}")
    print(f"      Total participant records: {total_participants}")

    db.close()
    print("\n✅ Done!")
    return 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Backfill call participants from Gong"
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Number of calls to process (default: 10 for testing)"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Process ALL calls (use with caution)"
    )

    args = parser.parse_args()

    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(backfill(args.limit, args.all))


if __name__ == "__main__":
    sys.exit(main())
