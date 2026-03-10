#!/usr/bin/env python3
"""
View generated question themes to analyze categorization quality.

Shows themes by persona with question counts and sample questions.
"""

import sys
import json
import argparse
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core import Config
from src.data import Database, Repository


def view_themes(persona_filter=None):
    """Display all generated themes grouped by persona."""
    config = Config()
    db = Database(config.SQLITE_DB_PATH)
    db.connect()
    repo = Repository(db.conn)

    print("=" * 80)
    print("GENERATED QUESTION THEMES")
    print("=" * 80)
    print()

    if persona_filter:
        personas = [persona_filter]
    else:
        personas = ['Decision Maker', 'Influencer', 'User']

    for persona in personas:
        print(f"\n{'=' * 80}")
        print(f"🎭 {persona}")
        print(f"{'=' * 80}\n")

        # Get themes for this persona
        cursor = repo.conn.execute("""
            SELECT
                id,
                theme_name,
                theme_description,
                suggested_collateral,
                question_count,
                last_generated
            FROM question_themes
            WHERE persona = ?
            ORDER BY question_count DESC
        """, (persona,))

        themes = cursor.fetchall()

        if not themes:
            print(f"  No themes generated for {persona}\n")
            continue

        print(f"  Total themes: {len(themes)}\n")

        for i, theme_row in enumerate(themes, 1):
            theme_id = theme_row['id']
            theme_name = theme_row['theme_name']
            theme_desc = theme_row['theme_description']
            q_count = theme_row['question_count']

            try:
                collateral = json.loads(theme_row['suggested_collateral']) if theme_row['suggested_collateral'] else []
            except:
                collateral = []

            print(f"  {i}. {theme_name}")
            print(f"     Questions: {q_count}")
            if theme_desc:
                print(f"     Description: {theme_desc}")

            # Get top 3 questions for this theme
            q_cursor = repo.conn.execute("""
                SELECT question_original, frequency
                FROM question_theme_assignments
                WHERE theme_id = ?
                ORDER BY frequency DESC
                LIMIT 3
            """, (theme_id,))

            questions = q_cursor.fetchall()
            if questions:
                print(f"     Top questions:")
                for q_row in questions:
                    q_text = q_row['question_original']
                    freq = q_row['frequency']
                    # Truncate long questions
                    if len(q_text) > 80:
                        q_text = q_text[:77] + "..."
                    print(f"       • {q_text} ({freq}x)")

            if collateral:
                print(f"     Suggested collateral: {', '.join(collateral[:2])}")

            print()

    # Analysis (only show cross-persona analysis if viewing all personas)
    if not persona_filter:
        print("\n" + "=" * 80)
        print("ANALYSIS")
        print("=" * 80)
        print()

        # Check for similar theme names across personas
        all_themes = {}
        for persona in personas:
            cursor = repo.conn.execute("""
                SELECT theme_name, question_count
                FROM question_themes
                WHERE persona = ?
            """, (persona,))

            for row in cursor.fetchall():
                theme_name = row['theme_name']
                if theme_name not in all_themes:
                    all_themes[theme_name] = []
                all_themes[theme_name].append({
                    'persona': persona,
                    'count': row['question_count']
                })

        # Show themes that appear in multiple personas
        print("Themes appearing in multiple personas:")
        multi_persona_themes = {k: v for k, v in all_themes.items() if len(v) > 1}
        if multi_persona_themes:
            for theme_name, personas_list in multi_persona_themes.items():
                persona_str = ", ".join([f"{p['persona']} ({p['count']}q)" for p in personas_list])
                print(f"  • {theme_name}")
                print(f"    → {persona_str}")
        else:
            print("  None (all themes are persona-specific)")

        print()

        # Show similar theme names (potential duplicates)
        print("Potentially similar/overlapping themes:")
        theme_names = list(all_themes.keys())
        found_similar = False

        for i, name1 in enumerate(theme_names):
            for name2 in theme_names[i+1:]:
                # Check for similar words
                words1 = set(name1.lower().split())
                words2 = set(name2.lower().split())
                overlap = words1.intersection(words2)

                if len(overlap) >= 2:  # At least 2 words in common
                    found_similar = True
                    personas1 = [p['persona'] for p in all_themes[name1]]
                    personas2 = [p['persona'] for p in all_themes[name2]]
                    print(f"  • '{name1}' ({', '.join(personas1)})")
                    print(f"    vs")
                    print(f"    '{name2}' ({', '.join(personas2)})")
                    print(f"    Common words: {', '.join(overlap)}")
                    print()

        if not found_similar:
            print("  None detected")

    db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='View generated question themes by persona'
    )
    parser.add_argument(
        '--persona',
        choices=['Decision Maker', 'Influencer', 'User'],
        help='Filter by specific persona (default: show all)'
    )

    args = parser.parse_args()
    view_themes(persona_filter=args.persona)
