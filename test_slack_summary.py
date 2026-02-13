#!/usr/bin/env python3
"""
Test Slack summary table posting.

Creates fake data and posts summary tables to verify Slack integration.
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config import load_settings
from src.models import (
    AccountCall,
    AccountRecord,
    CallAnalysis,
    MEDDPICCScores,
    Participants,
)
from src.slack_client import SlackClient


async def test_slack_summaries():
    """Test both summary table formats."""
    print("=" * 80)
    print("Slack Summary Table Test")
    print("=" * 80)

    # Load settings
    settings = load_settings()

    if not settings.slack_bot_token or not settings.slack_channel_id:
        print("\n❌ Error: SLACK_BOT_TOKEN or SLACK_CHANNEL_ID not configured in .env")
        print("   Add these to your .env file:")
        print("   SLACK_BOT_TOKEN=xoxb-your-token-here")
        print("   SLACK_CHANNEL_ID=C01234567")
        return False

    print(f"\n✓ Slack configured:")
    print(f"  Channel ID: {settings.slack_channel_id}")
    print(f"  Token: {settings.slack_bot_token[:20]}...")

    slack_client = SlackClient(settings.slack_bot_token, settings.slack_channel_id)

    # Create fake discovery call data
    print(f"\n📝 Creating test data...")

    fake_calls = [
        CallAnalysis(
            call_id="test-call-001",
            call_title="Discovery Call - Acme Corp",
            gong_link="https://app.gong.io/call?id=test-001",
            call_date=datetime(2025, 2, 8, 10, 0, 0),
            sales_rep_email="alice@coderabbit.ai",
            participants=Participants(
                internal=["alice@coderabbit.ai"],
                external=["bob@acme.com", "carol@acme.com"],
            ),
            is_discovery_call=True,
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
        ),
        CallAnalysis(
            call_id="test-call-002",
            call_title="Product Demo - Beta Inc",
            gong_link="https://app.gong.io/call?id=test-002",
            call_date=datetime(2025, 2, 8, 14, 0, 0),
            sales_rep_email="alice@coderabbit.ai",
            participants=Participants(
                internal=["alice@coderabbit.ai"],
                external=["dave@beta.com"],
            ),
            is_discovery_call=True,
            meddpicc_scores=MEDDPICCScores(
                metrics=4,
                economic_buyer=4,
                decision_criteria=4,
                decision_process=4,
                paper_process=3,
                identify_pain=4,
                champion=4,
                competition=3,
                overall_score=3.75,
            ),
            meddpicc_summary="Strong progress, engaged VP level",
        ),
        CallAnalysis(
            call_id="test-call-003",
            call_title="Initial Discovery - Gamma LLC",
            gong_link="https://app.gong.io/call?id=test-003",
            call_date=datetime(2025, 2, 8, 16, 0, 0),
            sales_rep_email="bob@coderabbit.ai",
            participants=Participants(
                internal=["bob@coderabbit.ai"],
                external=["frank@gamma.com"],
            ),
            is_discovery_call=True,
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
        ),
    ]

    fake_accounts = [
        AccountRecord(
            domain="acme.com",
            created_at=datetime(2025, 2, 5, 10, 0, 0),
            updated_at=datetime(2025, 2, 8, 10, 0, 0),
            calls=[
                AccountCall(
                    call_id="test-call-001",
                    call_date=datetime(2025, 2, 8, 10, 0, 0),
                    sales_rep="alice@coderabbit.ai",
                    external_participants=["bob@acme.com", "carol@acme.com"],
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
                )
            ],
            overall_meddpicc=MEDDPICCScores(
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
        ),
        AccountRecord(
            domain="beta.com",
            created_at=datetime(2025, 2, 8, 14, 0, 0),
            updated_at=datetime(2025, 2, 8, 14, 0, 0),
            calls=[
                AccountCall(
                    call_id="test-call-002",
                    call_date=datetime(2025, 2, 8, 14, 0, 0),
                    sales_rep="alice@coderabbit.ai",
                    external_participants=["dave@beta.com"],
                    meddpicc_scores=MEDDPICCScores(
                        metrics=4,
                        economic_buyer=4,
                        decision_criteria=4,
                        decision_process=4,
                        paper_process=3,
                        identify_pain=4,
                        champion=4,
                        competition=3,
                        overall_score=3.75,
                    ),
                )
            ],
            overall_meddpicc=MEDDPICCScores(
                metrics=4,
                economic_buyer=4,
                decision_criteria=4,
                decision_process=4,
                paper_process=3,
                identify_pain=4,
                champion=4,
                competition=3,
                overall_score=3.75,
            ),
        ),
    ]

    print(f"  • Created {len(fake_calls)} test calls")
    print(f"  • Created {len(fake_accounts)} test accounts")

    # Test 1: Call Summary Table (by rep)
    print(f"\n📊 Test 1: Posting Call Summary Table (by rep)...")
    try:
        success = await slack_client.post_summary_table(fake_calls)
        if success:
            print(f"   ✅ SUCCESS - Check your Slack channel!")
        else:
            print(f"   ❌ FAILED - Check error logs above")
            return False
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        return False

    # Wait a bit to avoid rate limiting
    await asyncio.sleep(2)

    # Test 2: Account Summary Table (by domain)
    print(f"\n📊 Test 2: Posting Account Summary Table (by domain)...")
    try:
        success = await slack_client.post_account_summary_table(fake_accounts)
        if success:
            print(f"   ✅ SUCCESS - Check your Slack channel!")
        else:
            print(f"   ❌ FAILED - Check error logs above")
            return False
    except Exception as e:
        print(f"   ❌ ERROR: {e}")
        return False

    print(f"\n{'='*80}")
    print(f"✅ All tests passed! Check your Slack channel for the summary tables.")
    print(f"{'='*80}")
    return True


if __name__ == "__main__":
    success = asyncio.run(test_slack_summaries())
    sys.exit(0 if success else 1)
