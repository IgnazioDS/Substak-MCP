# ABOUTME: Verifies server-side confirmation tokens for write actions.
# ABOUTME: Ensures first-call previews cannot be bypassed by blind confirm flags.

import asyncio
import re
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock, patch

from mcp.types import CallToolRequest

from src.server import SubstackMCPServer


def call_tool(server: SubstackMCPServer, name: str, arguments: dict):
    handler = server.server.request_handlers[CallToolRequest]
    result = asyncio.run(
        handler(CallToolRequest(params={"name": name, "arguments": arguments}))
    )
    return result.root.content[0].text


def extract_token(text: str) -> str:
    match = re.search(r"Confirmation token: ([A-Za-z0-9_-]+)", text)
    assert match is not None
    return match.group(1)


def test_create_post_preview_returns_confirmation_token():
    server = SubstackMCPServer()

    text = call_tool(
        server,
        "create_formatted_post",
        {"title": "Token Test", "content": "hello world"},
    )

    assert "Confirmation token:" in text
    assert "confirm_create" in text


def test_create_post_rejects_confirm_without_token():
    server = SubstackMCPServer()

    text = call_tool(
        server,
        "create_formatted_post",
        {"title": "Token Test", "content": "hello world", "confirm_create": True},
    )

    assert "confirmation token is required" in text.lower()


def test_create_post_rejects_wrong_token():
    server = SubstackMCPServer()
    preview_text = call_tool(
        server,
        "create_formatted_post",
        {"title": "Token Test", "content": "hello world"},
    )
    assert extract_token(preview_text)

    text = call_tool(
        server,
        "create_formatted_post",
        {
            "title": "Token Test",
            "content": "hello world",
            "confirm_create": True,
            "confirmation_token": "wrong-token",
        },
    )

    assert "invalid or expired confirmation token" in text.lower()


def test_create_post_rejects_argument_mismatch():
    server = SubstackMCPServer()
    preview_text = call_tool(
        server,
        "create_formatted_post",
        {"title": "Token Test", "content": "hello world"},
    )
    token = extract_token(preview_text)

    text = call_tool(
        server,
        "create_formatted_post",
        {
            "title": "Different Title",
            "content": "hello world",
            "confirm_create": True,
            "confirmation_token": token,
        },
    )

    assert "do not match the approved preview" in text.lower()


def test_create_post_consumes_confirmation_token_once():
    server = SubstackMCPServer()
    preview_text = call_tool(
        server,
        "create_formatted_post",
        {"title": "Token Test", "content": "hello world"},
    )
    token = extract_token(preview_text)

    mock_client = Mock()
    mock_post_handler = Mock()
    mock_post_handler.create_draft = AsyncMock(return_value={"id": "draft-123"})

    with patch.object(
        server, "_get_authenticated_client", AsyncMock(return_value=mock_client)
    ):
        with patch("src.server.PostHandler", return_value=mock_post_handler):
            success_text = call_tool(
                server,
                "create_formatted_post",
                {
                    "title": "Token Test",
                    "content": "hello world",
                    "confirm_create": True,
                    "confirmation_token": token,
                },
            )

    assert "draft created successfully" in success_text.lower()

    retry_text = call_tool(
        server,
        "create_formatted_post",
        {
            "title": "Token Test",
            "content": "hello world",
            "confirm_create": True,
            "confirmation_token": token,
        },
    )

    assert "invalid or expired confirmation token" in retry_text.lower()


def test_create_post_rejects_expired_confirmation_token():
    server = SubstackMCPServer()
    preview_text = call_tool(
        server,
        "create_formatted_post",
        {"title": "Token Test", "content": "hello world"},
    )
    token = extract_token(preview_text)
    server._confirmation_tokens[token]["expires_at"] = datetime.now(
        timezone.utc
    ) - timedelta(seconds=1)

    text = call_tool(
        server,
        "create_formatted_post",
        {
            "title": "Token Test",
            "content": "hello world",
            "confirm_create": True,
            "confirmation_token": token,
        },
    )

    assert "invalid or expired confirmation token" in text.lower()
