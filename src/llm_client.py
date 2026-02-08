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

✅ IT IS A DISCOVERY CALL if it includes:
1. **Introductions among people** - Getting to know each other, backgrounds, roles
2. **Introduction to the product** - Explaining what CodeRabbit is, how it works
3. **Discussion of features and benefits** - What CodeRabbit can do, value propositions
4. **Discussion of a potential trial** - Exploring pilot programs, getting started
5. **Lots of questions FROM CodeRabbit** - Asking about customer's needs, current process, team size, tech stack, challenges
6. **Lots of questions FROM customer** - Asking about CodeRabbit's features, integrations, pricing, security, use cases

❌ IT IS NOT A DISCOVERY CALL if:
1. **No-show** - External participant never joined or didn't speak (only internal CodeRabbit team talking)
2. **Deal terms discussed** - Pricing negotiations, contract terms, legal discussions
3. **Trial feedback discussed** - Reviewing results after a trial, discussing what worked/didn't work
4. **Specific technical challenges** - Deep technical troubleshooting, debugging specific issues (not product introduction)

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
5: All competitors identified, strengths/weaknesses understood
4: Main competitors known with some differentiation clarity
3: Some competitive alternatives mentioned
1: Vague awareness or minimal mention of alternatives
0: No competitive discussion

<transcript>
{transcript[:15000]}
</transcript>

Respond with ONLY a valid JSON object (no markdown, no code blocks, no extra text):
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
            max_tokens=2048,
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
            notes = AnalysisNotes(**result["notes"])

            return scores, notes, summary

        except (json.JSONDecodeError, KeyError) as e:
            print(f"\n[DEBUG] Failed to parse MEDDPICC response: {e}")
            print(f"[DEBUG] Raw response: {content[:500]}")
            raise ValueError(f"Failed to parse MEDDPICC scores from LLM: {e}")
