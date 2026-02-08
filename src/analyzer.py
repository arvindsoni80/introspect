"""Main analyzer orchestrating the analysis workflow."""

from datetime import datetime
from typing import Optional

from .config import Settings
from .gong_client import AsyncGongClient
from .llm_client import LLMClient
from .models import CallAnalysis
from .repository import CallRepository
from .sqlite_repository import SQLiteCallRepository


class CallAnalyzer:
    """Orchestrates the analysis workflow."""

    def __init__(self, settings: Settings, slack_client=None, repository: Optional[CallRepository] = None):
        """Initialize the analyzer."""
        self.settings = settings
        self.llm_client = LLMClient(settings)
        self.slack_client = slack_client

        # Initialize repository if not provided
        if repository is None:
            if settings.db_type == "sqlite":
                repository = SQLiteCallRepository(settings.sqlite_db_path)
            # Future: Add firestore support
            # elif settings.db_type == "firestore":
            #     repository = FirestoreCallRepository(settings.firestore_project)
        self.repository = repository

    async def analyze_calls(
        self, sales_rep_emails: list[str], verbose: bool = True
    ) -> list[CallAnalysis]:
        """
        Analyze calls for specified sales reps.

        If slack_client is provided, posts results as they complete (grouped by rep).

        Args:
            sales_rep_emails: List of sales rep email addresses (should be pre-sorted)
            verbose: Print progress information

        Returns:
            List of CallAnalysis results
        """
        results = []

        def log(msg: str):
            if verbose:
                print(msg)

        async with AsyncGongClient(self.settings) as gong_client:
            # Step 1: Fetch calls from Gong (already filtered for external participants)
            log(f"\n📞 Fetching calls with extended metadata (last {self.settings.gong_lookback_days} days)...")
            # Request more fields to get account/deal information
            calls = await gong_client.get_calls_for_sales_reps(sales_rep_emails, include_all_fields=False)

            if not calls:
                log("   No calls found with external participants")
                return results

            # Group by rep for reporting
            calls_by_rep = {}
            for call in calls:
                email = call.get("sales_rep_email", "Unknown")
                calls_by_rep[email] = calls_by_rep.get(email, 0) + 1

            log(f"   ✓ Found {len(calls)} calls with external participants")
            for email, count in sorted(calls_by_rep.items()):
                log(f"     • {email}: {count} calls")

            # Step 2: Extract call IDs for batch transcript fetch
            call_ids = []
            for call in calls:
                meta = call.get("metaData", {})
                call_id = meta.get("id")
                if call_id:
                    call_ids.append(call_id)

            # Step 3: Batch fetch transcripts
            log(f"\n📝 Fetching transcripts for {len(call_ids)} calls...")
            transcripts = await gong_client.get_transcripts(call_ids)
            log(f"   ✓ Fetched {len(transcripts)} transcripts")

            transcripts_by_rep = {}
            for call in calls:
                email = call.get("sales_rep_email", "Unknown")
                call_id = call.get("metaData", {}).get("id")
                if call_id and call_id in transcripts:
                    transcripts_by_rep[email] = transcripts_by_rep.get(email, 0) + 1

            for email, count in sorted(transcripts_by_rep.items()):
                log(f"     • {email}: {count} transcripts")

            # Step 4: Group calls by rep for ordered processing
            calls_by_rep = {}
            for call in calls:
                email = call.get("sales_rep_email", "Unknown")
                if email not in calls_by_rep:
                    calls_by_rep[email] = []
                calls_by_rep[email].append(call)

            # Step 5: Process each rep's calls in alphabetical order
            log(f"\n🤖 Analyzing calls with LLM (processing by rep)...")

            total_processed = 0
            for rep_email in sorted(calls_by_rep.keys()):
                rep_calls = calls_by_rep[rep_email]
                log(f"\n   Processing {rep_email} ({len(rep_calls)} calls)...")

                # Post thread header if Slack client provided
                if self.slack_client:
                    await self.slack_client.post_rep_thread_header(rep_email)

                rep_discovery_count = 0

                for i, call in enumerate(rep_calls, 1):
                    total_processed += 1
                    meta = call.get("metaData", {})
                    call_id = meta.get("id")
                    call_title = meta.get("title", "Untitled")
                    sales_rep = call.get("sales_rep_email", "Unknown")

                    if not call_id or call_id not in transcripts:
                        log(f"      [{i}/{len(rep_calls)}] Skipping {call_id} - no transcript")
                        continue

                    # Check if call already evaluated (skip LLM analysis)
                    if self.repository and await self.repository.call_exists(call_id):
                        log(f"      [{i}/{len(rep_calls)}] Skipping {call_id} - already evaluated")
                        continue

                    transcript = transcripts[call_id]

                    log(f"      [{i}/{len(rep_calls)}] {call_title[:50]}...")

                    # Classify if discovery call
                    is_discovery, reasoning = await self.llm_client.is_discovery_call(transcript)

                    # Extract participants
                    participants = gong_client.extract_participants(call)

                    # Build Gong link
                    gong_link = f"https://app.gong.io/call?id={call_id}"

                    # Parse call date
                    call_started = meta.get("started")
                    call_date = (
                        datetime.fromisoformat(call_started.replace("Z", "+00:00"))
                        if call_started
                        else datetime.now()
                    )

                    # Build base analysis
                    analysis = CallAnalysis(
                        call_id=call_id,
                        call_title=call_title,
                        gong_link=gong_link,
                        call_date=call_date,
                        sales_rep_email=call.get("sales_rep_email", ""),
                        participants=participants,
                        is_discovery_call=is_discovery,
                        discovery_reasoning=reasoning,
                    )

                    # If discovery call, score MEDDPICC
                    if is_discovery:
                        log(f"         → ✅ Discovery call!")
                        log(f"         → Scoring MEDDPICC...")
                        scores, notes, summary = await self.llm_client.score_meddpicc(transcript)
                        analysis.meddpicc_scores = scores
                        analysis.meddpicc_summary = summary
                        analysis.analysis_notes = notes
                        log(f"         → Score: {scores.overall_score}/5.0")

                        rep_discovery_count += 1

                        # Store in database if repository available
                        if self.repository and participants.external:
                            # Extract domain from first external participant
                            first_external = participants.external[0]
                            domain = first_external.split("@")[-1] if "@" in first_external else first_external
                            log(f"         → Storing to database (domain: {domain})...")
                            account_record = await self.repository.add_discovery_call(domain, analysis)
                            log(f"         → Account now has {len(account_record.calls)} discovery call(s)")
                            log(f"         → Account overall score: {account_record.overall_meddpicc.overall_score}/5.0")

                        # Post to Slack immediately
                        if self.slack_client:
                            log(f"         → Posting to Slack...")
                            await self.slack_client.post_call_eval(analysis)
                    else:
                        log(f"         → ❌ Not discovery")

                    results.append(analysis)

                # Post completion summary for this rep
                if self.slack_client:
                    log(f"   → Posting completion summary for {rep_email}...")
                    await self.slack_client.post_rep_completion_summary(
                        rep_email, rep_discovery_count, len(rep_calls)
                    )

            discovery_count = sum(1 for r in results if r.is_discovery_call)
            log(f"\n✓ Analysis complete:")
            log(f"   • Total external calls: {len(results)}")
            log(f"   • Discovery calls: {discovery_count}")

            # Post summary table at the end
            if self.slack_client and discovery_count > 0:
                log(f"\n📊 Posting summary table...")
                await self.slack_client.post_summary_table(results)

        return results

    async def close(self) -> None:
        """Close any open connections."""
        if self.repository:
            await self.repository.close()
