"""Call processor orchestrates the entire evaluation flow."""

from datetime import datetime
from typing import Optional, Dict, Any

from ..core.llm_client import LLMClient
from ..core.gong_client import GongClient
from ..data import Repository
from ..domain import (
    Call, Account, SalesRep,
    CallMEDDPICCScores, CallTrialScores, CallCloseScores, CallWinLossAnalysis,
    AccountRepHistory,
)
from .stage_classifier import StageClassifier
from .evaluators import MEDDPICCEvaluator, TrialEvaluator, CloseEvaluator, WinLossAnalyzer


class CallProcessor:
    """Orchestrates fetching, classifying, and evaluating calls."""

    def __init__(
        self,
        gong_client: GongClient,
        llm_client: LLMClient,
        repository: Repository,
        internal_domain: str = "",
    ):
        """
        Initialize call processor.

        Args:
            gong_client: Gong API client
            llm_client: LLM client for evaluations
            repository: Data repository
            internal_domain: Company domain for identifying internal participants
        """
        self.gong_client = gong_client
        self.llm_client = llm_client
        self.repository = repository
        self.internal_domain = internal_domain

        # Initialize services
        self.stage_classifier = StageClassifier(llm_client)
        self.meddpicc_evaluator = MEDDPICCEvaluator(llm_client)
        self.trial_evaluator = TrialEvaluator(llm_client)
        self.close_evaluator = CloseEvaluator(llm_client)
        self.winloss_analyzer = WinLossAnalyzer(llm_client)

    def process_call(self, call_data: dict, transcript: str) -> Call:
        """
        Process a single call: classify, evaluate, and store.

        Args:
            call_data: Call data dict from Gong API (with metaData, parties, etc.)
            transcript: Call transcript text

        Returns:
            Call object with evaluation scores stored
        """
        # Extract call ID and metadata
        meta = call_data.get("metaData", {})
        gong_call_id = call_data.get("id") or meta.get("id")
        call_title = meta.get("title", "")
        started = meta.get("started", "")

        print(f"\n{'='*60}")
        print(f"Processing call: {gong_call_id}")
        print(f"  Title: {call_title[:50]}")
        print(f"{'='*60}")

        # 1. Check if call already processed
        existing_call = self.repository.get_call_by_gong_id(gong_call_id)
        if existing_call:
            print(f"✓ Call already processed (call_id: {existing_call.call_id})")
            return existing_call

        # 2. Parse call data
        try:
            call_date = datetime.fromisoformat(started.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            call_date = datetime.now()
            print(f"  ⚠️  Could not parse date, using current time")

        parties = call_data.get("parties", [])

        # Extract sales rep and customer domain
        sales_rep_email = call_data.get("sales_rep_email") or self._extract_sales_rep(parties)
        customer_domain = self._extract_customer_domain(parties)

        print(f"  Sales Rep: {sales_rep_email}")
        print(f"  Customer Domain: {customer_domain}")
        print(f"  Call Date: {call_date.strftime('%Y-%m-%d')}")

        if not transcript:
            print(f"  ⚠️  No transcript available, skipping...")
            return None

        # 3. Ensure sales rep exists
        self._ensure_sales_rep_exists(sales_rep_email)

        # 4. Get or create account
        account = self._get_or_create_account(customer_domain)
        print(f"  Account ID: {account.id}")

        # 5. Classify stage
        print("\n→ Classifying call stage...")
        stage_result = self.stage_classifier.classify_stage(transcript, call_title)
        print(f"  Primary Stage: {stage_result.primary_stage}")
        print(f"  Confidence: {stage_result.confidence:.2f}")
        if stage_result.secondary_stage:
            print(f"  Secondary Stage: {stage_result.secondary_stage}")

        # 6. Create call record
        call = Call(
            call_id=gong_call_id,
            account_id=account.id,
            sales_rep_email=sales_rep_email,
            call_date=call_date,
            call_title=call_title,
            primary_stage=stage_result.primary_stage,
            secondary_stage=stage_result.secondary_stage,
            stage_confidence=stage_result.confidence,
            segment_at_call_time=account.primary_segment,
        )
        call = self.repository.create_call(call)
        print(f"\n✓ Call created (ID: {call.call_id})")

        # 6b. Store call participants
        if parties:
            try:
                inserted_count = self.repository.store_call_participants(gong_call_id, parties)
                print(f"✓ Stored {inserted_count} participants")
            except Exception as e:
                print(f"⚠️  Failed to store participants: {e}")

        # 6c. Enrich transcript with participant info
        enriched_transcript = self.repository.enrich_transcript_with_participants(gong_call_id, transcript)
        participants_count = len(self.repository.get_call_participants(gong_call_id))
        if participants_count > 0:
            print(f"✓ Enriched transcript with {participants_count} participants")

        # 7. Evaluate based on stage (using enriched transcript)
        print(f"\n→ Evaluating {stage_result.primary_stage} stage...")
        if stage_result.primary_stage == "discovery":
            self._evaluate_discovery(call, enriched_transcript)
        elif stage_result.primary_stage == "trial":
            self._evaluate_trial(call, enriched_transcript)
        elif stage_result.primary_stage == "negotiation":
            self._evaluate_negotiation(call, enriched_transcript)
        elif stage_result.primary_stage == "closed":
            self._evaluate_closed(call, enriched_transcript)

        # 8. Update account state
        print("\n→ Updating account state...")
        self._update_account_after_call(account, call)

        # 9. Update account-rep history
        self._update_account_rep_history(account.id, sales_rep_email, call_date)

        print(f"\n{'='*60}")
        print(f"✅ Call processing complete!")
        print(f"{'='*60}\n")

        return call

    def _extract_sales_rep(self, parties: list) -> str:
        """Extract sales rep email from call parties."""
        # Find internal participant
        for party in parties:
            email = party.get("emailAddress", "")
            if self.internal_domain and f"@{self.internal_domain}" in email:
                return email
        # Fallback to first participant if no match
        return parties[0].get("emailAddress", "unknown@example.com") if parties else "unknown@example.com"

    def _extract_customer_domain(self, parties: list) -> str:
        """Extract customer email domain from call parties."""
        # Find external participant
        for party in parties:
            email = party.get("emailAddress", "")
            if "@" in email:
                domain = email.split("@")[1]
                # Skip if it's our internal domain
                if self.internal_domain and domain == self.internal_domain:
                    continue
                return domain
        # Fallback
        return "unknown.com"

    def _ensure_sales_rep_exists(self, email: str):
        """Ensure sales rep exists in database."""
        existing_rep = self.repository.get_sales_rep(email)
        if not existing_rep:
            # Create placeholder rep (ideally this would be loaded from a config)
            rep = SalesRep(
                email=email,
                segment="unknown",
                joining_date=datetime.now().date(),
                is_active=True,
            )
            self.repository.create_sales_rep(rep)
            print(f"  ℹ️  Created new sales rep: {email}")

    def _get_or_create_account(self, domain: str) -> Account:
        """Get or create account by domain."""
        account = self.repository.get_account_by_domain(domain)
        if not account:
            account = Account(
                id=None,
                domain=domain,
                current_stage=None,
                deal_status="active",
            )
            account = self.repository.create_account(account)
            print(f"  ℹ️  Created new account: {domain}")
        return account

    def _evaluate_discovery(self, call: Call, transcript: str):
        """Evaluate discovery stage call."""
        scores = self.meddpicc_evaluator.evaluate(transcript)
        print(f"  Overall MEDDPICC Score: {scores.overall_score:.1f}")

        # Save to database
        call_scores = CallMEDDPICCScores(
            call_id=call.call_id,
            scores=scores,
        )
        self.repository.create_call_meddpicc_scores(call_scores)
        print("  ✓ MEDDPICC scores saved")

    def _evaluate_trial(self, call: Call, transcript: str):
        """Evaluate trial stage call."""
        scores = self.trial_evaluator.evaluate(transcript)
        print(f"  Overall Trial Health: {scores.overall_score:.1f} ({scores.health_interpretation})")

        # Save to database
        call_scores = CallTrialScores(
            call_id=call.call_id,
            scores=scores,
        )
        self.repository.create_call_trial_scores(call_scores)
        print("  ✓ Trial scores saved")

    def _evaluate_negotiation(self, call: Call, transcript: str):
        """Evaluate negotiation stage call."""
        scores = self.close_evaluator.evaluate(transcript)
        print(f"  Overall Deal Health: {scores.overall_score:.1f} ({scores.health_interpretation})")

        # Save to database
        call_scores = CallCloseScores(
            call_id=call.call_id,
            scores=scores,
        )
        self.repository.create_call_close_scores(call_scores)
        print("  ✓ Close scores saved")

    def _evaluate_closed(self, call: Call, transcript: str):
        """Evaluate closed stage call."""
        analysis = self.winloss_analyzer.evaluate(transcript)
        print(f"  Outcome: {analysis.outcome.upper()}")
        print(f"  Primary Reasons: {analysis.primary_reasons}")

        # Save to database
        call_analysis = CallWinLossAnalysis(
            call_id=call.call_id,
            analysis=analysis,
        )
        self.repository.create_call_win_loss_analysis(call_analysis)
        print("  ✓ Win/Loss analysis saved")

    def _update_account_after_call(self, account: Account, call: Call):
        """Update account state after processing a call.

        Note: Calls can be processed in any order (not necessarily chronological).
        Only update stage, primary_sales_rep, primary_segment, and last_call_date if this call is newer.
        """
        # Only update current state fields if this call is newer
        if account.last_call_date is None or call.call_date > account.last_call_date:
            # Get sales rep's segment
            sales_rep = self.repository.get_sales_rep(call.sales_rep_email)
            rep_segment = sales_rep.segment if sales_rep else "unknown"

            # Update all "current state" fields
            account.current_stage = call.primary_stage
            account.primary_sales_rep = call.sales_rep_email
            account.primary_segment = rep_segment
            account.last_call_date = call.call_date

            print(f"  → Updated state (newer call): stage={call.primary_stage}, rep={call.sales_rep_email}, segment={rep_segment}")
        else:
            print(f"  → State not updated (call is older than last_call_date)")

        # Only update first_call_date if this call is older
        if account.first_call_date is None or call.call_date < account.first_call_date:
            account.first_call_date = call.call_date

        # Always increment total calls
        account.total_calls += 1

        # Save account
        self.repository.update_account(account)
        print(f"  ✓ Account updated (stage: {account.current_stage}, rep: {account.primary_sales_rep}, calls: {account.total_calls})")

    def _update_account_rep_history(self, account_id: int, sales_rep_email: str, call_date: datetime):
        """Update account-rep history."""
        history = AccountRepHistory(
            id=None,
            account_id=account_id,
            sales_rep_email=sales_rep_email,
            first_call_date=call_date,
            last_call_date=call_date,
            total_calls=1,
        )
        self.repository.upsert_account_rep_history(history)

    def process_recent_calls(self, days: int = 30, limit: Optional[int] = None, segment: Optional[str] = None):
        """
        Process recent calls from Gong.

        Args:
            days: Number of days to look back (uses lookback_days from GongClient)
            limit: Optional limit on number of calls to process
            segment: Optional segment filter (e.g., 'enterprise', 'scale', 'velocity')
        """
        # 1. Load sales reps from database
        print(f"\n🔍 Loading sales reps from database...")
        sales_reps = self.repository.list_sales_reps(active_only=True)

        if not sales_reps:
            print(f"❌ No sales reps found in database")
            print(f"   Run: python load_sales_reps.py first")
            return

        print(f"  ✓ Found {len(sales_reps)} active sales reps")

        # Filter by segment if specified
        if segment:
            sales_reps = [rep for rep in sales_reps if rep.segment and rep.segment.lower() == segment.lower()]
            if not sales_reps:
                print(f"❌ No sales reps found in segment: {segment}")
                return
            print(f"  ✓ Filtered to {len(sales_reps)} reps in '{segment}' segment")

        sales_rep_emails = [rep.email for rep in sales_reps]

        # 2. Fetch calls for sales reps
        print(f"\n🔍 Fetching calls from Gong (last {days} days)...")
        print(f"   (Only calls with external participants)")

        try:
            calls = self.gong_client.get_calls_for_sales_reps(sales_rep_emails)
            print(f"  ✓ Found {len(calls)} calls with external participants")
        except Exception as e:
            print(f"❌ Failed to fetch calls: {e}")
            import traceback
            traceback.print_exc()
            return

        if not calls:
            print(f"⚠️  No calls found")
            return

        # Apply limit
        if limit:
            calls = calls[:limit]
            print(f"  → Processing first {len(calls)} calls (limit applied)")

        # 3. Extract call IDs and fetch transcripts
        print(f"\n📝 Fetching transcripts...")
        call_ids = []
        for call in calls:
            meta = call.get("metaData", {})
            call_id = call.get("id") or meta.get("id")
            if call_id:
                call_ids.append(call_id)

        try:
            transcripts = self.gong_client.get_transcripts(call_ids)
            print(f"  ✓ Fetched {len(transcripts)} transcripts")
        except Exception as e:
            print(f"❌ Failed to fetch transcripts: {e}")
            import traceback
            traceback.print_exc()
            return

        # 4. Process each call
        print(f"\n{'='*70}")
        print(f"PROCESSING CALLS")
        print(f"{'='*70}")

        processed = 0
        skipped = 0
        failed = 0

        for i, call_data in enumerate(calls, 1):
            meta = call_data.get("metaData", {})
            call_id = call_data.get("id") or meta.get("id")

            print(f"\n[{i}/{len(calls)}] Call ID: {call_id}")

            # Get transcript
            transcript = transcripts.get(call_id, "")
            if not transcript:
                print(f"  ⚠️  No transcript available, skipping...")
                skipped += 1
                continue

            try:
                result = self.process_call(call_data, transcript)
                if result:
                    processed += 1
                else:
                    skipped += 1
            except Exception as e:
                print(f"❌ Error processing call: {e}")
                import traceback
                traceback.print_exc()
                failed += 1
                continue

        # Summary
        print(f"\n{'='*70}")
        print(f"SUMMARY")
        print(f"{'='*70}")
        print(f"  ✅ Processed: {processed}")
        if skipped > 0:
            print(f"  ⏭️  Skipped: {skipped}")
        if failed > 0:
            print(f"  ❌ Failed: {failed}")
        print(f"  📊 Total: {len(calls)}")
