# ABOUTME: Limited developer-surface handler for Substack feeds, embeds, and API discovery.
# ABOUTME: Wraps RSS plus narrow help-documented profile-search capabilities without account auth.

import os
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional
from urllib.parse import quote, urlparse

import aiohttp


class DeveloperSurfaceHandler:
    """Access limited documented Substack integration and profile-search surfaces."""

    RSS_SUPPORT_URL = (
        "https://support.substack.com/hc/en-us/articles/"
        "360038239391-Is-there-an-RSS-feed-for-my-publication"
    )
    SIGNUP_EMBED_SUPPORT_URL = (
        "https://support.substack.com/hc/en-us/articles/"
        "360041759232-Can-I-embed-a-signup-form-for-my-Substack-publication"
    )
    POST_AND_NOTE_EMBED_SUPPORT_URL = (
        "https://support.substack.com/hc/en-us/articles/"
        "25665267911572-How-do-I-embed-Substack-posts-or-notes-on-a-website"
    )
    PODCAST_DISTRIBUTION_SUPPORT_URL = (
        "https://support.substack.com/hc/en-us/articles/"
        "360038462911-How-do-I-distribute-my-podcast-to-apps"
    )
    DEVELOPER_API_SUPPORT_URL = (
        "https://support.substack.com/hc/en-us/articles/"
        "45099095296916-Substack-Developer-API"
    )

    async def get_publication_rss_feed(
        self, publication_url: str, limit: int = 10
    ) -> Dict[str, Any]:
        """Fetch and parse the Substack-supported public RSS feed for a publication."""
        normalized_url = self._normalize_http_url(
            publication_url, "publication_url must be a valid http(s) URL"
        )
        limit = max(1, min(limit, 25))
        feed_url = f"{normalized_url}/feed"

        rss_text = await self._fetch_feed_text(feed_url)
        root = ET.fromstring(rss_text)
        channel = root.find("channel")
        if channel is None:
            raise ValueError("Feed did not contain an RSS channel")

        items: List[Dict[str, Any]] = []
        for item in channel.findall("item")[:limit]:
            items.append(
                {
                    "title": self._rss_text(item, "title"),
                    "link": self._rss_text(item, "link"),
                    "description": self._rss_text(item, "description"),
                    "published_at": self._rss_text(item, "pubDate"),
                    "guid": self._rss_text(item, "guid"),
                }
            )

        return {
            "publication_url": normalized_url,
            "feed_url": feed_url,
            "title": self._rss_text(channel, "title"),
            "link": self._rss_text(channel, "link"),
            "description": self._rss_text(channel, "description"),
            "items": items,
            "support_links": [
                {"label": "RSS feed article", "url": self.RSS_SUPPORT_URL},
            ],
        }

    def get_official_integration_options(
        self, url: str, target_type: str = "publication"
    ) -> Dict[str, Any]:
        """Return documented Substack integration surfaces for a target URL."""
        normalized_url = self._normalize_http_url(
            url, "url must be a valid http(s) URL"
        )
        if target_type not in {"publication", "post", "note"}:
            raise ValueError("target_type must be one of: publication, post, note")

        capabilities: List[Dict[str, str]]
        support_links: List[Dict[str, str]]
        rss_feed_url = None

        if target_type == "publication":
            rss_feed_url = f"{normalized_url}/feed"
            capabilities = [
                {
                    "name": "publication_rss",
                    "availability": "supported",
                    "how_to_access": "Use the public /feed URL.",
                },
                {
                    "name": "signup_form_embed",
                    "availability": "supported",
                    "how_to_access": (
                        "Use Settings -> Growth features to copy the iframe embed code."
                    ),
                },
                {
                    "name": "podcast_rss_distribution",
                    "availability": "supported",
                    "how_to_access": (
                        "Use Podcast settings to copy the podcast RSS feed and submit it to external players."
                    ),
                },
                {
                    "name": "developer_api_profile_search",
                    "availability": "supported_with_token",
                    "how_to_access": (
                        "Enable Developer API access in your Substack account settings, create a token, and query the LinkedIn profile-search endpoint."
                    ),
                },
            ]
            support_links = [
                {"label": "RSS feed article", "url": self.RSS_SUPPORT_URL},
                {
                    "label": "Signup form embed article",
                    "url": self.SIGNUP_EMBED_SUPPORT_URL,
                },
                {
                    "label": "Podcast distribution article",
                    "url": self.PODCAST_DISTRIBUTION_SUPPORT_URL,
                },
                {
                    "label": "Developer API article",
                    "url": self.DEVELOPER_API_SUPPORT_URL,
                },
            ]
        elif target_type == "post":
            capabilities = [
                {
                    "name": "post_embed",
                    "availability": "supported",
                    "how_to_access": (
                        "Use Share -> More -> Embed on the published post page."
                    ),
                }
            ]
            support_links = [
                {
                    "label": "Post and note embed article",
                    "url": self.POST_AND_NOTE_EMBED_SUPPORT_URL,
                }
            ]
        else:
            capabilities = [
                {
                    "name": "note_embed",
                    "availability": "supported",
                    "how_to_access": "Use the note share menu and select Embed note.",
                }
            ]
            support_links = [
                {
                    "label": "Post and note embed article",
                    "url": self.POST_AND_NOTE_EMBED_SUPPORT_URL,
                }
            ]

        return {
            "target_url": normalized_url,
            "target_type": target_type,
            "rss_feed_url": rss_feed_url,
            "official_capabilities": capabilities,
            "support_links": support_links,
        }

    async def search_profiles_by_linkedin(
        self, linkedin_handle: str, developer_api_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """Call Substack's limited help-documented profile lookup surface."""
        handle = (linkedin_handle or "").strip().strip("/")
        if not handle:
            raise ValueError("linkedin_handle must be a non-empty string")

        resolved_token = developer_api_token or os.getenv(
            "SUBSTACK_DEVELOPER_API_TOKEN"
        )
        payload = await self._fetch_json(
            f"https://substack.com/profile/search/linkedin/{quote(handle)}",
            developer_api_token=resolved_token,
        )
        raw_results = payload.get("results", []) if isinstance(payload, dict) else []

        matches = []
        for item in raw_results:
            if not isinstance(item, dict):
                continue
            matches.append(
                {
                    "identity_handle": item.get("identityHandle"),
                    "profile_url": item.get("profileUrl"),
                    "leaderboard_status": item.get("leaderboardStatus"),
                    "bestseller_tier": item.get("bestsellerTier"),
                    "rough_num_free_subscribers": item.get("roughNumFreeSubscribers"),
                    "follower_count": item.get("followerCount"),
                }
            )

        return {
            "linkedin_handle": handle,
            "used_developer_token": bool(resolved_token),
            "matches": matches,
            "support_links": [
                {
                    "label": "Developer API article",
                    "url": self.DEVELOPER_API_SUPPORT_URL,
                }
            ],
        }

    async def _fetch_feed_text(self, feed_url: str) -> str:
        """Fetch RSS XML from a public feed URL."""
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=20)
        ) as session:
            async with session.get(feed_url) as response:
                if response.status != 200:
                    raise ValueError(
                        f"Feed request failed with status {response.status}"
                    )
                return await response.text()

    async def _fetch_json(
        self, url: str, developer_api_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """Fetch JSON from a limited help-documented profile lookup endpoint."""
        headers = {"Accept": "application/json"}
        if developer_api_token:
            headers["Authorization"] = f"Bearer {developer_api_token}"

        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=20)
        ) as session:
            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    if response.status in {401, 403, 404}:
                        raise ValueError(
                            "Developer API request failed. Substack may require an approved "
                            "Developer API token in SUBSTACK_DEVELOPER_API_TOKEN or the "
                            "tool argument `developer_api_token`."
                        )
                    raise ValueError(
                        f"Developer API request failed with status {response.status}"
                    )
                payload = await response.json()
                if not isinstance(payload, dict):
                    raise ValueError("Developer API response was not a dictionary")
                return payload

    def _normalize_http_url(self, url: str, error_message: str) -> str:
        """Normalize a user-supplied public URL."""
        if not url or not isinstance(url, str):
            raise ValueError(error_message)

        normalized = url.strip().rstrip("/")
        parsed = urlparse(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError(error_message)
        return normalized

    def _rss_text(self, element: ET.Element, tag_name: str) -> str:
        """Read RSS text content safely."""
        node = element.find(tag_name)
        if node is None or node.text is None:
            return ""
        return node.text.strip()
