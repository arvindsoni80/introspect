#!/usr/bin/env python3
"""
Introspect CLI - Command-line interface for the tool.
"""

import asyncio
import subprocess
import sys
from pathlib import Path

import click

from src.analyzer import CallAnalyzer
from src.config import load_settings
from src.formatters import format_console_output
from src.models import CallAnalysis, Participants
from src.slack_client import SlackClient
from src.sqlite_repository import SQLiteCallRepository


@click.group()
@click.version_option(version="1.0.0", prog_name="introspect")
def cli():
    """
    Introspect - Gong Transcript MEDDPICC Analysis Tool

    Analyze sales discovery calls and track MEDDPICC qualification.
    """
    pass


@cli.command()
@click.option(
    "-t",
    "--days",
    type=int,
    default=7,
    help="Lookback window in days (default: 7)",
)
@click.option(
    "-r",
    "--rep",
    "reps",
    multiple=True,
    help="Sales rep email (can specify multiple times)",
)
@click.option(
    "--reps-file",
    type=click.Path(exists=True),
    help="File containing sales rep emails (one per line)",
)
@click.option(
    "-p",
    "--post-slack",
    is_flag=True,
    help="Post discovery calls to Slack after analysis",
)
def analyze(days, reps, reps_file, post_slack):
    """
    Analyze Gong call transcripts for MEDDPICC scoring.

    Fetches calls from the specified lookback window where sales reps participated
    and external participants were present. Discovery calls are scored on
    MEDDPICC dimensions.

    Examples:
        introspect analyze -t 7 -r john@company.com -p
        introspect analyze --days 30 --reps-file sales_reps.txt
        introspect analyze --post-slack
    """
    # Collect email addresses
    emails = list(reps)

    if reps_file:
        with open(reps_file) as f:
            file_emails = [line.strip() for line in f if line.strip()]
            emails.extend(file_emails)

    # Default to sales_reps.txt if no reps specified
    if not emails:
        default_file = Path("sales_reps.txt")
        if default_file.exists():
            with open(default_file) as f:
                emails = [line.strip() for line in f if line.strip()]
            click.echo(f"📋 Using sales reps from sales_reps.txt")
        else:
            click.echo("Error: No sales rep emails provided.", err=True)
            click.echo("Use -r or --reps-file to specify email addresses, or create sales_reps.txt")
            sys.exit(1)

    # Sort emails alphabetically for consistent processing order
    emails = sorted(set(emails))  # Remove duplicates and sort

    click.echo("\n" + "=" * 70)
    click.echo("Introspect - Gong Transcript MEDDPICC Analysis")
    click.echo("=" * 70)
    click.echo(f"\n📧 Sales reps: {', '.join(emails)}")
    click.echo(f"📅 Lookback: {days} days")

    try:
        settings = load_settings()
        # Override lookback days with CLI parameter
        settings.gong_lookback_days = days

        click.echo(f"⚙️  Configuration loaded")
        click.echo(f"   • Gong API: {settings.gong_api_url}")
        click.echo(f"   • LLM Model: {settings.llm_model}")
    except Exception as e:
        click.echo(f"\n❌ Error loading settings: {e}", err=True)
        click.echo("\nMake sure .env file is configured correctly.")
        sys.exit(1)

    # Run async analysis
    try:
        results = asyncio.run(run_analysis(settings, emails, post_slack))
    except Exception as e:
        click.echo(f"\n❌ Error during analysis: {e}", err=True)
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Display console output
    console_output = format_console_output(results)
    click.echo(console_output)


async def run_analysis(settings, emails, post_slack):
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


@cli.command()
@click.option(
    "-a",
    "--accounts",
    is_flag=True,
    help="Post account summaries (grouped by domain)",
)
@click.option(
    "-r",
    "--reps",
    is_flag=True,
    help="Post sales rep summaries (grouped by rep)",
)
def post(accounts, reps):
    """
    Post MEDDPICC summary tables to Slack from database.

    Reads discovery calls from the database and posts to Slack in batches.
    No analysis is performed - just reads and posts existing data.

    If neither -a nor -r is specified, both summaries are posted.

    Examples:
        introspect post              # Post both summaries
        introspect post -a           # Post only account summaries
        introspect post -r           # Post only rep summaries
        introspect post -a -r        # Post both summaries
    """
    # Default to both if neither specified
    if not accounts and not reps:
        accounts = True
        reps = True

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
        asyncio.run(post_summaries(settings, reps, accounts))
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
            click.echo("   Run 'introspect analyze' first to populate the database")
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


@cli.command()
@click.option(
    "--port",
    type=int,
    default=8501,
    help="Port to run the UI on (default: 8501)",
)
@click.option(
    "--host",
    default="localhost",
    help="Host to bind to (default: localhost)",
)
def ui(port, host):
    """
    Launch the Streamlit coaching dashboard.

    Opens an interactive web interface for exploring MEDDPICC scores,
    coaching insights, and account qualification.

    Examples:
        introspect ui                    # Launch on default port 8501
        introspect ui --port 8080        # Launch on custom port
        introspect ui --host 0.0.0.0     # Make accessible on network
    """
    # Find the streamlit_app directory
    # cli.py is in src/, so we go up one level to project root
    cli_file = Path(__file__).resolve()
    project_root = cli_file.parent.parent
    streamlit_app_path = project_root / "streamlit_app" / "app.py"

    if not streamlit_app_path.exists():
        click.echo(f"\n❌ Error: Could not find Streamlit app at {streamlit_app_path}", err=True)
        click.echo("   Make sure streamlit_app/app.py exists in the project directory.")
        sys.exit(1)

    click.echo("\n" + "=" * 70)
    click.echo("Introspect - Launching Coaching Dashboard")
    click.echo("=" * 70)
    click.echo(f"\n🚀 Starting Streamlit UI...")
    click.echo(f"   • URL: http://{host}:{port}")
    click.echo(f"   • Path: {streamlit_app_path}")
    click.echo("\n💡 Press Ctrl+C to stop the server\n")

    # Launch streamlit
    try:
        subprocess.run(
            [
                "streamlit",
                "run",
                str(streamlit_app_path),
                "--server.port", str(port),
                "--server.address", host,
                "--server.headless", "true",
            ],
            check=True
        )
    except subprocess.CalledProcessError as e:
        click.echo(f"\n❌ Error launching Streamlit: {e}", err=True)
        sys.exit(1)
    except KeyboardInterrupt:
        click.echo("\n\n👋 Shutting down UI...")
    except FileNotFoundError:
        click.echo("\n❌ Error: Streamlit is not installed", err=True)
        click.echo("   Install it with: pip install streamlit")
        sys.exit(1)
