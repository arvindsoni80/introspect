#!/usr/bin/env python3
"""Test stage classification for calls from a specific sales segment."""

import argparse
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core import Config, GongClient, LLMClient
from src.data import Database, Repository
from src.services import StageClassifier


def main():
    parser = argparse.ArgumentParser(
        description="Test stage classification for calls from a specific segment"
    )
    parser.add_argument(
        "--segment",
        type=str,
        help="Sales segment to filter by (e.g., 'enterprise', 'smb'). If not specified, uses all segments.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Number of calls to classify (default: 5)",
    )
    parser.add_argument(
        "--rep",
        type=str,
        help="Specific sales rep email to filter by",
    )
    args = parser.parse_args()

    print("🧪 Testing Stage Classification by Segment\n")
    print("=" * 70)

    # Initialize config
    print("\n1. Loading configuration...")
    config = Config()

    # Validate config
    if not config.validate():
        print("\n❌ Configuration incomplete. Please check your .env file.")
        return

    print(f"   ✓ Config loaded")
    print(f"   ✓ Gong API URL: {config.GONG_API_URL}")
    print(f"   ✓ Internal Domain: {config.INTERNAL_DOMAIN}")
    print(f"   ✓ Lookback Days: {config.GONG_LOOKBACK_DAYS}")
    print(f"   ✓ LLM Provider: {config.LLM_PROVIDER}")
    print(f"   ✓ LLM Model: {config.LLM_MODEL}")

    # Load sales reps from database
    print("\n2. Loading sales reps from database...")
    db_path = config.SQLITE_DB_PATH
    db = Database(db_path)
    db.connect()
    repo = Repository(db.conn)

    all_reps = repo.list_sales_reps(active_only=True)
    db.close()

    if not all_reps:
        print("   ⚠️  No sales reps found in database")
        print("   Run: python load_sales_reps.py first")
        return

    # Filter by segment if specified
    if args.segment:
        sales_reps = [
            rep for rep in all_reps
            if rep.segment.lower() == args.segment.lower()
        ]
        if not sales_reps:
            print(f"\n❌ No sales reps found in segment '{args.segment}'")
            print(f"\n   Available segments:")
            segments = sorted(set(rep.segment for rep in all_reps))
            for seg in segments:
                count = sum(1 for r in all_reps if r.segment == seg)
                print(f"      • {seg}: {count} reps")
            return
        print(f"   ✓ Filtered to segment '{args.segment}': {len(sales_reps)} reps")
    else:
        sales_reps = all_reps
        print(f"   ✓ Using all segments: {len(sales_reps)} reps")

    # Filter by specific rep if specified
    if args.rep:
        sales_reps = [rep for rep in sales_reps if rep.email.lower() == args.rep.lower()]
        if not sales_reps:
            print(f"\n❌ Sales rep '{args.rep}' not found")
            return
        print(f"   ✓ Filtered to rep: {args.rep}")

    # Show reps being used
    print(f"\n   Sales reps to fetch calls for:")
    for rep in sorted(sales_reps, key=lambda r: r.email):
        print(f"      • {rep.email} ({rep.segment})")

    sales_rep_emails = [rep.email for rep in sales_reps]

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

    # Initialize LLM client
    print("\n4. Initializing LLM client...")
    try:
        llm_client = LLMClient(
            anthropic_api_key=config.LLM_API_KEY,
            model=config.LLM_MODEL,
        )
        print("   ✓ LLM client initialized")
    except Exception as e:
        print(f"   ❌ Failed to initialize LLM client: {e}")
        return

    # Initialize stage classifier
    print("\n5. Initializing stage classifier...")
    classifier = StageClassifier(llm_client)
    print("   ✓ Stage classifier initialized")

    # Fetch recent calls for sales reps
    print(f"\n6. Fetching calls from last {config.GONG_LOOKBACK_DAYS} days...")
    print("   (Only calls with external participants)")
    print("   (This may take a few seconds...)")
    try:
        calls = gong_client.get_calls_for_sales_reps(sales_rep_emails)
        print(f"   ✓ Fetched {len(calls)} calls")
    except Exception as e:
        print(f"   ❌ Failed to fetch calls: {e}")
        print(f"   Error details: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return

    if not calls:
        print(f"\n⚠️  No calls found in the last {config.GONG_LOOKBACK_DAYS} days")
        print("   Check: python test_fetch_calls.py")
        return

    # Limit to requested number of calls
    calls_to_test = calls[:args.limit]
    print(f"   → Testing with first {len(calls_to_test)} calls")

    # Debug: Check call structure (only on first call)
    if calls_to_test:
        print(f"\n   🔍 Debug - Sample call keys: {list(calls_to_test[0].keys())}")
        meta = calls_to_test[0].get("metaData", {})
        if meta:
            print(f"   🔍 Debug - metaData keys: {list(meta.keys())[:10]}...")  # Show first 10

    # Fetch transcripts for these calls
    print(f"\n7. Fetching transcripts...")
    # Try both "id" and metaData.id
    call_ids = []
    for call in calls_to_test:
        call_id = call.get("id")
        if not call_id:
            # Try in metaData
            meta = call.get("metaData", {})
            call_id = meta.get("id")
        if call_id:
            call_ids.append(call_id)

    if not call_ids:
        print(f"   ❌ Could not extract call IDs from calls")
        print(f"   Debug: First call structure: {calls_to_test[0] if calls_to_test else 'No calls'}")
        return

    print(f"   → Found {len(call_ids)} call IDs")

    try:
        transcripts = gong_client.get_transcripts(call_ids)
        print(f"   ✓ Fetched {len(transcripts)} transcripts")
    except Exception as e:
        print(f"   ❌ Failed to fetch transcripts: {e}")
        import traceback
        traceback.print_exc()
        return

    # Process each call
    print("\n" + "=" * 70)
    print("CLASSIFYING CALLS")
    print("=" * 70)

    successful = 0
    failed = 0

    for i, call in enumerate(calls_to_test, 1):
        print(f"\n📞 Call {i}/{len(calls_to_test)}")
        print("-" * 70)

        # Extract call ID (try both locations)
        call_id = call.get("id")
        meta = call.get("metaData", {})
        if not call_id:
            call_id = meta.get("id", "unknown")

        # Extract basic info
        try:
            print(f"   Call ID: {call_id}")

            # Get title
            title = meta.get("title", "Untitled")
            print(f"   Title: {title}")

            # Get date
            started = meta.get("started", "")
            if started:
                try:
                    call_date = datetime.fromisoformat(started.replace("Z", "+00:00"))
                    print(f"   Date: {call_date.strftime('%Y-%m-%d %H:%M')}")
                except:
                    print(f"   Date: {started}")

            # Get sales rep
            sales_rep_email = call.get("sales_rep_email", "unknown")
            print(f"   Sales Rep: {sales_rep_email}")

            # Get segment
            rep_segment = next((r.segment for r in sales_reps if r.email == sales_rep_email), "unknown")
            print(f"   Segment: {rep_segment}")

            # Get participants
            parties = call.get("parties", [])
            external_count = sum(1 for p in parties if p.get("affiliation") in ("External", "Unknown"))
            print(f"   Participants: {len(parties)} ({external_count} external)")

        except Exception as e:
            print(f"   ⚠️  Could not extract metadata: {e}")

        # Get transcript
        transcript = transcripts.get(call_id, "")

        if not transcript:
            print(f"   ⚠️  No transcript available for this call")
            print(f"   Skipping classification...")
            failed += 1
            continue

        transcript_length = len(transcript)
        print(f"   Transcript: {transcript_length:,} characters")

        # Show snippet
        snippet = transcript[:200].replace("\n", " ")
        print(f"   Preview: {snippet}...")

        # Classify stage
        print(f"\n   → Classifying stage...")
        try:
            result = classifier.classify_stage(transcript, title)

            print(f"\n   ✅ CLASSIFICATION RESULT:")
            print(f"      Primary Stage: {result.primary_stage.upper()}")
            print(f"      Confidence: {result.confidence:.1%}")

            if result.secondary_stage:
                print(f"      Secondary Stage: {result.secondary_stage}")

            if result.reasoning:
                # Show first 150 chars of reasoning
                reasoning = result.reasoning[:150].replace("\n", " ")
                print(f"      Reasoning: {reasoning}...")

            # Color-coded output
            confidence_indicator = "🟢" if result.confidence >= 0.8 else "🟡" if result.confidence >= 0.6 else "🔴"
            print(f"\n      {confidence_indicator} Confidence Level: ", end="")
            if result.confidence >= 0.8:
                print("HIGH")
            elif result.confidence >= 0.6:
                print("MEDIUM")
            else:
                print("LOW")

            successful += 1

        except Exception as e:
            print(f"   ❌ Classification failed: {e}")
            print(f"   Error type: {type(e).__name__}")
            failed += 1

        print()  # Blank line between calls

    # Summary
    print("\n" + "=" * 70)
    print("✅ TEST COMPLETE")
    print("=" * 70)

    if args.segment:
        print(f"\nSegment: {args.segment}")
    if args.rep:
        print(f"Rep: {args.rep}")

    print(f"\nClassified: {successful} calls successfully")
    if failed > 0:
        print(f"Failed/Skipped: {failed} calls")
    print(f"Total calls available: {len(calls)} (last {config.GONG_LOOKBACK_DAYS} days)")

    print("\nNext steps:")
    print("  1. If classifications look good, try processing more calls")
    print("  2. Test full pipeline: python process_calls.py --limit 3")
    print()


if __name__ == "__main__":
    main()
