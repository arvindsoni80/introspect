#!/usr/bin/env python3
"""
Generate question themes from extracted questions.

Aggregates questions by persona, uses LLM to generate themes,
and stores results in question_themes tables.
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict, Counter

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core import Config, LLMClient
from src.data import Database, Repository
from src.services import ThemeGenerator


def normalize_question(q: str) -> str:
    """Normalize question for grouping."""
    return q.lower().strip().rstrip('?').strip()


def aggregate_questions_by_persona(repo: Repository, days: int = 30, segment: str = None, stage: str = None):
    """
    Aggregate all questions grouped by persona.

    Returns:
        Dict mapping persona -> list of {question, frequency, call_ids}
    """
    # Build query
    query = """
        SELECT
            cp.persona,
            cp.speaker_questions,
            c.call_id
        FROM call_participants cp
        JOIN calls c ON cp.call_id = c.call_id
        JOIN accounts a ON c.account_id = a.id
        WHERE cp.affiliation = 'External'
          AND cp.speaker_questions IS NOT NULL
          AND cp.question_count > 0
          AND cp.persona IS NOT NULL
          AND c.call_date >= ?
    """

    params = [(datetime.now() - timedelta(days=days)).isoformat()]

    if segment:
        query += " AND a.primary_segment = ?"
        params.append(segment)

    if stage:
        query += " AND c.primary_stage = ?"
        params.append(stage)

    cursor = repo.conn.execute(query, params)
    rows = cursor.fetchall()

    # Aggregate questions by persona
    questions_by_persona = defaultdict(lambda: defaultdict(lambda: {
        'original': None,
        'count': 0,
        'call_ids': set()
    }))

    for row in rows:
        persona = row['persona']
        call_id = row['call_id']

        # Parse questions JSON
        try:
            questions = json.loads(row['speaker_questions']) if row['speaker_questions'] else []
        except json.JSONDecodeError:
            continue

        for question in questions:
            normalized = normalize_question(question)

            # Store original (first occurrence)
            if questions_by_persona[persona][normalized]['original'] is None:
                questions_by_persona[persona][normalized]['original'] = question

            # Increment count
            questions_by_persona[persona][normalized]['count'] += 1

            # Add call ID
            questions_by_persona[persona][normalized]['call_ids'].add(call_id)

    # Convert to list format
    result = {}
    for persona, questions_map in questions_by_persona.items():
        questions_list = []
        for normalized, data in questions_map.items():
            questions_list.append({
                'question': data['original'],
                'frequency': data['count'],
                'call_ids': list(data['call_ids'])
            })

        # Sort by frequency
        questions_list.sort(key=lambda x: x['frequency'], reverse=True)
        result[persona] = questions_list

    return result


def main():
    """Generate themes for all personas."""
    parser = argparse.ArgumentParser(
        description='Generate question themes from extracted questions'
    )
    parser.add_argument('--days', type=int, default=30,
                       help='Number of days to look back (default: 30)')
    parser.add_argument('--segment', type=str, default=None,
                       help='Filter by segment (e.g., enterprise)')
    parser.add_argument('--stage', type=str, default=None,
                       help='Filter by stage (e.g., discovery)')
    parser.add_argument('--num-themes', type=int, default=6,
                       help='Target number of themes per persona (default: 6)')
    parser.add_argument('--skip-consolidation', action='store_true',
                       help='Skip automatic theme consolidation after generation')

    args = parser.parse_args()

    print("=" * 70)
    print("GENERATE QUESTION THEMES")
    print("=" * 70)
    print()
    print(f"Configuration:")
    print(f"  Lookback: {args.days} days")
    if args.segment:
        print(f"  Segment: {args.segment}")
    if args.stage:
        print(f"  Stage: {args.stage}")
    print(f"  Target themes per persona: {args.num_themes}")
    print()

    # Initialize
    config = Config()
    db = Database(config.SQLITE_DB_PATH)
    db.connect()
    repo = Repository(db.conn)

    # Check if tables exist
    cursor = repo.conn.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='question_themes'
    """)
    if not cursor.fetchone():
        print("❌ Table 'question_themes' does not exist!")
        print("   Run: python scripts/migrate_add_question_themes.py first")
        return 1

    # Initialize LLM client
    try:
        llm_client = LLMClient(
            anthropic_api_key=config.LLM_API_KEY,
            model=config.LLM_MODEL
        )
        print("✓ LLM client initialized")
    except Exception as e:
        print(f"❌ Failed to initialize LLM client: {e}")
        return 1

    theme_generator = ThemeGenerator(
        llm_client,
        repository=repo,
        auto_consolidate=not args.skip_consolidation
    )
    consolidation_status = "enabled" if not args.skip_consolidation else "disabled"
    print(f"✓ Theme generator initialized (auto-consolidation: {consolidation_status})")
    print()

    # Aggregate questions by persona
    print("🔍 Aggregating questions by persona...")
    questions_by_persona = aggregate_questions_by_persona(
        repo,
        days=args.days,
        segment=args.segment,
        stage=args.stage
    )

    if not questions_by_persona:
        print("⚠️  No questions found. Exiting.")
        return 0

    for persona, questions in questions_by_persona.items():
        print(f"  ✓ {persona}: {len(questions)} unique questions")
    print()

    # Generate themes for each persona
    print("=" * 70)
    print("GENERATING THEMES")
    print("=" * 70)
    print()

    total_themes = 0

    for persona in ['Decision Maker', 'Influencer', 'User']:
        questions = questions_by_persona.get(persona, [])

        if not questions:
            print(f"⏭️  {persona}: No questions, skipping")
            print()
            continue

        print(f"🎭 {persona}")
        print(f"  Questions: {len(questions)}")
        print(f"  Generating {args.num_themes} themes...")

        # Clear existing themes for this persona before starting
        repo.conn.execute("DELETE FROM question_themes WHERE persona = ?", (persona,))
        repo.conn.commit()
        print(f"  🗑️  Cleared existing themes for {persona}")

        try:
            # Generate themes (batching and DB storage handled internally)
            themes_data = theme_generator.generate_themes(
                questions,
                persona,
                num_themes=args.num_themes
            )

            themes = themes_data.get('themes', [])
            if not themes:
                print(f"  ⚠️  No themes generated")
                print()
                continue

            print(f"  ✅ Generated and stored {len(themes)} themes:")
            for theme in themes:
                theme_name = theme.get('theme_name', 'Untitled')
                q_count = len(theme.get('questions', []))
                print(f"    • {theme_name} ({q_count} questions)")

            total_themes += len(themes)

        except Exception as e:
            print(f"  ❌ Error: {e}")
            import traceback
            traceback.print_exc()

        print()

    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  ✅ Total themes generated: {total_themes}")
    print(f"  📊 Personas processed: {len([p for p in questions_by_persona if questions_by_persona[p]])}")
    if not args.skip_consolidation:
        print(f"  🔄 Theme consolidation: Automatic (ran after each persona)")
    else:
        print(f"  ⏭️  Theme consolidation: Skipped (use --skip-consolidation to enable)")
    print()
    print("💡 Next steps:")
    print("   • View themes: streamlit run streamlit_app/app.py → Persona page")
    if args.skip_consolidation:
        print("   • Consolidate themes: python scripts/consolidate_question_themes.py")

    db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
