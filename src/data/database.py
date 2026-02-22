"""Database connection and schema management."""

import sqlite3
from pathlib import Path
from typing import Optional


class Database:
    """Manages SQLite database connection and schema."""

    def __init__(self, db_path: str):
        """
        Initialize database connection.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None

    def connect(self):
        """Open database connection."""
        self.conn = sqlite3.connect(self.db_path)
        # Return rows as sqlite3.Row for dict-like access
        self.conn.row_factory = sqlite3.Row
        return self

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None

    def __enter__(self):
        """Context manager entry."""
        return self.connect()

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    def create_tables(self):
        """Create all tables from schema.sql."""
        schema_path = Path(__file__).parent / "schema.sql"

        with open(schema_path, 'r') as f:
            schema_sql = f.read()

        # Execute the schema SQL
        self.conn.executescript(schema_sql)
        self.conn.commit()

        print(f"✓ Database schema created/updated at {self.db_path}")

    def drop_all_tables(self):
        """
        Drop all tables (use with caution!).

        This is useful for fresh starts during development.
        """
        cursor = self.conn.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
        """)

        tables = [row['name'] for row in cursor.fetchall()]

        for table in tables:
            self.conn.execute(f"DROP TABLE IF EXISTS {table}")
            print(f"✓ Dropped table: {table}")

        self.conn.commit()

        print(f"✓ All tables dropped")

    def reset_database(self):
        """Drop all tables and recreate schema."""
        print("⚠️  Resetting database...")
        self.drop_all_tables()
        self.create_tables()
        print("✅ Database reset complete")

    def get_table_counts(self) -> dict:
        """Get row counts for all tables."""
        cursor = self.conn.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
        """)

        tables = [row['name'] for row in cursor.fetchall()]
        counts = {}

        for table in tables:
            cursor = self.conn.execute(f"SELECT COUNT(*) as count FROM {table}")
            counts[table] = cursor.fetchone()['count']

        return counts


def init_database(db_path: str, reset: bool = False) -> Database:
    """
    Initialize database with schema.

    Args:
        db_path: Path to SQLite database file
        reset: If True, drop all tables and recreate (DANGEROUS!)

    Returns:
        Connected Database instance
    """
    db = Database(db_path)
    db.connect()

    if reset:
        db.reset_database()
    else:
        db.create_tables()

    return db


if __name__ == "__main__":
    # For testing: create database and show table counts
    import sys

    db_path = sys.argv[1] if len(sys.argv) > 1 else "introspect.db"
    reset = "--reset" in sys.argv

    db = init_database(db_path, reset=reset)

    print("\n📊 Table Counts:")
    counts = db.get_table_counts()
    for table, count in sorted(counts.items()):
        print(f"  {table}: {count}")

    db.close()
