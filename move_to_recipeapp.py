#!/usr/bin/env python3
"""Convenience wrapper so Windows users can run from repo root.

Usage:
    python move_to_recipeapp.py
"""

from pathlib import Path
import runpy
import sys

SCRIPT = Path(__file__).resolve().parent / "scripts" / "move_to_recipeapp.py"

if not SCRIPT.exists():
    print(
        "Could not find scripts/move_to_recipeapp.py. "
        "Make sure you are in the FocusApp repository root and pulled the latest changes.",
        file=sys.stderr,
    )
    raise SystemExit(1)

runpy.run_path(str(SCRIPT), run_name="__main__")
