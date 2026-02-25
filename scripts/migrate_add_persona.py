#!/usr/bin/env python3
"""
Migration: Add persona column to call_participants table.

This enables storing persona classification (Decision Maker, Influencer, User)
for each participant based on their title.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core import Config
from src.data import Database


def migrate():
    """Add persona column to call_participants table."""
    config = Config()
    db = Database(config.SQLITE_DB_PATH)
    db.connect()

    print("🔧 Starting migration: Add persona column")
    print(f"   Database: {config.SQLITE_DB_PATH}")
    print()

    try:
        # Check if column already exists
        cursor = db.conn.execute("PRAGMA table_info(call_participants)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'persona' in columns:
            print("⚠️  Column 'persona' already exists. Skipping.")
        else:
            print("➕ Adding column: persona (TEXT)")
            db.conn.execute("""
                ALTER TABLE call_participants
                ADD COLUMN persona TEXT
            """)
            print("   ✅ Added persona column")

        db.conn.commit()
        print()
        print("✅ Migration complete!")
        print()
        print("📊 Updated schema:")
        cursor = db.conn.execute("PRAGMA table_info(call_participants)")
        print("\nColumns:")
        for row in cursor.fetchall():
            print(f"  - {row[1]} ({row[2]})")
        print()
        print("💡 Next step: Run backfill_persona.py to classify existing participants")

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        db.conn.rollback()
        return 1
    finally:
        db.close()

    return 0


if __name__ == "__main__":
    sys.exit(migrate())
