#!/usr/bin/env python3
"""
Re-classify calls currently marked as "trial" stage using updated classification criteria.

This script:
1. Loads all calls currently in "trial" stage
2. Re-runs stage classification with the new, stricter criteria
3. Updates the database if the stage changed
4. Reports what changed

Usage:
    python reclassify_trial_calls.py                    # Dry run (preview changes)
    python reclassify_trial_calls.py --apply            # Apply changes to database
    python reclassify_trial_calls.py --apply --verbose  # Apply with detailed output
"""

import argparse
import sys
from pathlib import Path
from collections import defaultdict

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core import Config, LLMClient
from src.data import Database, init_database, Repository
from src.services.stage_classifier import StageClassifier


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Re-classify trial calls with updated criteria")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes to database (default is dry-run)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed output for each call",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of calls to process (for testing)",
    )

    args = parser.parse_args()

    # Initialize configuration
    print("🔧 Initializing configuration...")
    config = Config()

    if not config.validate():
        print("\n❌ Configuration incomplete. Please check your .env file.")
        return 1

    print(f"   ✓ Config loaded")

    # Initialize database
    db_path = config.SQLITE_DB_PATH
    print(f"\n🗄️  Connecting to database: {db_path}")
    db = init_database(db_path, reset=False)
    repository = Repository(db.conn)

    # Initialize LLM client
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

    # Initialize stage classifier
    classifier = StageClassifier(llm_client)

    # Load all trial calls
    print("\n🔍 Loading calls currently in 'trial' stage...")
    query = """
        SELECT * FROM calls
        WHERE primary_stage = 'trial'
        ORDER BY call_date DESC
    """
    cursor = repository.conn.execute(query)
    trial_calls = cursor.fetchall()

    if not trial_calls:
        print("   ℹ️  No trial calls found in database")
        return 0

    print(f"   ✓ Found {len(trial_calls)} trial calls")

    if args.limit:
        trial_calls = trial_calls[:args.limit]
        print(f"   → Processing first {len(trial_calls)} calls (limit applied)")

    # Load transcripts from Gong
    print("\n📝 Loading transcripts from Gong...")
    from src.core import GongClient

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

    call_ids = [row['call_id'] for row in trial_calls]
    try:
        transcripts = gong_client.get_transcripts(call_ids)
        print(f"   ✓ Fetched {len(transcripts)} transcripts")
    except Exception as e:
        print(f"   ❌ Failed to fetch transcripts: {e}")
        return 1

    # Process each call
    print("\n" + "="*70)
    if args.apply:
        print("🔄 RE-CLASSIFYING TRIAL CALLS (APPLYING CHANGES)")
    else:
        print("🔍 RE-CLASSIFYING TRIAL CALLS (DRY RUN - NO CHANGES)")
    print("="*70)

    changes = defaultdict(int)
    unchanged = 0
    failed = 0

    for i, call_row in enumerate(trial_calls, 1):
        call = repository._row_to_call(call_row)
        call_id = call.call_id
        old_stage = call.primary_stage

        if args.verbose:
            print(f"\n[{i}/{len(trial_calls)}] Call ID: {call_id}")
            print(f"   Title: {call.call_title[:60]}")
            print(f"   Date: {call.call_date.strftime('%Y-%m-%d')}")
            print(f"   Current stage: {old_stage}")

        # Get transcript
        transcript = transcripts.get(call_id, "")
        if not transcript:
            print(f"   ⚠️  No transcript available, skipping...")
            failed += 1
            continue

        try:
            # Re-classify
            result = classifier.classify_stage(transcript, call.call_title)
            new_stage = result.primary_stage

            if args.verbose:
                print(f"   New classification: {new_stage} (confidence: {result.confidence:.2f})")
                if result.reasoning:
                    print(f"   Reasoning: {result.reasoning}")

            # Check if changed
            if new_stage != old_stage:
                changes[f"{old_stage} → {new_stage}"] += 1

                if args.verbose:
                    print(f"   🔄 CHANGED: {old_stage} → {new_stage}")

                # Update database if applying
                if args.apply:
                    repository.conn.execute("""
                        UPDATE calls
                        SET primary_stage = ?,
                            secondary_stage = ?,
                            stage_confidence = ?,
                            updated_at = datetime('now')
                        WHERE call_id = ?
                    """, (new_stage, result.secondary_stage, result.confidence, call_id))
                    repository.conn.commit()

                    if args.verbose:
                        print(f"   ✓ Database updated")

            else:
                unchanged += 1
                if args.verbose:
                    print(f"   ✓ No change (still {old_stage})")

        except Exception as e:
            print(f"   ❌ Error re-classifying call: {e}")
            failed += 1
            continue

    # Summary
    print("\n" + "="*70)
    print("📊 SUMMARY")
    print("="*70)

    total_changed = sum(changes.values())

    if args.apply:
        print(f"✅ Changes Applied to Database:")
    else:
        print(f"🔍 Changes Preview (Dry Run):")

    print(f"\n  📝 Total calls processed: {len(trial_calls)}")
    print(f"  🔄 Calls changed: {total_changed}")
    print(f"  ✓ Calls unchanged: {unchanged}")
    if failed > 0:
        print(f"  ❌ Calls failed: {failed}")

    if changes:
        print(f"\n  Stage Changes:")
        for change, count in sorted(changes.items()):
            print(f"    • {change}: {count}")

    if not args.apply and total_changed > 0:
        print("\n" + "="*70)
        print("⚠️  DRY RUN MODE - No changes were made to the database")
        print("   Run with --apply to apply these changes")
        print("="*70)

    db.close()
    print("\n✅ Done!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
