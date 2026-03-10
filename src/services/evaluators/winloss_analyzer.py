"""Win/Loss analyzer for closed deals."""

import json
from typing import Dict, Any

from .base_evaluator import BaseEvaluator
from ...domain import WinLossAnalysis


class WinLossAnalyzer(BaseEvaluator):
    """Analyzes closed deals to understand win/loss factors."""

    def evaluate(self, transcript: str, call_context: dict = None) -> WinLossAnalysis:
        """
        Analyze a closed deal to understand why it was won or lost.

        Args:
            transcript: Full call transcript
            call_context: Optional context (not used for Win/Loss)

        Returns:
            WinLossAnalysis object with outcome and analysis
        """
        prompt = self._build_evaluation_prompt(transcript, call_context)

        response = self.llm_client.call_llm(
            prompt=prompt,
            system_message="You are a sales methodology expert specializing in win/loss analysis.",
        )

        return self._parse_evaluation_response(response)

    def _build_evaluation_prompt(self, transcript: str, call_context: dict) -> str:
        """Build the win/loss analysis prompt."""
        return f"""You are analyzing a sales call transcript where the deal outcome is discussed (won or lost).

Conduct a comprehensive win/loss analysis to understand the factors behind the outcome.

**ANALYSIS QUESTIONS:**

**If Won:**
1. What were the key factors that led to the win?
2. Which dimensions (MEDDPICC/TRIAL/CLOSE) were strongest?
3. What did we do exceptionally well?
4. What could we have done better or faster?
5. What did the customer say were deciding factors?

**If Lost:**
1. What were the primary reasons for the loss?
2. At which stage did we lose control? (Discovery, Trial, Negotiation)
3. Which dimensions were weakest?
4. Did we lose to competition? If so, who and why?
5. What could we have done differently?

**FOR BOTH:**
- At which stage was the outcome determined? (Discovery, Trial, Negotiation)
- What specific factors at that stage led to win/loss?
- Competitive Factor: Did we face competition? Who and why did they win/lose?
- Key Learnings: What should we replicate or avoid in future deals?
- Which MEDDPICC/TRIAL/CLOSE dimensions were critical?

**TRANSCRIPT:**
{transcript}

**OUTPUT FORMAT:**
Respond in JSON format only:
{{
    "outcome": "won|lost",
    "primary_reasons": "Pipe-separated list of key reasons (e.g., 'Strong champion|Clear ROI|Beat competition')",
    "stage_of_decision": "discovery|trial|negotiation",
    "critical_dimensions": "Which dimensions mattered most (e.g., 'Champion, Technical Validation, Commercial Alignment')",
    "competitive_factor": "Who we competed against and why we won/lost (or 'No competition' if sole vendor)",
    "key_learnings": "Bullet list of learnings for future deals",
    "verbatim_quotes": "Key quotes from the call supporting the analysis"
}}

Respond with JSON only, no additional text."""

    def _parse_evaluation_response(self, response: str) -> WinLossAnalysis:
        """Parse the LLM response into a WinLossAnalysis object."""
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

            # Create WinLossAnalysis object
            return WinLossAnalysis(
                outcome=data["outcome"],
                primary_reasons=to_string(data.get("primary_reasons", "")),
                stage_of_decision=data.get("stage_of_decision"),
                critical_dimensions=to_string(data.get("critical_dimensions")),
                competitive_factor=to_string(data.get("competitive_factor")),
                key_learnings=to_string(data.get("key_learnings")),
                verbatim_quotes=to_string(data.get("verbatim_quotes")),
            )

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            # Return default analysis if parsing fails
            print(f"⚠️  Failed to parse Win/Loss analysis: {e}")
            print(f"Response: {response}")

            return WinLossAnalysis(
                outcome="lost",  # Default to lost if parsing fails
                primary_reasons=f"Analysis failed: {str(e)}",
                key_learnings="Unable to extract learnings due to parsing error",
            )
