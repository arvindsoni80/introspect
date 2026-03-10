#!/usr/bin/env python3
"""
Migrate SQLite database to PostgreSQL.

This script exports all data from SQLite and imports into PostgreSQL.
Works with Cloud SQL PostgreSQL or any PostgreSQL database.

Usage:
    # Local PostgreSQL (for testing)
    python migrate_sqlite_to_postgres.py --sqlite-path introspect.db \
        --postgres-url "postgresql://user:pass@localhost:5432/introspect"

    # Cloud SQL (via cloud-sql-proxy)
    python migrate_sqlite_to_postgres.py --sqlite-path introspect.db \
        --postgres-url "postgresql://user:pass@/introspect?host=/cloudsql/PROJECT:REGION:INSTANCE"
"""

import argparse
import sqlite3
import sys
from pathlib import Path

try:
    import psycopg2
    from psycopg2.extras import execute_batch
except ImportError:
    print("❌ psycopg2 not installed. Run: pip install psycopg2-binary")
    sys.exit(1)


def migrate_table(sqlite_conn, postgres_conn, table_name, batch_size=1000):
    """Migrate a single table from SQLite to PostgreSQL."""
    print(f"\n📊 Migrating table: {table_name}")

    sqlite_cursor = sqlite_conn.cursor()
    postgres_cursor = postgres_conn.cursor()

    # Get column names from SQLite
    sqlite_cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in sqlite_cursor.fetchall()]

    # Count rows
    sqlite_cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    total_rows = sqlite_cursor.fetchone()[0]

    if total_rows == 0:
        print(f"  ⏭️  Table is empty, skipping")
        return

    print(f"  → Found {total_rows} rows")

    # Prepare insert query
    placeholders = ", ".join(["%s"] * len(columns))
    insert_query = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders})"

    # Fetch all rows from SQLite
    sqlite_cursor.execute(f"SELECT {', '.join(columns)} FROM {table_name}")

    # Insert in batches
    rows = sqlite_cursor.fetchall()
    execute_batch(postgres_cursor, insert_query, rows, page_size=batch_size)

    postgres_conn.commit()
    print(f"  ✓ Migrated {len(rows)} rows")


def create_postgres_schema(sqlite_path, postgres_conn):
    """Create PostgreSQL schema from SQLite schema."""
    print("\n🏗️  Creating PostgreSQL schema...")

    # Read schema from schema.sql (already PostgreSQL compatible)
    # Go up from scripts/ directory to repository root, then to src/data/schema.sql
    schema_path = Path(__file__).resolve().parent.parent / "src" / "data" / "schema.sql"

    if not schema_path.exists():
        print(f"  ⚠️  schema.sql not found, using SQLite schema")
        # Fallback: extract from SQLite
        sqlite_conn = sqlite3.connect(sqlite_path)
        cursor = sqlite_conn.cursor()
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table'")
        schema_statements = [row[0] for row in cursor.fetchall() if row[0]]
        sqlite_conn.close()
    else:
        with open(schema_path) as f:
            schema_sql = f.read()
            schema_statements = [s.strip() for s in schema_sql.split(';') if s.strip()]

    postgres_cursor = postgres_conn.cursor()

    for statement in schema_statements:
        if not statement:
            continue

        # Convert SQLite-specific syntax to PostgreSQL
        postgres_statement = statement.replace(
            "AUTOINCREMENT", "SERIAL"
        ).replace(
            "datetime('now')", "CURRENT_TIMESTAMP"
        )

        try:
            postgres_cursor.execute(postgres_statement)
            print(f"  ✓ Executed: {postgres_statement[:60]}...")
        except Exception as e:
            print(f"  ⚠️  Warning: {e}")
            # Continue on errors (table might already exist)

    postgres_conn.commit()
    print("  ✓ Schema created")


def main():
    parser = argparse.ArgumentParser(description="Migrate SQLite to PostgreSQL")
    parser.add_argument("--sqlite-path", required=True, help="Path to SQLite database")
    parser.add_argument("--postgres-url", required=True, help="PostgreSQL connection URL")
    parser.add_argument("--skip-schema", action="store_true", help="Skip schema creation")
    args = parser.parse_args()

    print("=" * 80)
    print("SQLite → PostgreSQL Migration")
    print("=" * 80)

    # Connect to SQLite
    print(f"\n📂 Connecting to SQLite: {args.sqlite_path}")
    if not Path(args.sqlite_path).exists():
        print(f"❌ SQLite database not found: {args.sqlite_path}")
        return 1

    sqlite_conn = sqlite3.connect(args.sqlite_path)
    sqlite_conn.row_factory = sqlite3.Row

    # Connect to PostgreSQL
    print(f"\n🐘 Connecting to PostgreSQL...")
    try:
        postgres_conn = psycopg2.connect(args.postgres_url)
    except Exception as e:
        print(f"❌ Failed to connect to PostgreSQL: {e}")
        return 1

    print("  ✓ Connected")

    # Create schema
    if not args.skip_schema:
        create_postgres_schema(args.sqlite_path, postgres_conn)

    # Get list of tables
    cursor = sqlite_conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]

    print(f"\n📋 Found {len(tables)} tables to migrate:")
    for table in tables:
        print(f"  • {table}")

    # Migrate each table
    print("\n" + "=" * 80)
    print("MIGRATION")
    print("=" * 80)

    for table in tables:
        try:
            migrate_table(sqlite_conn, postgres_conn, table)
        except Exception as e:
            print(f"  ❌ Error migrating {table}: {e}")
            import traceback
            traceback.print_exc()

    # Close connections
    sqlite_conn.close()
    postgres_conn.close()

    print("\n" + "=" * 80)
    print("✅ Migration complete!")
    print("=" * 80)

    return 0


if __name__ == "__main__":
    sys.exit(main())
