# ABOUTME: Main MCP server implementation for Substack MCP Plus
# ABOUTME: Provides tools for creating, updating, publishing posts with rich formatting

import asyncio
import json
import logging
import secrets
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from mcp.server import NotificationOptions, Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import EmbeddedResource, ImageContent, TextContent, Tool

from src.handlers.auth_handler import AuthHandler
from src.handlers.developer_surface_handler import DeveloperSurfaceHandler
from src.handlers.image_handler import ImageHandler
from src.handlers.post_handler import PostHandler
from src.handlers.research_handler import ResearchHandler
from src.handlers.strategy_handler import StrategyHandler
from src.version import SERVER_VERSION

# Set up logging - use stderr for MCP servers
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger(__name__)


class SubstackMCPServer:
    """MCP server for Substack operations"""

    CONFIRMATION_TTL = timedelta(minutes=5)

    def __init__(self) -> None:
        """Initialize the MCP server"""
        self.server = Server("substack-mcp-plus")
        self._listed_tool_names: tuple[str, ...] = ()
        self._dispatch_tool_names: tuple[str, ...] = ()
        self._confirmation_tokens: Dict[str, Dict[str, Any]] = {}
        self._initialize_handlers()
        self._register_handlers()

    def _initialize_handlers(self) -> None:
        """Initialize handlers that do not require account authentication.

        MCP clients call `tools/list` before any credentials are available to the
        server process. If we require Substack auth during startup, the server
        exits before discovery and Codex sees `Tools: (none)`.
        """
        try:
            self.auth_handler: Optional[AuthHandler] = None
            self.developer_surface_handler = DeveloperSurfaceHandler()
            self.research_handler = ResearchHandler()
            self.strategy_handler = StrategyHandler()
            logger.info("Non-auth handlers initialized; auth will be created lazily")
        except Exception as e:
            logger.error(f"Failed to initialize handlers: {e}")
            raise

    async def _get_authenticated_client(self) -> Any:
        """Create the auth handler only when an account-bound tool is invoked."""
        if self.auth_handler is None:
            self.auth_handler = AuthHandler()
            logger.info("Authentication handler initialized lazily")
        return await self.auth_handler.authenticate()

    def _build_dispatch_tool_names(self) -> tuple[str, ...]:
        """Return the tool names handled by call_tool dispatch."""
        return (
            "create_formatted_post",
            "update_post",
            "publish_post",
            "schedule_post",
            "list_drafts",
            "list_scheduled_posts",
            "upload_image",
            "delete_draft",
            "list_published",
            "get_post_analytics",
            "get_post_content",
            "duplicate_post",
            "get_sections",
            "get_subscriber_count",
            "preview_draft",
            "get_publication_rss_feed",
            "get_substack_integration_options",
            "search_substack_profiles_by_linkedin",
            "research_substack",
            "analyze_my_posts",
            "research_substack_post",
            "research_substack_publication",
            "generate_post_ideas",
            "repurpose_post",
            "content_gap_analysis",
            "title_and_hook_optimizer",
            "series_planner",
            "study_topic_on_substack",
            "extract_coding_lessons",
        )

    def _prune_confirmation_tokens(self) -> None:
        """Drop expired confirmation tokens."""
        now = datetime.now(timezone.utc)
        expired_tokens = [
            token
            for token, payload in self._confirmation_tokens.items()
            if payload["expires_at"] <= now
        ]
        for token in expired_tokens:
            del self._confirmation_tokens[token]

    def _normalized_confirmation_arguments(
        self, arguments: Dict[str, Any], confirm_field: str
    ) -> Dict[str, Any]:
        """Return the arguments covered by a confirmation token."""
        normalized = dict(arguments or {})
        normalized.pop(confirm_field, None)
        normalized.pop("confirmation_token", None)
        return normalized

    def _issue_confirmation_token(
        self, tool_name: str, arguments: Dict[str, Any], confirm_field: str
    ) -> str:
        """Create a short-lived confirmation token for a write action."""
        self._prune_confirmation_tokens()
        token = secrets.token_urlsafe(18)
        self._confirmation_tokens[token] = {
            "tool_name": tool_name,
            "arguments": self._normalized_confirmation_arguments(
                arguments, confirm_field
            ),
            "expires_at": datetime.now(timezone.utc) + self.CONFIRMATION_TTL,
        }
        return token

    def _validate_confirmation_token(
        self, tool_name: str, arguments: Dict[str, Any], confirm_field: str
    ) -> Optional[str]:
        """Validate a confirmation token without consuming it."""
        self._prune_confirmation_tokens()
        token = arguments.get("confirmation_token")
        if not token:
            return "Error: A confirmation token is required before this action can run."

        payload = self._confirmation_tokens.get(token)
        if payload is None:
            return "Error: Invalid or expired confirmation token."

        normalized_arguments = self._normalized_confirmation_arguments(
            arguments, confirm_field
        )
        if payload["tool_name"] != tool_name:
            return "Error: Invalid or expired confirmation token."
        if payload["arguments"] != normalized_arguments:
            return (
                "Error: Confirmation token arguments do not match the approved preview."
            )

        return None

    def _consume_confirmation_token(self, token: str) -> None:
        """Consume a confirmation token after a successful write action."""
        self._confirmation_tokens.pop(token, None)

    def _confirmation_message(
        self, header: str, detail_lines: List[str], confirm_field: str, token: str
    ) -> str:
        """Build a standard confirmation preview message."""
        lines = [header, "", *detail_lines, ""]
        lines.append("Reply by recalling the same tool with:")
        lines.append(f"- `{confirm_field}=true`")
        lines.append(f"- `confirmation_token={token}`")
        lines.append("")
        lines.append(f"Confirmation token: {token}")
        lines.append("This token expires in 5 minutes and can be used once.")
        return "\n".join(lines)

    def _register_handlers(self) -> None:
        """Register all handlers with the MCP server"""

        @self.server.list_tools()
        async def handle_list_tools() -> List[Tool]:
            """List all available tools"""
            return [
                Tool(
                    name="create_formatted_post",
                    description="Create a new formatted draft post on Substack. Supports full markdown formatting. IMPORTANT: You MUST ALWAYS ask the user to confirm creation in a follow-up message BEFORE calling this tool with confirm_create=true. Never set confirm_create=true on the first request, even if the user explicitly asks to create. This ensures users have time to review the content before creating.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "title": {
                                "type": "string",
                                "description": "The main title/headline of the post. This will appear as the post title in Substack.",
                            },
                            "content": {
                                "type": "string",
                                "description": "The full content of the post in markdown format. Supports all standard markdown: # headers, **bold**, *italic*, [links](url), lists, code blocks, > quotes. Use '<!-- PAYWALL -->' to add paywall marker.",
                            },
                            "subtitle": {
                                "type": "string",
                                "description": "Optional subtitle that appears below the main title. Useful for additional context or taglines.",
                            },
                            "confirm_create": {
                                "type": "boolean",
                                "description": "NEVER set to true without explicit user confirmation in a follow-up message. Always false on first call.",
                                "default": False,
                            },
                        },
                        "required": ["title", "content"],
                    },
                ),
                Tool(
                    name="update_post",
                    description="Update an existing Substack draft post. WARNING: This tool COMPLETELY REPLACES the specified fields - it does NOT make partial edits. If you provide content, it will REPLACE ALL existing content. To make small edits, first use get_post_content to read the current content, make your changes, then provide the ENTIRE updated content. IMPORTANT: You MUST ALWAYS ask the user to confirm updates in a follow-up message BEFORE calling this tool with confirm_update=true. Never set confirm_update=true on the first request.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "post_id": {
                                "type": "string",
                                "description": "The unique ID of the draft post to update. Get this from list_drafts output.",
                            },
                            "title": {
                                "type": "string",
                                "description": "New title for the post (optional). WARNING: COMPLETELY REPLACES the current title.",
                            },
                            "content": {
                                "type": "string",
                                "description": "New content in markdown format (optional). WARNING: COMPLETELY REPLACES ALL existing content. This is NOT for partial edits - provide the ENTIRE new content.",
                            },
                            "subtitle": {
                                "type": "string",
                                "description": "New subtitle for the post (optional). WARNING: COMPLETELY REPLACES the current subtitle.",
                            },
                            "confirm_update": {
                                "type": "boolean",
                                "description": "NEVER set to true without explicit user confirmation in a follow-up message. Always false on first call.",
                                "default": False,
                            },
                        },
                        "required": ["post_id"],
                    },
                ),
                Tool(
                    name="publish_post",
                    description="Publish a draft post immediately to your Substack publication. This makes the post publicly visible to subscribers and sends it via email if enabled. IMPORTANT: You MUST ALWAYS ask the user to confirm publishing in a follow-up message BEFORE calling this tool with confirm_publish=true. Never set confirm_publish=true on the first request, even if the user explicitly asks to publish. This action cannot be easily undone.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "post_id": {
                                "type": "string",
                                "description": "The unique ID of the draft post to publish. Get this from list_drafts output.",
                            },
                            "confirm_publish": {
                                "type": "boolean",
                                "description": "NEVER set to true without explicit user confirmation in a follow-up message. Always false on first call.",
                                "default": False,
                            },
                        },
                        "required": ["post_id"],
                    },
                ),
                Tool(
                    name="schedule_post",
                    description="Schedule a draft post for future publication on Substack. This relies on a reverse-engineered private endpoint and should be treated as best-effort until verified on your publication. IMPORTANT: You MUST ALWAYS ask the user to confirm scheduling in a follow-up message BEFORE calling this tool with confirm_schedule=true. Never set confirm_schedule=true on the first request.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "post_id": {
                                "type": "string",
                                "description": "The unique ID of the draft post to schedule. Get this from list_drafts output.",
                            },
                            "scheduled_at": {
                                "type": "string",
                                "description": "When the post should publish, as an ISO 8601 datetime like 2026-03-10T09:00:00Z.",
                            },
                            "post_audience": {
                                "type": "string",
                                "description": "Who should get access when the post goes live. Default everyone.",
                                "default": "everyone",
                            },
                            "email_audience": {
                                "type": "string",
                                "description": "Who should receive the email when the post is sent. Default everyone.",
                                "default": "everyone",
                            },
                            "confirm_schedule": {
                                "type": "boolean",
                                "description": "NEVER set to true without explicit user confirmation in a follow-up message. Always false on first call.",
                                "default": False,
                            },
                        },
                        "required": ["post_id", "scheduled_at"],
                    },
                ),
                Tool(
                    name="list_drafts",
                    description="List your recent draft posts with their titles and IDs. Use this to see what drafts are available for updating, publishing, or deleting. Returns basic info about each draft.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of drafts to return. Default is 10, maximum is 25.",
                                "default": 10,
                            }
                        },
                    },
                ),
                Tool(
                    name="list_scheduled_posts",
                    description="List your scheduled future posts with their publish times and audiences. Use this to see what is queued to go live later.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of scheduled posts to return. Default is 10, maximum is 25.",
                                "default": 10,
                            }
                        },
                    },
                ),
                Tool(
                    name="upload_image",
                    description="Upload an image to Substack's CDN from either a local file path or a direct image URL. The server validates supported image content and rejects files larger than 25 MB before upload. The returned URL can be used in markdown content as ![alt text](url).",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "source": {
                                "type": "string",
                                "description": "Local file path or direct image URL to upload to Substack.",
                            }
                        },
                        "required": ["source"],
                    },
                ),
                Tool(
                    name="delete_draft",
                    description="Delete a draft post. IMPORTANT: You MUST ALWAYS ask the user to confirm deletion in a follow-up message BEFORE calling this tool with confirm_delete=true. Never set confirm_delete=true on the first request, even if the user explicitly asks to delete. This ensures users have time to reconsider this permanent action.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "post_id": {
                                "type": "string",
                                "description": "The unique ID of the draft to delete. Get this from list_drafts output.",
                            },
                            "confirm_delete": {
                                "type": "boolean",
                                "description": "NEVER set to true without explicit user confirmation in a follow-up message. Always false on first call.",
                                "default": False,
                            },
                        },
                        "required": ["post_id"],
                    },
                ),
                Tool(
                    name="list_published",
                    description="List your recently published posts with their titles, publication dates, and IDs. Use this to see what's already been published on your Substack.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "limit": {
                                "type": "integer",
                                "description": "Maximum number of published posts to return. Default is 10, maximum is 25.",
                                "default": 10,
                            }
                        },
                    },
                ),
                Tool(
                    name="get_post_analytics",
                    description="Get analytics for a published Substack post, including views, deliveries, opens, subscribers gained, and estimated value when available.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "post_id": {
                                "type": "string",
                                "description": "The ID of the published post to inspect. Get this from list_published.",
                            }
                        },
                        "required": ["post_id"],
                    },
                ),
                Tool(
                    name="get_post_content",
                    description="Read the full content of a specific post (draft or published) with all its formatting. Returns the post in a readable markdown format. Useful for reviewing content, copying from old posts, or checking formatting.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "post_id": {
                                "type": "string",
                                "description": "The ID of the post to read. Get this from list_drafts or list_published.",
                            }
                        },
                        "required": ["post_id"],
                    },
                ),
                Tool(
                    name="duplicate_post",
                    description="Create a copy of an existing post as a new draft. Perfect for using posts as templates. IMPORTANT: You MUST ALWAYS ask the user to confirm duplication in a follow-up message BEFORE calling this tool with confirm_duplicate=true. Never set confirm_duplicate=true on the first request, even if the user explicitly asks to duplicate.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "post_id": {
                                "type": "string",
                                "description": "The ID of the post to duplicate.",
                            },
                            "new_title": {
                                "type": "string",
                                "description": "Optional custom title for the duplicate. If not provided, will use 'Copy of [original title]'.",
                            },
                            "confirm_duplicate": {
                                "type": "boolean",
                                "description": "NEVER set to true without explicit user confirmation in a follow-up message. Always false on first call.",
                                "default": False,
                            },
                        },
                        "required": ["post_id"],
                    },
                ),
                Tool(
                    name="get_sections",
                    description="Get a list of available sections/categories in your Substack publication. Sections help organize your posts by topic or type. Returns section names and IDs that can be used when creating posts.",
                    inputSchema={"type": "object", "properties": {}},
                ),
                Tool(
                    name="get_subscriber_count",
                    description="Get the total number of subscribers to your Substack publication. Useful for tracking growth and understanding your audience size.",
                    inputSchema={"type": "object", "properties": {}},
                ),
                Tool(
                    name="preview_draft",
                    description="Generate the best available preview link for a draft post. When Substack does not expose a shareable preview token, this returns an author-only preview/edit URL that requires you to be logged in.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "post_id": {
                                "type": "string",
                                "description": "The ID of the draft to preview.",
                            }
                        },
                        "required": ["post_id"],
                    },
                ),
                Tool(
                    name="get_publication_rss_feed",
                    description="Fetch the Substack-supported public RSS feed for a publication and summarize its latest items.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "publication_url": {
                                "type": "string",
                                "description": "Publication base URL such as https://example.substack.com.",
                            },
                            "limit": {
                                "type": "integer",
                                "description": "How many feed items to return. Default 10, max 25.",
                                "default": 10,
                            },
                        },
                        "required": ["publication_url"],
                    },
                ),
                Tool(
                    name="get_substack_integration_options",
                    description="Describe the limited documented Substack integration surfaces for a publication, post, or note, including RSS feeds and embed flows.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "url": {
                                "type": "string",
                                "description": "Publication, post, or note URL to inspect.",
                            },
                            "target_type": {
                                "type": "string",
                                "enum": ["publication", "post", "note"],
                                "default": "publication",
                                "description": "Which documented surface to describe for the URL.",
                            },
                        },
                        "required": ["url"],
                    },
                ),
                Tool(
                    name="search_substack_profiles_by_linkedin",
                    description="Call Substack's limited help-documented Developer API profile lookup by LinkedIn handle. Provide a Developer API token directly or through SUBSTACK_DEVELOPER_API_TOKEN when your account requires it.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "linkedin_handle": {
                                "type": "string",
                                "description": "LinkedIn handle such as johndoe from https://www.linkedin.com/in/johndoe.",
                            },
                            "developer_api_token": {
                                "type": "string",
                                "description": "Optional Substack Developer API token. If omitted, the server will use SUBSTACK_DEVELOPER_API_TOKEN when available.",
                            },
                        },
                        "required": ["linkedin_handle"],
                    },
                ),
                Tool(
                    name="research_substack",
                    description="Research a topic across Substack with a rich discovery bundle. Searches for relevant newsletters and posts, reads top pages, extracts recurring themes, and recommends the best publications/posts to study.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Topic, niche, or keyword to research across Substack.",
                            },
                            "max_results": {
                                "type": "integer",
                                "description": "How many search results to gather before ranking. Default 25, max 30.",
                                "default": 25,
                            },
                            "deep_read_count": {
                                "type": "integer",
                                "description": "How many top results to fetch and analyze deeply. Default 5, max 5.",
                                "default": 5,
                            },
                        },
                        "required": ["query"],
                    },
                ),
                Tool(
                    name="analyze_my_posts",
                    description="Analyze your own Substack posts to uncover recurring themes, title patterns, CTA patterns, and recommended focus areas for your writing.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "source": {
                                "type": "string",
                                "description": "Which posts to analyze: published, drafts, or all. Default published.",
                                "default": "published",
                            },
                            "limit": {
                                "type": "integer",
                                "description": "How many posts to analyze. Default 10, max 15.",
                                "default": 10,
                            },
                        },
                    },
                ),
                Tool(
                    name="research_substack_post",
                    description="Analyze a specific public Substack post URL. Returns summary, hook analysis, CTA analysis, and study notes.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "url": {
                                "type": "string",
                                "description": "Public Substack post URL to analyze.",
                            }
                        },
                        "required": ["url"],
                    },
                ),
                Tool(
                    name="research_substack_publication",
                    description="Analyze a Substack publication URL. Returns positioning guess, themes, and audience fit based on visible page metadata and text.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "url": {
                                "type": "string",
                                "description": "Substack publication or archive URL to analyze.",
                            }
                        },
                        "required": ["url"],
                    },
                ),
                Tool(
                    name="generate_post_ideas",
                    description="Generate Substack post ideas using a topic plus optional analysis of your own posts and Substack research.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Topic or niche to generate ideas around.",
                            },
                            "count": {
                                "type": "integer",
                                "description": "How many ideas to return. Default 10, max 20.",
                                "default": 10,
                            },
                            "include_my_posts": {
                                "type": "boolean",
                                "description": "Whether to use your own published posts as part of idea generation.",
                                "default": True,
                            },
                        },
                        "required": ["query"],
                    },
                ),
                Tool(
                    name="repurpose_post",
                    description="Repurpose one of your posts, or provided title/content, into a Twitter thread, LinkedIn post, YouTube outline, or another lightweight format.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "post_id": {
                                "type": "string",
                                "description": "Optional post ID from your Substack account.",
                            },
                            "title": {
                                "type": "string",
                                "description": "Optional title if not using post_id.",
                            },
                            "content": {
                                "type": "string",
                                "description": "Optional content if not using post_id.",
                            },
                            "target_format": {
                                "type": "string",
                                "description": "Target format: twitter_thread, linkedin_post, youtube_outline, or short_summary.",
                                "default": "twitter_thread",
                            },
                        },
                    },
                ),
                Tool(
                    name="content_gap_analysis",
                    description="Compare your own post themes with researched Substack themes to identify content gaps and opportunities.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Topic or niche to compare your content against.",
                            },
                            "limit": {
                                "type": "integer",
                                "description": "How many of your own posts to inspect. Default 10.",
                                "default": 10,
                            },
                        },
                        "required": ["query"],
                    },
                ),
                Tool(
                    name="title_and_hook_optimizer",
                    description="Generate stronger title and opening-hook options from one of your posts or from provided title/content.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "post_id": {
                                "type": "string",
                                "description": "Optional post ID from your Substack account.",
                            },
                            "title": {
                                "type": "string",
                                "description": "Optional title if not using post_id.",
                            },
                            "content": {
                                "type": "string",
                                "description": "Optional content if not using post_id.",
                            },
                            "count": {
                                "type": "integer",
                                "description": "How many title/hook options to return. Default 5.",
                                "default": 5,
                            },
                        },
                    },
                ),
                Tool(
                    name="series_planner",
                    description="Turn a topic into a short Substack content series with a logical progression from beginner-friendly to deeper pieces.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "topic": {
                                "type": "string",
                                "description": "Topic to turn into a series.",
                            },
                            "count": {
                                "type": "integer",
                                "description": "How many parts in the series. Default 5, max 10.",
                                "default": 5,
                            },
                        },
                        "required": ["topic"],
                    },
                ),
                Tool(
                    name="study_topic_on_substack",
                    description="Create a study plan for a topic using researched Substack results, themes, and a suggested reading order.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "topic": {
                                "type": "string",
                                "description": "Topic to study on Substack.",
                            },
                            "max_results": {
                                "type": "integer",
                                "description": "How many research results to gather. Default 20.",
                                "default": 20,
                            },
                            "deep_read_count": {
                                "type": "integer",
                                "description": "How many results to read deeply. Default 5.",
                                "default": 5,
                            },
                        },
                        "required": ["topic"],
                    },
                ),
                Tool(
                    name="extract_coding_lessons",
                    description="Heuristically summarize coding or technical lessons from a research query or a specific public Substack URL.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "Optional research topic to study.",
                            },
                            "url": {
                                "type": "string",
                                "description": "Optional specific public Substack post URL.",
                            },
                        },
                    },
                ),
            ]

        async def collect_account_posts(
            client: Any, source: str = "published", limit: int = 10
        ) -> List[Dict[str, Any]]:
            source = (source or "published").lower()
            limit = max(1, min(limit, 15))
            post_handler = PostHandler(client)

            if source == "drafts":
                raw_posts = await post_handler.list_drafts(limit=limit)
            elif source == "all":
                published = await post_handler.list_published(
                    limit=max(1, limit // 2 or 1)
                )
                drafts = await post_handler.list_drafts(
                    limit=max(1, limit - len(published))
                )
                raw_posts = (published + drafts)[:limit]
            else:
                raw_posts = await post_handler.list_published(limit=limit)

            collected = []
            for post in raw_posts[:limit]:
                post_id = post.get("id")
                if not post_id:
                    continue
                try:
                    full_post = await post_handler.get_post_content(str(post_id))
                    collected.append(
                        {
                            "id": str(post_id),
                            "title": full_post.get("title", "Untitled"),
                            "content": full_post.get("content", ""),
                            "status": full_post.get("status", source),
                        }
                    )
                except Exception:
                    collected.append(
                        {
                            "id": str(post_id),
                            "title": post.get("title")
                            or post.get("draft_title")
                            or "Untitled",
                            "content": "",
                            "status": "published" if post.get("post_date") else "draft",
                        }
                    )
            return collected

        @self.server.call_tool()
        async def handle_call_tool(
            name: str, arguments: Optional[Dict[str, Any]]
        ) -> List[TextContent | ImageContent | EmbeddedResource]:
            """Handle tool execution"""
            arguments = arguments or {}
            try:
                if name == "research_substack":
                    result = await self.research_handler.research_substack(
                        query=arguments["query"],
                        max_results=arguments.get("max_results", 25),
                        deep_read_count=arguments.get("deep_read_count", 5),
                    )

                    lines = []
                    lines.append(f"🔎 Substack Research: {result['query']}")
                    lines.append("=" * 60)
                    lines.append(
                        f"Strategy: {result['search_strategy']} | Results: {result['results_found']}"
                    )
                    lines.append("")

                    if result.get("warnings"):
                        lines.append("Warnings:")
                        for warning in result["warnings"]:
                            lines.append(f"- {warning}")
                        lines.append("")

                    if result["themes"]:
                        lines.append("Top Themes:")
                        for theme in result["themes"]:
                            lines.append(
                                f"- {theme['theme']} ({theme['mentions']} mentions)"
                            )
                        lines.append("")

                    if result["publication_leaders"]:
                        lines.append("Publications Showing Up Most:")
                        for publication in result["publication_leaders"]:
                            lines.append(
                                f"- {publication['publication']} ({publication['mentions']} mentions)"
                            )
                        lines.append("")

                    if result["recommended_to_study"]:
                        lines.append("Best Results To Study:")
                        for recommendation in result["recommended_to_study"]:
                            lines.append(
                                f"- {recommendation['title']} | {recommendation['publication']}"
                            )
                            lines.append(f"  URL: {recommendation['url']}")
                            lines.append(f"  Why: {recommendation['why_study']}")
                        lines.append("")

                    lines.append("Search Results:")
                    for index, item in enumerate(result["results"], start=1):
                        lines.append(
                            f"{index}. {item.get('resolved_title') or item['title']}"
                        )
                        lines.append(
                            f"   Publication: {item.get('publication') or 'unknown'} | Type: {item.get('page_type', 'unknown')} | Provider: {item.get('provider', 'unknown')}"
                        )
                        if item.get("author"):
                            lines.append(f"   Author: {item['author']}")
                        if item.get("published_at"):
                            lines.append(f"   Published: {item['published_at']}")
                        lines.append(
                            f"   URL: {item.get('resolved_url') or item['url']}"
                        )
                        if item.get("summary"):
                            lines.append(f"   Summary: {item['summary']}")
                        lines.append("")

                    return [TextContent(type="text", text="\n".join(lines).strip())]

                if name == "research_substack_post":
                    result = await self.strategy_handler.research_post_url(
                        arguments["url"]
                    )
                    lines = [
                        f"📄 Substack Post Research: {result['title']}",
                        "=" * 60,
                        f"URL: {result['url']}",
                    ]
                    if result.get("publication"):
                        lines.append(f"Publication: {result['publication']}")
                    if result.get("author"):
                        lines.append(f"Author: {result['author']}")
                    if result.get("published_at"):
                        lines.append(f"Published: {result['published_at']}")
                    lines.extend(
                        [
                            "",
                            f"Summary: {result['summary']}",
                            f"Hook Analysis: {result['hook_analysis']}",
                            f"CTA Analysis: {result['cta_analysis']}",
                            "",
                            "Study Notes:",
                        ]
                    )
                    lines.extend([f"- {note}" for note in result["study_notes"]])
                    return [TextContent(type="text", text="\n".join(lines).strip())]

                if name == "research_substack_publication":
                    result = await self.strategy_handler.research_publication_url(
                        arguments["url"]
                    )
                    lines = [
                        f"📰 Publication Research: {result['title']}",
                        "=" * 60,
                        f"URL: {result['url']}",
                        f"Publication: {result.get('publication') or 'unknown'}",
                        "",
                        f"Summary: {result['summary']}",
                        f"Positioning Guess: {result['positioning_guess']}",
                        f"Audience Guess: {result['who_it_is_for']}",
                        "",
                        "Themes:",
                    ]
                    lines.extend(
                        [
                            f"- {theme['theme']} ({theme['mentions']} mentions)"
                            for theme in result["themes"]
                        ]
                    )
                    return [TextContent(type="text", text="\n".join(lines).strip())]

                if name == "get_publication_rss_feed":
                    result = (
                        await self.developer_surface_handler.get_publication_rss_feed(
                            arguments["publication_url"],
                            limit=arguments.get("limit", 10),
                        )
                    )
                    lines = [
                        f"🛰️ Publication RSS Feed: {result['title'] or result['publication_url']}",
                        "=" * 60,
                        f"Publication URL: {result['publication_url']}",
                        f"Feed URL: {result['feed_url']}",
                    ]
                    if result.get("description"):
                        lines.append(f"Description: {result['description']}")
                    lines.extend(["", "Latest Items:"])
                    if result["items"]:
                        for item in result["items"]:
                            lines.append(f"- {item.get('title') or 'Untitled'}")
                            if item.get("published_at"):
                                lines.append(f"  Published: {item['published_at']}")
                            if item.get("link"):
                                lines.append(f"  URL: {item['link']}")
                    else:
                        lines.append("- No feed items were found.")
                    return [TextContent(type="text", text="\n".join(lines).strip())]

                if name == "get_substack_integration_options":
                    result = (
                        self.developer_surface_handler.get_official_integration_options(
                            arguments["url"],
                            target_type=arguments.get("target_type", "publication"),
                        )
                    )
                    lines = [
                        f"🧩 Substack Integration Options: {result['target_type']}",
                        "=" * 60,
                        f"Target URL: {result['target_url']}",
                    ]
                    if result.get("rss_feed_url"):
                        lines.append(f"RSS Feed: {result['rss_feed_url']}")
                    lines.extend(["", "Official Capabilities:"])
                    for capability in result["official_capabilities"]:
                        lines.append(f"- {capability['name']}")
                        lines.append(f"  Availability: {capability['availability']}")
                        lines.append(f"  Access: {capability['how_to_access']}")
                    if result.get("support_links"):
                        lines.extend(["", "Support Links:"])
                        for link in result["support_links"]:
                            lines.append(f"- {link['label']}: {link['url']}")
                    return [TextContent(type="text", text="\n".join(lines).strip())]

                if name == "search_substack_profiles_by_linkedin":
                    result = await self.developer_surface_handler.search_profiles_by_linkedin(
                        arguments["linkedin_handle"],
                        developer_api_token=arguments.get("developer_api_token"),
                    )
                    lines = [
                        f"👤 Substack Profile Search: {result['linkedin_handle']}",
                        "=" * 60,
                    ]
                    lines.append(
                        "Developer token: "
                        + (
                            "provided"
                            if result.get("used_developer_token")
                            else "not provided"
                        )
                    )
                    if result["matches"]:
                        for match in result["matches"]:
                            lines.append(
                                f"- Handle: {match.get('identity_handle') or 'unknown'}"
                            )
                            if match.get("profile_url"):
                                lines.append(f"  Profile: {match['profile_url']}")
                            if match.get("follower_count") is not None:
                                lines.append(f"  Followers: {match['follower_count']}")
                            if match.get("rough_num_free_subscribers") is not None:
                                lines.append(
                                    "  Rough free subscribers: "
                                    f"{match['rough_num_free_subscribers']}"
                                )
                    else:
                        lines.append(
                            "- No public Substack profile matches were returned."
                        )
                    return [TextContent(type="text", text="\n".join(lines).strip())]

                if name == "series_planner":
                    plan = self.strategy_handler.series_plan(
                        topic=arguments["topic"],
                        count=arguments.get("count", 5),
                    )
                    lines = [
                        f"🧵 Series Plan: {arguments['topic']}",
                        "=" * 60,
                    ]
                    for item in plan:
                        lines.append(f"{item['part']}. {item['title']}")
                        lines.append(f"   Goal: {item['goal']}")
                    return [TextContent(type="text", text="\n".join(lines).strip())]

                if name == "study_topic_on_substack":
                    research = await self.research_handler.research_substack(
                        query=arguments["topic"],
                        max_results=arguments.get("max_results", 20),
                        deep_read_count=arguments.get("deep_read_count", 5),
                    )
                    study_plan = self.strategy_handler.study_topic_on_substack(
                        arguments["topic"], research
                    )
                    lines = [
                        f"📚 Study Plan: {study_plan['topic']}",
                        "=" * 60,
                        "Themes to watch:",
                    ]
                    if study_plan["themes"]:
                        lines.extend(
                            [
                                f"- {theme['theme']} ({theme['mentions']} mentions)"
                                for theme in study_plan["themes"]
                            ]
                        )
                    else:
                        lines.append("- No strong recurring themes were found.")
                    lines.extend(["", "Suggested Reading Order:"])
                    if study_plan["study_order"]:
                        for item in study_plan["study_order"]:
                            lines.append(f"{item['step']}. {item['title']}")
                            lines.append(f"   URL: {item['url']}")
                            lines.append(f"   Why: {item['why']}")
                    else:
                        lines.append("- No recommended reading order yet.")
                    if study_plan.get("warnings"):
                        lines.extend(["", "Warnings:"])
                        lines.extend(
                            [f"- {warning}" for warning in study_plan["warnings"]]
                        )
                    lines.extend(["", f"Study Tip: {study_plan['study_tip']}"])
                    return [TextContent(type="text", text="\n".join(lines).strip())]

                if name == "extract_coding_lessons":
                    if arguments.get("url"):
                        inspected = await self.strategy_handler.research_post_url(
                            arguments["url"]
                        )
                        research_result = {
                            "results": [
                                {
                                    "title": inspected["title"],
                                    "resolved_title": inspected["title"],
                                    "url": inspected["url"],
                                    "resolved_url": inspected["url"],
                                    "summary": inspected["summary"],
                                }
                            ]
                        }
                    elif arguments.get("query"):
                        research_result = await self.research_handler.research_substack(
                            query=arguments["query"],
                            max_results=15,
                            deep_read_count=5,
                        )
                    else:
                        raise ValueError("Provide either query or url")

                    lessons = self.strategy_handler.extract_coding_lessons(
                        research_result
                    )
                    lines = ["🧠 Coding Lessons", "=" * 60]
                    for lesson in lessons:
                        lines.append(f"- Source: {lesson['source']}")
                        lines.append(f"  URL: {lesson['url']}")
                        lines.append(f"  Lesson: {lesson['lesson']}")
                    return [TextContent(type="text", text="\n".join(lines).strip())]

                if name == "create_formatted_post":
                    confirm = arguments.get("confirm_create", False)
                    if not confirm:
                        content_preview = (
                            arguments["content"][:200] + "..."
                            if len(arguments["content"]) > 200
                            else arguments["content"]
                        )
                        token = self._issue_confirmation_token(
                            name, arguments, "confirm_create"
                        )
                        return [
                            TextContent(
                                type="text",
                                text=self._confirmation_message(
                                    "⚠️ CONFIRMATION REQUIRED ⚠️",
                                    [
                                        "You are about to CREATE a new draft:",
                                        f'- Title: "{arguments["title"]}"',
                                        f'- Subtitle: "{arguments.get("subtitle", "[none]")}"',
                                        f"- Content preview: {content_preview}",
                                        "⚡ This will create a new draft in your Substack account.",
                                    ],
                                    "confirm_create",
                                    token,
                                ),
                            )
                        ]

                    error = self._validate_confirmation_token(
                        name, arguments, "confirm_create"
                    )
                    if error:
                        return [TextContent(type="text", text=error)]

                # Authenticate and get client for account-specific tools
                client = await self._get_authenticated_client()

                # Debug: Check if client is wrapped
                logger.debug(f"Client type after authenticate: {type(client)}")
                logger.debug(f"Client class: {client.__class__.__name__}")
                logger.debug(
                    f"Is APIWrapper: {client.__class__.__name__ == 'APIWrapper'}"
                )
                logger.debug(f"Client has get_draft: {hasattr(client, 'get_draft')}")

                if name == "create_formatted_post":
                    post_handler = PostHandler(client)
                    result = await post_handler.create_draft(
                        title=arguments["title"],
                        content=arguments["content"],
                        subtitle=arguments.get("subtitle"),
                        content_type="markdown",
                    )
                    self._consume_confirmation_token(arguments["confirmation_token"])
                    return [
                        TextContent(
                            type="text",
                            text=f"✅ Draft created successfully!\nID: {result.get('id')}\nTitle: {arguments['title']}",
                        )
                    ]

                elif name == "update_post":
                    confirm = arguments.get("confirm_update", False)
                    if confirm:
                        error = self._validate_confirmation_token(
                            name, arguments, "confirm_update"
                        )
                        if error:
                            return [TextContent(type="text", text=error)]

                    if not confirm:
                        # Get the draft details to show what will be updated
                        try:
                            draft = client.get_draft(arguments["post_id"])

                            # Check if API returned a string error
                            if isinstance(draft, str):
                                raise ValueError(f"API error: {draft}")
                            if not isinstance(draft, dict):
                                raise ValueError("Invalid API response")

                            current_title = (
                                draft.get("draft_title")
                                or draft.get("title")
                                or "Untitled"
                            )

                            changes = []
                            if arguments.get("title"):
                                changes.append(f"- Title: \"{arguments['title']}\"")
                            if arguments.get("subtitle") is not None:
                                changes.append(
                                    f"- Subtitle: \"{arguments['subtitle']}\""
                                )
                            if arguments.get("content"):
                                changes.append("- Content: [new content provided]")

                            changes_text = (
                                "\n".join(changes)
                                if changes
                                else "- No changes specified"
                            )

                            token = self._issue_confirmation_token(
                                name, arguments, "confirm_update"
                            )
                            return [
                                TextContent(
                                    type="text",
                                    text=self._confirmation_message(
                                        "⚠️ CONFIRMATION REQUIRED ⚠️",
                                        [
                                            "You are about to UPDATE this draft:",
                                            f'- Post: "{current_title}"',
                                            f"- Changes:\n{changes_text}",
                                            "⚡ This will ONLY update the fields listed above.",
                                            "⚡ Other fields (like content) will remain unchanged.",
                                        ],
                                        "confirm_update",
                                        token,
                                    ),
                                )
                            ]
                        except Exception as e:
                            return [
                                TextContent(
                                    type="text",
                                    text=f"⚠️ Error getting draft details: {str(e)}\n\n"
                                    f"Cannot proceed with update without confirmation.",
                                )
                            ]

                    # Proceed with update
                    post_handler = PostHandler(client)
                    result = await post_handler.update_draft(
                        post_id=arguments["post_id"],
                        title=arguments.get("title"),
                        content=arguments.get("content"),
                        subtitle=arguments.get("subtitle"),
                        content_type="markdown",
                    )
                    self._consume_confirmation_token(arguments["confirmation_token"])
                    return [
                        TextContent(
                            type="text",
                            text=f"✅ Post updated successfully!\nID: {arguments['post_id']}",
                        )
                    ]

                elif name == "publish_post":
                    confirm = arguments.get("confirm_publish", False)
                    if confirm:
                        error = self._validate_confirmation_token(
                            name, arguments, "confirm_publish"
                        )
                        if error:
                            return [TextContent(type="text", text=error)]

                    if not confirm:
                        # Get the draft details to show what will be published
                        try:
                            draft = client.get_draft(arguments["post_id"])

                            # Check if API returned a string error
                            if isinstance(draft, str):
                                raise ValueError(f"API error: {draft}")
                            if not isinstance(draft, dict):
                                raise ValueError("Invalid API response")

                            title = (
                                draft.get("draft_title")
                                or draft.get("title")
                                or "Untitled"
                            )

                            # Check subscriber count if possible
                            try:
                                sections = client.get_sections()
                                pub_info = f"- Subscribers: {sections[0].get('subscriber_count', 'unknown')}"
                            except:
                                pub_info = "- Subscribers: [count unavailable]"

                            token = self._issue_confirmation_token(
                                name, arguments, "confirm_publish"
                            )
                            return [
                                TextContent(
                                    type="text",
                                    text=self._confirmation_message(
                                        "⚠️ CONFIRMATION REQUIRED ⚠️",
                                        [
                                            "You are about to PUBLISH this draft:",
                                            f'- Post: "{title}"',
                                            pub_info,
                                            "- Action: Publish immediately and send to all subscribers",
                                            "⚡ This CANNOT be undone and will send emails to all subscribers.",
                                        ],
                                        "confirm_publish",
                                        token,
                                    ),
                                )
                            ]
                        except Exception as e:
                            return [
                                TextContent(
                                    type="text",
                                    text=f"⚠️ Error getting draft details: {str(e)}\n\n"
                                    f"Cannot proceed with publishing without confirmation.",
                                )
                            ]

                    # Proceed with publishing
                    post_handler = PostHandler(client)
                    result = await post_handler.publish_draft(
                        post_id=arguments["post_id"]
                    )
                    self._consume_confirmation_token(arguments["confirmation_token"])
                    return [
                        TextContent(
                            type="text",
                            text=f"✅ Post published successfully!\nID: {arguments['post_id']}",
                        )
                    ]

                elif name == "schedule_post":
                    confirm = arguments.get("confirm_schedule", False)
                    if confirm:
                        error = self._validate_confirmation_token(
                            name, arguments, "confirm_schedule"
                        )
                        if error:
                            return [TextContent(type="text", text=error)]

                    if not confirm:
                        try:
                            draft = client.get_draft(arguments["post_id"])

                            if isinstance(draft, str):
                                raise ValueError(f"API error: {draft}")
                            if not isinstance(draft, dict):
                                raise ValueError("Invalid API response")

                            title = (
                                draft.get("draft_title")
                                or draft.get("title")
                                or "Untitled"
                            )
                            scheduled_at = arguments["scheduled_at"]
                            post_audience = arguments.get("post_audience", "everyone")
                            email_audience = arguments.get("email_audience", "everyone")

                            token = self._issue_confirmation_token(
                                name, arguments, "confirm_schedule"
                            )
                            return [
                                TextContent(
                                    type="text",
                                    text=self._confirmation_message(
                                        "⚠️ CONFIRMATION REQUIRED ⚠️",
                                        [
                                            "You are about to SCHEDULE this draft:",
                                            f'- Post: "{title}"',
                                            f"- Publish time: {scheduled_at}",
                                            f"- Access audience: {post_audience}",
                                            f"- Email audience: {email_audience}",
                                            "⚡ This will queue the post for future publication.",
                                        ],
                                        "confirm_schedule",
                                        token,
                                    ),
                                )
                            ]
                        except Exception as e:
                            return [
                                TextContent(
                                    type="text",
                                    text=f"⚠️ Error getting draft details: {str(e)}\n\n"
                                    f"Cannot proceed with scheduling without confirmation.",
                                )
                            ]

                    post_handler = PostHandler(client)
                    result = await post_handler.schedule_draft(
                        post_id=arguments["post_id"],
                        scheduled_at=arguments["scheduled_at"],
                        post_audience=arguments.get("post_audience", "everyone"),
                        email_audience=arguments.get("email_audience", "everyone"),
                    )
                    self._consume_confirmation_token(arguments["confirmation_token"])
                    schedules = result.get("postSchedules") or []
                    next_schedule = schedules[0] if schedules else {}
                    scheduled_time = (
                        next_schedule.get("trigger_at") or arguments["scheduled_at"]
                    )

                    return [
                        TextContent(
                            type="text",
                            text=f"✅ Post scheduled successfully!\n"
                            f"ID: {arguments['post_id']}\n"
                            f"Scheduled for: {scheduled_time}",
                        )
                    ]

                elif name == "list_drafts":
                    logger.info(f"list_drafts called with arguments: {arguments}")
                    post_handler = PostHandler(client)
                    drafts = await post_handler.list_drafts(
                        limit=arguments.get("limit", 10)
                    )
                    logger.info(f"list_drafts returned {len(drafts)} drafts")

                    draft_list = []
                    for draft in drafts:
                        title = (
                            draft.get("draft_title") or draft.get("title") or "Untitled"
                        )
                        draft_id = draft.get("id")
                        draft_list.append(f"- {title} (ID: {draft_id})")

                    response_text = f"Found {len(drafts)} drafts:\n" + "\n".join(
                        draft_list
                    )
                    logger.info(f"Returning response: {response_text[:100]}...")

                    return [TextContent(type="text", text=response_text)]

                elif name == "list_scheduled_posts":
                    post_handler = PostHandler(client)
                    scheduled_posts = await post_handler.list_scheduled_posts(
                        limit=arguments.get("limit", 10)
                    )

                    if not scheduled_posts:
                        return [
                            TextContent(
                                type="text",
                                text="No scheduled future posts found.",
                            )
                        ]

                    lines = [f"Found {len(scheduled_posts)} scheduled posts:"]
                    for post in scheduled_posts:
                        lines.append(
                            f"- {post['title']} (ID: {post['id']}, Scheduled: {post.get('scheduled_at')}, Access: {post.get('post_audience')}, Email: {post.get('email_audience')})"
                        )

                    return [TextContent(type="text", text="\n".join(lines))]

                elif name == "upload_image":
                    image_handler = ImageHandler(client)
                    source = arguments.get("source") or arguments.get("image_path")
                    if not source:
                        raise ValueError("source is required")
                    result = await image_handler.upload_image(source)
                    return [
                        TextContent(
                            type="text",
                            text=f"Image uploaded successfully!\nURL: {result['url']}",
                        )
                    ]

                elif name == "delete_draft":
                    post_id = arguments["post_id"]
                    confirm = arguments.get("confirm_delete", False)
                    if confirm:
                        error = self._validate_confirmation_token(
                            name, arguments, "confirm_delete"
                        )
                        if error:
                            return [TextContent(type="text", text=error)]

                    if not confirm:
                        # First call - get draft details and show warning
                        try:
                            draft = client.get_draft(post_id)
                            if isinstance(draft, dict):
                                title = (
                                    draft.get("draft_title")
                                    or draft.get("title")
                                    or "Untitled"
                                )
                            else:
                                title = "Unknown Title"
                        except:
                            title = "Unknown Title"

                        token = self._issue_confirmation_token(
                            name, arguments, "confirm_delete"
                        )
                        return [
                            TextContent(
                                type="text",
                                text=self._confirmation_message(
                                    "⚠️ DELETION CONFIRMATION REQUIRED ⚠️",
                                    [
                                        "You are about to permanently delete:",
                                        f'📄 Title: "{title}"',
                                        f"🆔 ID: {post_id}",
                                        "This action CANNOT be undone.",
                                    ],
                                    "confirm_delete",
                                    token,
                                ),
                            )
                        ]

                    # Confirmation received - proceed with deletion
                    try:
                        draft = client.get_draft(post_id)

                        if isinstance(draft, str):
                            raise ValueError(f"API error: {draft}")
                        if not isinstance(draft, dict):
                            raise ValueError("Invalid API response")

                        title = (
                            draft.get("draft_title") or draft.get("title") or "Untitled"
                        )

                        client.delete_draft(post_id)
                        self._consume_confirmation_token(
                            arguments["confirmation_token"]
                        )

                        return [
                            TextContent(
                                type="text",
                                text=f"✅ Draft deleted successfully!\n\n"
                                f"Deleted: {title}\n"
                                f"ID: {post_id}",
                            )
                        ]

                    except Exception as e:
                        return [
                            TextContent(
                                type="text", text=f"❌ Failed to delete draft: {str(e)}"
                            )
                        ]

                elif name == "list_published":
                    post_handler = PostHandler(client)
                    published = await post_handler.list_published(
                        limit=arguments.get("limit", 10)
                    )

                    if not published:
                        return [
                            TextContent(type="text", text="No published posts found.")
                        ]

                    published_list = []
                    for post in published:
                        title = post.get("title", "Untitled")
                        post_id = post.get("id")
                        post_date = post.get("post_date", "Unknown date")
                        published_list.append(
                            f"- {title} (ID: {post_id}, Published: {post_date})"
                        )

                    return [
                        TextContent(
                            type="text",
                            text=f"Found {len(published)} published posts:\n"
                            + "\n".join(published_list),
                        )
                    ]

                elif name == "get_post_analytics":
                    post_handler = PostHandler(client)
                    analytics = await post_handler.get_post_analytics(
                        arguments["post_id"]
                    )
                    open_rate_text = (
                        f"{analytics['open_rate'] * 100:.1f}%"
                        if analytics.get("open_rate") is not None
                        else "N/A"
                    )

                    lines = [
                        "📈 Post Analytics",
                        "=" * 50,
                        f"Title: {analytics['title']}",
                        f"ID: {analytics['id']}",
                    ]
                    if analytics.get("post_date"):
                        lines.append(f"Published: {analytics['post_date']}")
                    if analytics.get("email_sent_at"):
                        lines.append(f"Email sent: {analytics['email_sent_at']}")
                    lines.extend(
                        [
                            f"Views: {analytics['views']}",
                            f"Sent: {analytics['sent']}",
                            f"Delivered: {analytics['delivered']}",
                            f"Opened: {analytics['opened']}",
                            f"Open rate: {open_rate_text}",
                            f"Signups: {analytics['signups']}",
                            f"New subscribers: {analytics['subscribes']}",
                            f"Comments: {analytics['comment_count']}",
                            f"Reactions: {analytics['reaction_count']}",
                        ]
                    )
                    if analytics.get("estimated_value") is not None:
                        lines.append(f"Estimated value: {analytics['estimated_value']}")

                    return [TextContent(type="text", text="\n".join(lines))]

                elif name == "get_post_content":
                    logger.debug(
                        f"Creating PostHandler for get_post_content with client type: {type(client)}"
                    )
                    post_handler = PostHandler(client)
                    result = await post_handler.get_post_content(arguments["post_id"])

                    content_text = []
                    content_text.append("📄 Post Content")
                    content_text.append("=" * 50)
                    content_text.append(f"Title: {result['title']}")
                    if result["subtitle"]:
                        content_text.append(f"Subtitle: {result['subtitle']}")
                    content_text.append(f"Status: {result['status']}")
                    if result["publication_date"]:
                        content_text.append(f"Published: {result['publication_date']}")
                    content_text.append(f"Audience: {result['audience']}")
                    content_text.append("")
                    content_text.append("Content:")
                    content_text.append("-" * 50)
                    content_text.append(result["content"])

                    return [TextContent(type="text", text="\n".join(content_text))]

                elif name == "duplicate_post":
                    logger.debug(
                        f"Creating PostHandler for duplicate_post with client type: {type(client)}"
                    )
                    confirm = arguments.get("confirm_duplicate", False)
                    if confirm:
                        error = self._validate_confirmation_token(
                            name, arguments, "confirm_duplicate"
                        )
                        if error:
                            return [TextContent(type="text", text=error)]

                    if not confirm:
                        # Get the post details to show what will be duplicated
                        try:
                            post = client.get_draft(arguments["post_id"])
                            original_title = (
                                post.get("draft_title")
                                or post.get("title")
                                or "Untitled"
                            )
                            new_title = arguments.get(
                                "new_title", f"Copy of {original_title}"
                            )

                            token = self._issue_confirmation_token(
                                name, arguments, "confirm_duplicate"
                            )
                            return [
                                TextContent(
                                    type="text",
                                    text=self._confirmation_message(
                                        "⚠️ CONFIRMATION REQUIRED ⚠️",
                                        [
                                            "You are about to DUPLICATE this post:",
                                            f'- Original: "{original_title}"',
                                            f'- New draft title: "{new_title}"',
                                            "⚡ This will create a new draft with the same content.",
                                        ],
                                        "confirm_duplicate",
                                        token,
                                    ),
                                )
                            ]
                        except Exception as e:
                            return [
                                TextContent(
                                    type="text",
                                    text=f"⚠️ Error getting post details: {str(e)}\n\n"
                                    f"Cannot proceed with duplication without confirmation.",
                                )
                            ]

                    # Proceed with duplication
                    post_handler = PostHandler(client)
                    result = await post_handler.duplicate_post(
                        post_id=arguments["post_id"],
                        new_title=arguments.get("new_title"),
                    )
                    self._consume_confirmation_token(arguments["confirmation_token"])

                    return [
                        TextContent(
                            type="text",
                            text=f"✅ Post duplicated successfully!\n\n"
                            f"New draft ID: {result.get('id')}\n"
                            f"Title: {result.get('draft_title', 'Untitled')}",
                        )
                    ]

                elif name == "get_sections":
                    post_handler = PostHandler(client)
                    sections = await post_handler.get_sections()

                    if not sections:
                        return [
                            TextContent(
                                type="text",
                                text="No sections found in your publication.",
                            )
                        ]

                    section_list = []
                    section_list.append("📁 Available Sections:")
                    section_list.append("=" * 50)

                    for section in sections:
                        name = section.get("name", "Unnamed")
                        section_id = section.get("id")
                        description = section.get("description", "")

                        section_list.append(f"• {name} (ID: {section_id})")
                        if description:
                            section_list.append(f"  Description: {description}")

                    return [TextContent(type="text", text="\n".join(section_list))]

                elif name == "get_subscriber_count":
                    try:
                        post_handler = PostHandler(client)
                        result = await post_handler.get_subscriber_count()

                        if result.get("available"):
                            details = [
                                "📊 Subscriber Statistics",
                                f"{'=' * 50}",
                                f"Total Subscribers: {result['total_subscribers']:,}",
                                f"Publication: {result['publication_url']}",
                            ]
                            if result.get("source"):
                                details.append(f"Source: {result['source']}")
                            return [TextContent(type="text", text="\n".join(details))]

                        return [
                            TextContent(
                                type="text",
                                text=(
                                    "📊 Subscriber Statistics\n"
                                    f"{'=' * 50}\n"
                                    "Subscriber count is currently unavailable.\n"
                                    f"Publication: {result['publication_url']}\n"
                                    f"Reason: {result.get('reason') or 'Unknown'}\n"
                                    f"Checked Sources: {', '.join(result.get('checked_sources', [])) or 'none'}"
                                ),
                            )
                        ]
                    except ValueError as e:
                        return [TextContent(type="text", text=f"❌ {str(e)}")]
                    except Exception as e:
                        logger.error(
                            f"Unexpected error in get_subscriber_count: {str(e)}, type: {type(e)}"
                        )
                        return [
                            TextContent(
                                type="text",
                                text=f"❌ Failed to get subscriber count: {str(e)}",
                            )
                        ]

                elif name == "preview_draft":
                    try:
                        post_handler = PostHandler(client)
                        result = await post_handler.preview_draft(arguments["post_id"])

                        preview_text = []
                        preview_text.append("🔗 Preview Generated")
                        preview_text.append("=" * 50)
                        preview_text.append(f"Post ID: {result['post_id']}")

                        # Show the title if available
                        if result.get("title"):
                            preview_text.append(f"Title: {result['title']}")

                        # Show if it's published
                        if result.get("is_published"):
                            preview_text.append("Status: Published")
                        else:
                            preview_text.append("Status: Draft")

                        # Show the preview URL prominently
                        if result.get("preview_url"):
                            preview_text.append("")

                            # Show the URL on its own line for easy copying
                            if "/publish/post/" in result[
                                "preview_url"
                            ] and not result.get("is_published"):
                                preview_text.append("📋 AUTHOR-ONLY PREVIEW URL:")
                            elif result.get("is_published"):
                                preview_text.append("📋 PUBLISHED POST URL:")
                            else:
                                preview_text.append("📋 PREVIEW URL:")

                            preview_text.append("")
                            preview_text.append(result["preview_url"])
                            preview_text.append("")

                            # Add appropriate instructions
                            if "/publish/post/" in result[
                                "preview_url"
                            ] and not result.get("is_published"):
                                preview_text.append(
                                    "⚠️ This is an author-only preview link"
                                )
                                preview_text.append(
                                    "⚠️ You must be logged in as the author to view it"
                                )
                                preview_text.append(
                                    "⚠️ This link CANNOT be shared for feedback"
                                )
                                preview_text.append("")
                                preview_text.append(
                                    "ℹ️ Shareable preview links are not currently supported"
                                )
                            elif result.get("is_published"):
                                preview_text.append("ℹ️ This post is already published")
                                preview_text.append(
                                    "ℹ️ Anyone with this link can read it"
                                )
                        else:
                            preview_text.append("")
                            preview_text.append(
                                result.get(
                                    "message", "Preview generated but URL not available"
                                )
                            )

                        return [TextContent(type="text", text="\n".join(preview_text))]
                    except ValueError as e:
                        return [TextContent(type="text", text=f"❌ {str(e)}")]
                    except Exception as e:
                        logger.error(
                            f"Unexpected error in preview_draft: {str(e)}, type: {type(e)}"
                        )
                        return [
                            TextContent(
                                type="text",
                                text=f"❌ Failed to generate preview: {str(e)}",
                            )
                        ]

                elif name == "analyze_my_posts":
                    posts = await collect_account_posts(
                        client,
                        source=arguments.get("source", "published"),
                        limit=arguments.get("limit", 10),
                    )
                    analysis = self.strategy_handler.analyze_post_collection(posts)
                    lines = [
                        "📊 My Post Analysis",
                        "=" * 60,
                        f"Posts analyzed: {analysis['total_posts']}",
                        "",
                        "Themes:",
                    ]
                    lines.extend(
                        [
                            f"- {theme['theme']} ({theme['mentions']} mentions)"
                            for theme in analysis["themes"]
                        ]
                    )
                    lines.extend(["", "Title Patterns:"])
                    lines.extend(
                        [
                            f"- {item['pattern']} ({item['count']})"
                            for item in analysis["title_patterns"]
                        ]
                    )
                    lines.extend(["", "CTA Patterns:"])
                    lines.extend(
                        [
                            f"- {item['pattern']} ({item['count']})"
                            for item in analysis["cta_patterns"]
                        ]
                    )
                    lines.extend(["", "Recommended Focus:"])
                    lines.extend(
                        [f"- {item}" for item in analysis["recommended_focus"]]
                    )
                    return [TextContent(type="text", text="\n".join(lines).strip())]

                elif name == "generate_post_ideas":
                    my_posts_analysis: Dict[str, Any] = {"themes": []}
                    if arguments.get("include_my_posts", True):
                        my_posts = await collect_account_posts(
                            client, source="published", limit=10
                        )
                        my_posts_analysis = (
                            self.strategy_handler.analyze_post_collection(my_posts)
                        )
                    research = await self.research_handler.research_substack(
                        query=arguments["query"],
                        max_results=20,
                        deep_read_count=5,
                    )
                    ideas = self.strategy_handler.generate_post_ideas(
                        query=arguments["query"],
                        my_post_analysis=my_posts_analysis,
                        research_results=research,
                        count=arguments.get("count", 10),
                    )
                    lines = [
                        f"💡 Post Ideas: {arguments['query']}",
                        "=" * 60,
                    ]
                    for index, idea in enumerate(ideas, start=1):
                        lines.append(f"{index}. {idea['title']}")
                        lines.append(f"   Angle: {idea['angle']}")
                        lines.append(f"   Why now: {idea['why_now']}")
                        lines.append(f"   Hook: {idea['suggested_hook']}")
                    return [TextContent(type="text", text="\n".join(lines).strip())]

                elif name == "repurpose_post":
                    if arguments.get("post_id"):
                        post_handler = PostHandler(client)
                        post = await post_handler.get_post_content(arguments["post_id"])
                        title = post["title"]
                        content = post["content"]
                    else:
                        title = arguments.get("title")
                        content = arguments.get("content")
                    if not title or not content:
                        raise ValueError("Provide post_id or both title and content")
                    result = self.strategy_handler.repurpose_post(
                        title=title,
                        content=content,
                        target_format=arguments.get("target_format", "twitter_thread"),
                    )
                    return [
                        TextContent(
                            type="text",
                            text=f"♻️ Repurposed as {result['target_format']}\n"
                            f"{'=' * 60}\n{result['repurposed']}",
                        )
                    ]

                elif name == "content_gap_analysis":
                    my_posts = await collect_account_posts(
                        client, source="published", limit=arguments.get("limit", 10)
                    )
                    my_analysis = self.strategy_handler.analyze_post_collection(
                        my_posts
                    )
                    research = await self.research_handler.research_substack(
                        query=arguments["query"],
                        max_results=20,
                        deep_read_count=5,
                    )
                    gap = self.strategy_handler.content_gap_analysis(
                        my_analysis, research
                    )
                    lines = [
                        f"🕳️ Content Gap Analysis: {arguments['query']}",
                        "=" * 60,
                        "Shared Themes:",
                    ]
                    lines.extend([f"- {item}" for item in gap["shared_themes"]])
                    lines.extend(["", "Market-Only Themes:"])
                    lines.extend([f"- {item}" for item in gap["market_only_themes"]])
                    lines.extend(["", "Opportunities:"])
                    lines.extend([f"- {item}" for item in gap["opportunities"]])
                    return [TextContent(type="text", text="\n".join(lines).strip())]

                elif name == "title_and_hook_optimizer":
                    if arguments.get("post_id"):
                        post_handler = PostHandler(client)
                        post = await post_handler.get_post_content(arguments["post_id"])
                        title = post["title"]
                        content = post["content"]
                    else:
                        title = arguments.get("title")
                        content = arguments.get("content")
                    if not title or not content:
                        raise ValueError("Provide post_id or both title and content")
                    result = self.strategy_handler.optimize_title_and_hook(
                        title=title,
                        content=content,
                        count=arguments.get("count", 5),
                    )
                    lines = ["🎯 Title + Hook Options", "=" * 60, "Title Options:"]
                    lines.extend([f"- {item}" for item in result["title_options"]])
                    lines.extend(["", "Hook Options:"])
                    lines.extend([f"- {item}" for item in result["hook_options"]])
                    return [TextContent(type="text", text="\n".join(lines).strip())]

                else:
                    return [TextContent(type="text", text=f"Unknown tool: {name}")]

            except Exception as e:
                logger.error(f"Error executing tool {name}: {e}")
                return [TextContent(type="text", text=f"Error: {str(e)}")]

        self._dispatch_tool_names = self._build_dispatch_tool_names()
        self._listed_tool_names = self._dispatch_tool_names
        logger.info("Registered %s tools", len(self._listed_tool_names))

    async def run(self) -> None:
        """Run the MCP server using stdio transport"""
        logger.info("Starting MCP server...")
        async with stdio_server() as (read_stream, write_stream):
            logger.info("Stdio transport established")
            await self.server.run(
                read_stream,
                write_stream,
                InitializationOptions(
                    server_name="substack-mcp-plus",
                    server_version=SERVER_VERSION,
                    capabilities=self.server.get_capabilities(
                        NotificationOptions(),
                        experimental_capabilities={},
                    ),
                ),
            )
            logger.info("Server run completed")


def main() -> None:
    """Main entry point"""
    try:
        server = SubstackMCPServer()
        asyncio.run(server.run())
    except KeyboardInterrupt:
        logger.info("Server shutdown requested")
    except Exception as e:
        logger.error(f"Server error: {e}")
        raise


if __name__ == "__main__":
    main()
