# ABOUTME: Tests MCP server wiring for official Substack developer-surface tools.
# ABOUTME: Verifies RSS feed and integration-option tools stay public and formatted.

import asyncio
from unittest.mock import AsyncMock

from mcp.types import CallToolRequest

from src.server import SubstackMCPServer


def call_tool(server: SubstackMCPServer, name: str, arguments: dict) -> str:
    handler = server.server.request_handlers[CallToolRequest]
    result = asyncio.run(
        handler(CallToolRequest(params={"name": name, "arguments": arguments}))
    )
    return result.root.content[0].text


def test_get_publication_rss_feed_tool_formats_feed_results(monkeypatch):
    server = SubstackMCPServer()
    monkeypatch.setattr(
        server.developer_surface_handler,
        "get_publication_rss_feed",
        AsyncMock(
            return_value={
                "publication_url": "https://example.substack.com",
                "feed_url": "https://example.substack.com/feed",
                "title": "Example Publication",
                "description": "Feed summary",
                "items": [
                    {
                        "title": "First Post",
                        "link": "https://example.substack.com/p/first-post",
                        "published_at": "Wed, 27 May 2026 10:00:00 GMT",
                    }
                ],
            }
        ),
    )

    text = call_tool(
        server,
        "get_publication_rss_feed",
        {"publication_url": "https://example.substack.com", "limit": 5},
    )

    assert "Example Publication" in text
    assert "https://example.substack.com/feed" in text
    assert "First Post" in text


def test_get_substack_integration_options_tool_formats_capabilities(monkeypatch):
    server = SubstackMCPServer()
    monkeypatch.setattr(
        server.developer_surface_handler,
        "get_official_integration_options",
        lambda url, target_type="publication": {
            "target_url": url,
            "target_type": target_type,
            "rss_feed_url": "https://example.substack.com/feed",
            "official_capabilities": [
                {
                    "name": "publication_rss",
                    "availability": "supported",
                    "how_to_access": "Use the public /feed URL.",
                },
                {
                    "name": "signup_form_embed",
                    "availability": "supported",
                    "how_to_access": "Use Settings -> Growth features.",
                },
            ],
            "support_links": [
                {
                    "label": "RSS feed article",
                    "url": "https://support.substack.com/hc/en-us/articles/360038239391-Is-there-an-RSS-feed-for-my-publication",
                }
            ],
        },
    )

    text = call_tool(
        server,
        "get_substack_integration_options",
        {
            "url": "https://example.substack.com",
            "target_type": "publication",
        },
    )

    assert "publication_rss" in text
    assert "signup_form_embed" in text
    assert "Use the public /feed URL." in text


def test_search_substack_profiles_by_linkedin_tool_formats_matches(monkeypatch):
    server = SubstackMCPServer()
    monkeypatch.setattr(
        server.developer_surface_handler,
        "search_profiles_by_linkedin",
        AsyncMock(
            return_value={
                "linkedin_handle": "johndoe",
                "matches": [
                    {
                        "identity_handle": "johndoe",
                        "profile_url": "https://substack.com/@johndoe",
                        "follower_count": 1250,
                        "rough_num_free_subscribers": 5000,
                    }
                ],
            }
        ),
    )

    text = call_tool(
        server,
        "search_substack_profiles_by_linkedin",
        {"linkedin_handle": "johndoe"},
    )

    assert "johndoe" in text
    assert "https://substack.com/@johndoe" in text
    assert "1250" in text
