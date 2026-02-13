"""Slack client for posting analysis results."""

import asyncio

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

        # Limit table to 30 rows to avoid exceeding Slack 3000 char limit
        sorted_calls = sorted(discovery_calls, key=lambda r: (r.sales_rep_email, -r.meddpicc_scores.overall_score))
        table_calls = sorted_calls[:30]

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
        if len(discovery_calls) > 30:
            table_text += f"Showing top 30 of {len(discovery_calls)} calls (by rep, then score)\n\n"
        table_text += "Rep              │ Score │ M E D D P I C C │ Call\n"
        table_text += "─────────────────┼───────┼─────────────────┼─────────────────\n"

        # Add rows for each discovery call, sorted by rep email then score
        for result in table_calls:
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

        # Add top call links (limit to top 20 to avoid exceeding 50 block limit)
        blocks.append({"type": "divider"})

        top_calls = sorted(discovery_calls, key=lambda r: r.meddpicc_scores.overall_score, reverse=True)[:20]

        if len(discovery_calls) <= 20:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*📎 Top Calls:*",
                },
            })
        else:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*📎 Top 20 Calls (of {len(discovery_calls)} total):*",
                },
            })

        for result in top_calls:
            score_emoji = "🟢" if result.meddpicc_scores.overall_score >= 4.0 else "🟡" if result.meddpicc_scores.overall_score >= 2.5 else "🔴"
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{score_emoji} *{result.meddpicc_scores.overall_score:.1f}* - <{result.gong_link}|{result.call_title[:50]}>",
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

    async def post_account_summary_table(self, account_records: list) -> bool:
        """
        Post account-level MEDDPICC summary table.

        Args:
            account_records: List of AccountRecord objects with aggregated MEDDPICC

        Returns:
            True if posted successfully
        """
        if not account_records:
            return False

        # Limit to top 50 accounts to avoid exceeding Slack character limits
        sorted_accounts = sorted(account_records, key=lambda a: a.overall_meddpicc.overall_score, reverse=True)
        top_accounts = sorted_accounts[:50]
        total_accounts = len(account_records)

        # Build table header
        header = (
            "┌─────────────────────────┬───────┬─────────┬─────────────────────────────────────────────┐\n"
            "│ Account Domain          │ Calls │ Overall │ MEDDPICC (M|E|DC|DP|PP|IP|CH|CO)            │\n"
            "├─────────────────────────┼───────┼─────────┼─────────────────────────────────────────────┤\n"
        )

        # Build table rows
        rows = []
        for account in top_accounts:
            domain = account.domain[:23]  # Truncate if needed
            calls_count = len(account.calls)
            overall = account.overall_meddpicc.overall_score

            # MEDDPICC compact format: M:4 E:3 DC:4...
            m = account.overall_meddpicc
            meddpicc_str = f"{m.metrics}|{m.economic_buyer}|{m.decision_criteria}|{m.decision_process}|{m.paper_process}|{m.identify_pain}|{m.champion}|{m.competition}"

            row = f"│ {domain:<23} │ {calls_count:>5} │ {overall:>7.2f} │ {meddpicc_str:<43} │\n"
            rows.append(row)

        footer = "└─────────────────────────┴───────┴─────────┴─────────────────────────────────────────────┘"

        table = header + "".join(rows) + footer

        # Create Slack blocks
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "📊 Account-Level MEDDPICC Coverage",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"```\n{table}\n```",
                },
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": (
                            f"Showing top *{len(top_accounts)}* of *{total_accounts}* accounts | "
                            f"Sorted by overall score (highest first) | "
                            f"MEDDPICC format: M|E|DC|DP|PP|IP|CH|CO"
                        ) if total_accounts > 50 else (
                            f"*{total_accounts}* accounts tracked | "
                            f"Sorted by overall score (highest first) | "
                            f"MEDDPICC format: M|E|DC|DP|PP|IP|CH|CO"
                        ),
                    }
                ],
            },
        ]

        payload = {
            "channel": self.channel_id,
            "text": f"Account Summary: {len(account_records)} accounts",
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
            print(f"[ERROR] Failed to post account summary table to Slack: {e}")
            return False

    async def post_summary_table_batched(self, results: list[CallAnalysis], batch_size: int = 25) -> bool:
        """
        Post call summary table in batches, grouped by sales rep.

        Calls are grouped by sales rep first, then batched within each rep.
        This ensures batches never mix calls from different reps.

        Args:
            results: List of CallAnalysis objects
            batch_size: Number of calls per batch (default 25)

        Returns:
            True if all batches posted successfully
        """
        discovery_calls = [r for r in results if r.is_discovery_call and r.meddpicc_scores]

        if not discovery_calls:
            return await self._post_simple_summary(results)

        # Calculate overall stats
        avg_score = sum(r.meddpicc_scores.overall_score for r in discovery_calls) / len(discovery_calls)

        # Group calls by sales rep
        from collections import defaultdict
        calls_by_rep = defaultdict(list)
        for call in discovery_calls:
            calls_by_rep[call.sales_rep_email].append(call)

        # Sort reps alphabetically and sort calls within each rep by score
        sorted_reps = sorted(calls_by_rep.keys())
        for rep in sorted_reps:
            calls_by_rep[rep].sort(key=lambda r: -r.meddpicc_scores.overall_score)

        # Calculate total batches across all reps
        total_batches = sum((len(calls) + batch_size - 1) // batch_size for calls in calls_by_rep.values())

        # Post header with overall stats
        header_blocks = [
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
                        f"*Total Discovery Calls:* {len(discovery_calls)}\n"
                        f"*Sales Reps:* {len(sorted_reps)}\n"
                        f"*Average Score:* {avg_score:.2f}/5.0\n"
                        f"*Total Batches:* {total_batches}"
                    ),
                },
            },
            {"type": "divider"},
        ]

        payload = {
            "channel": self.channel_id,
            "text": f"Discovery Calls Summary: {len(discovery_calls)} calls",
            "blocks": header_blocks,
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

                if response.status_code != 200 or not response.json().get("ok"):
                    print(f"[ERROR] Failed to post header: {response.text}")
                    return False

            # Post batches grouped by rep
            global_batch_num = 0
            for rep_email in sorted_reps:
                rep_calls = calls_by_rep[rep_email]
                rep_batches = (len(rep_calls) + batch_size - 1) // batch_size
                rep_avg_score = sum(c.meddpicc_scores.overall_score for c in rep_calls) / len(rep_calls)

                # Post rep header
                rep_header_blocks = [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": (
                                f"*👤 {rep_email}*\n"
                                f"Calls: {len(rep_calls)} | Avg Score: {rep_avg_score:.2f}/5.0"
                            ),
                        },
                    },
                ]

                rep_header_payload = {
                    "channel": self.channel_id,
                    "text": f"Rep: {rep_email}",
                    "blocks": rep_header_blocks,
                }

                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        self.api_url,
                        headers={
                            "Authorization": f"Bearer {self.bot_token}",
                            "Content-Type": "application/json",
                        },
                        json=rep_header_payload,
                        timeout=10.0,
                    )

                    if response.status_code != 200 or not response.json().get("ok"):
                        print(f"[ERROR] Failed to post rep header for {rep_email}: {response.text}")
                        return False

                # Post batches for this rep
                for rep_batch_num, i in enumerate(range(0, len(rep_calls), batch_size), 1):
                    global_batch_num += 1
                    batch = rep_calls[i:i + batch_size]

                    # Build table for this batch
                    if rep_batches > 1:
                        table_text = f"```\nBatch {rep_batch_num}/{rep_batches} for {rep_email.split('@')[0]}\n\n"
                    else:
                        table_text = "```\n"

                    table_text += "Score │ M E D D P I C C │ Call\n"
                    table_text += "──────┼─────────────────┼─────────────────────────────\n"

                    for result in batch:
                        s = result.meddpicc_scores
                        score = f"{s.overall_score:.1f}"
                        dimensions = f"{s.metrics} {s.economic_buyer} {s.decision_criteria} {s.decision_process} {s.paper_process} {s.identify_pain} {s.champion} {s.competition}"
                        call_title = result.call_title[:30] + "..." if len(result.call_title) > 30 else result.call_title

                        table_text += f"{score.ljust(5)} │ {dimensions.ljust(15)} │ {call_title}\n"

                    table_text += "```"

                    # Build call links for this batch
                    links_text = "\n".join([
                        f"• <{r.gong_link}|{r.call_title[:60]}> ({r.meddpicc_scores.overall_score:.1f})"
                        for r in batch
                    ])

                    batch_blocks = [
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": table_text,
                            },
                        },
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": f"*🔗 Links:*\n{links_text}",
                            },
                        },
                    ]

                    # Add divider after this rep's batches (except if last rep)
                    if rep_email != sorted_reps[-1] and rep_batch_num == rep_batches:
                        batch_blocks.append({"type": "divider"})

                    batch_payload = {
                        "channel": self.channel_id,
                        "text": f"Batch {global_batch_num}/{total_batches}",
                        "blocks": batch_blocks,
                    }

                    async with httpx.AsyncClient() as client:
                        response = await client.post(
                            self.api_url,
                            headers={
                                "Authorization": f"Bearer {self.bot_token}",
                                "Content-Type": "application/json",
                            },
                            json=batch_payload,
                            timeout=10.0,
                        )

                        if response.status_code != 200 or not response.json().get("ok"):
                            print(f"[ERROR] Failed to post batch {global_batch_num}: {response.text}")
                            return False

                    # Small delay between batches to avoid rate limiting
                    await asyncio.sleep(1)

            return True

        except Exception as e:
            print(f"[ERROR] Failed to post batched summary: {e}")
            return False

    async def post_account_summary_table_batched(self, account_records: list, batch_size: int = 25) -> bool:
        """
        Post account summary table in batches.

        Args:
            account_records: List of AccountRecord objects
            batch_size: Number of accounts per batch (default 25)

        Returns:
            True if all batches posted successfully
        """
        if not account_records:
            return False

        # Sort by overall score
        sorted_accounts = sorted(account_records, key=lambda a: a.overall_meddpicc.overall_score, reverse=True)
        total_batches = (len(sorted_accounts) + batch_size - 1) // batch_size

        # Post header
        header_blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "📊 Account-Level MEDDPICC Coverage",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*Total Accounts:* {len(sorted_accounts)}\n"
                        f"*Batches:* {total_batches}"
                    ),
                },
            },
            {"type": "divider"},
        ]

        payload = {
            "channel": self.channel_id,
            "text": f"Account Summary: {len(sorted_accounts)} accounts",
            "blocks": header_blocks,
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

                if response.status_code != 200 or not response.json().get("ok"):
                    print(f"[ERROR] Failed to post header: {response.text}")
                    return False

            # Post batches
            for batch_num, i in enumerate(range(0, len(sorted_accounts), batch_size), 1):
                batch = sorted_accounts[i:i + batch_size]

                # Build table for this batch
                table_text = f"```\nBatch {batch_num}/{total_batches}\n\n"
                table_text += "Account Domain          │ Calls │ Overall │ M│E│DC│DP│PP│IP│CH│CO\n"
                table_text += "────────────────────────┼───────┼─────────┼──────────────────────\n"

                for account in batch:
                    domain = account.domain[:23].ljust(23)
                    calls_count = f"{len(account.calls):>5}"
                    overall = f"{account.overall_meddpicc.overall_score:>7.2f}"

                    m = account.overall_meddpicc
                    meddpicc_str = f"{m.metrics}│{m.economic_buyer}│{m.decision_criteria}│{m.decision_process}│{m.paper_process}│{m.identify_pain}│{m.champion}│{m.competition}"

                    table_text += f"{domain} │ {calls_count} │ {overall} │ {meddpicc_str}\n"

                table_text += "```"

                batch_blocks = [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": table_text,
                        },
                    },
                ]

                # Add divider between batches (except last)
                if batch_num < total_batches:
                    batch_blocks.append({"type": "divider"})

                batch_payload = {
                    "channel": self.channel_id,
                    "text": f"Batch {batch_num}/{total_batches}",
                    "blocks": batch_blocks,
                }

                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        self.api_url,
                        headers={
                            "Authorization": f"Bearer {self.bot_token}",
                            "Content-Type": "application/json",
                        },
                        json=batch_payload,
                        timeout=10.0,
                    )

                    if response.status_code != 200 or not response.json().get("ok"):
                        print(f"[ERROR] Failed to post batch {batch_num}: {response.text}")
                        return False

                # Small delay between batches to avoid rate limiting
                await asyncio.sleep(1)

            return True

        except Exception as e:
            print(f"[ERROR] Failed to post batched account summary: {e}")
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
