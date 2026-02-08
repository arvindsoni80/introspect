#!/usr/bin/env python3
"""
Test script to verify Gong API integration.

Tests:
1. Map sales rep emails to Gong user IDs
2. Fetch calls with external participants
3. Fetch transcripts for those calls
"""

import asyncio
import sys
from pathlib import Path

import click

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import load_settings
from src.gong_client import AsyncGongClient


async def test_gong_connection(sales_rep_emails: list[str]):
    """Test Gong API connection and call fetching."""
    print("=" * 70)
    print("Gong API Integration Test")
    print("=" * 70)

    # Load settings
    print("\nStep 1: Loading configuration...")
    try:
        settings = load_settings()
        print(f"  ✓ Config loaded")
        print(f"    - API URL: {settings.gong_api_url}")
        print(f"    - Lookback days: {settings.gong_lookback_days}")
        print(f"    - Internal domain: {settings.internal_domain}")
    except Exception as e:
        print(f"  ✗ Error: {e}")
        print("\n  Make sure .env file has:")
        print("    GONG_API_URL, GONG_ACCESS_KEY, GONG_SECRET_KEY, INTERNAL_DOMAIN")
        return False

    try:
        async with AsyncGongClient(settings) as gong:
            # Step 1: Map emails to user IDs
            print(f"\nStep 2: Mapping {len(sales_rep_emails)} email(s) to Gong user IDs...")
            email_to_id = await gong.get_user_ids_for_emails(sales_rep_emails)

            if not email_to_id:
                print(f"  ✗ No matching Gong users found")
                print(f"\n  Checking available users...")
                users = await gong.list_users()
                print(f"  Found {len(users)} total users. First 10:")
                for u in users[:10]:
                    email = u.get("emailAddress") or u.get("email")
                    name = f"{u.get('firstName', '')} {u.get('lastName', '')}".strip()
                    print(f"    - {email} ({name})")
                return False

            print(f"  ✓ Mapped {len(email_to_id)} emails to user IDs:")
            for email, user_id in email_to_id.items():
                print(f"    - {email} → {user_id}")

            # Step 2: Fetch calls with external participants
            print(f"\nStep 3: Fetching calls with external participants...")
            calls = await gong.get_calls_for_sales_reps(sales_rep_emails)

            if not calls:
                print(f"  ⚠️  No calls found with external participants")
                print(f"     (Last {settings.gong_lookback_days} days)")
                print("\n" + "=" * 70)
                print("✓ Test completed - Gong API working, but no calls to analyze")
                print("=" * 70)
                return True

            print(f"  ✓ Found {len(calls)} calls with external participants")

            # Group calls by email
            calls_by_email = {}
            for call in calls:
                email = call.get("sales_rep_email", "Unknown")
                if email not in calls_by_email:
                    calls_by_email[email] = []
                calls_by_email[email].append(call)

            # Step 3: Fetch transcripts
            print(f"\nStep 4: Fetching transcripts...")
            all_call_ids = [
                call.get("metaData", {}).get("id")
                for call in calls
                if call.get("metaData", {}).get("id")
            ]

            transcripts = await gong.get_transcripts(all_call_ids)
            print(f"  ✓ Fetched {len(transcripts)} transcripts")

            # Step 4: Print status per email
            print(f"\nStep 5: Status per sales rep:")
            print("  " + "-" * 66)
            print(f"  {'Email':<40} {'Calls':<12} {'Transcripts':<15} {'Status'}")
            print("  " + "-" * 66)

            all_match = True
            for email in sales_rep_emails:
                if email not in calls_by_email:
                    print(f"  {email:<40} {'0':<12} {'0':<15} ⚠️  No calls")
                    continue

                rep_calls = calls_by_email[email]
                rep_call_ids = [
                    c.get("metaData", {}).get("id") for c in rep_calls
                ]
                rep_transcript_count = sum(
                    1 for cid in rep_call_ids if cid and cid in transcripts
                )

                status = (
                    "✓ OK"
                    if rep_transcript_count == len(rep_calls)
                    else "⚠️  MISSING"
                )
                if rep_transcript_count != len(rep_calls):
                    all_match = False

                print(
                    f"  {email:<40} {len(rep_calls):<12} "
                    f"{rep_transcript_count:<15} {status}"
                )

            print("  " + "-" * 66)

            # Sample transcript preview
            if transcripts:
                sample_id = list(transcripts.keys())[0]
                sample_text = transcripts[sample_id]
                print(f"\nSample transcript preview:")
                print(f"  Call ID: {sample_id}")
                print(f"  Length: {len(sample_text)} characters")
                print(f"  First 200 chars: {sample_text[:200]}...")

            # Final summary
            print("\n" + "=" * 70)
            if all_match and transcripts:
                print("✓ All tests PASSED!")
                print("  - All emails mapped to user IDs")
                print("  - All calls have external participants")
                print("  - All calls have transcripts")
            elif not transcripts:
                print("⚠️  Tests passed but no transcripts available")
            else:
                print("⚠️  Some transcripts missing")
                print("  This may indicate calls without recorded transcripts")
            print("=" * 70)

            print(f"\nSummary:")
            print(f"  - Sales reps tested: {len(sales_rep_emails)}")
            print(f"  - Calls with external participants: {len(calls)}")
            print(f"  - Transcripts fetched: {len(transcripts)}")
            print(f"\n✓ Ready to run main analysis with --post-slack")

            return True

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback

        print("\nFull traceback:")
        traceback.print_exc()
        return False


@click.command()
@click.option(
    "--sales-reps",
    multiple=True,
    help="Sales rep email addresses",
)
@click.option(
    "--sales-reps-file",
    type=click.Path(exists=True),
    help="File containing sales rep emails (one per line)",
)
def main(sales_reps, sales_reps_file):
    """Test Gong API integration without LLM calls."""
    # Collect emails
    emails = list(sales_reps)

    if sales_reps_file:
        with open(sales_reps_file) as f:
            file_emails = [
                line.strip()
                for line in f
                if line.strip() and not line.strip().startswith("#")
            ]
            emails.extend(file_emails)

    if not emails:
        click.echo("Error: No sales rep emails provided.")
        click.echo("\nUsage:")
        click.echo("  python test_gong.py --sales-reps email@company.com")
        click.echo("  python test_gong.py --sales-reps-file sales_reps.txt")
        sys.exit(1)

    success = asyncio.run(test_gong_connection(emails))
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
