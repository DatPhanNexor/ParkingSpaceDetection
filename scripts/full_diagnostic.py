#!/usr/bin/env python3
"""Run an ASCII-safe package diagnostic and return a truthful exit code."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
import platform
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"


def full_diagnostic() -> bool:
    print("=== PARKINGSPACE DIAGNOSTIC ===")
    print(f"Python: {platform.python_version()}")
    print(f"Project root: {PROJECT_ROOT}")
    if str(SRC_DIR) not in sys.path:
        sys.path.insert(0, str(SRC_DIR))

    failures = []
    try:
        package = import_module("parkingspace")
        print(f"OK: package import, version={package.__version__}")
    except Exception as exc:
        print(f"ERROR: package import: {type(exc).__name__}: {exc}")
        return False

    print("=== COMPONENT IMPORTS ===")
    components = [
        "main",
        "config",
        "pipeline",
        "regions",
        "utils",
        "performance",
        "capabilities",
        "services",
    ]
    for component in components:
        module_name = f"parkingspace.{component}"
        try:
            import_module(module_name)
            print(f"OK: {module_name}")
        except Exception as exc:
            failures.append(module_name)
            print(f"ERROR: {module_name}: {type(exc).__name__}: {exc}")

    if failures:
        print("Diagnostic failed: " + ", ".join(failures))
        return False
    print("Full diagnostic completed successfully")
    return True


if __name__ == "__main__":
    raise SystemExit(0 if full_diagnostic() else 1)
