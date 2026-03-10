#!/usr/bin/env python3
"""Load sales reps from CSV (no header) into database."""

import sys
import csv
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

from src.core import Config
from src.data import Database, Repository
from src.domain import SalesRep


def parse_date(date_str: str):
    """Parse date from MM/DD/YYYY format."""
    try:
        return datetime.strptime(date_str, "%m/%d/%Y").date()
    except ValueError:
        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return None


def main():
    print("📊 Loading Sales Reps from CSV (no header)\n")
    print("=" * 70)

    # Load config
    print("\n1. Loading configuration...")
    config = Config()
    db_path = config.SQLITE_DB_PATH
    print(f"   ✓ Database path: {db_path}")

    # Check if CSV exists
    csv_path = Path("sales_rep.csv")
    if not csv_path.exists():
        print(f"\n❌ Error: sales_rep.csv not found")
        return

    print(f"   ✓ Found CSV: {csv_path}")

    # Connect to database
    print("\n2. Connecting to database...")
    db = Database(db_path)
    db.connect()
    repo = Repository(db.conn)
    print("   ✓ Connected")

    # Read CSV (no header, format: email, segment, joining_date)
    print("\n3. Reading CSV file...")
    print("   Format: email, segment, joining_date")
    sales_reps = []

    with open(csv_path, 'r') as f:
        reader = csv.reader(f)

        for row_num, row in enumerate(reader, start=1):
            if len(row) < 3:
                print(f"   ⚠️  Row {row_num}: Expected 3 columns, got {len(row)}, skipping")
                continue

            email = row[0].strip()
            segment = row[1].strip()
            joining_date_str = row[2].strip()

            if not email or not segment or not joining_date_str:
                print(f"   ⚠️  Row {row_num}: Missing data, skipping")
                continue

            # Parse date
            joining_date = parse_date(joining_date_str)
            if not joining_date:
                print(f"   ⚠️  Row {row_num}: Invalid date '{joining_date_str}', skipping")
                continue

            # Create SalesRep
            rep = SalesRep(
                email=email,
                segment=segment,
                joining_date=joining_date,
                is_active=True,
                left_date=None,
            )
            sales_reps.append(rep)

    print(f"   ✓ Parsed {len(sales_reps)} sales reps")

    if not sales_reps:
        print("\n❌ No valid sales reps found")
        db.close()
        return

    # Display
    print("\n4. Sales reps to be loaded:")
    print("-" * 70)
    for rep in sales_reps:
        print(f"   • {rep.email:30s} | {rep.segment:15s} | {rep.joining_date}")

    # Insert
    print("\n5. Inserting into database...")
    inserted = 0
    updated = 0

    for rep in sales_reps:
        existing = repo.get_sales_rep(rep.email)

        if existing:
            print(f"   → Updating {rep.email}")
            existing.segment = rep.segment
            existing.joining_date = rep.joining_date
            existing.is_active = True
            repo.update_sales_rep(existing)
            updated += 1
        else:
            print(f"   → Creating {rep.email}")
            repo.create_sales_rep(rep)
            inserted += 1

    db.conn.commit()
    db.close()

    # Summary
    print("\n" + "=" * 70)
    print("✅ COMPLETE")
    print("=" * 70)
    print(f"\nResults:")
    print(f"   Inserted: {inserted} new")
    print(f"   Updated:  {updated} existing")
    print(f"   Total:    {inserted + updated}")

    # Verify
    print("\n6. Verification:")
    print("-" * 70)

    db = Database(db_path)
    db.connect()
    repo = Repository(db.conn)

    all_reps = repo.list_sales_reps(active_only=True)
    for rep in sorted(all_reps, key=lambda r: r.email):
        print(f"   • {rep.email:30s} | {rep.segment:15s} | {rep.days_tenure:4d} days")

    db.close()
    print(f"\n✅ Done! {len(all_reps)} active sales reps in database\n")


if __name__ == "__main__":
    main()
