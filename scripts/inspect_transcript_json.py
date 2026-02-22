#!/usr/bin/env python3
"""
Inspect the raw JSON structure of a Gong transcript response.

This script fetches a single transcript and prints its JSON structure
to understand what fields are available.

Usage:
    python inspect_transcript_json.py [call_id]

    If no call_id is provided, uses the most recent call from the database.
"""

import argparse
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core import Config
from src.data import Database, init_database, Repository


async def fetch_and_inspect(call_id: str = None):
    """Fetch a transcript and inspect its JSON structure."""
    from src.core.gong_client import AsyncGongClient

    # Initialize configuration
    print("🔧 Initializing configuration...")
    config = Config()

    if not config.validate():
        print("❌ Configuration incomplete. Please check your .env file.")
        return 1

    print(f"✓ Config loaded")

    # Get call ID if not provided
    if not call_id:
        # Initialize database to get a call ID
        db_path = config.SQLITE_DB_PATH
        print(f"\n🗄️  Connecting to database: {db_path}")
        db = init_database(db_path, reset=False)
        repository = Repository(db.conn)

        # Get a single call ID
        query = "SELECT call_id FROM calls ORDER BY call_date DESC LIMIT 1"
        cursor = repository.conn.execute(query)
        row = cursor.fetchone()

        if not row:
            print("❌ No calls found in database")
            return 1

        call_id = row['call_id']
        print(f"✓ Using most recent call ID: {call_id}")
        db.close()
    else:
        print(f"✓ Using provided call ID: {call_id}")

    # Initialize Gong client
    print("\n🌐 Fetching data from Gong...")
    async with AsyncGongClient(
        access_key=config.GONG_ACCESS_KEY,
        secret_key=config.GONG_SECRET_KEY,
        api_url=config.GONG_API_URL,
        internal_domain=config.INTERNAL_DOMAIN,
    ) as gong_client:

        # ===================================================================
        # SECTION 1: FETCH CALL DETAILS
        # ===================================================================
        print("\n" + "=" * 80)
        print("SECTION 1: CALL DETAILS")
        print("=" * 80)

        call_details_payload = {
            "filter": {
                "callIds": [call_id]
            },
            "contentSelector": {
                "exposedFields": {
                    "parties": True,
                }
            }
        }

        print(f"\n📞 Calling: POST /v2/calls/extensive")
        print(f"   Payload: {json.dumps(call_details_payload, indent=2)}")

        call_details_data = await gong_client._api_call(
            "/v2/calls/extensive",
            "POST",
            payload=call_details_payload,
            paginate=False,
        )

        print("\n" + "-" * 80)
        print("CALL DETAILS RESPONSE STRUCTURE")
        print("-" * 80)

        # Print top-level keys
        print(f"\n📋 Top-level keys: {list(call_details_data.keys())}")

        calls = call_details_data.get("calls", [])
        print(f"\n📊 Number of calls: {len(calls)}")

        if calls:
            call = calls[0]
            print(f"\n📄 Call object keys: {list(call.keys())}")

            # Show metadata
            metadata = call.get("metaData", {}) or call.get("metadata", {})
            if metadata:
                print(f"\n📝 Metadata keys: {list(metadata.keys())}")
                print(f"\n   Call metadata:")
                print(json.dumps(metadata, indent=2)[:1000])

            # Show parties (IMPORTANT - this has speaker info)
            parties = call.get("parties", [])
            print(f"\n👥 Number of parties: {len(parties)}")

            if parties:
                print(f"\n   First party keys: {list(parties[0].keys())}")
                print(f"\n   All parties:")
                for i, party in enumerate(parties, 1):
                    print(f"\n   Party {i}:")
                    print(json.dumps(party, indent=2))

            # Show full call structure (truncated)
            print("\n" + "-" * 80)
            print("FULL CALL STRUCTURE (first 2000 chars)")
            print("-" * 80)
            print(json.dumps(call, indent=2)[:2000])
            print("\n... (truncated)")

        # ===================================================================
        # SECTION 2: FETCH TRANSCRIPT
        # ===================================================================
        print("\n\n" + "=" * 80)
        print("SECTION 2: TRANSCRIPT")
        print("=" * 80)

        # Fetch transcript - call the API directly to get raw response
        payload = {
            "filter": {
                "callIds": [call_id]
            }
        }

        print(f"\n📝 Calling: POST /v2/calls/transcript")
        print(f"   Payload: {json.dumps(payload, indent=2)}")

        data = await gong_client._api_call(
            "/v2/calls/transcript",
            "POST",
            payload=payload,
            paginate=False,
        )

        print("\n" + "=" * 80)
        print("RAW API RESPONSE STRUCTURE")
        print("=" * 80)

        # Print top-level keys
        print(f"\n📋 Top-level keys: {list(data.keys())}")

        # Get transcript list
        transcript_list = data.get("callTranscripts", []) or data.get("transcripts", [])
        print(f"\n📊 Number of transcripts: {len(transcript_list)}")

        if transcript_list:
            transcript = transcript_list[0]

            print(f"\n📄 Transcript object keys: {list(transcript.keys())}")
            print(f"\n   Call ID: {transcript.get('callId')}")

            # Check for transcript segments
            segments = transcript.get("sentences") or transcript.get("transcript", [])
            print(f"\n   Number of segments: {len(segments)}")

            if segments:
                print(f"\n📝 First segment structure:")
                first_segment = segments[0]
                print(f"   Segment keys: {list(first_segment.keys())}")
                print(f"\n   Full first segment:")
                print(json.dumps(first_segment, indent=2)[:1000])  # Limit output

                # Check if there's speaker metadata
                speaker_id = first_segment.get("speakerId")
                print(f"\n   Speaker ID: {speaker_id}")

                # Check for speaker metadata in segment
                if "speaker" in first_segment:
                    print(f"\n   ✓ Speaker metadata found in segment!")
                    print(f"   Speaker object: {json.dumps(first_segment.get('speaker'), indent=2)}")
                else:
                    print(f"\n   ⚠️  No 'speaker' field in segment")

                # Show a few sentences
                sentences = first_segment.get("sentences", [])
                print(f"\n   Number of sentences in first segment: {len(sentences)}")

                if sentences:
                    print(f"\n   First sentence structure:")
                    print(f"   Sentence keys: {list(sentences[0].keys())}")
                    print(f"\n   Sample sentences (first 3):")
                    for i, sentence in enumerate(sentences[:3], 1):
                        text = sentence.get("text", "")
                        print(f"   {i}. {text[:100]}")

            # Check if there's a speakers array at transcript level
            if "speakers" in transcript:
                print(f"\n👥 Speakers array found at transcript level!")
                speakers = transcript.get("speakers", [])
                print(f"   Number of speakers: {len(speakers)}")
                if speakers:
                    print(f"\n   First speaker:")
                    print(json.dumps(speakers[0], indent=2))
            else:
                print(f"\n   ⚠️  No 'speakers' array at transcript level")

            # Print full structure (truncated) for reference
            print("\n" + "=" * 80)
            print("FULL TRANSCRIPT STRUCTURE (first 2000 chars)")
            print("=" * 80)
            print(json.dumps(transcript, indent=2)[:2000])
            print("\n... (truncated)")

    print("\n✅ Done!")
    return 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Inspect Gong transcript JSON structure"
    )
    parser.add_argument(
        "call_id",
        nargs="?",
        help="Call ID to fetch (optional - uses most recent if not provided)"
    )

    args = parser.parse_args()

    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(fetch_and_inspect(args.call_id))


if __name__ == "__main__":
    sys.exit(main())
