# ABOUTME: Verifies package and runtime identifiers use the current repo naming.
# ABOUTME: Guards the CLI, auth storage, and MCP server against stale plus-era names.

import json
from pathlib import Path

from src.server import SubstackMCPServer


def test_package_json_uses_substack_mcp_names():
    package_json = json.loads(Path("package.json").read_text())

    assert package_json["name"] == "@ignaziods/substack-mcp"
    assert package_json["bin"] == {
        "substack-mcp": "src/index.js",
        "substack-mcp-setup": "src/setup.js",
    }


def test_pyproject_uses_substack_mcp_name():
    pyproject_text = Path("pyproject.toml").read_text()

    assert 'name = "substack-mcp"' in pyproject_text


def test_server_registers_substack_mcp_name():
    server = SubstackMCPServer()

    assert server.server.name == "substack-mcp"
