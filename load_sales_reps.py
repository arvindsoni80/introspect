#!/usr/bin/env python3
"""
Load sales rep data from CSV into database.

Usage:
    python load_sales_reps.py
"""

import asyncio
import csv
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config import load_settings
from src.sqlite_repository import SQLiteCallRepository


async def load_sales_reps(csv_file: str = "sales_rep_data.csv"):
    """Load sales rep data from CSV into database."""

    # Load settings
    settings = load_settings()
    repo = SQLiteCallRepository(settings.sqlite_db_path)

    try:
        csv_path = Path(csv_file)
        if not csv_path.exists():
            print(f"❌ Error: CSV file not found: {csv_file}")
            sys.exit(1)

        print(f"📂 Loading sales rep data from: {csv_file}")

        # Read CSV
        sales_reps = []
        with open(csv_path, 'r') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue

                # Parse CSV line: email, segment, joining_date
                parts = [p.strip() for p in line.split(',')]
                if len(parts) != 3:
                    print(f"⚠️  Warning: Line {line_num} has {len(parts)} fields (expected 3), skipping")
                    continue

                email, segment, joining_date_str = parts

                # Parse date (format: MM/DD/YYYY)
                try:
                    joining_date = datetime.strptime(joining_date_str, "%m/%d/%Y")
                except ValueError:
                    print(f"⚠️  Warning: Line {line_num} has invalid date format '{joining_date_str}', skipping")
                    continue

                sales_reps.append({
                    'email': email,
                    'segment': segment,
                    'joining_date': joining_date
                })

        if not sales_reps:
            print("⚠️  No valid sales rep data found in CSV")
            return

        print(f"\n📊 Found {len(sales_reps)} sales reps")

        # Group by segment for summary
        segments = {}
        for rep in sales_reps:
            seg = rep['segment']
            segments[seg] = segments.get(seg, 0) + 1

        for segment, count in sorted(segments.items()):
            print(f"   • {segment}: {count} reps")

        # Insert into database
        now = datetime.now().isoformat()
        inserted = 0
        updated = 0

        for rep in sales_reps:
            # Check if rep already exists
            cursor = repo.conn.execute(
                "SELECT email FROM sales_reps WHERE email = ?",
                (rep['email'],)
            )
            exists = cursor.fetchone() is not None

            # Insert or update
            repo.conn.execute(
                """
                INSERT OR REPLACE INTO sales_reps (email, segment, joining_date, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    rep['email'],
                    rep['segment'],
                    rep['joining_date'].isoformat(),
                    now if not exists else repo.conn.execute(
                        "SELECT created_at FROM sales_reps WHERE email = ?",
                        (rep['email'],)
                    ).fetchone()[0],
                    now
                )
            )

            if exists:
                updated += 1
            else:
                inserted += 1

        repo.conn.commit()

        print(f"\n✅ Success!")
        print(f"   • Inserted: {inserted} new reps")
        print(f"   • Updated: {updated} existing reps")
        print(f"   • Database: {settings.sqlite_db_path}")

    finally:
        await repo.close()


if __name__ == "__main__":
    asyncio.run(load_sales_reps())
