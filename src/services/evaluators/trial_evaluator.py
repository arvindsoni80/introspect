"""TRIAL evaluator for trial/POC stage calls."""

import json
from typing import Dict, Any

from .base_evaluator import BaseEvaluator
from ...domain import TrialScores


class TrialEvaluator(BaseEvaluator):
    """Evaluates trial/POC calls using the TRIAL health framework."""

    def evaluate(self, transcript: str, call_context: dict = None) -> TrialScores:
        """
        Evaluate a trial call using TRIAL health assessment.

        Args:
            transcript: Full call transcript
            call_context: Optional context (not used for TRIAL)

        Returns:
            TrialScores object with all dimensions scored
        """
        prompt = self._build_evaluation_prompt(transcript, call_context)

        response = self.llm_client.call_llm(
            prompt=prompt,
            system_message="You are a sales methodology expert specializing in trial/POC health assessment.",
        )

        return self._parse_evaluation_response(response)

    def _build_evaluation_prompt(self, transcript: str, call_context: dict) -> str:
        """Build the TRIAL health evaluation prompt."""
        return f"""You are analyzing a sales call transcript to evaluate TRIAL/POC stage execution.

Evaluate the following TRIAL health dimensions on a 0/2/5 scale.
Be strict - only award 5 when the trial is clearly healthy with no significant concerns.
Note: Higher score = healthier trial (5 = healthy, 0 = critical issues).

**SCORING CRITERIA:**

1. **TECHNICAL VALIDATION (T)** - Are users able to use the product successfully?
   - 5 = Users able to use product successfully, all technical requirements met, no blockers
   - 2 = Some technical concerns or minor blockers identified but addressable
   - 0 = Major technical blockers preventing success or fundamental performance/architecture issues

2. **READINESS & PROGRESS (R)** - Is the trial progressing on schedule?
   - 5 = Trial on schedule, success criteria being met, compelling results, readout ready
   - 2 = Some delays or mixed results but still progressing
   - 0 = Trial stalled, significantly delayed, or results not compelling

3. **INTERNAL ADOPTION (I)** - Are users actively engaged and satisfied?
   - 5 = High user engagement and satisfaction, users actively using product
   - 2 = Moderate engagement or mixed user feedback
   - 0 = Users unhappy, not using product, or poor adoption

4. **ADVOCACY & SENTIMENT (A)** - Is the champion confident? Are stakeholders aligned?
   - 5 = Champion confident and advocating strongly, stakeholders aligned, positive sentiment
   - 2 = Champion supportive but not strongly advocating, or some stakeholder concerns
   - 0 = Champion wavering, negative sentiment, or stakeholders misaligned

5. **LANDSCAPE & COMPETITION (L)** - Is this a bake-off? Are we winning?
   - 5 = Clear leader in evaluation, no serious competitive threats, or sole vendor
   - 2 = Competitive bake-off but performing well, or some competitive concerns
   - 0 = Losing to competition or serious competitive threat

**ADDITIONAL ANALYSIS:**

Provide the following qualitative analysis:
- **Health Interpretation**: Healthy (4.0-5.0), At Risk (2.5-3.9), or Critical (0.0-2.4)
- **Primary Concern Category**: Technical, Adoption, Competitive, Timeline, or None (if healthy)
- **Concern Severity**: Critical, High, Medium, Low, or None
- **Likelihood to Advance**: High (>70%), Medium (40-70%), or Low (<40%)
- **Is Bake-off**: Boolean - Is this a competitive evaluation?
- **Key Concerns**: List the main concerns to address (if any)
- **Recommended Actions**: What actions should be taken to improve trial health?
- **Next Steps**: What are the recommended next steps?

**TRANSCRIPT:**
{transcript}

**OUTPUT FORMAT:**
Respond in JSON format only:
{{
    "technical_validation": 0|2|5,
    "readiness_progress": 0|2|5,
    "internal_adoption": 0|2|5,
    "advocacy_sentiment": 0|2|5,
    "landscape_competition": 0|2|5,
    "overall_score": 0.0-5.0,
    "health_interpretation": "healthy|at_risk|critical",
    "primary_concern_category": "technical|adoption|competitive|timeline|none",
    "concern_severity": "critical|high|medium|low|none",
    "likelihood_to_advance": "high|medium|low",
    "is_bake_off": true|false,
    "key_concerns": "list of concerns",
    "recommended_actions": "recommended actions",
    "next_steps": "next steps"
}}

Respond with JSON only, no additional text."""

    def _parse_evaluation_response(self, response: str) -> TrialScores:
        """Parse the LLM response into a TrialScores object."""
        try:
            # Extract JSON from response (handle potential markdown code blocks)
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            response = response.strip()

            data = json.loads(response)

            # Helper to convert lists to strings
            def to_string(value):
                if value is None:
                    return None
                if isinstance(value, list):
                    return "\n".join(str(item) for item in value)
                return str(value)

            # Helper to round scores to nearest valid value (0, 2, 5)
            def round_score(value: int) -> int:
                """Round to nearest valid score: 0-1 → 0, 2-3 → 2, 4-5 → 5"""
                if value <= 1:
                    return 0
                elif value <= 3:
                    return 2
                else:
                    return 5

            # Create TrialScores object
            return TrialScores(
                technical_validation=round_score(int(data["technical_validation"])),
                readiness_progress=round_score(int(data["readiness_progress"])),
                internal_adoption=round_score(int(data["internal_adoption"])),
                advocacy_sentiment=round_score(int(data["advocacy_sentiment"])),
                landscape_competition=round_score(int(data["landscape_competition"])),
                overall_score=float(data["overall_score"]),
                health_interpretation=data.get("health_interpretation"),
                primary_concern_category=data.get("primary_concern_category"),
                concern_severity=data.get("concern_severity"),
                likelihood_to_advance=data.get("likelihood_to_advance"),
                is_bake_off=bool(data.get("is_bake_off", False)),
                key_concerns=to_string(data.get("key_concerns")),
                recommended_actions=to_string(data.get("recommended_actions")),
                next_steps=to_string(data.get("next_steps")),
            )

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            # Return default scores if parsing fails
            print(f"⚠️  Failed to parse TRIAL evaluation: {e}")
            print(f"Response: {response}")

            return TrialScores(
                technical_validation=0,
                readiness_progress=0,
                internal_adoption=0,
                advocacy_sentiment=0,
                landscape_competition=0,
                overall_score=0.0,
                health_interpretation="critical",
                key_concerns=f"Evaluation failed: {str(e)}",
            )
