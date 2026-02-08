"""Slack client for posting analysis results."""

import httpx

from .models import CallAnalysis


class SlackClient:
    """Client for posting to Slack via Web API (supports threading)."""

    def __init__(self, bot_token: str, channel_id: str):
        """
        Initialize the Slack client.

        Args:
            bot_token: Slack Bot User OAuth Token (xoxb-...)
            channel_id: Slack channel ID to post to (e.g., C01234567)
        """
        self.bot_token = bot_token
        self.channel_id = channel_id
        self.api_url = "https://slack.com/api/chat.postMessage"
        self.thread_ts_by_rep = {}  # Store thread timestamps for each rep

    async def post_rep_thread_header(self, rep_email: str) -> bool:
        """
        Post thread header for a sales rep and store thread_ts.

        Args:
            rep_email: Sales rep email address

        Returns:
            True if posted successfully, False otherwise
        """
        payload = {
            "channel": self.channel_id,
            "text": f"Discovery eval for {rep_email}",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"📊 Discovery Eval for {rep_email}",
                    },
                },
            ],
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.api_url,
                    headers={
                        "Authorization": f"Bearer {self.bot_token}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=10.0,
                )

                if response.status_code == 200:
                    result = response.json()
                    if result.get("ok"):
                        # Store the thread timestamp for this rep
                        self.thread_ts_by_rep[rep_email] = result["ts"]
                        return True
                    else:
                        print(f"[ERROR] Slack API error: {result.get('error')}")
                        return False
                else:
                    print(f"[ERROR] HTTP {response.status_code}: {response.text}")
                    return False

        except Exception as e:
            print(f"[ERROR] Failed to post thread header for {rep_email}: {e}")
            return False

    async def post_call_eval(self, analysis: CallAnalysis) -> bool:
        """
        Post a single discovery call evaluation as a thread reply.

        Args:
            analysis: CallAnalysis object for a discovery call

        Returns:
            True if posted successfully, False otherwise
        """
        if not analysis.is_discovery_call or not analysis.meddpicc_scores:
            return False

        # Get thread_ts for this rep
        thread_ts = self.thread_ts_by_rep.get(analysis.sales_rep_email)
        if not thread_ts:
            print(f"[ERROR] No thread_ts found for {analysis.sales_rep_email}")
            return False

        # Build message
        s = analysis.meddpicc_scores
        date = analysis.call_date.strftime("%Y-%m-%d")

        # Color code based on score
        if s.overall_score >= 4.0:
            emoji = "🟢"
        elif s.overall_score >= 2.5:
            emoji = "🟡"
        else:
            emoji = "🔴"

        message_text = (
            f"{emoji} *<{analysis.gong_link}|{analysis.call_title}>*\n"
            f"📅 {date}\n\n"
            f"*MEDDPICC Score: {s.overall_score:.1f}/5.0*\n"
            f"M:{s.metrics} │ E:{s.economic_buyer} │ D:{s.decision_criteria} │ D:{s.decision_process}\n"
            f"P:{s.paper_process} │ I:{s.identify_pain} │ C:{s.champion} │ C:{s.competition}\n\n"
        )

        if analysis.meddpicc_summary:
            message_text += f"💡 _{analysis.meddpicc_summary}_"

        payload = {
            "channel": self.channel_id,
            "thread_ts": thread_ts,  # Post as reply in thread
            "text": f"{analysis.call_title} - {s.overall_score}/5.0",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": message_text,
                    },
                }
            ],
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.api_url,
                    headers={
                        "Authorization": f"Bearer {self.bot_token}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=10.0,
                )

                if response.status_code == 200:
                    result = response.json()
                    return result.get("ok", False)
                else:
                    print(f"[ERROR] HTTP {response.status_code}: {response.text}")
                    return False

        except Exception as e:
            print(f"[ERROR] Failed to post call eval: {e}")
            return False

    async def post_rep_completion_summary(self, rep_email: str, discovery_count: int, total_count: int) -> bool:
        """
        Post completion summary for a sales rep in their thread.

        Args:
            rep_email: Sales rep email address
            discovery_count: Number of discovery calls found
            total_count: Total number of external calls

        Returns:
            True if posted successfully, False otherwise
        """
        # Get thread_ts for this rep
        thread_ts = self.thread_ts_by_rep.get(rep_email)
        if not thread_ts:
            print(f"[ERROR] No thread_ts found for {rep_email}")
            return False

        message_text = (
            f"✅ Eval completed for *{discovery_count} discovery call{'s' if discovery_count != 1 else ''}* "
            f"out of *{total_count} external call{'s' if total_count != 1 else ''}*"
        )

        payload = {
            "channel": self.channel_id,
            "thread_ts": thread_ts,  # Post as reply in thread
            "text": f"Eval completed for {rep_email}",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": message_text,
                    },
                },
                {"type": "divider"},
            ],
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.api_url,
                    headers={
                        "Authorization": f"Bearer {self.bot_token}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=10.0,
                )

                if response.status_code == 200:
                    result = response.json()
                    return result.get("ok", False)
                else:
                    print(f"[ERROR] HTTP {response.status_code}: {response.text}")
                    return False

        except Exception as e:
            print(f"[ERROR] Failed to post completion summary for {rep_email}: {e}")
            return False

    async def post_rep_thread(self, rep_email: str, calls: list[CallAnalysis]) -> bool:
        """
        Post a thread for a sales rep with all their discovery calls.

        Args:
            rep_email: Sales rep email address
            calls: List of CallAnalysis objects for this rep (discovery calls only)

        Returns:
            True if posted successfully, False otherwise
        """
        if not calls:
            return False

        # Calculate average score for this rep
        avg_score = sum(c.meddpicc_scores.overall_score for c in calls) / len(calls)
        emoji = "🟢" if avg_score >= 4.0 else "🟡" if avg_score >= 2.5 else "🔴"

        # Main thread post
        main_message = {
            "text": f"Discovery eval for {rep_email}",
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"Discovery Eval for {rep_email}",
                    },
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            f"{emoji} *{len(calls)} discovery call{'s' if len(calls) > 1 else ''}* | "
                            f"*Average Score: {avg_score:.1f}/5.0*"
                        ),
                    },
                },
            ],
        }

        try:
            # Post main thread message
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.webhook_url,
                    json=main_message,
                    timeout=10.0,
                )

                if response.status_code != 200:
                    print(f"[ERROR] Failed to post thread for {rep_email}: {response.text}")
                    return False

                # Note: Slack incoming webhooks don't support threading
                # So we'll post individual calls as separate messages
                # But we'll make them clearly belong together by formatting

                # Post each call
                for call in sorted(calls, key=lambda c: c.call_date, reverse=True):
                    call_message = self._build_call_message(call)
                    await client.post(
                        self.webhook_url,
                        json=call_message,
                        timeout=10.0,
                    )

                return True

        except Exception as e:
            print(f"[ERROR] Failed to post thread for {rep_email}: {e}")
            return False

    def _build_call_message(self, analysis: CallAnalysis) -> dict:
        """Build a Slack message for a single call."""
        s = analysis.meddpicc_scores
        date = analysis.call_date.strftime("%Y-%m-%d")

        # Color code based on score
        if s.overall_score >= 4.0:
            emoji = "🟢"
        elif s.overall_score >= 2.5:
            emoji = "🟡"
        else:
            emoji = "🔴"

        # Build message
        message_text = (
            f"  {emoji} *<{analysis.gong_link}|{analysis.call_title}>*\n"
            f"  📅 {date}\n\n"
            f"  *MEDDPICC Score: {s.overall_score:.1f}/5.0*\n"
            f"  M:{s.metrics} │ E:{s.economic_buyer} │ D:{s.decision_criteria} │ D:{s.decision_process}\n"
            f"  P:{s.paper_process} │ I:{s.identify_pain} │ C:{s.champion} │ C:{s.competition}\n\n"
        )

        if analysis.meddpicc_summary:
            message_text += f"  💡 _{analysis.meddpicc_summary}_"

        return {
            "text": f"{analysis.call_title} - {s.overall_score}/5.0",
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": message_text,
                    },
                }
            ],
        }

    async def post_discovery_call(self, analysis: CallAnalysis) -> bool:
        """
        Post a single discovery call analysis to Slack.

        Args:
            analysis: CallAnalysis object for a discovery call

        Returns:
            True if posted successfully, False otherwise
        """
        if not analysis.is_discovery_call or not analysis.meddpicc_scores:
            return False

        # Build the message blocks
        blocks = self._build_message_blocks(analysis)
        payload = {
            "text": f"Discovery Call Analysis: {analysis.call_title}",
            "blocks": blocks,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.webhook_url,
                    json=payload,
                    timeout=10.0,
                )
                return response.status_code == 200
        except Exception as e:
            print(f"[ERROR] Failed to post to Slack: {e}")
            return False

    def _build_message_blocks(self, analysis: CallAnalysis) -> list:
        """Build Slack Block Kit message for a discovery call."""
        s = analysis.meddpicc_scores
        date = analysis.call_date.strftime("%Y-%m-%d")

        # Color code based on score
        if s.overall_score >= 4.0:
            emoji = "🟢"  # Green - Strong
        elif s.overall_score >= 2.5:
            emoji = "🟡"  # Yellow - Moderate
        else:
            emoji = "🔴"  # Red - Weak

        blocks = [
            # Header with sales rep
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"👤 *{analysis.sales_rep_email}*",
                },
            },
            # Call title and date
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"📞 *{analysis.call_title}*\n📅 {date}",
                },
            },
            {"type": "divider"},
            # Overall score
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{emoji} *MEDDPICC Score: {s.overall_score:.1f}/5.0*",
                },
            },
            # Dimension scores
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*M:*{s.metrics} │ *E:*{s.economic_buyer} │ "
                        f"*D:*{s.decision_criteria} │ *D:*{s.decision_process}\n"
                        f"*P:*{s.paper_process} │ *I:*{s.identify_pain} │ "
                        f"*C:*{s.champion} │ *C:*{s.competition}"
                    ),
                },
            },
        ]

        # Add summary if available
        if analysis.meddpicc_summary:
            blocks.append(
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"💡 _{analysis.meddpicc_summary}_",
                    },
                }
            )

        # Add Gong link button
        blocks.append({"type": "divider"})
        blocks.append(
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "🔗 View in Gong",
                        },
                        "url": analysis.gong_link,
                        "style": "primary",
                    }
                ],
            }
        )

        return blocks

    async def post_summary_table(self, results: list[CallAnalysis]) -> bool:
        """
        Post a summary table of all discovery calls.

        Table includes:
        - Overall score
        - Individual dimension scores
        - Sales rep email
        - Call title (hyperlinked to Gong)

        Args:
            results: List of CallAnalysis objects

        Returns:
            True if posted successfully, False otherwise
        """
        discovery_calls = [r for r in results if r.is_discovery_call and r.meddpicc_scores]

        if not discovery_calls:
            return await self._post_simple_summary(results)

        # Calculate average score
        avg_score = sum(r.meddpicc_scores.overall_score for r in discovery_calls) / len(discovery_calls)

        # Build header
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "📊 Discovery Calls Summary",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*Total Analyzed:* {len(results)} calls\n"
                        f"*Discovery Calls:* {len(discovery_calls)} calls\n"
                        f"*Average Score:* {avg_score:.1f}/5.0"
                    ),
                },
            },
            {"type": "divider"},
        ]

        # Build table header
        table_text = "```\n"
        table_text += "Rep              │ Score │ M E D D P I C C │ Call\n"
        table_text += "─────────────────┼───────┼─────────────────┼─────────────────\n"

        # Add rows for each discovery call, sorted by rep email then score
        for result in sorted(discovery_calls, key=lambda r: (r.sales_rep_email, -r.meddpicc_scores.overall_score)):
            s = result.meddpicc_scores
            score = f"{s.overall_score:.1f}"
            dimensions = f"{s.metrics} {s.economic_buyer} {s.decision_criteria} {s.decision_process} {s.paper_process} {s.identify_pain} {s.champion} {s.competition}"
            rep = result.sales_rep_email.split('@')[0][:16].ljust(16)  # First part of email, truncated

            # Call title truncated
            call_title = result.call_title[:20] + "..." if len(result.call_title) > 20 else result.call_title

            table_text += f"{rep} │ {score.ljust(5)} │ {dimensions.ljust(15)} │ {call_title}\n"

        # Add separator and Overall Average row
        table_text += "─────────────────┼───────┼─────────────────┼─────────────────\n"

        # Calculate averages
        avg_overall = sum(r.meddpicc_scores.overall_score for r in discovery_calls) / len(discovery_calls)
        avg_metrics = sum(r.meddpicc_scores.metrics for r in discovery_calls) / len(discovery_calls)
        avg_economic = sum(r.meddpicc_scores.economic_buyer for r in discovery_calls) / len(discovery_calls)
        avg_decision_criteria = sum(r.meddpicc_scores.decision_criteria for r in discovery_calls) / len(discovery_calls)
        avg_decision_process = sum(r.meddpicc_scores.decision_process for r in discovery_calls) / len(discovery_calls)
        avg_paper = sum(r.meddpicc_scores.paper_process for r in discovery_calls) / len(discovery_calls)
        avg_pain = sum(r.meddpicc_scores.identify_pain for r in discovery_calls) / len(discovery_calls)
        avg_champion = sum(r.meddpicc_scores.champion for r in discovery_calls) / len(discovery_calls)
        avg_competition = sum(r.meddpicc_scores.competition for r in discovery_calls) / len(discovery_calls)

        avg_dimensions = f"{avg_metrics:.1f} {avg_economic:.1f} {avg_decision_criteria:.1f} {avg_decision_process:.1f} {avg_paper:.1f} {avg_pain:.1f} {avg_champion:.1f} {avg_competition:.1f}"

        table_text += f"{'Overall Average'.ljust(16)} │ {f'{avg_overall:.1f}'.ljust(5)} │ {avg_dimensions.ljust(15)} │\n"

        table_text += "```\n"

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": table_text,
            },
        })

        # Add individual call links as a list
        blocks.append({"type": "divider"})
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*📎 Call Links:*",
            },
        })

        for result in sorted(discovery_calls, key=lambda r: r.meddpicc_scores.overall_score, reverse=True):
            score_emoji = "🟢" if result.meddpicc_scores.overall_score >= 4.0 else "🟡" if result.meddpicc_scores.overall_score >= 2.5 else "🔴"
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{score_emoji} *{result.meddpicc_scores.overall_score:.1f}* - <{result.gong_link}|{result.call_title}>",
                },
            })

        payload = {
            "channel": self.channel_id,
            "text": f"Discovery Calls Summary: {len(discovery_calls)} calls analyzed",
            "blocks": blocks,
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.api_url,
                    headers={
                        "Authorization": f"Bearer {self.bot_token}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=10.0,
                )

                if response.status_code == 200:
                    result = response.json()
                    return result.get("ok", False)
                else:
                    print(f"[ERROR] HTTP {response.status_code}: {response.text}")
                    return False

        except Exception as e:
            print(f"[ERROR] Failed to post summary table to Slack: {e}")
            return False

    async def _post_simple_summary(self, results: list[CallAnalysis]) -> bool:
        """Post simple summary when no discovery calls found."""
        total_calls = len(results)
        text = f"📊 Analysis Complete: {total_calls} calls analyzed, 0 discovery calls found."

        payload = {
            "channel": self.channel_id,
            "text": text,
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": text,
                    },
                }
            ],
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.api_url,
                    headers={
                        "Authorization": f"Bearer {self.bot_token}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=10.0,
                )

                if response.status_code == 200:
                    result = response.json()
                    return result.get("ok", False)
                else:
                    return False

        except Exception as e:
            print(f"[ERROR] Failed to post summary to Slack: {e}")
            return False
