#!/usr/bin/env python3
"""
Extract speaker questions from call transcripts.

Focuses on:
- Discovery stage calls
- Enterprise and mid-enterprise segments
- Last 30 days
- External participants (customers) only

This script can be run standalone for testing, and the logic can be
integrated into the main call processing pipeline later.
"""

import sys
import json
import argparse
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core import Config, GongClient, LLMClient
from src.data import Database, Repository
from src.services import QuestionExtractor


def get_filtered_calls(repo: Repository, stage: str, segments: list, days: int = 30):
    """
    Get calls matching our criteria:
    - Specified stage
    - Specified segments
    - Last N days

    Args:
        repo: Repository instance
        stage: Stage to filter by (e.g., 'discovery')
        segments: List of segments to filter by (e.g., ['enterprise'])
        days: Number of days to look back

    Returns:
        List of call objects
    """
    # Calculate date threshold
    date_threshold = datetime.now() - timedelta(days=days)

    # Get all calls from last N days
    query = """
        SELECT c.* FROM calls c
        JOIN accounts a ON c.account_id = a.id
        WHERE c.primary_stage = ?
        AND c.call_date >= ?
        AND a.primary_segment IN ({})
        ORDER BY c.call_date DESC
    """.format(','.join(['?' for _ in segments]))

    params = [stage, date_threshold.isoformat()] + segments

    cursor = repo.conn.execute(query, params)
    rows = cursor.fetchall()

    calls = []
    for row in rows:
        call = repo._row_to_call(row)
        calls.append(call)

    return calls


def get_call_transcript(gong_client: GongClient, call_id: str) -> str:
    """
    Fetch transcript for a call.

    Args:
        gong_client: Gong API client
        call_id: Call ID

    Returns:
        Transcript text
    """
    try:
        transcripts = gong_client.get_transcripts([call_id])
        return transcripts.get(call_id, "")
    except Exception as e:
        print(f"  ⚠️  Failed to fetch transcript: {e}")
        return ""


def extract_and_store_questions(
    call,
    transcript: str,
    repo: Repository,
    extractor: QuestionExtractor
):
    """
    Extract questions from transcript and store in database.

    Args:
        call: Call object
        transcript: Call transcript
        repo: Repository instance
        extractor: QuestionExtractor instance
    """
    # Get participants for this call
    participants = repo.get_call_participants(call.call_id)

    if not participants:
        print(f"  ⚠️  No participants found")
        return 0

    # Extract questions
    print(f"  → Extracting questions from {len(participants)} participants...")
    questions_by_speaker = extractor.extract_questions_for_call(transcript, participants)

    if not questions_by_speaker:
        print(f"  ℹ️  No questions extracted")
        return 0

    # Store in database and display questions
    total_questions = 0
    all_questions = []

    for speaker_id, questions in questions_by_speaker.items():
        if not questions:
            continue

        participant = participants.get(speaker_id, {})
        name = participant.get('name', 'Unknown')
        title = participant.get('title', '')
        question_count = len(questions)
        total_questions += question_count

        print(f"  ✓ {name} ({title}): {question_count} questions")

        # Collect questions for display
        for q in questions:
            all_questions.append((name, title, q))

        # Format for storage
        questions_json = extractor.format_questions_for_storage(questions)

        # Update database
        try:
            repo.conn.execute("""
                UPDATE call_participants
                SET speaker_questions = ?,
                    question_count = ?
                WHERE call_id = ? AND speaker_id = ?
            """, (questions_json, question_count, call.call_id, speaker_id))
        except Exception as e:
            print(f"  ⚠️  Failed to update database: {e}")
            continue

    # Display first 10 questions
    if all_questions:
        print(f"\n  📋 Sample Questions (showing {min(10, len(all_questions))} of {len(all_questions)}):")
        for i, (name, title, question) in enumerate(all_questions[:10], 1):
            # Truncate long questions to fit on one line
            display_q = question if len(question) <= 100 else question[:97] + "..."
            print(f"     {i}. [{name}] {display_q}")

    repo.conn.commit()
    return total_questions


