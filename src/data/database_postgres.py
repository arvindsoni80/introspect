"""Database connection supporting both SQLite and PostgreSQL."""

import re
import sqlite3
from pathlib import Path
from typing import Optional, Union

try:
    import psycopg2
    import psycopg2.extras
    HAS_POSTGRES = True
except ImportError:
    HAS_POSTGRES = False


class Database:
    """Manages database connection (SQLite or PostgreSQL)."""

    def __init__(self, connection_string: str):
        """
        Initialize database connection.

        Args:
            connection_string: Either:
                - Path to SQLite database file (e.g., "introspect.db")
                - PostgreSQL URL (e.g., "postgresql://user:pass@host:5432/dbname")
        """
        self.connection_string = connection_string
        self.conn: Optional[Union[sqlite3.Connection, 'psycopg2.extensions.connection']] = None
        self.db_type = self._detect_db_type()

    def _detect_db_type(self) -> str:
        """Detect database type from connection string."""
        if self.connection_string.startswith(('postgresql://', 'postgres://')):
            if not HAS_POSTGRES:
                raise ImportError(
                    "PostgreSQL support requires psycopg2. "
                    "Install with: pip install psycopg2-binary"
                )
            return 'postgresql'
        return 'sqlite'

    def connect(self):
        """Open database connection."""
        if self.db_type == 'postgresql':
            self.conn = psycopg2.connect(
                self.connection_string,
                cursor_factory=psycopg2.extras.RealDictCursor
            )
            # Register JSONB handlers
            psycopg2.extras.register_default_jsonb(self.conn)
        else:
            self.conn = sqlite3.connect(self.connection_string)
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

        if self.db_type == 'postgresql':
            # PostgreSQL: convert SQLite-specific syntax using regex

            # Fix 1: INTEGER PRIMARY KEY AUTOINCREMENT → SERIAL PRIMARY KEY
            # Pattern: column_name INTEGER PRIMARY KEY AUTOINCREMENT
            # Replace: column_name SERIAL PRIMARY KEY
            schema_sql = re.sub(
                r'(\w+)\s+INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT',
                r'\1 SERIAL PRIMARY KEY',
                schema_sql,
                flags=re.IGNORECASE
            )

            # Fix 2: datetime('now') → CURRENT_TIMESTAMP
            schema_sql = schema_sql.replace("datetime('now')", "CURRENT_TIMESTAMP")

            # Fix 3: CHECK (column IN (..., NULL)) → CHECK (column IS NULL OR column IN (...))
            # Pattern: CHECK (column_name IN ('val1', 'val2', ..., NULL))
            # Replace: CHECK (column_name IS NULL OR column_name IN ('val1', 'val2', ...))
            def fix_null_in_check(match):
                column = match.group(1)
                values = match.group(2)
                # Remove NULL from the values list
                values_clean = re.sub(r',\s*NULL\s*\)', ')', values)
                values_clean = re.sub(r'\(\s*NULL\s*,', '(', values_clean)
                return f"CHECK ({column} IS NULL OR {column} IN {values_clean})"

            schema_sql = re.sub(
                r'CHECK\s*\((\w+)\s+IN\s*(\([^)]*,\s*NULL[^)]*\))\)',
                fix_null_in_check,
                schema_sql,
                flags=re.IGNORECASE
            )

            # Execute statements individually (PostgreSQL doesn't support executescript)
            cursor = self.conn.cursor()
            for statement in schema_sql.split(';'):
                if statement.strip():
                    try:
                        cursor.execute(statement)
                    except Exception as e:
                        print(f"Warning: {e}")
                        # Continue on errors (table might already exist)
            self.conn.commit()
            cursor.close()
        else:
            # SQLite: use executescript
            self.conn.executescript(schema_sql)
            self.conn.commit()

        print(f"✓ Database schema created/updated")

    def drop_all_tables(self):
        """
        Drop all tables (use with caution!).

        This is useful for fresh starts during development.
        """
        cursor = self.conn.cursor()

        if self.db_type == 'postgresql':
            cursor.execute("""
                SELECT tablename FROM pg_tables
                WHERE schemaname = 'public'
            """)
            tables = [row[0] for row in cursor.fetchall()]

            for table in tables:
                cursor.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
                print(f"✓ Dropped table: {table}")
        else:
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
            """)
            tables = [row[0] for row in cursor.fetchall()]

            for table in tables:
                cursor.execute(f"DROP TABLE IF EXISTS {table}")
                print(f"✓ Dropped table: {table}")

        self.conn.commit()
        cursor.close()
        print(f"✓ All tables dropped")

    def reset_database(self):
        """Drop all tables and recreate schema."""
        print("⚠️  Resetting database...")
        self.drop_all_tables()
        self.create_tables()
        print("✅ Database reset complete")

    def get_table_counts(self) -> dict:
        """Get row counts for all tables."""
        cursor = self.conn.cursor()

        if self.db_type == 'postgresql':
            cursor.execute("""
                SELECT tablename FROM pg_tables
                WHERE schemaname = 'public'
                ORDER BY tablename
            """)
            tables = [row[0] for row in cursor.fetchall()]
        else:
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
                ORDER BY name
            """)
            tables = [row[0] for row in cursor.fetchall()]

        counts = {}
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) as count FROM {table}")
            result = cursor.fetchone()
            counts[table] = result[0] if self.db_type == 'postgresql' else result['count']

        cursor.close()
        return counts


def init_database(connection_string: str, reset: bool = False) -> Database:
    """
    Initialize database with schema.

    Args:
        connection_string: SQLite path or PostgreSQL URL
        reset: If True, drop all tables and recreate (DANGEROUS!)

    Returns:
        Connected Database instance
    """
    db = Database(connection_string)
    db.connect()

    if reset:
        db.reset_database()
    else:
        db.create_tables()

    return db


if __name__ == "__main__":
    # For testing: create database and show table counts
    import sys

    connection_string = sys.argv[1] if len(sys.argv) > 1 else "introspect.db"
    reset = "--reset" in sys.argv

    db = init_database(connection_string, reset=reset)

    print(f"\n📊 Database Type: {db.db_type}")
    print(f"\n📊 Table Counts:")
    counts = db.get_table_counts()
    for table, count in sorted(counts.items()):
        print(f"  {table}: {count}")

    db.close()
