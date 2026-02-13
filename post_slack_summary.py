#!/usr/bin/env python3
"""
Post summary tables to Slack from database.

Standalone script to post MEDDPICC summaries without running analysis.
Useful for daily status updates or when you want to view historical data.
"""

import asyncio
import sys
from pathlib import Path

import click

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config import load_settings
from src.models import CallAnalysis, Participants
from src.slack_client import SlackClient
from src.sqlite_repository import SQLiteCallRepository


@click.command()
@click.option(
    "--by-rep",
    is_flag=True,
    help="Post call summary table (grouped by sales rep)",
)
@click.option(
    "--by-domain",
    is_flag=True,
    help="Post account summary table (grouped by domain)",
)
def main(by_rep, by_domain):
    """
    Post MEDDPICC summary tables to Slack from database.

    Reads all discovery calls from the database and posts to Slack in batches.
    No analysis is performed - just reads and posts existing data.

    Examples:
        # Post both tables
        python post_slack_summary.py --by-rep --by-domain

        # Post only call summary (by rep)
        python post_slack_summary.py --by-rep

        # Post only account summary (by domain)
        python post_slack_summary.py --by-domain
    """
    # Default to both if neither specified
    if not by_rep and not by_domain:
        by_rep = True
        by_domain = True

    click.echo("\n" + "=" * 70)
    click.echo("Post Slack Summary - Database to Slack")
    click.echo("=" * 70)

    try:
        settings = load_settings()

        if not settings.slack_bot_token or not settings.slack_channel_id:
            click.echo("\n❌ Error: Slack not configured")
            click.echo("   Add SLACK_BOT_TOKEN and SLACK_CHANNEL_ID to .env")
            sys.exit(1)

        click.echo(f"\n✓ Configuration loaded")
        click.echo(f"  • Database: {settings.sqlite_db_path}")
        click.echo(f"  • Slack Channel: {settings.slack_channel_id}")

    except Exception as e:
        click.echo(f"\n❌ Error loading settings: {e}")
        sys.exit(1)

    # Run async posting
    try:
        asyncio.run(post_summaries(settings, by_rep, by_domain))
        click.echo("\n✅ Done!")
    except Exception as e:
        click.echo(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


async def post_summaries(settings, by_rep: bool, by_domain: bool):
    """Post summary tables to Slack."""
    # Initialize repository
    repository = SQLiteCallRepository(settings.sqlite_db_path)

    try:
        # Check database
        all_accounts = await repository.get_all_accounts()

        if not all_accounts:
            click.echo("\n⚠️  No accounts found in database")
            click.echo("   Run the analyzer first to populate the database")
            return

        # Count total calls
        total_calls = sum(len(account.calls) for account in all_accounts)

        click.echo(f"\n📊 Database summary:")
        click.echo(f"   • Accounts: {len(all_accounts)}")
        click.echo(f"   • Discovery calls: {total_calls}")

        # Initialize Slack client
        slack_client = SlackClient(settings.slack_bot_token, settings.slack_channel_id)

        # Post call summary (by rep)
        if by_rep:
            click.echo(f"\n📤 Posting call summary table (by rep) in batches...")

            # Build CallAnalysis objects from database
            call_analyses = []
            for account in all_accounts:
                for call in account.calls:
                    analysis = CallAnalysis(
                        call_id=call.call_id,
                        call_title=f"Discovery - {account.domain}",
                        gong_link=f"https://app.gong.io/call?id={call.call_id}",
                        call_date=call.call_date,
                        sales_rep_email=call.sales_rep,
                        participants=Participants(
                            internal=[call.sales_rep],
                            external=call.external_participants
                        ),
                        is_discovery_call=True,
                        meddpicc_scores=call.meddpicc_scores,
                        meddpicc_summary=call.meddpicc_summary or "",
                        discovery_reasoning="From database",
                    )
                    call_analyses.append(analysis)

            # Post in batches (batch_size defaults to 25, grouped by rep)
            success = await slack_client.post_summary_table_batched(call_analyses)

            if success:
                click.echo(f"   ✅ Posted {len(call_analyses)} calls in batches (grouped by rep)")
            else:
                click.echo(f"   ❌ Failed to post call summary")

        # Post account summary (by domain)
        if by_domain:
            click.echo(f"\n📤 Posting account summary table (by domain) in batches...")

            success = await slack_client.post_account_summary_table_batched(all_accounts)

            if success:
                click.echo(f"   ✅ Posted {len(all_accounts)} accounts in batches")
            else:
                click.echo(f"   ❌ Failed to post account summary")

    finally:
        await repository.close()


if __name__ == "__main__":
    main()
