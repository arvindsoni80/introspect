#!/usr/bin/env python3
"""
Introspect - Gong Transcript MEDDPICC Analysis Tool

Main entry point (backward compatibility wrapper).
Use `introspect` command after installation.
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))

from src.cli import cli

if __name__ == "__main__":
    cli()
