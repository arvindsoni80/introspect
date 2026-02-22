#!/usr/bin/env python3
"""
Test full scoring pipeline: classification + stage-specific evaluation.

Usage:
    python test_scoring.py CALL_ID1 CALL_ID2 ...
    python test_scoring.py --file call_ids.txt
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core import Config, GongClient, LLMClient
from src.services import StageClassifier
from src.services.evaluators import (
    MEDDPICCEvaluator,
    TrialEvaluator,
    CloseEvaluator,
    WinLossAnalyzer,
)


def print_separator(char="=", length=70):
    """Print a separator line."""
    print(char * length)


def print_meddpicc_scores(scores):
    """Print MEDDPICC scores in a readable format."""
    print("\n   📊 MEDDPICC SCORES (Discovery Stage)")
    print("   " + "-" * 66)

    dimensions = [
        ("Metrics", scores.metrics, "Understanding of customer metrics/KPIs"),
        ("Economic Buyer", scores.economic_buyer, "Identification and engagement of economic buyer"),
        ("Decision Criteria", scores.decision_criteria, "Understanding of decision criteria"),
        ("Decision Process", scores.decision_process, "Understanding of decision process"),
        ("Paper Process", scores.paper_process, "Understanding of procurement/legal process"),
        ("Identify Pain", scores.identify_pain, "Pain identification and quantification"),
        ("Champion", scores.champion, "Champion identification and development"),
        ("Competition", scores.competition, "Competitive landscape understanding"),
    ]

    total = 0
    max_possible = len(dimensions) * 5

    for name, score, description in dimensions:
        indicator = "🟢" if score >= 4 else "🟡" if score >= 2 else "🔴"
        print(f"   {indicator} {name:20s}: {score}/5  ({description})")
        total += score

    print(f"\n   📈 Overall Score: {scores.overall_score}/5.0 ({scores.overall_score/5.0*100:.0f}%)")
    print(f"   📈 Total Points: {total}/{max_possible} ({total/max_possible*100:.0f}%)")

    if scores.meddpicc_summary:
        print(f"\n   💬 MEDDPICC Summary:")
        print(f"      {scores.meddpicc_summary[:300]}...")

    if scores.key_gaps:
        print(f"\n   ⚠️  Key Gaps:")
        print(f"      {scores.key_gaps[:200]}...")

    if scores.clarity_of_need:
        print(f"\n   🎯 Clarity of Need:")
        print(f"      {scores.clarity_of_need[:200]}...")

    if scores.trial_readiness:
        print(f"\n   ✅ Trial Readiness:")
        print(f"      {scores.trial_readiness[:200]}...")


def print_trial_scores(scores):
    """Print TRIAL health scores in a readable format."""
    print("\n   📊 TRIAL HEALTH SCORES (Trial/POC Stage)")
    print("   " + "-" * 66)

    dimensions = [
        ("Technical Validation", scores.technical_validation, "Technical fit and validation"),
        ("Readiness Progress", scores.readiness_progress, "Progress toward production readiness"),
        ("Internal Adoption", scores.internal_adoption, "Customer internal adoption"),
        ("Advocacy Sentiment", scores.advocacy_sentiment, "Champion strength and sentiment"),
        ("Landscape Competition", scores.landscape_competition, "Competitive position"),
    ]

    total = 0
    max_possible = len(dimensions) * 5

    for name, score, description in dimensions:
        indicator = "🟢" if score >= 4 else "🟡" if score >= 2 else "🔴"
        print(f"   {indicator} {name:20s}: {score}/5  ({description})")
        total += score

    print(f"\n   📈 Overall Health: {scores.overall_score}/5.0 ({scores.overall_score/5.0*100:.0f}%)")
    print(f"   📈 Total Points: {total}/{max_possible} ({total/max_possible*100:.0f}%)")
    print(f"   🏥 Health Status: {scores.health_interpretation.upper()}")

    if scores.is_bake_off:
        print(f"\n   ⚔️  BAKE-OFF DETECTED")

    if scores.primary_concern_category:
        print(f"\n   ⚠️  Primary Concern: {scores.primary_concern_category} (Severity: {scores.concern_severity})")

    if scores.likelihood_to_advance:
        print(f"   📊 Likelihood to Advance: {scores.likelihood_to_advance.upper()}")

    if scores.key_concerns:
        print(f"\n   🚨 Key Concerns:")
        print(f"      {scores.key_concerns[:300]}...")

    if scores.recommended_actions:
        print(f"\n   📋 Recommended Actions:")
        print(f"      {scores.recommended_actions[:300]}...")


def print_close_scores(scores):
    """Print CLOSE health scores in a readable format."""
    print("\n   📊 CLOSE HEALTH SCORES (Negotiation Stage)")
    print("   " + "-" * 66)

    dimensions = [
        ("Commercial Alignment", scores.commercial_alignment, "Pricing and commercial terms aligned"),
        ("Legal Compliance", scores.legal_compliance, "Legal/procurement on track"),
        ("Organizational Consensus", scores.organizational_consensus, "Stakeholder consensus achieved"),
        ("Single Threading Risk", scores.single_threading_risk, "Multiple champions engaged"),
        ("Execution Momentum", scores.execution_momentum, "Deal momentum and urgency"),
    ]

    total = 0
    max_possible = len(dimensions) * 5

    for name, score, description in dimensions:
        indicator = "🟢" if score >= 4 else "🟡" if score >= 2 else "🔴"
        print(f"   {indicator} {name:20s}: {score}/5  ({description})")
        total += score

    print(f"\n   📈 Overall Health: {scores.overall_score}/5.0 ({scores.overall_score/5.0*100:.0f}%)")
    print(f"   📈 Total Points: {total}/{max_possible} ({total/max_possible*100:.0f}%)")
    print(f"   🏥 Health Status: {scores.health_interpretation.upper()}")

    if scores.has_competitive_pressure:
        print(f"\n   ⚔️  COMPETITIVE PRESSURE DETECTED")

    if scores.primary_concern_category:
        print(f"\n   ⚠️  Primary Concern: {scores.primary_concern_category} (Severity: {scores.concern_severity})")

    if scores.likelihood_to_close:
        print(f"   📊 Likelihood to Close: {scores.likelihood_to_close.upper()}")

    if scores.key_concerns:
        print(f"\n   🚨 Key Concerns:")
        print(f"      {scores.key_concerns[:300]}...")

    if scores.recommended_actions:
        print(f"\n   📋 Recommended Actions:")
        print(f"      {scores.recommended_actions[:300]}...")


def print_winloss_analysis(analysis):
    """Print Win/Loss analysis in a readable format."""
    print("\n   📊 WIN/LOSS ANALYSIS (Closed Stage)")
    print("   " + "-" * 66)

    outcome_emoji = "🎉" if analysis.outcome == "won" else "😞"
    print(f"\n   {outcome_emoji} Outcome: {analysis.outcome.upper()}")

    if analysis.stage_of_decision:
        print(f"   📍 Stage of Decision: {analysis.stage_of_decision}")

    if analysis.primary_reasons:
        print(f"\n   🎯 Primary Reasons:")
        print(f"      {analysis.primary_reasons[:300]}...")

    if analysis.critical_dimensions:
        print(f"\n   📊 Critical Dimensions:")
        print(f"      {analysis.critical_dimensions[:300]}...")

    if analysis.competitive_factor:
        print(f"\n   ⚔️  Competitive Factor:")
        print(f"      {analysis.competitive_factor[:300]}...")

    if analysis.key_learnings:
        print(f"\n   💡 Key Learnings:")
        print(f"      {analysis.key_learnings[:300]}...")

    if analysis.verbatim_quotes:
        print(f"\n   💬 Verbatim Quotes:")
        print(f"      {analysis.verbatim_quotes[:300]}...")


def main():
    parser = argparse.ArgumentParser(
        description="Test full scoring pipeline with classification and evaluation"
    )
    parser.add_argument(
        "call_ids",
        nargs="*",
        help="Call IDs to test (space-separated)",
    )
    parser.add_argument(
        "--file",
        type=str,
        help="File containing call IDs (one per line)",
    )
    args = parser.parse_args()

    # Get call IDs from args or file
    call_ids = []
    if args.file:
        try:
            with open(args.file, 'r') as f:
                call_ids = [line.strip() for line in f if line.strip()]
        except Exception as e:
            print(f"❌ Error reading file: {e}")
            return
    else:
        call_ids = args.call_ids

    if not call_ids:
        print("❌ No call IDs provided")
        print("\nUsage:")
        print("  python test_scoring.py CALL_ID1 CALL_ID2 ...")
        print("  python test_scoring.py --file call_ids.txt")
        return

    print("🧪 Testing Full Scoring Pipeline\n")
    print_separator()
    print(f"\n📋 Testing {len(call_ids)} call(s)")
    for i, cid in enumerate(call_ids, 1):
        print(f"   {i}. {cid}")

    # Initialize config
    print("\n1. Loading configuration...")
    config = Config()

    if not config.validate():
        print("\n❌ Configuration incomplete. Please check your .env file.")
        return

    print(f"   ✓ Config loaded")
    print(f"   ✓ LLM Model: {config.LLM_MODEL}")

    # Initialize clients
    print("\n2. Initializing clients...")
    try:
        gong_client = GongClient(
            access_key=config.GONG_ACCESS_KEY,
            secret_key=config.GONG_SECRET_KEY,
            api_url=config.GONG_API_URL,
            internal_domain=config.INTERNAL_DOMAIN,
            lookback_days=config.GONG_LOOKBACK_DAYS,
        )
        print("   ✓ Gong client initialized")
    except Exception as e:
        print(f"   ❌ Failed to initialize Gong client: {e}")
        return

    try:
        llm_client = LLMClient(
            anthropic_api_key=config.LLM_API_KEY,
            model=config.LLM_MODEL,
        )
        print("   ✓ LLM client initialized")
    except Exception as e:
        print(f"   ❌ Failed to initialize LLM client: {e}")
        return

    # Initialize evaluators
    print("\n3. Initializing evaluators...")
    classifier = StageClassifier(llm_client)
    meddpicc_evaluator = MEDDPICCEvaluator(llm_client)
    trial_evaluator = TrialEvaluator(llm_client)
    close_evaluator = CloseEvaluator(llm_client)
    winloss_analyzer = WinLossAnalyzer(llm_client)
    print("   ✓ All evaluators initialized")

    # Fetch transcripts
    print(f"\n4. Fetching transcripts for {len(call_ids)} calls...")
    try:
        transcripts = gong_client.get_transcripts(call_ids)
        print(f"   ✓ Fetched {len(transcripts)} transcripts")
    except Exception as e:
        print(f"   ❌ Failed to fetch transcripts: {e}")
        import traceback
        traceback.print_exc()
        return

    if not transcripts:
        print("\n❌ No transcripts found for provided call IDs")
        return

    # Process each call
    print("\n" + "=" * 70)
    print("PROCESSING CALLS")
    print_separator()

    successful = 0
    failed = 0

    for i, call_id in enumerate(call_ids, 1):
        print(f"\n{'='*70}")
        print(f"📞 CALL {i}/{len(call_ids)}")
        print(f"{'='*70}")
        print(f"\n   Call ID: {call_id}")

        transcript = transcripts.get(call_id)
        if not transcript:
            print(f"   ❌ No transcript available for this call")
            failed += 1
            continue

        print(f"   Transcript: {len(transcript):,} characters")

        # Step 1: Classify stage
        print(f"\n   🔍 Step 1: Classifying stage...")
        try:
            classification = classifier.classify_stage(transcript, call_title="")

            print(f"\n   ✅ STAGE CLASSIFICATION")
            print(f"   {'-'*66}")
            print(f"   Primary Stage: {classification.primary_stage.upper()}")
            print(f"   Confidence: {classification.confidence:.1%}")

            if classification.secondary_stage:
                print(f"   Secondary Stage: {classification.secondary_stage}")

            if classification.reasoning:
                print(f"\n   💭 Reasoning:")
                # Print reasoning with proper wrapping
                reasoning_lines = classification.reasoning.split('\n')
                for line in reasoning_lines[:5]:  # Show first 5 lines
                    print(f"      {line}")
                if len(reasoning_lines) > 5:
                    print(f"      ... ({len(reasoning_lines) - 5} more lines)")

            stage = classification.primary_stage.lower()

        except Exception as e:
            print(f"   ❌ Classification failed: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
            continue

        # Step 2: Run stage-specific evaluation
        print(f"\n   🔍 Step 2: Running {stage.upper()} evaluation...")

        try:
            if stage == "discovery":
                scores = meddpicc_evaluator.evaluate(transcript)
                print_meddpicc_scores(scores)
                print(f"\n   💾 Would be stored in: account_meddpicc_scores table")

            elif stage == "trial":
                scores = trial_evaluator.evaluate(transcript)
                print_trial_scores(scores)
                print(f"\n   💾 Would be stored in: account_trial_health table")

            elif stage == "negotiation":
                scores = close_evaluator.evaluate(transcript)
                print_close_scores(scores)
                print(f"\n   💾 Would be stored in: account_close_health table")

            elif stage == "closed":
                analysis = winloss_analyzer.evaluate(transcript)
                print_winloss_analysis(analysis)
                print(f"\n   💾 Would be stored in: call_win_loss_analysis table")

            else:
                print(f"   ⚠️  Unknown stage: {stage}")
                print(f"   Skipping evaluation...")
                failed += 1
                continue

            successful += 1

        except Exception as e:
            print(f"\n   ❌ Evaluation failed: {e}")
            print(f"   Error type: {type(e).__name__}")
            import traceback
            traceback.print_exc()
            failed += 1

    # Final summary
    print("\n" + "=" * 70)
    print("✅ TESTING COMPLETE")
    print_separator()
    print(f"\nResults:")
    print(f"   ✅ Successful: {successful}/{len(call_ids)}")
    if failed > 0:
        print(f"   ❌ Failed: {failed}/{len(call_ids)}")

    print(f"\n💡 These scores would be stored in the database when running:")
    print(f"   python process_calls.py")
    print()


if __name__ == "__main__":
    main()
