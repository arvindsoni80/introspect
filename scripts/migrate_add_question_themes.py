#!/usr/bin/env python3
"""
Migration: Add question themes tables.

Creates tables for storing question themes and their assignments:
- question_themes: Theme definitions (name, description, suggested collateral)
- question_theme_assignments: Question-to-theme mappings with frequency
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core import Config
from src.data import Database


def migrate():
    """Add question_themes and question_theme_assignments tables."""
    config = Config()
    db = Database(config.SQLITE_DB_PATH)
    db.connect()

    print("🔧 Starting migration: Add question themes tables")
    print(f"   Database: {config.SQLITE_DB_PATH}")
    print()

    try:
        # Check if tables already exist
        cursor = db.conn.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name IN ('question_themes', 'question_theme_assignments')
        """)
        existing_tables = [row[0] for row in cursor.fetchall()]

        if 'question_themes' in existing_tables and 'question_theme_assignments' in existing_tables:
            print("⚠️  Tables already exist. Skipping.")
            return 0

        # Create question_themes table
        print("➕ Creating table: question_themes")
        db.conn.execute("""
            CREATE TABLE IF NOT EXISTS question_themes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                persona TEXT NOT NULL,
                theme_name TEXT NOT NULL,
                theme_description TEXT,
                suggested_collateral TEXT,
                question_count INTEGER DEFAULT 0,
                last_generated DATETIME NOT NULL DEFAULT (datetime('now')),

                UNIQUE(persona, theme_name)
            )
        """)
        print("   ✅ Created question_themes table")

        # Create indexes for question_themes
        db.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_themes_persona
            ON question_themes(persona)
        """)
        print("   ✅ Created index: idx_themes_persona")

        # Create question_theme_assignments table
        print("➕ Creating table: question_theme_assignments")
        db.conn.execute("""
            CREATE TABLE IF NOT EXISTS question_theme_assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                theme_id INTEGER NOT NULL,
                question_normalized TEXT NOT NULL,
                question_original TEXT NOT NULL,
                frequency INTEGER NOT NULL,
                sample_call_ids TEXT,
                created_at DATETIME NOT NULL DEFAULT (datetime('now')),

                FOREIGN KEY (theme_id) REFERENCES question_themes(id) ON DELETE CASCADE,
                UNIQUE(theme_id, question_normalized)
            )
        """)
        print("   ✅ Created question_theme_assignments table")

        # Create indexes for question_theme_assignments
        db.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_assignments_theme
            ON question_theme_assignments(theme_id)
        """)
        print("   ✅ Created index: idx_assignments_theme")

        db.conn.commit()
        print()
        print("✅ Migration complete!")
        print()
        print("📊 New tables created:")
        print("   - question_themes: Theme definitions by persona")
        print("   - question_theme_assignments: Question-to-theme mappings")
        print()
        print("💡 Next step: Run generate_question_themes.py to populate themes")

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        db.conn.rollback()
        return 1
    finally:
        db.close()

    return 0


if __name__ == "__main__":
    sys.exit(migrate())
