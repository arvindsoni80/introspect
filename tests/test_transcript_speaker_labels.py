#!/usr/bin/env python3
"""
Test script to verify transcript fetching with speaker role identification.

This script:
1. Fetches a few calls from the database
2. Gets their transcripts with speaker labels
3. Prints the transcripts to verify speaker identification is working

Usage:
    python test_transcript_speaker_labels.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core import Config, GongClient
from src.data import Database, init_database, Repository


def main():
    """Main entry point."""
    print("=" * 80)
    print("TESTING TRANSCRIPT FETCHING WITH SPEAKER IDENTIFICATION")
    print("=" * 80)

    # Initialize configuration
    print("\n🔧 Initializing configuration...")
    config = Config()

    if not config.validate():
        print("\n❌ Configuration incomplete. Please check your .env file.")
        return 1

    print(f"   ✓ Config loaded")
    print(f"   ✓ Internal domain: {config.INTERNAL_DOMAIN}")

    # Initialize database
    db_path = config.SQLITE_DB_PATH
    print(f"\n🗄️  Connecting to database: {db_path}")
    db = init_database(db_path, reset=False)
    repository = Repository(db.conn)

    # Initialize Gong client
    print("\n🌐 Initializing Gong client...")
    try:
        gong_client = GongClient(
            access_key=config.GONG_ACCESS_KEY,
            secret_key=config.GONG_SECRET_KEY,
            api_url=config.GONG_API_URL,
            internal_domain=config.INTERNAL_DOMAIN,
        )
        print("   ✓ Gong client initialized")
    except Exception as e:
        print(f"   ❌ Failed to initialize Gong client: {e}")
        return 1

    # Get a few test calls
    print("\n📊 Finding test calls...")
    query = """
        SELECT c.* FROM calls c
        JOIN accounts a ON c.account_id = a.id
        WHERE a.primary_segment = 'enterprise'
        ORDER BY c.call_date DESC
        LIMIT 3
    """

    cursor = repository.conn.execute(query)
    test_calls = [repository._row_to_call(row) for row in cursor.fetchall()]

    if not test_calls:
        print("   ⚠️  No test calls found.")
        return 0

    print(f"   ✓ Found {len(test_calls)} test calls")

    # Fetch transcripts
    call_ids = [call.call_id for call in test_calls]
    print(f"\n📝 Fetching transcripts with speaker roles...")
    print(f"   Call IDs: {call_ids[:3]}")

    try:
        transcripts = gong_client.get_transcripts(call_ids)
        print(f"   ✓ Fetched {len(transcripts)} transcripts")
    except Exception as e:
        print(f"   ❌ Failed to fetch transcripts: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # Display transcripts with analysis
    for i, call in enumerate(test_calls, 1):
        print("\n" + "=" * 80)
        print(f"CALL {i}/{len(test_calls)}")
        print("=" * 80)
        print(f"Title: {call.call_title}")
        print(f"Date: {call.call_date.strftime('%Y-%m-%d')}")
        print(f"Call ID: {call.call_id}")
        print(f"Stage: {call.primary_stage}")

        transcript = transcripts.get(call.call_id, "")
        if not transcript:
            print("\n⚠️  No transcript available")
            continue

        # Analyze speaker labels
        lines = transcript.split("\n")
        speaker_counts = {}
        unknown_count = 0
        sales_count = 0
        customer_count = 0

        for line in lines:
            if line.startswith("["):
                # Extract speaker label
                end_bracket = line.find("]:")
                if end_bracket > 0:
                    speaker_label = line[1:end_bracket]
                    speaker_counts[speaker_label] = speaker_counts.get(speaker_label, 0) + 1

                    if speaker_label.startswith("Unknown"):
                        unknown_count += 1
                    elif speaker_label.startswith("Sales"):
                        sales_count += 1
                    elif speaker_label.startswith("Customer"):
                        customer_count += 1

        # Print statistics
        print(f"\n📊 Speaker Statistics:")
        print(f"   Total lines: {len(lines)}")
        print(f"   Sales lines: {sales_count} ({sales_count/len(lines)*100:.1f}%)")
        print(f"   Customer lines: {customer_count} ({customer_count/len(lines)*100:.1f}%)")
        print(f"   Unknown lines: {unknown_count} ({unknown_count/len(lines)*100:.1f}%)")

        print(f"\n👥 Unique Speakers:")
        for speaker, count in sorted(speaker_counts.items()):
            percentage = count / len(lines) * 100
            print(f"   • {speaker}: {count} lines ({percentage:.1f}%)")

        # Show first 30 lines of transcript
        print(f"\n📄 Transcript Preview (first 30 lines):")
        print("-" * 80)
        for j, line in enumerate(lines[:30], 1):
            print(f"{j:3d}. {line}")

        if len(lines) > 30:
            print(f"\n... ({len(lines) - 30} more lines)")

    # Summary
    print("\n" + "=" * 80)
    print("✅ TEST COMPLETE")
    print("=" * 80)
    print("\nReview the speaker labels above:")
    print("• ✅ Good: Most lines labeled as [Sales - Name] or [Customer - Name]")
    print("• ⚠️  Issue: Many lines labeled as [Unknown - ...]")
    print("\nIf you see many Unknown speakers, the speaker identification needs adjustment.")

    db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