def main():
    """Main extraction script."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description='Extract speaker questions from call transcripts',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Enterprise segment, discovery stage, last 7 days
  python scripts/extract_speaker_questions.py --stage discovery --segments enterprise --days 7

  # Multiple segments
  python scripts/extract_speaker_questions.py --segments enterprise mid-enterprise --days 30
        """
    )
    parser.add_argument('--stage', default='discovery',
                       help='Stage to filter by (default: discovery)')
    parser.add_argument('--segments', nargs='+', default=['enterprise', 'mid-enterprise'],
                       help='Segments to filter by (default: enterprise mid-enterprise)')
    parser.add_argument('--days', type=int, default=30,
                       help='Number of days to look back (default: 30)')
    parser.add_argument('--limit', type=int, default=None,
                       help='Limit number of calls to process (useful for testing)')
    parser.add_argument('--force', action='store_true',
                       help='Force re-extraction even if questions already exist')

    args = parser.parse_args()

    print("=" * 70)
    print("EXTRACT SPEAKER QUESTIONS")
    print("=" * 70)
    print()
    print(f"Configuration:")
    print(f"  Stage: {args.stage}")
    print(f"  Segments: {', '.join(args.segments)}")
    print(f"  Lookback: {args.days} days")
    print()

    # Initialize
    print("🔧 Initializing...")
    config = Config()

    if not config.validate():
        print("❌ Configuration incomplete. Check your .env file.")
        return 1

    db = Database(config.SQLITE_DB_PATH)
    db.connect()
    repo = Repository(db.conn)

    # Initialize clients
    try:
        gong_client = GongClient(
            access_key=config.GONG_ACCESS_KEY,
            secret_key=config.GONG_SECRET_KEY,
            api_url=config.GONG_API_URL,
            internal_domain=config.INTERNAL_DOMAIN,
            lookback_days=args.days,
        )
        print("  ✓ Gong client initialized")
    except Exception as e:
        print(f"  ❌ Failed to initialize Gong client: {e}")
        db.close()
        return 1

    try:
        llm_client = LLMClient(
            anthropic_api_key=config.LLM_API_KEY,
            model=config.LLM_MODEL,
        )
        print("  ✓ LLM client initialized")
    except Exception as e:
        print(f"  ❌ Failed to initialize LLM client: {e}")
        db.close()
        return 1

    extractor = QuestionExtractor(llm_client)
    print("  ✓ Question extractor initialized")
    print()

    # Get filtered calls
    print("🔍 Fetching calls...")
    calls = get_filtered_calls(repo, stage=args.stage, segments=args.segments, days=args.days)
    print(f"  ✓ Found {len(calls)} calls matching criteria")

    # Apply limit if specified
    if args.limit and len(calls) > args.limit:
        calls = calls[:args.limit]
        print(f"  ℹ️  Limiting to first {args.limit} calls")
    print()

    if not calls:
        print("⚠️  No calls found. Exiting.")
        db.close()
        return 0

    # Process each call
    print("=" * 70)
    print("PROCESSING CALLS")
    print("=" * 70)
    print()

    processed = 0
    failed = 0
    total_questions_extracted = 0

    for i, call in enumerate(calls, 1):
        print(f"[{i}/{len(calls)}] {call.call_id}")
        print(f"  Title: {call.call_title[:60]}...")
        print(f"  Date: {call.call_date.strftime('%Y-%m-%d')}")

        try:
            # Check if already processed (skip unless --force)
            if not args.force:
                cursor = repo.conn.execute("""
                    SELECT COUNT(*) FROM call_participants
                    WHERE call_id = ? AND speaker_questions IS NOT NULL
                """, (call.call_id,))
                already_processed = cursor.fetchone()[0]

                if already_processed > 0:
                    print(f"  ⏭️  Already processed ({already_processed} participants with questions)")
                    processed += 1
                    continue

            # Get transcript
            transcript = get_call_transcript(gong_client, call.call_id)
            if not transcript:
                print(f"  ⚠️  No transcript available, skipping")
                failed += 1
                continue

            # Get enriched transcript with speaker labels
            enriched_transcript = repo.enrich_transcript_with_participants(
                call.call_id,
                transcript
            )

            # Extract and store questions
            questions_count = extract_and_store_questions(
                call,
                enriched_transcript,
                repo,
                extractor
            )

            total_questions_extracted += questions_count
            processed += 1
            print(f"  ✅ Extracted {questions_count} total questions")

        except Exception as e:
            print(f"  ❌ Error: {e}")
            import traceback
            traceback.print_exc()
            failed += 1

        print()

    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  ✅ Processed: {processed}")
    print(f"  ❌ Failed: {failed}")
    print(f"  📊 Total questions extracted: {total_questions_extracted}")
    print(f"  💰 Estimated cost: ${(processed * 0.02):.2f}")  # Rough estimate
    print()

    db.close()
    print("✅ Done!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
