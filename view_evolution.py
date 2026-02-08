#!/usr/bin/env python3
"""
View MEDDPICC evolution for accounts with multiple calls.

Shows how MEDDPICC scores and reasoning evolved across discovery calls.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.config import load_settings
from src.sqlite_repository import SQLiteCallRepository


async def main():
    """View MEDDPICC evolution."""
    settings = load_settings()
    db_path = settings.sqlite_db_path

    if not Path(db_path).exists():
        print(f"❌ Database not found at: {db_path}")
        sys.exit(1)

    print("=" * 80)
    print("MEDDPICC Evolution Tracker")
    print("=" * 80)

    repo = SQLiteCallRepository(db_path)

    try:
        domains = await repo.list_domains()

        if not domains:
            print("\n📭 No accounts in database yet.")
            return

        # Find accounts with multiple calls
        multi_call_accounts = []
        for domain in domains:
            account = await repo.get_account(domain)
            if len(account.calls) > 1:
                multi_call_accounts.append(account)

        if not multi_call_accounts:
            print("\n📊 No accounts with multiple discovery calls yet.")
            print("   Run more discovery calls to see MEDDPICC evolution!")
            return

        print(f"\n📈 Accounts with Multiple Discovery Calls: {len(multi_call_accounts)}\n")

        for account in multi_call_accounts:
            print(f"{'=' * 80}")
            print(f"🏢 {account.domain}")
            print(f"{'=' * 80}")
            print(f"Total Discovery Calls: {len(account.calls)}")
            print(f"Date Range: {account.created_at.strftime('%Y-%m-%d')} → {account.updated_at.strftime('%Y-%m-%d')}")
            print()

            # Show evolution table
            print(f"{'Call Date':<12} {'Call ID':<20} {'M':<3} {'EB':<3} {'DC':<3} {'DP':<3} {'PP':<3} {'IP':<3} {'CH':<3} {'CO':<3} {'Overall':<7}")
            print(f"{'-' * 80}")

            for call in account.calls:
                s = call.meddpicc_scores
                print(
                    f"{call.call_date.strftime('%Y-%m-%d'):<12} "
                    f"{call.call_id:<20} "
                    f"{s.metrics:<3} "
                    f"{s.economic_buyer:<3} "
                    f"{s.decision_criteria:<3} "
                    f"{s.decision_process:<3} "
                    f"{s.paper_process:<3} "
                    f"{s.identify_pain:<3} "
                    f"{s.champion:<3} "
                    f"{s.competition:<3} "
                    f"{s.overall_score:<7.2f}"
                )

            print(f"{'-' * 80}")
            print(f"{'OVERALL (Max)':<33} "
                  f"{account.overall_meddpicc.metrics:<3} "
                  f"{account.overall_meddpicc.economic_buyer:<3} "
                  f"{account.overall_meddpicc.decision_criteria:<3} "
                  f"{account.overall_meddpicc.decision_process:<3} "
                  f"{account.overall_meddpicc.paper_process:<3} "
                  f"{account.overall_meddpicc.identify_pain:<3} "
                  f"{account.overall_meddpicc.champion:<3} "
                  f"{account.overall_meddpicc.competition:<3} "
                  f"{account.overall_meddpicc.overall_score:<7.2f}")
            print()

            # Show dimension improvements
            print("📊 Dimension Evolution:")
            dimensions = [
                ("Metrics", "metrics"),
                ("Economic Buyer", "economic_buyer"),
                ("Decision Criteria", "decision_criteria"),
                ("Decision Process", "decision_process"),
                ("Paper Process", "paper_process"),
                ("Identify Pain", "identify_pain"),
                ("Champion", "champion"),
                ("Competition", "competition"),
            ]

            for dim_name, dim_key in dimensions:
                scores = [getattr(call.meddpicc_scores, dim_key) for call in account.calls]
                if max(scores) > min(scores):
                    print(f"   ✨ {dim_name}: {min(scores)} → {max(scores)} (improved by {max(scores) - min(scores)})")
                else:
                    print(f"   • {dim_name}: {scores[0]} (consistent)")

            print()

            # Show reasoning evolution for dimensions that improved
            for dim_name, dim_key in dimensions:
                scores = [getattr(call.meddpicc_scores, dim_key) for call in account.calls]
                if max(scores) > min(scores):
                    print(f"💡 {dim_name} Evolution (reasoning):")
                    for idx, call in enumerate(account.calls, 1):
                        score = getattr(call.meddpicc_scores, dim_key)
                        if call.analysis_notes:
                            reasoning = getattr(call.analysis_notes, dim_key)
                            print(f"   Call {idx} [{score}/5]: {reasoning}")
                    print()

            print()

    finally:
        await repo.close()


if __name__ == "__main__":
    asyncio.run(main())
