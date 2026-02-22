#!/usr/bin/env python3
"""
Migration: Add call_participants table

This migration adds a new table to store speaker/participant information
for each call, which can be used to enrich transcripts with speaker details.

Usage:
    python migrate_add_participants_table.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core import Config
from src.data import Database, init_database


def migrate():
    """Add call_participants table."""
    print("=" * 80)
    print("MIGRATION: Add call_participants table")
    print("=" * 80)

    # Initialize configuration
    print("\n🔧 Initializing configuration...")
    config = Config()

    if not config.validate():
        print("\n❌ Configuration incomplete. Please check your .env file.")
        return 1

    print(f"✓ Config loaded")

    # Initialize database
    db_path = config.SQLITE_DB_PATH
    print(f"\n🗄️  Connecting to database: {db_path}")
    db = init_database(db_path, reset=False)

    # Check if table already exists
    cursor = db.conn.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='call_participants'
    """)

    if cursor.fetchone():
        print("\n⚠️  call_participants table already exists!")
        print("   Migration not needed.")
        db.close()
        return 0

    # Create the table
    print("\n📝 Creating call_participants table...")

    db.conn.execute("""
        CREATE TABLE IF NOT EXISTS call_participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            call_id TEXT NOT NULL,

            -- Gong IDs
            speaker_id TEXT NOT NULL,
            party_id TEXT,
            user_id TEXT,

            -- Participant info
            email_address TEXT,
            name TEXT,
            title TEXT,
            affiliation TEXT,
            phone_number TEXT,

            created_at DATETIME NOT NULL DEFAULT (datetime('now')),

            UNIQUE(call_id, speaker_id),

            CHECK (affiliation IN ('Internal', 'External', 'Unknown', NULL))
        )
    """)

    # Create indexes
    print("   Creating indexes...")
    db.conn.execute("CREATE INDEX idx_participants_call ON call_participants(call_id)")
    db.conn.execute("CREATE INDEX idx_participants_speaker ON call_participants(speaker_id)")
    db.conn.execute("CREATE INDEX idx_participants_affiliation ON call_participants(affiliation)")
    db.conn.execute("CREATE INDEX idx_participants_email ON call_participants(email_address)")

    db.conn.commit()

    print("   ✓ Table created")

    # Verify
    cursor = db.conn.execute("""
        SELECT COUNT(*) as count FROM call_participants
    """)
    count = cursor.fetchone()['count']

    print(f"\n✅ Migration complete!")
    print(f"   call_participants table now exists with {count} rows")
    print("\nNext steps:")
    print("   1. Update your data ingestion to populate participant info")
    print("   2. Use participant data to enrich transcripts with speaker names")

    db.close()
    return 0


if __name__ == "__main__":
    sys.exit(migrate())
