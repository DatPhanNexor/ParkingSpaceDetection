#!/usr/bin/env python3
"""Import the package and its main modules with ASCII-safe diagnostics."""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"


def main() -> bool:
    if str(SRC_DIR) not in sys.path:
        sys.path.insert(0, str(SRC_DIR))

    print("=== IMPORT CHECK ===")
    modules = [
        "parkingspace",
        "parkingspace.main",
        "parkingspace.config",
        "parkingspace.logger",
        "parkingspace.exceptions",
        "parkingspace.pipeline",
        "parkingspace.regions",
        "parkingspace.utils",
        "parkingspace.performance",
        "parkingspace.capabilities",
        "parkingspace.services",
    ]
    failures = []
    for module_name in modules:
        try:
            import_module(module_name)
            print(f"OK: {module_name}")
        except Exception as exc:
            failures.append(module_name)
            print(f"ERROR: {module_name}: {type(exc).__name__}: {exc}")

    if failures:
        print("Import check failed: " + ", ".join(failures))
        return False
    print("All imports succeeded")
    return True


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
