#!/usr/bin/env python3
"""
View all evaluated calls with rejection reasons.

Shows which calls were analyzed and why they were/weren't discovery calls.
"""

import asyncio
import sqlite3
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config import load_settings


def main():
    """View evaluated calls."""
    settings = load_settings()
    db_path = settings.sqlite_db_path

    if not Path(db_path).exists():
        print(f"❌ Database not found at: {db_path}")
        sys.exit(1)

    print("=" * 80)
    print(f"Evaluated Calls Report: {db_path}")
    print("=" * 80)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check if evaluated_calls table exists
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='evaluated_calls'"
    )
    if not cursor.fetchone():
        print("\n❌ evaluated_calls table not found (old database schema)")
        print("   Run the analyzer once to create the new schema.")
        conn.close()
        sys.exit(1)

    # Get all evaluated calls
    cursor.execute(
        """
        SELECT call_id, evaluated_at, is_discovery, reason
        FROM evaluated_calls
        ORDER BY evaluated_at DESC
        """
    )
    calls = cursor.fetchall()

    if not calls:
        print("\n📭 No evaluated calls found yet.")
        conn.close()
        return

    # Statistics
    total_calls = len(calls)
    discovery_calls = sum(1 for c in calls if c[2] == 1)
    non_discovery_calls = total_calls - discovery_calls

    print(f"\n📊 Summary:")
    print(f"   Total Evaluated:    {total_calls}")
    print(f"   Discovery Calls:    {discovery_calls} ({discovery_calls/total_calls*100:.1f}%)")
    print(f"   Non-Discovery:      {non_discovery_calls} ({non_discovery_calls/total_calls*100:.1f}%)")

    # Analyze rejection reasons
    if non_discovery_calls > 0:
        reasons = [c[3] for c in calls if c[2] == 0 and c[3]]

        # Extract key phrases from reasons
        rejection_patterns = Counter()
        for reason in reasons:
            reason_lower = reason.lower()
            if "no-show" in reason_lower or "never joined" in reason_lower:
                rejection_patterns["No-show / Didn't join"] += 1
            elif "trial" in reason_lower or "feedback" in reason_lower:
                rejection_patterns["Trial feedback / Post-trial"] += 1
            elif "troubleshoot" in reason_lower or "technical" in reason_lower or "debug" in reason_lower:
                rejection_patterns["Technical troubleshooting"] += 1
            elif "negotiat" in reason_lower or "pricing" in reason_lower or "contract" in reason_lower:
                rejection_patterns["Pricing / Negotiation"] += 1
            elif "admin" in reason_lower or "logistics" in reason_lower:
                rejection_patterns["Admin / Logistics"] += 1
            else:
                rejection_patterns["Other"] += 1

        print(f"\n📉 Rejection Reasons Breakdown:")
        for pattern, count in rejection_patterns.most_common():
            pct = count / non_discovery_calls * 100
            print(f"   • {pattern:<30} {count:>4} ({pct:>5.1f}%)")

    # Recent calls (last 20)
    print(f"\n📋 Recent Calls (last 20):")
    print(f"   {'Date':<12} {'Discovery':<10} {'Call ID':<25} {'Reason'}")
    print(f"   {'-'*78}")

    for call_id, evaluated_at, is_discovery, reason in calls[:20]:
        date = datetime.fromisoformat(evaluated_at).strftime("%Y-%m-%d")
        discovery_str = "✅ Yes" if is_discovery == 1 else "❌ No"
        reason_str = reason[:40] + "..." if reason and len(reason) > 40 else (reason or "")
        print(f"   {date:<12} {discovery_str:<10} {call_id:<25} {reason_str}")

    conn.close()

    # Query options
    print(f"\n💡 Query Examples:")
    print(f"   # View all non-discovery calls")
    print(f"   sqlite3 {db_path} \"SELECT call_id, reason FROM evaluated_calls WHERE is_discovery=0\"")
    print()
    print(f"   # Count by rejection type")
    print(f"   sqlite3 {db_path} \"SELECT reason, COUNT(*) FROM evaluated_calls WHERE is_discovery=0 GROUP BY reason\"")
    print()
    print(f"   # Find specific pattern")
    print(f"   sqlite3 {db_path} \"SELECT * FROM evaluated_calls WHERE reason LIKE '%no-show%'\"")


if __name__ == "__main__":
    main()
