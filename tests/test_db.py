#!/usr/bin/env python3
"""
Test database integration.

Tests the SQLite repository with sample data.
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models import (
    AccountCall,
    AnalysisNotes,
    CallAnalysis,
    MEDDPICCScores,
    Participants,
)
from src.sqlite_repository import SQLiteCallRepository


async def main():
    """Test the database integration."""
    print("=" * 70)
    print("Database Integration Test")
    print("=" * 70)

    # Create test database in scratchpad
    db_path = "/tmp/test_calls.db"
    print(f"\n📦 Creating test database: {db_path}")
    repo = SQLiteCallRepository(db_path)

    try:
        # Create first test call analysis
        print("\n1️⃣  Creating first discovery call for example.com...")
        call1 = CallAnalysis(
            call_id="call-001",
            call_title="Discovery Call with Acme Corp",
            gong_link="https://app.gong.io/call?id=call-001",
            call_date=datetime(2025, 1, 15, 10, 0, 0),
            sales_rep_email="alice@ourcompany.com",
            participants=Participants(
                internal=["alice@ourcompany.com"],
                external=["bob@example.com", "carol@example.com"],
            ),
            is_discovery_call=True,
            discovery_reasoning="Clear discovery indicators present",
            meddpicc_scores=MEDDPICCScores(
                metrics=3,
                economic_buyer=2,
                decision_criteria=4,
                decision_process=3,
                paper_process=2,
                identify_pain=5,
                champion=3,
                competition=2,
                overall_score=3.0,
            ),
            meddpicc_summary="Good pain identification, needs economic buyer clarity",
            analysis_notes=AnalysisNotes(
                metrics="Discussed ROI expectations",
                economic_buyer="Only spoke with director level",
                decision_criteria="Clear technical requirements",
                decision_process="Budget cycle mentioned",
                paper_process="Security review needed",
                identify_pain="Major pain points identified",
                champion="Bob seems supportive",
                competition="Incumbent mentioned",
            ),
        )

        account1 = await repo.add_discovery_call("example.com", call1)
        print(f"   ✓ Created account for example.com")
        print(f"   ✓ Calls: {len(account1.calls)}")
        print(f"   ✓ Overall score: {account1.overall_meddpicc.overall_score}/5.0")

        # Create second call for same domain
        print("\n2️⃣  Adding second discovery call for example.com...")
        call2 = CallAnalysis(
            call_id="call-002",
            call_title="Technical Deep Dive with Acme",
            gong_link="https://app.gong.io/call?id=call-002",
            call_date=datetime(2025, 1, 20, 14, 0, 0),
            sales_rep_email="alice@ourcompany.com",
            participants=Participants(
                internal=["alice@ourcompany.com", "eve@ourcompany.com"],
                external=["bob@example.com", "dave@example.com"],
            ),
            is_discovery_call=True,
            discovery_reasoning="Technical validation session",
            meddpicc_scores=MEDDPICCScores(
                metrics=4,
                economic_buyer=4,  # Better than first call
                decision_criteria=4,
                decision_process=4,
                paper_process=3,
                identify_pain=4,
                champion=4,
                competition=3,
                overall_score=3.75,
            ),
            meddpicc_summary="Strong progress, engaged VP level",
            analysis_notes=AnalysisNotes(
                metrics="Quantified savings",
                economic_buyer="VP engaged",
                decision_criteria="Requirements validated",
                decision_process="Timeline confirmed",
                paper_process="Legal introduced",
                identify_pain="Pain quantified",
                champion="Strong champion identified",
                competition="Differentiation clear",
            ),
        )

        account2 = await repo.add_discovery_call("example.com", call2)
        print(f"   ✓ Updated account for example.com")
        print(f"   ✓ Calls: {len(account2.calls)}")
        print(f"   ✓ Overall score: {account2.overall_meddpicc.overall_score}/5.0")
        print(f"\n   📊 Overall MEDDPICC (max across calls):")
        print(f"      • Metrics: {account2.overall_meddpicc.metrics}/5")
        print(f"      • Economic Buyer: {account2.overall_meddpicc.economic_buyer}/5")
        print(f"      • Decision Criteria: {account2.overall_meddpicc.decision_criteria}/5")
        print(f"      • Decision Process: {account2.overall_meddpicc.decision_process}/5")
        print(f"      • Paper Process: {account2.overall_meddpicc.paper_process}/5")
        print(f"      • Identify Pain: {account2.overall_meddpicc.identify_pain}/5")
        print(f"      • Champion: {account2.overall_meddpicc.champion}/5")
        print(f"      • Competition: {account2.overall_meddpicc.competition}/5")

        # Create call for different domain
        print("\n3️⃣  Creating discovery call for different.com...")
        call3 = CallAnalysis(
            call_id="call-003",
            call_title="Initial Discovery - Different Corp",
            gong_link="https://app.gong.io/call?id=call-003",
            call_date=datetime(2025, 1, 18, 11, 0, 0),
            sales_rep_email="bob@ourcompany.com",
            participants=Participants(
                internal=["bob@ourcompany.com"],
                external=["frank@different.com"],
            ),
            is_discovery_call=True,
            discovery_reasoning="First discovery call",
            meddpicc_scores=MEDDPICCScores(
                metrics=2,
                economic_buyer=1,
                decision_criteria=3,
                decision_process=2,
                paper_process=1,
                identify_pain=4,
                champion=2,
                competition=2,
                overall_score=2.125,
            ),
            meddpicc_summary="Early stage, needs multi-threading",
            analysis_notes=AnalysisNotes(
                metrics="Vague on metrics",
                economic_buyer="Low level contact",
                decision_criteria="Some requirements discussed",
                decision_process="Unclear",
                paper_process="Not discussed",
                identify_pain="Pain identified",
                champion="Needs development",
                competition="Unknown",
            ),
        )

        account3 = await repo.add_discovery_call("different.com", call3)
        print(f"   ✓ Created account for different.com")
        print(f"   ✓ Calls: {len(account3.calls)}")
        print(f"   ✓ Overall score: {account3.overall_meddpicc.overall_score}/5.0")

        # List all domains
        print("\n4️⃣  Listing all tracked domains...")
        domains = await repo.list_domains()
        print(f"   ✓ Total domains: {len(domains)}")
        for domain in domains:
            account = await repo.get_account(domain)
            print(
                f"      • {domain}: {len(account.calls)} call(s), "
                f"score {account.overall_meddpicc.overall_score}/5.0"
            )

        # Retrieve and display full account
        print("\n5️⃣  Retrieving full account for example.com...")
        account = await repo.get_account("example.com")
        print(f"   ✓ Domain: {account.domain}")
        print(f"   ✓ Created: {account.created_at.strftime('%Y-%m-%d %H:%M')}")
        print(f"   ✓ Updated: {account.updated_at.strftime('%Y-%m-%d %H:%M')}")
        print(f"   ✓ Discovery calls:")
        for call in account.calls:
            print(
                f"      • {call.call_date.strftime('%Y-%m-%d')}: "
                f"{call.call_id} (score: {call.meddpicc_scores.overall_score}/5.0)"
            )

        print("\n✅ Database integration test complete!")

    finally:
        await repo.close()
        print(f"\n🔒 Closed database connection")


if __name__ == "__main__":
    asyncio.run(main())
