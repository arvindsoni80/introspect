"""MEDDPICC evaluator for discovery stage calls."""

import json
from typing import Dict, Any

from .base_evaluator import BaseEvaluator
from ...domain import MEDDPICCScores


class MEDDPICCEvaluator(BaseEvaluator):
    """Evaluates discovery calls using the MEDDPICC framework."""

    def evaluate(self, transcript: str, call_context: dict = None) -> MEDDPICCScores:
        """
        Evaluate a discovery call using MEDDPICC.

        Args:
            transcript: Full call transcript
            call_context: Optional context (not used for MEDDPICC)

        Returns:
            MEDDPICCScores object with all dimensions scored
        """
        prompt = self._build_evaluation_prompt(transcript, call_context)

        response = self.llm_client.call_llm(
            prompt=prompt,
            system_message="You are a sales methodology expert specializing in MEDDPICC qualification.",
        )

        return self._parse_evaluation_response(response)

    def _build_evaluation_prompt(self, transcript: str, call_context: dict) -> str:
        """Build the MEDDPICC evaluation prompt."""
        return f"""You are analyzing a sales call transcript to evaluate DISCOVERY stage execution using the MEDDPICC framework.

Evaluate the following MEDDPICC dimensions on a 0/2/5 scale.
Be strict - only award 5 when criteria are clearly and explicitly met.

**SCORING CRITERIA:**

1. **METRICS (M)** - Were quantifiable success metrics discussed?
   - 5 = Specific quantifiable metrics with numbers (revenue targets, cost savings, efficiency gains, KPIs)
   - 2 = General metrics mentioned without specific numbers
   - 0 = No metrics discussed or only vague "improvement" references

2. **ECONOMIC BUYER (E)** - Was the budget holder identified?
   - 5 = Economic buyer identified by name/title with confirmed budget authority
   - 2 = Discussion about who controls budget but not confirmed
   - 0 = No discussion of economic buyer or unclear who has budget authority

3. **DECISION CRITERIA (D)** - Were evaluation criteria discussed?
   - 5 = Explicit formal criteria documented or clearly stated (RFP, scorecard, must-haves, evaluation matrix)
   - 2 = Some evaluation factors mentioned but incomplete or informal
   - 0 = No decision criteria discussed

4. **DECISION PROCESS (D)** - Was the decision process mapped?
   - 5 = Process mapped with specific steps, timeline/dates, and stakeholders identified
   - 2 = Some process elements mentioned but incomplete (e.g., "needs board approval")
   - 0 = No process discussion

5. **PAPER PROCESS (P)** - Was procurement/legal/security process discussed?
   - 5 = Procurement/legal/security process mapped with steps, timeline, and approvers identified
   - 2 = Some procurement/legal/security requirements mentioned but incomplete
   - 0 = No paper process discussed

6. **IDENTIFY PAIN (I)** - Was business pain clearly articulated?
   - 5 = Pain point, underlying reasons for pain, and urgency all clearly articulated
   - 2 = Pain point clear but underlying reasons or urgency unclear
   - 0 = No pain identified or only vague problem statements

7. **CHAMPION (C)** - Was an internal champion identified?
   - 5 = Champion identified by name, committed to advocate internally, influence demonstrated
   - 2 = Potential champion identified but commitment or influence unclear
   - 0 = No champion identified or only minimal engagement

8. **COMPETITION (C)** - Was competitive landscape discussed?
   - 5 = Competitors identified with strengths/weaknesses understood and differentiation clear
   - 2 = Some competitive alternatives mentioned but incomplete understanding
   - 0 = No competitive discussion

**ADDITIONAL ANALYSIS:**

Provide the following qualitative analysis:
- **MEDDPICC Summary**: Brief summary of what was discovered and overall qualification
- **Key Gaps**: What critical information is missing?
- **Clarity of Need**: Is there absolute clarity on customer need and urgency to buy?
- **Key Influencers**: Beyond champion and EB, who else influences the purchase decision?
- **Next Steps**: Are there clear next steps? (e.g., trial, deeper dive with broader team)
- **Trial Readiness**: If moving to trial, note deployment preference (SaaS/self-hosted) and key success criteria

**TRANSCRIPT:**
{transcript}

**OUTPUT FORMAT:**
Respond in JSON format only:
{{
    "metrics": 0|2|5,
    "economic_buyer": 0|2|5,
    "decision_criteria": 0|2|5,
    "decision_process": 0|2|5,
    "paper_process": 0|2|5,
    "identify_pain": 0|2|5,
    "champion": 0|2|5,
    "competition": 0|2|5,
    "overall_score": 0.0-5.0,
    "meddpicc_summary": "brief summary",
    "key_gaps": "list of gaps",
    "clarity_of_need": "assessment",
    "key_influencers": "names/roles",
    "next_steps": "recommended actions",
    "trial_readiness": "deployment preferences and success criteria if applicable"
}}

Respond with JSON only, no additional text."""

    def _parse_evaluation_response(self, response: str) -> MEDDPICCScores:
        """Parse the LLM response into a MEDDPICCScores object."""
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

            # Helper to get field with fallback alternatives
            def get_field(data: dict, primary: str, *alternatives) -> int:
                """Try primary field name, then alternatives if not found."""
                if primary in data:
                    return round_score(int(data[primary]))
                for alt in alternatives:
                    if alt in data:
                        return round_score(int(data[alt]))
                raise KeyError(f"Field '{primary}' not found (tried: {', '.join([primary] + list(alternatives))})")

            # Create MEDDPICCScores object
            return MEDDPICCScores(
                metrics=get_field(data, "metrics"),
                economic_buyer=get_field(data, "economic_buyer"),
                decision_criteria=get_field(data, "decision_criteria"),
                decision_process=get_field(data, "decision_process"),
                paper_process=get_field(data, "paper_process", "decision_paper_process", "p"),
                identify_pain=get_field(data, "identify_pain", "pain"),
                champion=get_field(data, "champion"),
                competition=get_field(data, "competition"),
                overall_score=float(data["overall_score"]),
                meddpicc_summary=to_string(data.get("meddpicc_summary")),
                key_gaps=to_string(data.get("key_gaps")),
                clarity_of_need=to_string(data.get("clarity_of_need")),
                key_influencers=to_string(data.get("key_influencers")),
                next_steps=to_string(data.get("next_steps")),
                trial_readiness=to_string(data.get("trial_readiness")),
            )

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            # Return default scores if parsing fails
            print(f"⚠️  Failed to parse MEDDPICC evaluation: {e}")
            print(f"Response: {response}")

            return MEDDPICCScores(
                metrics=0,
                economic_buyer=0,
                decision_criteria=0,
                decision_process=0,
                paper_process=0,
                identify_pain=0,
                champion=0,
                competition=0,
                overall_score=0.0,
                meddpicc_summary=f"Evaluation failed: {str(e)}",
            )
