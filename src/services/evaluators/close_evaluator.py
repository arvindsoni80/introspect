"""CLOSE evaluator for negotiation stage calls."""

import json
from typing import Dict, Any

from .base_evaluator import BaseEvaluator
from ...domain import CloseScores


class CloseEvaluator(BaseEvaluator):
    """Evaluates negotiation calls using the CLOSE health framework."""

    def evaluate(self, transcript: str, call_context: dict = None) -> CloseScores:
        """
        Evaluate a negotiation call using CLOSE health assessment.

        Args:
            transcript: Full call transcript
            call_context: Optional context (not used for CLOSE)

        Returns:
            CloseScores object with all dimensions scored
        """
        prompt = self._build_evaluation_prompt(transcript, call_context)

        response = self.llm_client.call_llm(
            prompt=prompt,
            system_message="You are a sales methodology expert specializing in deal closing and negotiation health.",
        )

        return self._parse_evaluation_response(response)

    def _build_evaluation_prompt(self, transcript: str, call_context: dict) -> str:
        """Build the CLOSE health evaluation prompt."""
        return f"""You are analyzing a sales call transcript to evaluate NEGOTIATION stage execution.

Evaluate the following CLOSE health dimensions on a 0/2/5 scale.
Be strict - only award 5 when the deal is clearly healthy with no significant concerns.
Note: Higher score = healthier deal (5 = healthy, 0 = critical issues).

**SCORING CRITERIA:**

1. **COMMERCIAL ALIGNMENT (C)** - Is pricing within budget? Is ROI compelling?
   - 5 = Pricing agreed and within budget, ROI compelling to decision maker, payment terms acceptable
   - 2 = Some pricing concerns or budget questions but negotiations progressing
   - 0 = Major pricing/budget issues, ROI not compelling, or commercial terms far apart

2. **LEGAL & COMPLIANCE (L)** - Are legal, security, and compliance requirements being met?
   - 5 = All security/compliance requirements met, legal terms agreed (liability, indemnification, data residency)
   - 2 = Some legal/compliance items being worked through but progressing
   - 0 = Major legal or compliance blockers

3. **ORGANIZATIONAL CONSENSUS (O)** - Are all key stakeholders aligned and ready to buy?
   - 5 = Decision maker convinced and ready to buy, champion confident, all key stakeholders aligned
   - 2 = Some stakeholders aligned but others need convincing, or champion somewhat confident
   - 0 = Decision maker not convinced, champion wavering, or stakeholders misaligned

4. **SINGLE-THREADING RISK (S)** - Do we have multiple contacts and adequate coverage?
   - 5 = Multi-threaded relationship with multiple contacts across the organization, connected to all key stakeholders
   - 2 = Connected to 2-3 contacts but not all key stakeholders
   - 0 = Single contact only, at risk if they leave

5. **EXECUTION MOMENTUM (E)** - Is the deal progressing toward signatures?
   - 5 = Active momentum toward close, paper process moving, approvals being obtained, key people engaged
   - 2 = Some progress but slower than expected, or occasional delays
   - 0 = Stalled, blocked, or key people unavailable

**ADDITIONAL ANALYSIS:**

Provide the following qualitative analysis:
- **Health Interpretation**: Healthy (4.0-5.0), At Risk (2.5-3.9), or Critical (0.0-2.4)
- **Primary Concern Category**: Commercial, Technical, Stakeholder, Process, or None (if healthy)
- **Concern Severity**: Critical, High, Medium, Low, or None
- **Likelihood to Close**: High (>70%), Medium (40-70%), or Low (<40%)
- **Has Competitive Pressure**: Boolean - Are they considering alternative vendors?
- **Key Concerns**: List the main concerns to address (if any)
- **Recommended Actions**: What actions should be taken to improve deal health?
- **Next Steps**: What are the recommended next steps?

**TRANSCRIPT:**
{transcript}

**OUTPUT FORMAT:**
Respond in JSON format only:
{{
    "commercial_alignment": 0|2|5,
    "legal_compliance": 0|2|5,
    "organizational_consensus": 0|2|5,
    "single_threading_risk": 0|2|5,
    "execution_momentum": 0|2|5,
    "overall_score": 0.0-5.0,
    "health_interpretation": "healthy|at_risk|critical",
    "primary_concern_category": "commercial|technical|stakeholder|process|none",
    "concern_severity": "critical|high|medium|low|none",
    "likelihood_to_close": "high|medium|low",
    "has_competitive_pressure": true|false,
    "key_concerns": "list of concerns",
    "recommended_actions": "recommended actions",
    "next_steps": "next steps"
}}

Respond with JSON only, no additional text."""

    def _parse_evaluation_response(self, response: str) -> CloseScores:
        """Parse the LLM response into a CloseScores object."""
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

            # Create CloseScores object
            return CloseScores(
                commercial_alignment=round_score(int(data["commercial_alignment"])),
                legal_compliance=round_score(int(data["legal_compliance"])),
                organizational_consensus=round_score(int(data["organizational_consensus"])),
                single_threading_risk=round_score(int(data["single_threading_risk"])),
                execution_momentum=round_score(int(data["execution_momentum"])),
                overall_score=float(data["overall_score"]),
                health_interpretation=data.get("health_interpretation"),
                primary_concern_category=data.get("primary_concern_category"),
                concern_severity=data.get("concern_severity"),
                likelihood_to_close=data.get("likelihood_to_close"),
                has_competitive_pressure=bool(data.get("has_competitive_pressure", False)),
                key_concerns=to_string(data.get("key_concerns")),
                recommended_actions=to_string(data.get("recommended_actions")),
                next_steps=to_string(data.get("next_steps")),
            )

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            # Return default scores if parsing fails
            print(f"⚠️  Failed to parse CLOSE evaluation: {e}")
            print(f"Response: {response}")

            return CloseScores(
                commercial_alignment=0,
                legal_compliance=0,
                organizational_consensus=0,
                single_threading_risk=0,
                execution_momentum=0,
                overall_score=0.0,
                health_interpretation="critical",
                key_concerns=f"Evaluation failed: {str(e)}",
            )
