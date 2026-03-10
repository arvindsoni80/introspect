#!/usr/bin/env python3
"""
Find calls missing stage-specific scores and evaluate them.

This script:
1. Finds discovery calls without MEDDPICC scores
2. Finds trial calls without TRIAL scores
3. Finds negotiation calls without CLOSE scores
4. Fetches transcripts and evaluates with the correct framework
5. Stores the scores in the database

Usage:
    python evaluate_missing_scores.py                    # Dry run (preview what needs evaluation)
    python evaluate_missing_scores.py --apply            # Apply evaluations to database
    python evaluate_missing_scores.py --apply --verbose  # Apply with detailed output
    python evaluate_missing_scores.py --stage discovery  # Only process discovery calls
"""

import argparse
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core import Config, LLMClient, GongClient
from src.data import Database, init_database, Repository
from src.domain import CallMEDDPICCScores, CallTrialScores, CallCloseScores
from src.services.evaluators import MEDDPICCEvaluator, TrialEvaluator, CloseEvaluator


def find_missing_scores(repo: Repository, stage: str = None):
    """Find calls missing stage-specific scores."""
    missing_by_stage = {
        "discovery": [],
        "trial": [],
        "negotiation": []
    }

    stages_to_check = [stage] if stage else ["discovery", "trial", "negotiation"]

    for check_stage in stages_to_check:
        if check_stage == "discovery":
            # Find discovery calls without MEDDPICC scores
            query = """
                SELECT c.* FROM calls c
                LEFT JOIN call_meddpicc_scores s ON c.call_id = s.call_id
                WHERE c.primary_stage = 'discovery' AND s.call_id IS NULL
                ORDER BY c.call_date DESC
            """
        elif check_stage == "trial":
            # Find trial calls without TRIAL scores
            query = """
                SELECT c.* FROM calls c
                LEFT JOIN call_trial_scores s ON c.call_id = s.call_id
                WHERE c.primary_stage = 'trial' AND s.call_id IS NULL
                ORDER BY c.call_date DESC
            """
        elif check_stage == "negotiation":
            # Find negotiation calls without CLOSE scores
            query = """
                SELECT c.* FROM calls c
                LEFT JOIN call_close_scores s ON c.call_id = s.call_id
                WHERE c.primary_stage = 'negotiation' AND s.call_id IS NULL
                ORDER BY c.call_date DESC
            """
        else:
            continue

        cursor = repo.conn.execute(query)
        rows = cursor.fetchall()
        missing_by_stage[check_stage] = rows

    return missing_by_stage


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Evaluate calls with missing scores")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply evaluations to database (default is dry-run)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed output for each call",
    )
    parser.add_argument(
        "--stage",
        choices=["discovery", "trial", "negotiation"],
        help="Only process calls for this stage",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit number of calls to process per stage (for testing)",
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

    # Initialize evaluators
    meddpicc_evaluator = MEDDPICCEvaluator(llm_client)
    trial_evaluator = TrialEvaluator(llm_client)
    close_evaluator = CloseEvaluator(llm_client)

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

    # Find missing scores
    print("\n🔍 Finding calls with missing scores...")
    missing_by_stage = find_missing_scores(repository, args.stage)

    total_missing = sum(len(calls) for calls in missing_by_stage.values())

    if total_missing == 0:
        print("   ✅ All calls have appropriate scores!")
        return 0

    print(f"\n📊 Missing Scores Summary:")
    for stage, calls in missing_by_stage.items():
        if calls:
            print(f"   • {stage.title()}: {len(calls)} calls")

    # Apply limit if specified
    if args.limit:
        for stage in missing_by_stage:
            missing_by_stage[stage] = missing_by_stage[stage][:args.limit]
        print(f"\n   → Limiting to {args.limit} calls per stage")

    # Process each stage
    print("\n" + "="*70)
    if args.apply:
        print("🔄 EVALUATING MISSING SCORES (APPLYING CHANGES)")
    else:
        print("🔍 EVALUATING MISSING SCORES (DRY RUN - NO CHANGES)")
    print("="*70)

    total_evaluated = 0
    total_failed = 0

    for stage, call_rows in missing_by_stage.items():
        if not call_rows:
            continue

        print(f"\n📝 Processing {stage.title()} calls ({len(call_rows)} calls)...")

        # Collect call IDs for transcript fetching
        call_ids = [row['call_id'] for row in call_rows]

        # Fetch transcripts
        print(f"   Fetching transcripts from Gong...")
        try:
            transcripts = gong_client.get_transcripts(call_ids)
            print(f"   ✓ Fetched {len(transcripts)} transcripts")
        except Exception as e:
            print(f"   ❌ Failed to fetch transcripts: {e}")
            continue

        # Evaluate each call
        for i, call_row in enumerate(call_rows, 1):
            call = repository._row_to_call(call_row)
            call_id = call.call_id

            if args.verbose:
                print(f"\n   [{i}/{len(call_rows)}] Call ID: {call_id}")
                print(f"      Title: {call.call_title[:60]}")
                print(f"      Date: {call.call_date.strftime('%Y-%m-%d')}")

            # Get transcript
            transcript = transcripts.get(call_id, "")
            if not transcript:
                print(f"      ⚠️  No transcript available, skipping...")
                total_failed += 1
                continue

            try:
                # Evaluate based on stage
                if stage == "discovery":
                    if args.verbose:
                        print(f"      → Evaluating MEDDPICC...")

                    scores = meddpicc_evaluator.evaluate(transcript)

                    if args.verbose:
                        print(f"      ✓ Score: {scores.overall_score:.1f}")

                    if args.apply:
                        call_scores = CallMEDDPICCScores(
                            call_id=call.call_id,
                            scores=scores,
                        )
                        repository.create_call_meddpicc_scores(call_scores)
                        if args.verbose:
                            print(f"      ✓ Saved to database")

                elif stage == "trial":
                    if args.verbose:
                        print(f"      → Evaluating TRIAL...")

                    scores = trial_evaluator.evaluate(transcript)

                    if args.verbose:
                        print(f"      ✓ Score: {scores.overall_score:.1f} ({scores.health_interpretation})")

                    if args.apply:
                        call_scores = CallTrialScores(
                            call_id=call.call_id,
                            scores=scores,
                        )
                        repository.create_call_trial_scores(call_scores)
                        if args.verbose:
                            print(f"      ✓ Saved to database")

                elif stage == "negotiation":
                    if args.verbose:
                        print(f"      → Evaluating CLOSE...")

                    scores = close_evaluator.evaluate(transcript)

                    if args.verbose:
                        print(f"      ✓ Score: {scores.overall_score:.1f} ({scores.health_interpretation})")

                    if args.apply:
                        call_scores = CallCloseScores(
                            call_id=call.call_id,
                            scores=scores,
                        )
                        repository.create_call_close_scores(call_scores)
                        if args.verbose:
                            print(f"      ✓ Saved to database")

                total_evaluated += 1

            except Exception as e:
                print(f"      ❌ Error evaluating call: {e}")
                total_failed += 1
                continue

    # Summary
    print("\n" + "="*70)
    print("📊 SUMMARY")
    print("="*70)

    if args.apply:
        print(f"✅ Evaluations Applied to Database:")
    else:
        print(f"🔍 Evaluations Preview (Dry Run):")

    for stage, calls in missing_by_stage.items():
        if calls:
            processed = len(calls) if not args.limit else min(len(calls), args.limit)
            print(f"  • {stage.title()}: {processed} calls evaluated")

    print(f"\n  ✅ Successfully evaluated: {total_evaluated}")
    if total_failed > 0:
        print(f"  ❌ Failed: {total_failed}")

    if not args.apply and total_evaluated > 0:
        print("\n" + "="*70)
        print("⚠️  DRY RUN MODE - No changes were made to the database")
        print("   Run with --apply to save these evaluations")
        print("="*70)

    db.close()
    print("\n✅ Done!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
