"""Fast packaging and metadata regression tests (no model, camera, or GUI)."""

from __future__ import annotations

import importlib
from pathlib import Path
import sys

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


def _read_pyproject():
    try:
        import tomllib # pyright: ignore[reportMissingImports]
    except ModuleNotFoundError:  # Python 3.10: pip vendors the build parser.
        from pip._vendor import tomli as tomllib
    return tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def test_project_and_package_metadata_are_consistent():
    project = _read_pyproject()["project"]
    package = importlib.import_module("parkingspace")

    assert project["name"] == "parkingspace"
    assert project["version"] == package.__version__ == "1.0.0"
    assert project["authors"] == [
        {"name": package.__author__, "email": package.__email__}
    ]
    assert package.__author__ == "Python Apex"
    assert package.__email__ == "pythonapex01@gmail.com"
    assert package.__email__ == package.__email__.strip()
    assert project["license"]["text"] == package.__license__ == "Apache-2.0"
    assert project["requires-python"] == ">=3.10"


def test_console_entrypoints_target_the_explicit_legacy_callable():
    scripts = _read_pyproject()["project"]["scripts"]
    assert scripts["parkingspace"] == "parkingspace.main:legacy_main"
    assert scripts["parkingspace-legacy"] == "parkingspace.main:legacy_main"
    module = importlib.import_module("parkingspace.main")
    assert callable(module.legacy_main)
    assert module.main is module.legacy_main


def test_reset_config_has_none_contract_and_discards_singleton():
    from parkingspace.config import get_config, reset_config

    reset_config()
    first = get_config()
    assert reset_config() is None
    assert get_config() is not first
    reset_config()


def test_config_resolves_repository_assets_outside_project_cwd(monkeypatch, tmp_path):
    from parkingspace.config import Config

    monkeypatch.chdir(tmp_path)
    config = Config()
    assert Path(config.model_path).is_file() # pyright: ignore[reportArgumentType]
    assert "-seg" in Path(config.model_path).stem.lower() # pyright: ignore[reportArgumentType]
    assert Path(config.regions_file).is_file()
    assert Path(config.video.probability_map).is_file()


def test_missing_explicit_config_fails_clearly(tmp_path):
    from parkingspace.config import Config
    from parkingspace.exceptions import ConfigurationError

    with pytest.raises(ConfigurationError, match="Configuration file not found"):
        Config(str(tmp_path / "missing.json"))


def test_standard_apache_license_is_present():
    text = (PROJECT_ROOT / "LICENSE").read_text(encoding="utf-8")
    assert "Apache License" in text
    assert "Version 2.0, January 2004" in text
    assert "END OF TERMS AND CONDITIONS" in text
