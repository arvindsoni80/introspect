#!/usr/bin/env python3
"""
Backfill persona classifications for existing call participants.

Classifies all participants based on their job title and updates the persona column.
"""

import sys
from pathlib import Path
from collections import Counter

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core import Config
from src.data import Database
from src.services import PersonaClassifier


def backfill_persona():
    """Classify and update persona for all existing participants."""
    config = Config()
    db = Database(config.SQLITE_DB_PATH)
    db.connect()

    print("=" * 70)
    print("BACKFILL PERSONA CLASSIFICATIONS")
    print("=" * 70)
    print()

    try:
        # Check if persona column exists
        cursor = db.conn.execute("PRAGMA table_info(call_participants)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'persona' not in columns:
            print("❌ Column 'persona' does not exist!")
            print("   Run: python scripts/migrate_add_persona.py first")
            return 1

        # Get all participants
        print("🔍 Fetching all participants...")
        cursor = db.conn.execute("""
            SELECT id, name, title, persona
            FROM call_participants
            WHERE affiliation = 'External'
            ORDER BY id
        """)
        participants = cursor.fetchall()

        print(f"  ✓ Found {len(participants)} external participants")
        print()

        if not participants:
            print("⚠️  No external participants found. Exiting.")
            return 0

        # Classify and update
        print("🔄 Classifying participants...")
        print()

        updated = 0
        skipped = 0
        persona_counts = Counter()

        for row in participants:
            participant_id = row['id']
            name = row['name'] or 'Unknown'
            title = row['title'] or ''
            existing_persona = row['persona']

            # Classify
            persona = PersonaClassifier.classify(title)
            persona_counts[persona] += 1

            # Update if different or missing
            if existing_persona != persona:
                db.conn.execute("""
                    UPDATE call_participants
                    SET persona = ?
                    WHERE id = ?
                """, (persona, participant_id))
                updated += 1

                if updated <= 5:  # Show first 5 examples
                    print(f"  ✓ {name} ({title}) → {persona}")
            else:
                skipped += 1

        db.conn.commit()

        # Summary
        print()
        if updated > 5:
            print(f"  ... and {updated - 5} more")
        print()
        print("=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(f"  ✅ Updated: {updated}")
        print(f"  ⏭️  Skipped (already correct): {skipped}")
        print(f"  📊 Total: {len(participants)}")
        print()
        print("📊 Persona Distribution:")
        for persona in ['Decision Maker', 'Influencer', 'User']:
            count = persona_counts[persona]
            percentage = (count / len(participants) * 100) if participants else 0
            bar = "█" * int(percentage / 2)
            print(f"  {persona:20s}: {bar} {count:4d} ({percentage:5.1f}%)")
        print()

    except Exception as e:
        print(f"❌ Backfill failed: {e}")
        import traceback
        traceback.print_exc()
        db.conn.rollback()
        return 1
    finally:
        db.close()

    print("✅ Backfill complete!")
    return 0


if __name__ == "__main__":
    sys.exit(backfill_persona())
