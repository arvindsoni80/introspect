#!/usr/bin/env python3
"""
Test script to compare scores before and after speaker role identification.

This script:
1. Fetches 10 discovery calls and 10 trial calls from enterprise segment
2. Re-evaluates them with enhanced transcripts (with speaker roles)
3. Compares new scores to existing scores
4. Prints the differences

Usage:
    python test_speaker_role_scoring.py
"""

import sys
from pathlib import Path
from typing import List, Dict

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core import Config, LLMClient, GongClient
from src.data import Database, init_database, Repository
from src.services.evaluators import MEDDPICCEvaluator, TrialEvaluator


def get_test_calls(repo: Repository) -> Dict[str, List]:
    """Get 10 discovery and 10 trial calls from enterprise segment."""

    # Get discovery calls
    discovery_query = """
        SELECT c.* FROM calls c
        JOIN accounts a ON c.account_id = a.id
        WHERE c.primary_stage = 'discovery'
          AND a.primary_segment = 'enterprise'
          AND EXISTS (
              SELECT 1 FROM call_meddpicc_scores s
              WHERE s.call_id = c.call_id
          )
        ORDER BY c.call_date DESC
        LIMIT 10
    """

    cursor = repo.conn.execute(discovery_query)
    discovery_calls = [repo._row_to_call(row) for row in cursor.fetchall()]

    # Get trial calls
    trial_query = """
        SELECT c.* FROM calls c
        JOIN accounts a ON c.account_id = a.id
        WHERE c.primary_stage = 'trial'
          AND a.primary_segment = 'enterprise'
          AND EXISTS (
              SELECT 1 FROM call_trial_scores s
              WHERE s.call_id = c.call_id
          )
        ORDER BY c.call_date DESC
        LIMIT 10
    """

    cursor = repo.conn.execute(trial_query)
    trial_calls = [repo._row_to_call(row) for row in cursor.fetchall()]

    return {
        "discovery": discovery_calls,
        "trial": trial_calls
    }


def main():
    """Main entry point."""
    print("=" * 80)
    print("TESTING SPEAKER ROLE IDENTIFICATION IMPACT ON SCORES")
    print("=" * 80)

    # Initialize configuration
    print("\n🔧 Initializing configuration...")
    config = Config()

    if not config.validate():
        print("\n❌ Configuration incomplete. Please check your .env file.")
        return 1

    print("   ✓ Config loaded")

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

    # Initialize evaluators
    meddpicc_evaluator = MEDDPICCEvaluator(llm_client)
    trial_evaluator = TrialEvaluator(llm_client)

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

    # Get test calls
    print("\n📊 Finding test calls...")
    test_calls = get_test_calls(repository)

    discovery_calls = test_calls["discovery"]
    trial_calls = test_calls["trial"]

    print(f"   ✓ Found {len(discovery_calls)} discovery calls")
    print(f"   ✓ Found {len(trial_calls)} trial calls")

    if not discovery_calls and not trial_calls:
        print("\n⚠️  No test calls found with existing scores.")
        return 0

    # Process discovery calls
    if discovery_calls:
        print("\n" + "=" * 80)
        print("DISCOVERY CALLS (MEDDPICC Scoring)")
        print("=" * 80)

        call_ids = [call.call_id for call in discovery_calls]
        print(f"\n📝 Fetching transcripts with speaker roles...")
        transcripts = gong_client.get_transcripts(call_ids)
        print(f"   ✓ Fetched {len(transcripts)} transcripts")

        for i, call in enumerate(discovery_calls, 1):
            print(f"\n[{i}/{len(discovery_calls)}] {call.call_title[:60]}")
            print(f"   Date: {call.call_date.strftime('%Y-%m-%d')}")
            print(f"   Call ID: {call.call_id}")

            # Get existing score
            existing_scores = repository.get_call_meddpicc_scores(call.call_id)
            if not existing_scores:
                print("   ⚠️  No existing score found, skipping...")
                continue

            old_score = existing_scores.scores.overall_score

            # Get transcript
            transcript = transcripts.get(call.call_id, "")
            if not transcript:
                print("   ⚠️  No transcript available, skipping...")
                continue

            # Show sample of transcript with speaker roles
            lines = transcript.split("\n")[:3]
            print(f"\n   📄 Transcript sample:")
            for line in lines:
                print(f"      {line[:100]}")

            try:
                # Re-evaluate with new transcript
                print(f"\n   🔄 Re-evaluating...")
                new_scores = meddpicc_evaluator.evaluate(transcript)
                new_score = new_scores.overall_score

                # Compare
                diff = new_score - old_score
                arrow = "📈" if diff > 0 else "📉" if diff < 0 else "➡️"

                print(f"\n   {arrow} SCORE COMPARISON:")
                print(f"      Old Score: {old_score:.2f}/5.0")
                print(f"      New Score: {new_score:.2f}/5.0")
                print(f"      Difference: {diff:+.2f}")

                if abs(diff) > 0.3:
                    print(f"      ⚠️  Significant change!")

            except Exception as e:
                print(f"   ❌ Error re-evaluating: {e}")
                continue

    # Process trial calls
    if trial_calls:
        print("\n" + "=" * 80)
        print("TRIAL CALLS (TRIAL Health Scoring)")
        print("=" * 80)

        call_ids = [call.call_id for call in trial_calls]
        print(f"\n📝 Fetching transcripts with speaker roles...")
        transcripts = gong_client.get_transcripts(call_ids)
        print(f"   ✓ Fetched {len(transcripts)} transcripts")

        for i, call in enumerate(trial_calls, 1):
            print(f"\n[{i}/{len(trial_calls)}] {call.call_title[:60]}")
            print(f"   Date: {call.call_date.strftime('%Y-%m-%d')}")
            print(f"   Call ID: {call.call_id}")

            # Get existing score
            existing_scores = repository.get_call_trial_scores(call.call_id)
            if not existing_scores:
                print("   ⚠️  No existing score found, skipping...")
                continue

            old_score = existing_scores.scores.overall_score

            # Get transcript
            transcript = transcripts.get(call.call_id, "")
            if not transcript:
                print("   ⚠️  No transcript available, skipping...")
                continue

            # Show sample of transcript with speaker roles
            lines = transcript.split("\n")[:3]
            print(f"\n   📄 Transcript sample:")
            for line in lines:
                print(f"      {line[:100]}")

            try:
                # Re-evaluate with new transcript
                print(f"\n   🔄 Re-evaluating...")
                new_scores = trial_evaluator.evaluate(transcript)
                new_score = new_scores.overall_score

                # Compare
                diff = new_score - old_score
                arrow = "📈" if diff > 0 else "📉" if diff < 0 else "➡️"

                print(f"\n   {arrow} SCORE COMPARISON:")
                print(f"      Old Score: {old_score:.2f}/5.0")
                print(f"      New Score: {new_score:.2f}/5.0")
                print(f"      Difference: {diff:+.2f}")

                if abs(diff) > 0.3:
                    print(f"      ⚠️  Significant change!")

            except Exception as e:
                print(f"   ❌ Error re-evaluating: {e}")
                continue

    # Summary
    print("\n" + "=" * 80)
    print("✅ TEST COMPLETE")
    print("=" * 80)
    print("\nThis was a dry-run comparison. No database changes were made.")
    print("Review the score differences to assess impact of speaker role identification.")

    db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
