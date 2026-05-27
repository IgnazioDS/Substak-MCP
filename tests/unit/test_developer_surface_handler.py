# ABOUTME: Unit tests for Substack's officially documented developer-facing surfaces.
# ABOUTME: Covers RSS feed parsing plus embed/signup integration capability reporting.

import pytest

from src.handlers.developer_surface_handler import DeveloperSurfaceHandler

RSS_SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Example Publication</title>
    <link>https://example.substack.com</link>
    <description>Testing feed parsing.</description>
    <item>
      <title>First Post</title>
      <link>https://example.substack.com/p/first-post</link>
      <description>First summary.</description>
      <pubDate>Wed, 27 May 2026 10:00:00 GMT</pubDate>
      <guid>first-post</guid>
    </item>
    <item>
      <title>Second Post</title>
      <link>https://example.substack.com/p/second-post</link>
      <description>Second summary.</description>
      <pubDate>Tue, 26 May 2026 10:00:00 GMT</pubDate>
      <guid>second-post</guid>
    </item>
  </channel>
</rss>
"""


@pytest.mark.asyncio
async def test_get_publication_rss_feed_parses_channel_and_items(monkeypatch):
    handler = DeveloperSurfaceHandler()

    async def fake_fetch_feed_text(feed_url: str) -> str:
        assert feed_url == "https://example.substack.com/feed"
        return RSS_SAMPLE

    monkeypatch.setattr(handler, "_fetch_feed_text", fake_fetch_feed_text)

    result = await handler.get_publication_rss_feed(
        "https://example.substack.com", limit=1
    )

    assert result["publication_url"] == "https://example.substack.com"
    assert result["feed_url"] == "https://example.substack.com/feed"
    assert result["title"] == "Example Publication"
    assert len(result["items"]) == 1
    assert result["items"][0]["title"] == "First Post"


@pytest.mark.asyncio
async def test_get_publication_rss_feed_rejects_invalid_publication_url():
    handler = DeveloperSurfaceHandler()

    with pytest.raises(ValueError, match="publication_url must be a valid"):
        await handler.get_publication_rss_feed("notaurl")


def test_get_official_integration_options_for_publication_reports_supported_surfaces():
    handler = DeveloperSurfaceHandler()

    result = handler.get_official_integration_options(
        "https://example.substack.com", target_type="publication"
    )

    capability_names = {item["name"] for item in result["official_capabilities"]}

    assert result["target_type"] == "publication"
    assert result["rss_feed_url"] == "https://example.substack.com/feed"
    assert "publication_rss" in capability_names
    assert "signup_form_embed" in capability_names
    assert "podcast_rss_distribution" in capability_names
    assert "developer_api_profile_search" in capability_names


def test_get_official_integration_options_for_post_reports_embed_flow():
    handler = DeveloperSurfaceHandler()

    result = handler.get_official_integration_options(
        "https://example.substack.com/p/example-post", target_type="post"
    )

    assert result["target_type"] == "post"
    assert result["official_capabilities"][0]["name"] == "post_embed"
    assert "Share" in result["official_capabilities"][0]["how_to_access"]


def test_get_official_integration_options_rejects_unsupported_target_type():
    handler = DeveloperSurfaceHandler()

    with pytest.raises(ValueError, match="target_type must be one of"):
        handler.get_official_integration_options(
            "https://example.substack.com", target_type="podcast"
        )


@pytest.mark.asyncio
async def test_search_profiles_by_linkedin_returns_public_profile_matches(monkeypatch):
    handler = DeveloperSurfaceHandler()

    async def fake_fetch_json(url: str, developer_api_token: str | None = None) -> dict:
        assert url == "https://substack.com/profile/search/linkedin/johndoe"
        assert developer_api_token is None
        return {
            "results": [
                {
                    "identityHandle": "johndoe",
                    "profileUrl": "https://substack.com/@johndoe",
                    "roughNumFreeSubscribers": 5000,
                    "followerCount": 1250,
                }
            ]
        }

    monkeypatch.setattr(handler, "_fetch_json", fake_fetch_json)

    result = await handler.search_profiles_by_linkedin("johndoe")

    assert result["linkedin_handle"] == "johndoe"
    assert result["matches"][0]["profile_url"] == "https://substack.com/@johndoe"
    assert result["matches"][0]["follower_count"] == 1250


@pytest.mark.asyncio
async def test_search_profiles_by_linkedin_passes_developer_token(monkeypatch):
    handler = DeveloperSurfaceHandler()

    async def fake_fetch_json(url: str, developer_api_token: str | None = None) -> dict:
        assert url == "https://substack.com/profile/search/linkedin/johndoe"
        assert developer_api_token == "dev-token"
        return {"results": []}

    monkeypatch.setattr(handler, "_fetch_json", fake_fetch_json)

    result = await handler.search_profiles_by_linkedin(
        "johndoe", developer_api_token="dev-token"
    )

    assert result["linkedin_handle"] == "johndoe"
    assert result["matches"] == []
