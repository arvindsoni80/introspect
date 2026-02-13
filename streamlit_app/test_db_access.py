"""Test script to verify database access from streamlit_app directory."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

print(f"Project root: {project_root}")
print(f"Python path: {sys.path[:3]}")

try:
    from src.config import load_settings
    from src.sqlite_repository import SQLiteCallRepository
    print("✓ Imports successful")
except Exception as e:
    print(f"✗ Import error: {e}")
    sys.exit(1)


async def test_database():
    """Test database access."""
    print("\n--- Testing Database Access ---")

    # Load settings
    try:
        settings = load_settings()
        print(f"✓ Settings loaded")
        print(f"  DB Path (from settings): {settings.sqlite_db_path}")

        # Resolve path relative to project root
        db_path = Path(settings.sqlite_db_path)
        if not db_path.is_absolute():
            db_path = project_root / db_path
        print(f"  Resolved DB Path: {db_path}")
    except Exception as e:
        print(f"✗ Failed to load settings: {e}")
        return

    # Check if DB file exists (already resolved above)
    if not db_path.exists():
        print(f"✗ Database file does not exist: {db_path}")
        return
    else:
        print(f"✓ Database file exists")
        print(f"  Size: {db_path.stat().st_size / 1024:.2f} KB")

    # Connect to database
    try:
        repo = SQLiteCallRepository(str(db_path))
        print(f"✓ Connected to database")
    except Exception as e:
        print(f"✗ Failed to connect: {e}")
        return

    # Get accounts
    try:
        accounts = await repo.get_all_accounts()
        print(f"✓ Queried accounts")
        print(f"  Total accounts: {len(accounts)}")

        if accounts:
            print(f"\nFirst 3 accounts:")
            for account in accounts[:3]:
                print(f"  - {account.domain}: {len(account.calls)} calls, score: {account.overall_meddpicc.overall_score:.1f}")
        else:
            print("\n⚠️  No accounts found in database!")

            # Check evaluated_calls table
            cursor = repo.conn.execute("SELECT COUNT(*) FROM evaluated_calls")
            eval_count = cursor.fetchone()[0]
            print(f"  Evaluated calls table has {eval_count} records")

            cursor = repo.conn.execute("SELECT COUNT(*) FROM evaluated_calls WHERE is_discovery = 1")
            discovery_count = cursor.fetchone()[0]
            print(f"  Discovery calls: {discovery_count}")

    except Exception as e:
        print(f"✗ Failed to query accounts: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await repo.close()
        print("\n✓ Database connection closed")


if __name__ == "__main__":
    print("=" * 60)
    print("Database Access Test")
    print("=" * 60)
    asyncio.run(test_database())
    print("\n" + "=" * 60)
