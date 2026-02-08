#!/usr/bin/env python3
"""Test LLM analysis with a sample transcript."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import load_settings
from src.llm_client import LLMClient


SAMPLE_DISCOVERY_TRANSCRIPT = """
[Sales Rep]: Hi everyone, thanks for joining today. I'm excited to learn more about your business and see if we can help. Can you start by telling me about your current challenges with your code review process?

[Customer - CTO]: Sure, thanks for having us. Right now, we're spending about 4-5 hours per developer per week on code reviews. It's becoming a real bottleneck as we've grown to 50 engineers.

[Sales Rep]: That's significant. So if I'm doing the math, that's roughly 250 hours per week across your team. Have you quantified what that costs in terms of velocity or missed deadlines?

[Customer - CTO]: We estimate it's costing us about 2-3 sprint points per developer per sprint. That adds up to delays in our product roadmap.

[Sales Rep]: I see. Who typically makes the decision on tools like this in your organization? Is it you, or does it involve others?

[Customer - CTO]: I have budget authority for tools under $50K annually. Anything above that needs VP Engineering approval, but she trusts my judgment on technical tools.

[Sales Rep]: Got it. And what criteria are you using to evaluate solutions? What's most important to you?

[Customer - CTO]: Speed and accuracy are number one. We need something that catches real issues without too many false positives. Integration with GitHub is a must-have. And we need to be SOC 2 compliant.

[Sales Rep]: Makes sense. What does your evaluation process look like? What are the steps from here to a decision?

[Customer - CTO]: We're planning to do a 2-week trial with 2-3 vendors. Then present findings to the VP. We're hoping to make a decision by end of Q1.

[Sales Rep]: Perfect. Are you looking at any other solutions right now?

[Customer - CTO]: Yes, we're also evaluating GitHub Copilot's code review features and one other AI code review tool.

[Sales Rep]: And is there anyone on your team who's particularly excited about solving this problem? Someone who could help champion this internally?

[Customer - CTO]: Yes, actually our senior engineer Sarah has been pushing for this. She's been doing research and would definitely advocate for the right solution.

[Sales Rep]: That's great. Let me show you how we can help address these challenges...
"""

SAMPLE_NON_DISCOVERY_TRANSCRIPT = """
[Sales Rep]: Thanks for joining the demo today. Let me share my screen and walk you through the features.

[Sales Rep]: So here's the dashboard. You can see all your code reviews in one place. Let me click into this one...

[Sales Rep]: And here's how you configure the rules. Pretty straightforward, right?

[Sales Rep]: Any questions so far?

[Customer]: No, looks good. Keep going.

[Sales Rep]: Great. So next I'll show you the reporting features...
"""


async def test_llm():
    """Test LLM analysis."""
    print("=" * 70)
    print("Testing LLM Analysis")
    print("=" * 70)

    settings = load_settings()
    llm = LLMClient(settings)

    # Test 1: Discovery call classification
    print("\n1. Testing Discovery Call Classification...")
    print("\n   Sample 1: Clear discovery call")
    is_discovery_1 = await llm.is_discovery_call(SAMPLE_DISCOVERY_TRANSCRIPT)
    print(f"   Result: {'✓ Correctly identified as discovery' if is_discovery_1 else '✗ Incorrectly classified'}")

    print("\n   Sample 2: Demo call (not discovery)")
    is_discovery_2 = await llm.is_discovery_call(SAMPLE_NON_DISCOVERY_TRANSCRIPT)
    print(f"   Result: {'✓ Correctly identified as non-discovery' if not is_discovery_2 else '✗ Incorrectly classified'}")

    # Test 2: MEDDPICC scoring
    if is_discovery_1:
        print("\n2. Testing MEDDPICC Scoring...")
        scores, notes = await llm.score_meddpicc(SAMPLE_DISCOVERY_TRANSCRIPT)

        print(f"\n   Overall Score: {scores.overall_score}/5.0")
        print("\n   Dimension Scores:")
        print(f"     Metrics (M):          {scores.metrics}/5 - {notes.metrics}")
        print(f"     Economic Buyer (E):   {scores.economic_buyer}/5 - {notes.economic_buyer}")
        print(f"     Decision Criteria (D): {scores.decision_criteria}/5 - {notes.decision_criteria}")
        print(f"     Decision Process (D):  {scores.decision_process}/5 - {notes.decision_process}")
        print(f"     Paper Process (P):     {scores.paper_process}/5 - {notes.paper_process}")
        print(f"     Identify Pain (I):     {scores.identify_pain}/5 - {notes.identify_pain}")
        print(f"     Champion (C):          {scores.champion}/5 - {notes.champion}")
        print(f"     Competition (C):       {scores.competition}/5 - {notes.competition}")

    print("\n" + "=" * 70)
    print("✓ LLM tests complete!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_llm())
