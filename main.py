#!/usr/bin/env python3
"""
Introspect - Gong Transcript MEDDPICC Analysis Tool

Main entry point for the CLI application.
"""

import asyncio
import sys
from pathlib import Path

import click

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.analyzer import CallAnalyzer
from src.config import load_settings
from src.formatters import format_console_output
from src.slack_client import SlackClient


@click.command()
@click.option(
    "--sales-reps",
    multiple=True,
    help="Sales rep email addresses (can specify multiple times)",
)
@click.option(
    "--sales-reps-file",
    type=click.Path(exists=True),
    help="File containing sales rep emails (one per line)",
)
@click.option(
    "--post-slack",
    is_flag=True,
    help="Post discovery calls to Slack (requires SLACK_BOT_TOKEN in .env)",
)
def main(sales_reps, sales_reps_file, post_slack):
    """
    Analyze Gong call transcripts for MEDDPICC scoring.

    Fetches calls from the last 7 days where specified sales reps participated
    and external participants were present. Discovery calls are scored on
    MEDDPICC dimensions.
    """
    # Collect email addresses
    emails = list(sales_reps)

    if sales_reps_file:
        with open(sales_reps_file) as f:
            file_emails = [line.strip() for line in f if line.strip()]
            emails.extend(file_emails)

    if not emails:
        click.echo("Error: No sales rep emails provided.", err=True)
        click.echo(
            "Use --sales-reps or --sales-reps-file to specify email addresses."
        )
        sys.exit(1)

    # Sort emails alphabetically for consistent processing order
    emails = sorted(set(emails))  # Remove duplicates and sort

    click.echo("\n" + "=" * 70)
    click.echo("Introspect - Gong Transcript MEDDPICC Analysis")
    click.echo("=" * 70)
    click.echo(f"\n📧 Sales reps (alphabetical): {', '.join(emails)}")

    try:
        settings = load_settings()
        click.echo(f"⚙️  Configuration loaded")
        click.echo(f"   • Gong API: {settings.gong_api_url}")
        click.echo(f"   • LLM Model: {settings.llm_model}")
        click.echo(f"   • Lookback: {settings.gong_lookback_days} days")
    except Exception as e:
        click.echo(f"\n❌ Error loading settings: {e}", err=True)
        click.echo("\nMake sure .env file is configured correctly.")
        sys.exit(1)

    # Run async analysis
    try:
        results = asyncio.run(analyze(settings, emails, post_slack))
    except Exception as e:
        click.echo(f"\n❌ Error during analysis: {e}", err=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Display console output
    console_output = format_console_output(results)
    click.echo(console_output)


async def analyze(settings, emails, post_slack):
    """Run the async analysis."""
    # Initialize Slack client if posting enabled
    slack_client = None
    if post_slack:
        if not settings.slack_bot_token or not settings.slack_channel_id:
            click.echo("\n⚠️  --post-slack enabled but SLACK_BOT_TOKEN or SLACK_CHANNEL_ID not configured in .env")
            click.echo("   See: https://api.slack.com/messaging/sending#getting_started")
        else:
            slack_client = SlackClient(settings.slack_bot_token, settings.slack_channel_id)
            click.echo("\n📤 Slack posting enabled (will post as analysis completes)")

    # Run analysis with Slack client - posts as it processes
    analyzer = CallAnalyzer(settings, slack_client=slack_client)
    try:
        if analyzer.repository:
            click.echo(f"💾 Database: {settings.db_type} ({settings.sqlite_db_path if settings.db_type == 'sqlite' else 'N/A'})")
            click.echo(f"   ✓ Repository initialized - deduplication enabled")
        else:
            click.echo(f"⚠️  No repository - calls will not be deduplicated")
        results = await analyzer.analyze_calls(emails, verbose=True)
        return results
    finally:
        # Always close repository connection
        await analyzer.close()


if __name__ == "__main__":
    main()
