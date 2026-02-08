"""Output formatters for analysis results."""

from typing import List

from .models import CallAnalysis


def format_console_output(results: List[CallAnalysis]) -> str:
    """
    Format analysis results for console output.

    Args:
        results: List of CallAnalysis objects

    Returns:
        Formatted string for console display
    """
    if not results:
        return "No calls to analyze."

    # Group by sales rep
    by_rep = {}
    for result in results:
        email = result.sales_rep_email
        if email not in by_rep:
            by_rep[email] = []
        by_rep[email].append(result)

    output = []
    output.append("\n" + "=" * 70)
    output.append("DISCOVERY CALL ANALYSIS RESULTS")
    output.append("=" * 70)

    # Stats
    total_calls = len(results)
    discovery_calls = sum(1 for r in results if r.is_discovery_call)
    output.append(f"\n📊 Summary:")
    output.append(f"  • Total calls analyzed: {total_calls}")
    output.append(f"  • Discovery calls: {discovery_calls}")
    output.append(f"  • Non-discovery calls: {total_calls - discovery_calls}")

    if discovery_calls > 0:
        avg_score = sum(
            r.meddpicc_scores.overall_score
            for r in results
            if r.is_discovery_call and r.meddpicc_scores
        ) / discovery_calls
        output.append(f"  • Average MEDDPICC score: {avg_score:.1f}/5.0")

    # Results by rep
    output.append("\n" + "=" * 70)
    output.append("RESULTS BY SALES REP")
    output.append("=" * 70)

    for email, rep_results in sorted(by_rep.items()):
        output.append(f"\n👤 {email}")
        output.append("   " + "-" * 66)

        rep_discovery = sum(1 for r in rep_results if r.is_discovery_call)
        output.append(
            f"   Calls: {len(rep_results)} total | {rep_discovery} discovery"
        )

        for result in rep_results:
            call_date = result.call_date.strftime("%Y-%m-%d")
            call_title = result.call_title[:60] + "..." if len(result.call_title) > 60 else result.call_title

            if result.is_discovery_call and result.meddpicc_scores:
                score = result.meddpicc_scores.overall_score
                output.append(f"\n   ✅ {call_title}")
                output.append(f"     Discovery Call | Score: {score}/5.0")
                output.append(f"     📅 {call_date}")
                output.append(f"     🔗 {result.gong_link}")

                # MEDDPICC breakdown
                s = result.meddpicc_scores
                output.append(
                    f"     📊 MEDDPICC: M:{s.metrics} E:{s.economic_buyer} "
                    f"D:{s.decision_criteria} D:{s.decision_process} "
                    f"P:{s.paper_process} I:{s.identify_pain} "
                    f"C:{s.champion} C:{s.competition}"
                )

                # Summary
                if result.meddpicc_summary:
                    output.append(f"     💡 {result.meddpicc_summary}")
            else:
                output.append(f"\n   ❌ {call_title}")
                output.append(f"     Not a Discovery Call")
                output.append(f"     📅 {call_date}")
                output.append(f"     🔗 {result.gong_link}")
                if result.discovery_reasoning:
                    output.append(f"     💬 Reason: {result.discovery_reasoning}")

    output.append("\n" + "=" * 70)
    return "\n".join(output)


def format_slack_output(results: List[CallAnalysis]) -> dict:
    """
    Format analysis results for Slack Block Kit.

    Args:
        results: List of CallAnalysis objects

    Returns:
        Slack Block Kit formatted message
    """
    if not results:
        return {
            "text": "No calls to analyze",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "No calls to analyze.",
                    },
                }
            ],
        }

    # Stats
    total_calls = len(results)
    discovery_calls = sum(1 for r in results if r.is_discovery_call)

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "📊 Discovery Call Analysis Report",
            },
        },
        {"type": "divider"},
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Total Calls:*\n{total_calls}"},
                {"type": "mrkdwn", "text": f"*Discovery Calls:*\n{discovery_calls}"},
            ],
        },
    ]

    if discovery_calls > 0:
        avg_score = sum(
            r.meddpicc_scores.overall_score
            for r in results
            if r.is_discovery_call and r.meddpicc_scores
        ) / discovery_calls

        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Average MEDDPICC Score:* {avg_score:.1f}/5.0",
                },
            }
        )

    # Group by rep
    by_rep = {}
    for result in results:
        email = result.sales_rep_email
        if email not in by_rep:
            by_rep[email] = []
        by_rep[email].append(result)

    # Add each rep's results
    for email, rep_results in sorted(by_rep.items()):
        blocks.append({"type": "divider"})
        blocks.append(
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*👤 {email}*"},
            }
        )

        for result in rep_results:
            if result.is_discovery_call and result.meddpicc_scores:
                score = result.meddpicc_scores.overall_score
                date = result.call_date.strftime("%Y-%m-%d")
                s = result.meddpicc_scores

                blocks.append(
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": (
                                f"✅ *Discovery Call* | Score: *{score}/5.0*\n"
                                f"📅 {date} | <{result.gong_link}|View in Gong>\n"
                                f"```MEDDPICC: M:{s.metrics} E:{s.economic_buyer} "
                                f"D:{s.decision_criteria} D:{s.decision_process} "
                                f"P:{s.paper_process} I:{s.identify_pain} "
                                f"C:{s.champion} C:{s.competition}```"
                            ),
                        },
                    }
                )

    return {"text": f"Discovery Call Analysis: {discovery_calls}/{total_calls} calls", "blocks": blocks}
