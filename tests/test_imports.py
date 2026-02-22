#!/usr/bin/env python3
"""Test that all imports work correctly."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

print("Testing imports...")

print("  → Core modules...")
from src.core import Config, GongClient, LLMClient
print("    ✓ Core imports successful")

print("  → Domain models...")
from src.domain import (
    SalesRep, Account, Call,
    MEDDPICCScores, TrialScores, CloseScores, WinLossAnalysis,
)
print("    ✓ Domain imports successful")

print("  → Data layer...")
from src.data import Database, init_database, Repository
print("    ✓ Data imports successful")

print("  → Services...")
from src.services import (
    StageClassifier,
    MEDDPICCEvaluator,
    TrialEvaluator,
    CloseEvaluator,
    WinLossAnalyzer,
)
from src.services.call_processor import CallProcessor
print("    ✓ Services imports successful")

print("\n✅ All imports successful!")
print("\nNext steps:")
print("  1. Configure environment variables (GONG_ACCESS_KEY, OPENAI_API_KEY, etc.)")
print("  2. Run: python process_calls.py --reset --limit 5")
print("  3. Check introspect.db for results")
