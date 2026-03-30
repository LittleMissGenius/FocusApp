#!/usr/bin/env python3
"""Create a standalone RecipeApp repository from recipeapp_template/."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def run(cmd: list[str], cwd: Path) -> None:
    subprocess.run(cmd, cwd=str(cwd), check=True)


def main() -> int:
    source_dir = Path(__file__).resolve().parents[1]
    template_dir = source_dir / "recipeapp_template"
    target_dir = source_dir.parent / "RecipeApp"

    if not template_dir.exists():
        print(f"Missing template directory: {template_dir}", file=sys.stderr)
        return 1

    if target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    shutil.copytree(template_dir, target_dir, dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__"))

    run(["git", "init"], target_dir)
    run(["git", "add", "."], target_dir)
    run(["git", "commit", "-m", "Initialize standalone RecipeApp"], target_dir)

    print(f"RecipeApp created at {target_dir}")
    print("Next steps:")
    print(f"  cd {target_dir}")
    print("  python -m venv .venv")
    print("  source .venv/bin/activate   # Windows PowerShell: .venv\\Scripts\\Activate.ps1")
    print("  pip install -r requirements.txt")
    print("  python app.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
