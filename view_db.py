#!/usr/bin/env python3
"""
View SQLite database contents.

Displays all accounts and their discovery calls in a readable format.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.config import load_settings
from src.sqlite_repository import SQLiteCallRepository


async def main():
    """View database contents."""
    settings = load_settings()
    db_path = settings.sqlite_db_path

    if not Path(db_path).exists():
        print(f"❌ Database not found at: {db_path}")
        print("   Run the analyzer first to create discovery call records.")
        sys.exit(1)

    print("=" * 80)
    print(f"Database Viewer: {db_path}")
    print("=" * 80)

    repo = SQLiteCallRepository(db_path)

    try:
        # Get all domains
        domains = await repo.list_domains()

        if not domains:
            print("\n📭 No accounts in database yet.")
            print("   Run the analyzer with discovery calls to populate the database.")
            return

        print(f"\n📊 Total Accounts: {len(domains)}\n")

        # Display each account
        for i, domain in enumerate(domains, 1):
            account = await repo.get_account(domain)

            print(f"{i}. {domain}")
            print(f"   {'─' * 76}")
            print(f"   Created:  {account.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"   Updated:  {account.updated_at.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"   Calls:    {len(account.calls)} discovery call(s)")
            print()
            print(f"   📈 Overall MEDDPICC (max across all calls):")
            print(f"      • Metrics:           {account.overall_meddpicc.metrics}/5")
            print(f"      • Economic Buyer:    {account.overall_meddpicc.economic_buyer}/5")
            print(f"      • Decision Criteria: {account.overall_meddpicc.decision_criteria}/5")
            print(f"      • Decision Process:  {account.overall_meddpicc.decision_process}/5")
            print(f"      • Paper Process:     {account.overall_meddpicc.paper_process}/5")
            print(f"      • Identify Pain:     {account.overall_meddpicc.identify_pain}/5")
            print(f"      • Champion:          {account.overall_meddpicc.champion}/5")
            print(f"      • Competition:       {account.overall_meddpicc.competition}/5")
            print(f"      • Overall Score:     {account.overall_meddpicc.overall_score}/5.0")
            print()
            print(f"   📞 Discovery Calls:")
            for j, call in enumerate(account.calls, 1):
                print(f"      {j}. {call.call_id}")
                print(f"         Date:         {call.call_date.strftime('%Y-%m-%d %H:%M')}")
                print(f"         Sales Rep:    {call.sales_rep}")
                print(f"         Participants: {', '.join(call.external_participants)}")
                print(f"         Score:        {call.meddpicc_scores.overall_score}/5.0")

                # Show summary if available
                if call.meddpicc_summary:
                    print(f"         Summary:      {call.meddpicc_summary}")

                # Show detailed MEDDPICC scores with reasoning
                if call.analysis_notes:
                    print(f"         ")
                    print(f"         MEDDPICC Breakdown:")
                    print(f"           • Metrics [{call.meddpicc_scores.metrics}/5]: {call.analysis_notes.metrics}")
                    print(f"           • Economic Buyer [{call.meddpicc_scores.economic_buyer}/5]: {call.analysis_notes.economic_buyer}")
                    print(f"           • Decision Criteria [{call.meddpicc_scores.decision_criteria}/5]: {call.analysis_notes.decision_criteria}")
                    print(f"           • Decision Process [{call.meddpicc_scores.decision_process}/5]: {call.analysis_notes.decision_process}")
                    print(f"           • Paper Process [{call.meddpicc_scores.paper_process}/5]: {call.analysis_notes.paper_process}")
                    print(f"           • Identify Pain [{call.meddpicc_scores.identify_pain}/5]: {call.analysis_notes.identify_pain}")
                    print(f"           • Champion [{call.meddpicc_scores.champion}/5]: {call.analysis_notes.champion}")
                    print(f"           • Competition [{call.meddpicc_scores.competition}/5]: {call.analysis_notes.competition}")

                if j < len(account.calls):
                    print()
            print()

    finally:
        await repo.close()


if __name__ == "__main__":
    asyncio.run(main())
