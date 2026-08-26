#!/usr/bin/env python3
"""Parse package source files without importing runtime dependencies."""

from __future__ import annotations

import ast
from pathlib import Path


SOURCE_DIR = Path(__file__).resolve().parents[1] / "src" / "parkingspace"


def main() -> bool:
    print("=== SYNTAX CHECK ===")
    if not SOURCE_DIR.is_dir():
        print(f"ERROR: Source directory not found: {SOURCE_DIR}")
        return False

    failures = []
    for file_path in sorted(SOURCE_DIR.rglob("*.py")):
        try:
            ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
            print(f"OK: {file_path.relative_to(SOURCE_DIR)}")
        except (OSError, UnicodeError, SyntaxError) as exc:
            failures.append(file_path)
            print(f"ERROR: {file_path.name}: {type(exc).__name__}: {exc}")

    if failures:
        print(f"Syntax check failed for {len(failures)} file(s)")
        return False
    print("All package Python files are syntactically valid")
    return True


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
