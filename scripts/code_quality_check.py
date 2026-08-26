#!/usr/bin/env python3
"""Run dependency-free, ASCII-safe structural checks on package source."""

from __future__ import annotations

import ast
from pathlib import Path


SOURCE_DIR = Path(__file__).resolve().parents[1] / "src" / "parkingspace"


def check_code_quality() -> bool:
    print("=== BASIC CODE QUALITY CHECK ===")
    python_files = sorted(SOURCE_DIR.rglob("*.py")) if SOURCE_DIR.is_dir() else []
    if not python_files:
        print(f"ERROR: No Python files found under {SOURCE_DIR}")
        return False

    failures = []
    for file_path in python_files:
        try:
            source = file_path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(file_path))
            compile(tree, str(file_path), "exec")
            print(f"OK: {file_path.relative_to(SOURCE_DIR)}")
        except (OSError, UnicodeError, SyntaxError) as exc:
            failures.append(file_path)
            print(f"ERROR: {file_path.name}: {type(exc).__name__}: {exc}")

    if failures:
        print(f"Basic code quality check failed for {len(failures)} file(s)")
        return False
    print("All package files passed parse and compile checks")
    return True


if __name__ == "__main__":
    raise SystemExit(0 if check_code_quality() else 1)
