# ABOUTME: Main MCP server implementation for Substack MCP Plus
# ABOUTME: Provides tools for creating, updating, publishing posts with rich formatting

import asyncio
import logging
import sys
from typing import Any, Dict, List, Optional

from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import EmbeddedResource, ImageContent, TextContent, Tool

from src.handlers.auth_handler import AuthHandler
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

    def __init__(self):
        """Initialize the MCP server"""
        self.server = Server("substack-mcp-plus")
        self._listed_tool_names: tuple[str, ...] = ()
        self._dispatch_tool_names: tuple[str, ...] = ()
        self._initialize_handlers()
        self._register_handlers()

    def _initialize_handlers(self):
        """Initialize handlers that do not require account authentication.

        MCP clients call `tools/list` before any credentials are available to the
        server process. If we require Substack auth during startup, the server
        exits before discovery and Codex sees `Tools: (none)`.
        """
        try:
            self.auth_handler: Optional[AuthHandler] = None
            self.research_handler = ResearchHandler()
            self.strategy_handler = StrategyHandler()
            logger.info("Non-auth handlers initialized; auth will be created lazily")
        except Exception as e:
            logger.error(f"Failed to initialize handlers: {e}")
            raise

    async def _get_authenticated_client(self):
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

    def _load_registered_tool_names(self, handle_list_tools) -> tuple[str, ...]:
        """Resolve the tool names from the registered list_tools handler."""
        loop = asyncio.new_event_loop()
        try:
            tools = loop.run_until_complete(handle_list_tools())
        finally:
            loop.close()
        return tuple(tool.name for tool in tools)

    def _register_handlers(self):
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
                    description="Schedule a draft post for future publication on Substack. IMPORTANT: You MUST ALWAYS ask the user to confirm scheduling in a follow-up message BEFORE calling this tool with confirm_schedule=true. Never set confirm_schedule=true on the first request.",
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
                    description="Upload an image file from your local computer to Substack's CDN and get a URL that can be used in posts. LIMITATION: Currently only supports uploading files from your local filesystem using a file path - cannot upload images directly from chat or clipboard. Supports common image formats (JPG, PNG, GIF, WebP). The returned URL can be used in markdown content as ![alt text](url).",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "image_path": {
                                "type": "string",
                                "description": "Full file path to the image file to upload. Must be a valid image file already saved on your local computer (e.g., /Users/you/Pictures/image.jpg). Cannot accept image data directly from chat.",
                            }
                        },
                        "required": ["image_path"],
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
                    description="Generate a preview link for a draft post that can be shared with others for feedback. The preview link allows others to read the draft without it being published.",
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
                    description="Extract coding or technical lessons from a research query or a specific public Substack URL.",
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
            client, source: str = "published", limit: int = 10
        ) -> List[Dict[str, Any]]:
            source = (source or "published").lower()
            limit = max(1, min(limit, 15))
            post_handler = PostHandler(client)

            if source == "drafts":
                raw_posts = await post_handler.list_drafts(limit=limit)
            elif source == "all":
                published = await post_handler.list_published(limit=max(1, limit // 2 or 1))
                drafts = await post_handler.list_drafts(limit=max(1, limit - len(published)))
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
                            "title": post.get("title") or post.get("draft_title") or "Untitled",
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
                    plan = self.strategy_handler.study_topic_on_substack(
                        arguments["topic"], research
                    )
                    lines = [
                        f"📚 Study Plan: {plan['topic']}",
                        "=" * 60,
                        "Themes to watch:",
                    ]
                    if plan["themes"]:
                        lines.extend(
                            [
                                f"- {theme['theme']} ({theme['mentions']} mentions)"
                                for theme in plan["themes"]
                            ]
                        )
                    else:
                        lines.append("- No strong recurring themes were found.")
                    lines.extend(["", "Suggested Reading Order:"])
                    if plan["study_order"]:
                        for item in plan["study_order"]:
                            lines.append(f"{item['step']}. {item['title']}")
                            lines.append(f"   URL: {item['url']}")
                            lines.append(f"   Why: {item['why']}")
                    else:
                        lines.append("- No recommended reading order yet.")
                    if plan.get("warnings"):
                        lines.extend(["", "Warnings:"])
                        lines.extend([f"- {warning}" for warning in plan["warnings"]])
                    lines.extend(["", f"Study Tip: {plan['study_tip']}"])
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
                    confirm = arguments.get("confirm_create", False)

                    if not confirm:
                        # Show preview of what will be created
                        content_preview = (
                            arguments["content"][:200] + "..."
                            if len(arguments["content"]) > 200
                            else arguments["content"]
                        )

                        return [
                            TextContent(
                                type="text",
                                text=f"⚠️ CONFIRMATION REQUIRED ⚠️\n\n"
                                f"You are about to CREATE a new draft:\n"
                                f"- Title: \"{arguments['title']}\"\n"
                                f"- Subtitle: \"{arguments.get('subtitle', '[none]')}\"\n"
                                f"- Content preview: {content_preview}\n\n"
                                f"⚡ This will create a new draft in your Substack account.\n\n"
                                f"Are you sure you want to create this draft?\n\n"
                                f'To confirm, simply say "yes" or tell me to proceed.\n'
                                f'To cancel, say "no" or tell me to stop.',
                            )
                        ]

                    # Proceed with creation
                    post_handler = PostHandler(client)
                    result = await post_handler.create_draft(
                        title=arguments["title"],
                        content=arguments["content"],
                        subtitle=arguments.get("subtitle"),
                        content_type="markdown",
                    )
                    return [
                        TextContent(
                            type="text",
                            text=f"✅ Draft created successfully!\nID: {result.get('id')}\nTitle: {arguments['title']}",
                        )
                    ]

                elif name == "update_post":
                    confirm = arguments.get("confirm_update", False)

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

                            return [
                                TextContent(
                                    type="text",
                                    text=f"⚠️ CONFIRMATION REQUIRED ⚠️\n\n"
                                    f"You are about to UPDATE this draft:\n"
                                    f'- Post: "{current_title}"\n'
                                    f"- Changes:\n{changes_text}\n\n"
                                    f"⚡ This will ONLY update the fields listed above.\n"
                                    f"⚡ Other fields (like content) will remain unchanged.\n\n"
                                    f"Are you sure you want to update this draft?\n\n"
                                    f'To confirm, simply say "yes" or tell me to proceed.\n'
                                    f'To cancel, say "no" or tell me to stop.',
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
                    return [
                        TextContent(
                            type="text",
                            text=f"✅ Post updated successfully!\nID: {arguments['post_id']}",
                        )
                    ]

                elif name == "publish_post":
                    confirm = arguments.get("confirm_publish", False)

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

                            return [
                                TextContent(
                                    type="text",
                                    text=f"⚠️ CONFIRMATION REQUIRED ⚠️\n\n"
                                    f"You are about to PUBLISH this draft:\n"
                                    f'- Post: "{title}"\n'
                                    f"{pub_info}\n"
                                    f"- Action: Publish immediately and send to all subscribers\n\n"
                                    f"⚡ This CANNOT be undone and will send emails to all subscribers.\n\n"
                                    f"Are you sure you want to publish this post?\n\n"
                                    f'To confirm, simply say "yes" or tell me to proceed.\n'
                                    f'To cancel, say "no" or tell me to stop.',
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
                    return [
                        TextContent(
                            type="text",
                            text=f"✅ Post published successfully!\nID: {arguments['post_id']}",
                        )
                    ]

                elif name == "schedule_post":
                    confirm = arguments.get("confirm_schedule", False)

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
                            email_audience = arguments.get(
                                "email_audience", "everyone"
                            )

                            return [
                                TextContent(
                                    type="text",
                                    text=f"⚠️ CONFIRMATION REQUIRED ⚠️\n\n"
                                    f"You are about to SCHEDULE this draft:\n"
                                    f'- Post: "{title}"\n'
                                    f"- Publish time: {scheduled_at}\n"
                                    f"- Access audience: {post_audience}\n"
                                    f"- Email audience: {email_audience}\n\n"
                                    f"⚡ This will queue the post for future publication.\n\n"
                                    f"Are you sure you want to schedule this post?\n\n"
                                    f'To confirm, simply say "yes" or tell me to proceed.\n'
                                    f'To cancel, say "no" or tell me to stop.',
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
                    result = await image_handler.upload_image(arguments["image_path"])
                    return [
                        TextContent(
                            type="text",
                            text=f"Image uploaded successfully!\nURL: {result['url']}",
                        )
                    ]

                elif name == "delete_draft":
                    post_id = arguments["post_id"]
                    confirm = arguments.get("confirm_delete", False)

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

                        return [
                            TextContent(
                                type="text",
                                text=f"⚠️ DELETION CONFIRMATION REQUIRED ⚠️\n\n"
                                f"You are about to permanently delete:\n"
                                f'📄 Title: "{title}"\n'
                                f"🆔 ID: {post_id}\n\n"
                                f"This action CANNOT be undone.\n\n"
                                f"Please confirm: Do you really want to delete this draft?\n"
                                f"Reply with 'yes' to proceed with deletion.",
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

                        # Delete the draft
                        client.delete_draft(post_id)

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
                        lines.append(
                            f"Estimated value: {analytics['estimated_value']}"
                        )

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

                            return [
                                TextContent(
                                    type="text",
                                    text=f"⚠️ CONFIRMATION REQUIRED ⚠️\n\n"
                                    f"You are about to DUPLICATE this post:\n"
                                    f'- Original: "{original_title}"\n'
                                    f'- New draft title: "{new_title}"\n\n'
                                    f"⚡ This will create a new draft with the same content.\n\n"
                                    f"Are you sure you want to duplicate this post?\n\n"
                                    f'To confirm, simply say "yes" or tell me to proceed.\n'
                                    f'To cancel, say "no" or tell me to stop.',
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
                    my_posts_analysis = {"themes": []}
                    if arguments.get("include_my_posts", True):
                        my_posts = await collect_account_posts(
                            client, source="published", limit=10
                        )
                        my_posts_analysis = self.strategy_handler.analyze_post_collection(
                            my_posts
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
                    my_analysis = self.strategy_handler.analyze_post_collection(my_posts)
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

        self._listed_tool_names = self._load_registered_tool_names(handle_list_tools)
        self._dispatch_tool_names = self._build_dispatch_tool_names()
        if set(self._listed_tool_names) != set(self._dispatch_tool_names):
            raise ValueError(
                "Tool registration drift detected between list_tools() and call_tool()"
            )
        logger.info("Registered %s tools", len(self._listed_tool_names))

    async def run(self):
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
                    capabilities={},
                ),
            )
            logger.info("Server run completed")


def main():
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
