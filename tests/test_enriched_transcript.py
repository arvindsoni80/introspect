#!/usr/bin/env python3
"""
Test script to demonstrate transcript enrichment with participant information.

This shows how speaker IDs are replaced with meaningful names and roles.

Usage:
    python test_enriched_transcript.py [call_id]
"""

import argparse
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core import Config, GongClient
from src.data import Database, init_database, Repository


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test transcript enrichment with participant info"
    )
    parser.add_argument(
        "call_id",
        nargs="?",
        help="Call ID to test (optional - uses most recent if not provided)"
    )

    args = parser.parse_args()

    print("=" * 80)
    print("TRANSCRIPT ENRICHMENT TEST")
    print("=" * 80)

    # Initialize configuration
    print("\n🔧 Initializing configuration...")
    config = Config()

    if not config.validate():
        print("\n❌ Configuration incomplete. Please check your .env file.")
        return 1

    # Initialize database
    db_path = config.SQLITE_DB_PATH
    print(f"\n🗄️  Connecting to database: {db_path}")
    db = init_database(db_path, reset=False)
    repo = Repository(db.conn)

    # Get call ID
    if not args.call_id:
        # Find a call with participant data
        cursor = db.conn.execute("""
            SELECT DISTINCT call_id
            FROM call_participants
            ORDER BY call_id DESC
            LIMIT 1
        """)
        row = cursor.fetchone()

        if not row:
            print("\n❌ No calls with participant data found!")
            print("   Run: python backfill_call_participants.py")
            return 1

        call_id = row['call_id']
        print(f"✓ Using call with participant data: {call_id}")
    else:
        call_id = args.call_id
        print(f"✓ Using provided call ID: {call_id}")

    # Check if participants exist
    participants = repo.get_call_participants(call_id)
    if not participants:
        print(f"\n⚠️  No participant data found for call {call_id}")
        print("   Run: python backfill_call_participants.py")
        return 1

    print(f"\n👥 Found {len(participants)} participants:")
    for speaker_id, participant in list(participants.items())[:5]:
        name = participant['name']
        affiliation = participant['affiliation']
        email = participant['email_address']
        print(f"   • {name} ({affiliation}) - {email}")

    # Fetch transcript
    print(f"\n📝 Fetching transcript from Gong...")
    gong_client = GongClient(
        access_key=config.GONG_ACCESS_KEY,
        secret_key=config.GONG_SECRET_KEY,
        api_url=config.GONG_API_URL,
        internal_domain=config.INTERNAL_DOMAIN,
    )

    transcripts = gong_client.get_transcripts([call_id])
    raw_transcript = transcripts.get(call_id, "")

    if not raw_transcript:
        print(f"   ❌ No transcript found for call {call_id}")
        return 1

    print(f"   ✓ Fetched transcript ({len(raw_transcript)} chars)")

    # Show sample of raw transcript
    raw_lines = raw_transcript.split('\n')
    print(f"\n📄 RAW TRANSCRIPT (first 10 lines):")
    print("-" * 80)
    for i, line in enumerate(raw_lines[:10], 1):
        print(f"{i:3d}. {line}")

    # Enrich transcript
    print(f"\n✨ Enriching transcript with participant info...")
    enriched_transcript = repo.enrich_transcript_with_participants(call_id, raw_transcript)

    # Show sample of enriched transcript
    enriched_lines = enriched_transcript.split('\n')
    print(f"\n📄 ENRICHED TRANSCRIPT (first 50 lines):")
    print("-" * 80)
    for i, line in enumerate(enriched_lines[:50], 1):
        print(f"{i:3d}. {line}")

    # Compare
    print("\n" + "=" * 80)
    print("COMPARISON")
    print("=" * 80)

    # Count speaker formats
    raw_unique_speakers = set()
    enriched_unique_speakers = set()

    for line in raw_lines:
        if line.startswith('[') and ']:' in line:
            end_bracket = line.find(']:')
            speaker = line[1:end_bracket]
            raw_unique_speakers.add(speaker)

    for line in enriched_lines:
        if line.startswith('[') and ']:' in line:
            end_bracket = line.find(']:')
            speaker = line[1:end_bracket]
            enriched_unique_speakers.add(speaker)

    print(f"\nRaw transcript speakers:")
    for speaker in list(raw_unique_speakers)[:5]:
        print(f"   • [{speaker}]")
    if len(raw_unique_speakers) > 5:
        print(f"   ... and {len(raw_unique_speakers) - 5} more")

    print(f"\nEnriched transcript speakers:")
    for speaker in sorted(enriched_unique_speakers)[:10]:
        print(f"   • [{speaker}]")

    print("\n✅ Done!")
    print("\nThe enriched transcript can now be passed to LLM evaluators.")
    print("The LLM will see:")
    print('  • "Sales - John" instead of "2349112610150941359"')
    print('  • "Customer - Sarah" instead of "7726781942202217419"')
    print("\nThis helps the LLM understand who is speaking and analyze accordingly!")

    db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
