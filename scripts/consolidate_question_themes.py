#!/usr/bin/env python3
"""
Consolidate existing question themes to merge duplicates/similar themes.

NOTE: Consolidation runs AUTOMATICALLY at the end of generate_question_themes.py
This script is only needed if you want to:
  1. Re-consolidate themes without regenerating (faster)
  2. Consolidate themes that were generated with --skip-consolidation
  3. Test different consolidation strategies
"""

import sys
import argparse
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core import Config, LLMClient
from src.data import Database, Repository
from src.services import ThemeGenerator


def main():
    """Consolidate themes for specified personas."""
    parser = argparse.ArgumentParser(
        description='Consolidate duplicate/similar question themes'
    )
    parser.add_argument(
        '--persona',
        choices=['Decision Maker', 'Influencer', 'User'],
        help='Consolidate only this persona (default: all personas)'
    )
    parser.add_argument(
        '--min-themes',
        type=int,
        default=10,
        help='Only consolidate if theme count exceeds this (default: 10)'
    )

    args = parser.parse_args()

    print("=" * 70)
    print("CONSOLIDATE QUESTION THEMES")
    print("=" * 70)
    print()

    # Initialize
    config = Config()
    db = Database(config.SQLITE_DB_PATH)
    db.connect()
    repo = Repository(db.conn)

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

    theme_generator = ThemeGenerator(llm_client, repository=repo)
    print("✓ Theme generator initialized")
    print()

    # Determine which personas to process
    if args.persona:
        personas = [args.persona]
    else:
        personas = ['Decision Maker', 'Influencer', 'User']

    print("=" * 70)
    print("CONSOLIDATING THEMES")
    print("=" * 70)
    print()

    total_before = 0
    total_after = 0

    for persona in personas:
        print(f"🔍 Loading themes for {persona}...")

        # Load existing themes
        themes = theme_generator._load_existing_themes_from_db(persona)
        print(f"   Loaded {len(themes)} themes from database")

        if not themes:
            print(f"⏭️  {persona}: No themes found, skipping")
            print()
            continue

        print(f"\n🎭 {persona}")
        print(f"  Current themes: {len(themes)}")

        if len(themes) <= args.min_themes:
            print(f"  ℹ️  Theme count ≤ {args.min_themes}, skipping consolidation")
            print()
            total_before += len(themes)
            total_after += len(themes)
            continue

        total_before += len(themes)
        print(f"  Starting consolidation (min threshold: {args.min_themes})...")

        try:
            # Run consolidation
            print(f"  Calling _consolidate_themes()...")
            consolidated = theme_generator._consolidate_themes(persona, themes)
            print(f"  Consolidation returned {len(consolidated)} themes")

            total_after += len(consolidated)

            print()

        except Exception as e:
            print(f"  ❌ Error during consolidation: {e}")
            import traceback
            traceback.print_exc()
            total_after += len(themes)  # Keep original count

        print()

    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Before consolidation: {total_before} themes")
    print(f"  After consolidation:  {total_after} themes")
    print(f"  Reduction: {total_before - total_after} themes ({100 * (total_before - total_after) / total_before:.1f}%)" if total_before > 0 else "")
    print()
    print("💡 Next: View consolidated themes")
    print("   python scripts/view_generated_themes.py")

    db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
