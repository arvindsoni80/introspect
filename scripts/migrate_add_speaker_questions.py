#!/usr/bin/env python3
"""
Migration: Add speaker_questions columns to call_participants table.

This enables storing extracted questions per participant for persona analysis.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core import Config
from src.data import Database


def migrate():
    """Add speaker_questions and question_count columns."""
    config = Config()
    db = Database(config.SQLITE_DB_PATH)
    db.connect()

    print("🔧 Starting migration: Add speaker_questions columns")
    print(f"   Database: {config.SQLITE_DB_PATH}")
    print()

    try:
        # Check if columns already exist
        cursor = db.conn.execute("PRAGMA table_info(call_participants)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'speaker_questions' in columns:
            print("⚠️  Column 'speaker_questions' already exists. Skipping.")
        else:
            print("➕ Adding column: speaker_questions (TEXT - JSON array)")
            db.conn.execute("""
                ALTER TABLE call_participants
                ADD COLUMN speaker_questions TEXT
            """)
            print("   ✅ Added speaker_questions")

        if 'question_count' in columns:
            print("⚠️  Column 'question_count' already exists. Skipping.")
        else:
            print("➕ Adding column: question_count (INTEGER)")
            db.conn.execute("""
                ALTER TABLE call_participants
                ADD COLUMN question_count INTEGER DEFAULT 0
            """)
            print("   ✅ Added question_count")

        db.conn.commit()
        print()
        print("✅ Migration complete!")
        print()
        print("📊 Updated schema:")
        cursor = db.conn.execute("PRAGMA table_info(call_participants)")
        print("\nColumns:")
        for row in cursor.fetchall():
            print(f"  - {row[1]} ({row[2]})")

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        db.conn.rollback()
        return 1
    finally:
        db.close()

    return 0


if __name__ == "__main__":
    sys.exit(migrate())
