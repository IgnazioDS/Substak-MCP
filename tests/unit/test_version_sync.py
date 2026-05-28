# ABOUTME: Verifies package and runtime version metadata stay synchronized.
# ABOUTME: Prevents drift between npm, Python packaging, and MCP runtime versioning.

import json
import sys
if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib
from pathlib import Path

import src.version as runtime_version


def test_package_versions_match_runtime_version():
    repo_root = Path(__file__).resolve().parents[2]

    package_json = json.loads((repo_root / "package.json").read_text())
    pyproject = tomllib.loads((repo_root / "pyproject.toml").read_text())

    package_version = package_json["version"]
    pyproject_version = pyproject["project"]["version"]

    assert runtime_version.SERVER_VERSION == package_version
    assert runtime_version.SERVER_VERSION == pyproject_version
