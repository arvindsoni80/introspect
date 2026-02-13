"""LLM client for analyzing transcripts."""

import json

from anthropic import AsyncAnthropic

from .config import Settings
from .models import AnalysisNotes, MEDDPICCScores


class LLMClient:
    """Client for interacting with LLM APIs."""

    def __init__(self, settings: Settings):
        """Initialize the LLM client."""
        self.provider = settings.llm_provider
        self.model = settings.llm_model

        if self.provider == "anthropic":
            self.client = AsyncAnthropic(api_key=settings.llm_api_key)
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")

    async def is_discovery_call(self, transcript: str) -> tuple[bool, str]:
        """
        Classify if a transcript is a discovery call.

        Checks:
        1. Is this a discovery/qualification call?
        2. Did external participants actively engage?

        Args:
            transcript: The call transcript text

        Returns:
            Tuple of (is_discovery, reasoning)
        """
        prompt = f"""Analyze this sales call transcript and determine if it is a DISCOVERY CALL.

✅ IT IS A DISCOVERY CALL if it includes ANY of these (doesn't need all):
1. **Product introduction** - Explaining what CodeRabbit is, how it works, demonstrations
2. **Customer needs exploration** - Asking about their current code review process, challenges, team size, tech stack
3. **Feature discussions** - Explaining CodeRabbit features, integrations, capabilities
4. **Qualification questions** - Questions about budget, timeline, decision process, stakeholders
5. **Two-way engagement** - Both sales rep and customer asking questions and sharing information
6. **Exploration phase** - Learning about each other, assessing fit, discussing potential trial

Note: A call can be discovery even if it's the 2nd or 3rd conversation, as long as there's meaningful exploration of needs and product fit.

❌ IT IS NOT A DISCOVERY CALL if:
1. **No-show** - External participant never joined or barely spoke (only internal team talking)
2. **Pure negotiation** - Focused only on pricing, contract terms, legal discussions (no product or needs discussion)
3. **Pure troubleshooting** - Only technical debugging of specific issues (no exploration or qualification)
4. **Admin/logistics only** - Scheduling, onboarding logistics, account setup without substantive discussion

EXAMPLES:

Example 1 - ✅ DISCOVERY (Product Introduction):
"[Charles - CodeRabbit]: Thanks for joining Mark. Tell me about your code review process today?"
"[Mark - Cisco]: We have 50 engineers spending 4-5 hours per week on reviews..."
"[Charles]: Got it. Let me show you how CodeRabbit integrates as a GitHub app..."
"[Mark]: How does this handle security? We need SOC 2 compliance."
"[Charles]: Great question. We're SOC 2 certified. What's your timeline for evaluation?"
→ TRUE: Introductions, product explanation, features discussion, qualification questions both ways

Example 2 - ❌ NOT DISCOVERY (No-Show):
"[Gus - CodeRabbit]: Is he joining?"
"[Kush - CodeRabbit]: Don't think so, let's give him 5 more minutes"
"[Gus]: Yeah, this happens. Want to grab lunch after?"
"[Kush]: Sure, what are you thinking?"
→ FALSE: Prospect never showed up, only internal team chatting

Example 3 - ❌ NOT DISCOVERY (Trial Feedback):
"[Sales Rep]: So you completed the 2-week trial. How did it go?"
"[Customer]: We tested with 5 developers. Acceptance rate was 40%, found 15 bugs."
"[Sales Rep]: That's great ROI. Let's discuss pricing for the full team."
→ FALSE: This is post-trial review, discussing results and moving to negotiation

Example 4 - ❌ NOT DISCOVERY (Technical Troubleshooting):
"[Customer]: We're getting an error when CodeRabbit tries to access our monorepo."
"[Sales Rep]: Let me check the logs. What's the exact error message?"
"[Customer]: It says 'timeout after 30 seconds' on this specific file..."
→ FALSE: Deep technical debugging, not product introduction

<transcript>
{transcript[:12000]}
</transcript>

Analyze the transcript and respond with ONLY a valid JSON object (no markdown, no code blocks, no extra text):
{{
  "is_discovery_call": true,
  "reasoning": "Brief explanation (1-2 sentences) of why this is or isn't a discovery call based on the criteria above"
}}

OR

{{
  "is_discovery_call": false,
  "reasoning": "Brief explanation (1-2 sentences) of why this is or isn't a discovery call based on the criteria above"
}}"""

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )

        # Parse response
        content = response.content[0].text
        try:
            # Try to extract JSON from markdown code blocks if present
            if "```json" in content:
                json_start = content.find("```json") + 7
                json_end = content.find("```", json_start)
                content = content[json_start:json_end].strip()
            elif "```" in content:
                json_start = content.find("```") + 3
                json_end = content.find("```", json_start)
                content = content[json_start:json_end].strip()

            result = json.loads(content)
            is_discovery = result.get("is_discovery_call", False)
            reasoning = result.get("reasoning", "No reasoning provided")
            return is_discovery, reasoning
        except json.JSONDecodeError as e:
            # Log the actual response for debugging
            print(f"\n[DEBUG] Failed to parse LLM response: {e}")
            print(f"[DEBUG] Raw response: {content[:500]}")

            # Fallback: look for true/false in response
            is_discovery = "true" in content.lower() and "is_discovery_call" in content.lower()
            reasoning = f"Parse error: {content[:200]}..."
            return is_discovery, reasoning

    async def score_meddpicc(
        self, transcript: str
    ) -> tuple[MEDDPICCScores, AnalysisNotes, str]:
        """
        Score a transcript on MEDDPICC dimensions.

        Args:
            transcript: The call transcript text

        Returns:
            Tuple of (scores, analysis_notes, summary)
        """
        prompt = f"""Analyze this discovery call transcript and score it on each MEDDPICC dimension (0-5 scale).

IMPORTANT: Be STRICT in your evaluation. Only award high scores (4-5) when criteria are clearly and explicitly met with specific evidence. Use 0 when a dimension is absent, vague, or minimally mentioned.

MEDDPICC Scoring Framework:

**Metrics (0-5)**
5: Specific quantifiable metrics discussed (revenue targets, cost savings, efficiency gains with numbers)
3: General metrics mentioned without specific numbers
2: Business outcomes discussed but not quantified
0: Vague references to improvement or success, minimal mention, or no metrics discussed

**Economic Buyer (0-5)**
5: Economic buyer identified by name and title, confirmed budget authority
4: Economic buyer identified, authority implied
3: Discussion about who controls budget, but not confirmed
0: Unclear who has budget authority, vague references, or no discussion of economic buyer

**Decision Criteria (0-5)**
5: Explicit formal criteria documented (RFP, scorecard, evaluation matrix)
4: Clear informal criteria discussed (must-haves, priorities)
2: Some evaluation factors mentioned
0: Vague references, minimal discussion, or no decision criteria discussed

**Decision Process (0-5)**
5: Complete process mapped with steps, timeline, and stakeholders
4: Key steps and approximate timeline identified
3: Some process elements discussed
0: Vague references, minimal mention, or no process discussion

**Paper Process (0-5)**
5: Full procurement/legal process mapped with timeline
4: Key approval steps and stakeholders identified
3: Some procurement/legal requirements mentioned
0: Vague references, minimal mention, or no paper process discussed

**Identify Pain (0-5)**
5: Critical business pain clearly articulated with impact and urgency
4: Significant pain identified with business impact
2: Pain points mentioned but impact unclear
0: Vague problems, minimal mention, or no clear pain identified

**Champion (0-5)**
5: Champion identified, committed to advocate internally, has influence
4: Champion identified and supportive
3: Potential champion identified but commitment unclear
1: Friendly contact but not an advocate
0: Minimal engagement or no champion identified

**Competition (0-5)**
IMPORTANT: Focus on specific competitor tools for AI code review that the customer is currently using or considering.
Named tools include: Greptile, BugBot, Copilot, Claude, Graphite, Macroscope, SonarQube, Codacy, GitHub Advanced Security, etc.

5: Specific competitor tools named (e.g., "using Copilot", "evaluating Greptile"), with strengths/weaknesses discussed
4: Specific competitor tools named with some context about their usage
3: General mention of competitors or categories (e.g., "looking at AI tools", "comparing with others")
2: Vague competitive awareness (e.g., "might check alternatives")
0: No discussion of what customer currently uses or is considering

<transcript>
{transcript[:15000]}
</transcript>

CRITICAL: Respond with valid JSON in a markdown code block. Use this EXACT format with NO trailing commas:
{{
  "scores": {{
    "metrics": 2,
    "economic_buyer": 0,
    "decision_criteria": 4,
    "decision_process": 3,
    "paper_process": 0,
    "identify_pain": 4,
    "champion": 3,
    "competition": 0
  }},
  "summary": "2-3 sentence overall assessment highlighting key strengths and gaps in MEDDPICC coverage",
  "notes": {{
    "metrics": "Brief explanation for this score (cite specific evidence or lack thereof)",
    "economic_buyer": "Brief explanation for this score (cite specific evidence or lack thereof)",
    "decision_criteria": "Brief explanation for this score (cite specific evidence or lack thereof)",
    "decision_process": "Brief explanation for this score (cite specific evidence or lack thereof)",
    "paper_process": "Brief explanation for this score (cite specific evidence or lack thereof)",
    "identify_pain": "Brief explanation for this score (cite specific evidence or lack thereof)",
    "champion": "Brief explanation for this score (cite specific evidence or lack thereof)",
    "competition": "Brief explanation for this score (cite specific evidence or lack thereof)"
  }}
}}"""

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=3500,  # Increased for full response with detailed notes
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )

        # Parse response
        content = response.content[0].text

        # Retry logic for JSON parsing
        max_retries = 2
        for attempt in range(max_retries):
            try:
                # Try to extract JSON from markdown code blocks if present
                content_to_parse = content
                if "```json" in content_to_parse:
                    json_start = content_to_parse.find("```json") + 7
                    json_end = content_to_parse.find("```", json_start)
                    content_to_parse = content_to_parse[json_start:json_end].strip()
                elif "```" in content_to_parse:
                    json_start = content_to_parse.find("```") + 3
                    json_end = content_to_parse.find("```", json_start)
                    content_to_parse = content_to_parse[json_start:json_end].strip()

                # Try to clean up common JSON issues
                # Remove trailing commas before closing braces/brackets
                import re
                content_to_parse = re.sub(r',(\s*[}\]])', r'\1', content_to_parse)

                result = json.loads(content_to_parse)

                # Calculate overall score
                scores_dict = result["scores"]
                overall = sum(scores_dict.values()) / len(scores_dict)

                scores = MEDDPICCScores(
                    metrics=scores_dict["metrics"],
                    economic_buyer=scores_dict["economic_buyer"],
                    decision_criteria=scores_dict["decision_criteria"],
                    decision_process=scores_dict["decision_process"],
                    paper_process=scores_dict["paper_process"],
                    identify_pain=scores_dict["identify_pain"],
                    champion=scores_dict["champion"],
                    competition=scores_dict["competition"],
                    overall_score=round(overall, 1),
                )

                summary = result.get("summary", "No summary provided")

                # Validate notes has all required fields
                notes_data = result.get("notes", {})
                required_fields = ["metrics", "economic_buyer", "decision_criteria",
                                  "decision_process", "paper_process", "identify_pain",
                                  "champion", "competition"]
                missing_fields = [f for f in required_fields if f not in notes_data]

                if missing_fields and attempt < max_retries - 1:
                    print(f"\n[WARNING] Missing fields in notes: {missing_fields}, retrying...")
                    # Will retry in next iteration
                    continue
                elif missing_fields:
                    print(f"\n[WARNING] Missing fields in notes: {missing_fields}, using defaults")

                notes = AnalysisNotes(**notes_data)

                return scores, notes, summary

            except (json.JSONDecodeError, KeyError) as e:
                if attempt < max_retries - 1:
                    # Retry with a simpler prompt
                    print(f"\n[WARNING] JSON parse failed (attempt {attempt + 1}/{max_retries}), retrying...")
                    print(f"[DEBUG] Error: {e}")
                    print(f"[DEBUG] Problematic JSON (first 1000 chars):\n{content[:1000]}")

                    # Retry the API call with emphasis on JSON format
                    response = await self.client.messages.create(
                        model=self.model,
                        max_tokens=4000,
                        messages=[
                            {
                                "role": "user",
                                "content": f"{prompt}\n\nIMPORTANT: Return ONLY valid JSON with no trailing commas. Double-check your JSON syntax.\n\nTranscript:\n{transcript[:15000]}",
                            }
                        ],
                    )
                    content = response.content[0].text
                    continue
                else:
                    # Final attempt failed
                    print(f"\n[ERROR] Failed to parse MEDDPICC response after {max_retries} attempts")
                    print(f"[ERROR] Error: {e}")
                    print(f"[ERROR] Full response:\n{content}")
                    raise ValueError(f"Failed to parse MEDDPICC scores from LLM after {max_retries} attempts: {e}")
