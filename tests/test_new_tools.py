# ABOUTME: Test file for the 6 new Substack MCP tools
# ABOUTME: Tests get_post_content, duplicate_post, get_sections, get_subscriber_count, preview_draft

import asyncio
import json
from datetime import datetime, timedelta, timezone
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from substack.post import Post

# Import the handlers we need to test
from src.handlers.post_handler import PostHandler
from src.utils.api_wrapper import SubstackAPIError


class TestNewTools:
    """Test suite for the 6 new Substack MCP tools - TDD approach"""

    @pytest.fixture
    def mock_client(self):
        """Create a mock Substack client"""
        client = Mock()
        client.get_user_id.return_value = 123456  # User ID must be numeric
        client.publication_url = "https://test.substack.com"
        return client

    @pytest.fixture
    def post_handler(self, mock_client):
        """Create a PostHandler instance with mock client"""
        return PostHandler(mock_client)

    @pytest.mark.asyncio
    async def test_get_post_content_published(self, post_handler, mock_client):
        """Test get_post_content tool with published post"""
        # Mock response data
        mock_post = {
            "id": "post-123",
            "title": "Test Post Title",
            "subtitle": "Test subtitle",
            "post_date": "2024-01-15T10:00:00Z",
            "audience": "everyone",
            "body": {
                "blocks": [
                    {
                        "type": "heading-one",
                        "content": [{"type": "text", "content": "Main Heading"}],
                    },
                    {
                        "type": "paragraph",
                        "content": [
                            {"type": "text", "content": "This is a test paragraph."}
                        ],
                    },
                    {"type": "code", "content": "print('Hello World')"},
                ]
            },
        }

        mock_client.get_draft.return_value = mock_post

        # Call the method
        result = await post_handler.get_post_content("post-123")

        # Verify the result
        assert result["id"] == "post-123"
        assert result["title"] == "Test Post Title"
        assert result["subtitle"] == "Test subtitle"
        assert result["status"] == "published"
        assert "# Main Heading" in result["content"]
        assert "This is a test paragraph." in result["content"]
        assert "print('Hello World')" in result["content"]

        # Verify client was called
        mock_client.get_draft.assert_called_once_with("post-123")

    @pytest.mark.asyncio
    async def test_get_post_content_draft(self, post_handler, mock_client):
        """Test get_post_content tool with draft post"""
        # Mock draft data (no post_date means it's a draft)
        mock_draft = {
            "id": "draft-456",
            "draft_title": "Draft Post Title",
            "draft_subtitle": "Draft subtitle",
            "audience": "only_paid",
            "draft_body": {
                "blocks": [
                    {
                        "type": "paragraph",
                        "content": [
                            {"type": "text", "content": "Draft content with "},
                            {
                                "type": "text",
                                "content": "bold text",
                                "marks": [{"type": "strong"}],
                            },
                            {"type": "text", "content": " and "},
                            {
                                "type": "text",
                                "content": "italic",
                                "marks": [{"type": "em"}],
                            },
                        ],
                    },
                    {"type": "paywall"},
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "content": "Premium content"}],
                    },
                ]
            },
        }

        mock_client.get_draft.return_value = mock_draft

        # Call the method
        result = await post_handler.get_post_content("draft-456")

        # Verify the result
        assert result["id"] == "draft-456"
        assert result["title"] == "Draft Post Title"
        assert result["subtitle"] == "Draft subtitle"
        assert result["status"] == "draft"
        assert result["audience"] == "only_paid"
        assert "Draft content with **bold text** and *italic*" in result["content"]
        assert "<!-- PAYWALL -->" in result["content"]
        assert "Premium content" in result["content"]

    @pytest.mark.asyncio
    async def test_get_post_content_with_complex_formatting(
        self, post_handler, mock_client
    ):
        """Test get_post_content with complex formatting"""
        mock_post = {
            "id": "complex-789",
            "title": "Complex Post",
            "body": {
                "blocks": [
                    {
                        "type": "heading-two",
                        "content": [{"type": "text", "content": "Section Header"}],
                    },
                    {
                        "type": "bulleted-list",
                        "content": [
                            {
                                "content": [
                                    {
                                        "type": "paragraph",
                                        "content": [
                                            {"type": "text", "content": "First item"}
                                        ],
                                    }
                                ]
                            },
                            {
                                "content": [
                                    {
                                        "type": "paragraph",
                                        "content": [
                                            {"type": "text", "content": "Second item"}
                                        ],
                                    }
                                ]
                            },
                        ],
                    },
                    {
                        "type": "ordered-list",
                        "content": [
                            {
                                "content": [
                                    {
                                        "type": "paragraph",
                                        "content": [
                                            {"type": "text", "content": "Step one"}
                                        ],
                                    }
                                ]
                            },
                            {
                                "content": [
                                    {
                                        "type": "paragraph",
                                        "content": [
                                            {"type": "text", "content": "Step two"}
                                        ],
                                    }
                                ]
                            },
                        ],
                    },
                    {
                        "type": "blockquote",
                        "content": [{"type": "text", "content": "Important quote"}],
                    },
                    {"type": "hr"},
                    {
                        "type": "captioned-image",
                        "src": "https://example.com/image.jpg",
                        "alt": "Test image",
                        "caption": "Image caption",
                    },
                ]
            },
        }

        mock_client.get_draft.return_value = mock_post

        result = await post_handler.get_post_content("complex-789")

        # Verify all formatting is preserved
        assert "## Section Header" in result["content"]
        assert "• First item" in result["content"]
        assert "• Second item" in result["content"]
        assert "1. Step one" in result["content"]
        assert "2. Step two" in result["content"]
        assert "> Important quote" in result["content"]
        assert "---" in result["content"]
        assert "![Test image](https://example.com/image.jpg)" in result["content"]
        assert "*Image caption*" in result["content"]

    @pytest.mark.asyncio
    async def test_duplicate_post_default_title(self, post_handler, mock_client):
        """Test duplicate_post tool with default title"""
        # Mock original post
        mock_original = {
            "id": "original-123",
            "title": "Original Post",
            "subtitle": "Original subtitle",
            "audience": "only_paid",
            "body": {
                "blocks": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "content": "Original content"}],
                    }
                ]
            },
        }

        mock_client.get_draft.return_value = mock_original
        mock_client.post_draft.return_value = {
            "id": "copy-456",
            "draft_title": "Copy of Original Post",
        }

        # Call without custom title
        result = await post_handler.duplicate_post("original-123")

        assert result["id"] == "copy-456"
        assert result["draft_title"] == "Copy of Original Post"

        # Verify post_draft was called with correct data
        mock_client.post_draft.assert_called_once()
        call_args = mock_client.post_draft.call_args[0][0]
        assert "Copy of Original Post" in str(
            call_args
        )  # Title should contain "Copy of"

    @pytest.mark.asyncio
    async def test_duplicate_post_custom_title(self, post_handler, mock_client):
        """Test duplicate_post tool with custom title"""
        # Mock original post
        mock_original = {
            "id": "original-123",
            "title": "Original Post",
            "subtitle": "Original subtitle",
            "audience": "everyone",
            "body": {
                "blocks": [
                    {
                        "type": "heading-one",
                        "content": [{"type": "text", "content": "Header"}],
                    },
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "content": "Content"}],
                    },
                ]
            },
        }

        mock_client.get_draft.return_value = mock_original
        mock_client.post_draft.return_value = {
            "id": "custom-789",
            "draft_title": "My Custom Title",
        }

        # Call with custom title
        result = await post_handler.duplicate_post("original-123", "My Custom Title")

        assert result["id"] == "custom-789"
        assert result["draft_title"] == "My Custom Title"

        # Verify the custom title was used
        call_args = mock_client.post_draft.call_args[0][0]
        assert "My Custom Title" in str(call_args)

    @pytest.mark.asyncio
    async def test_duplicate_post_preserves_all_content(
        self, post_handler, mock_client
    ):
        """Test duplicate_post preserves all content and settings"""
        # Mock complex original post
        mock_original = {
            "id": "complex-original",
            "title": "Complex Post",
            "subtitle": "With lots of formatting",
            "audience": "only_paid",
            "body": {
                "blocks": [
                    {
                        "type": "heading-one",
                        "content": [{"type": "text", "content": "Main Title"}],
                    },
                    {
                        "type": "paragraph",
                        "content": [
                            {"type": "text", "content": "Text with "},
                            {
                                "type": "text",
                                "content": "bold",
                                "marks": [{"type": "strong"}],
                            },
                            {"type": "text", "content": " and "},
                            {
                                "type": "text",
                                "content": "links",
                                "marks": [
                                    {"type": "link", "href": "https://example.com"}
                                ],
                            },
                        ],
                    },
                    {"type": "paywall"},
                    {"type": "code", "content": "def hello():\n    print('world')"},
                    {
                        "type": "captioned-image",
                        "src": "image.jpg",
                        "alt": "Alt",
                        "caption": "Caption",
                    },
                ]
            },
        }

        mock_client.get_draft.return_value = mock_original
        mock_client.post_draft.return_value = {
            "id": "dup-123",
            "draft_title": "Copy of Complex Post",
        }

        # Duplicate the post
        result = await post_handler.duplicate_post("complex-original")

        # Verify the post_draft call preserved all content
        call_args = mock_client.post_draft.call_args[0][0]

        # The call_args is a JSON string from Post.get_draft()
        # We need to parse it or just verify it contains expected content
        call_args_str = str(call_args)
        assert "Copy of Complex Post" in call_args_str
        assert "With lots of formatting" in call_args_str
        assert "Main Title" in call_args_str
        assert "bold" in call_args_str
        assert "paywall" in call_args_str

    @pytest.mark.asyncio
    async def test_get_sections_with_data(self, post_handler, mock_client):
        """Test get_sections tool with multiple sections"""
        # Mock sections data
        mock_sections = [
            {"id": "section-1", "name": "Tech", "description": "Technology posts"},
            {"id": "section-2", "name": "Life", "description": "Personal stories"},
            {"id": "section-3", "name": "Business", "description": ""},
        ]

        mock_client.get_sections.return_value = mock_sections

        # Call the method
        result = await post_handler.get_sections()

        # Verify
        assert len(result) == 3
        assert result[0]["name"] == "Tech"
        assert result[0]["description"] == "Technology posts"
        assert result[1]["name"] == "Life"
        assert result[2]["name"] == "Business"
        assert result[2]["description"] == ""  # Empty description
        mock_client.get_sections.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_sections_empty(self, post_handler, mock_client):
        """Test get_sections when no sections exist"""
        # Mock empty sections
        mock_client.get_sections.return_value = []

        # Call the method
        result = await post_handler.get_sections()

        # Verify
        assert result == []
        mock_client.get_sections.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_sections_none_response(self, post_handler, mock_client):
        """Test get_sections when API returns None"""
        # Mock None response
        mock_client.get_sections.return_value = None

        # Call the method
        result = await post_handler.get_sections()

        # Verify it returns empty list
        assert result == []
        mock_client.get_sections.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_subscriber_count(self, post_handler, mock_client):
        """Test get_subscriber_count tool"""
        # Mock subscriber count
        mock_client.get_publication_subscriber_stats.return_value = {
            "available": True,
            "total_subscribers": 12345,
            "source": "python_substack",
            "checked_sources": ["python_substack"],
        }

        # Call the method
        result = await post_handler.get_subscriber_count()

        # Verify
        assert result["total_subscribers"] == 12345
        assert result["available"] is True
        assert result["source"] == "python_substack"
        assert result["publication_url"] == "https://test.substack.com"
        mock_client.get_publication_subscriber_stats.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_subscriber_count_zero(self, post_handler, mock_client):
        """Test get_subscriber_count with zero subscribers"""
        # Mock zero subscribers
        mock_client.get_publication_subscriber_stats.return_value = {
            "available": True,
            "total_subscribers": 0,
            "source": "python_substack",
            "checked_sources": ["python_substack"],
        }

        # Call the method
        result = await post_handler.get_subscriber_count()

        # Verify
        assert result["total_subscribers"] == 0
        assert result["available"] is True
        assert result["publication_url"] == "https://test.substack.com"

    @pytest.mark.asyncio
    async def test_get_subscriber_count_large_number(self, post_handler, mock_client):
        """Test get_subscriber_count with large number"""
        # Mock large subscriber count
        mock_client.get_publication_subscriber_stats.return_value = {
            "available": True,
            "total_subscribers": 1000000,
            "source": "publication_page",
            "checked_sources": ["python_substack", "publication_page"],
        }

        # Call the method
        result = await post_handler.get_subscriber_count()

        # Verify
        assert result["total_subscribers"] == 1000000
        assert result["publication_url"] == "https://test.substack.com"
        assert result["source"] == "publication_page"

    @pytest.mark.asyncio
    async def test_get_subscriber_count_unavailable_is_structured(
        self, post_handler, mock_client
    ):
        """Test get_subscriber_count when count is unavailable anywhere"""
        mock_client.get_publication_subscriber_stats.return_value = {
            "available": False,
            "total_subscribers": None,
            "source": None,
            "checked_sources": ["python_substack", "publication_page", "sections"],
            "reason": "Subscriber count was not exposed in publication metadata, page markup, or section summaries.",
        }

        result = await post_handler.get_subscriber_count()

        assert result["available"] is False
        assert result["total_subscribers"] is None
        assert "publication metadata" in result["reason"]

    @pytest.mark.asyncio
    async def test_get_subscriber_count_wraps_generic_errors(
        self, post_handler, mock_client
    ):
        """Test get_subscriber_count wraps unexpected errors."""
        mock_client.get_publication_subscriber_stats.side_effect = RuntimeError(
            "service unavailable"
        )

        with pytest.raises(
            SubstackAPIError,
            match="Failed to get subscriber count: service unavailable",
        ):
            await post_handler.get_subscriber_count()

    @pytest.mark.asyncio
    async def test_get_subscriber_count_reraises_api_errors(
        self, post_handler, mock_client
    ):
        """Test get_subscriber_count preserves API wrapper errors."""
        mock_client.get_publication_subscriber_stats.side_effect = SubstackAPIError(
            "upstream said no"
        )

        with pytest.raises(SubstackAPIError, match="upstream said no"):
            await post_handler.get_subscriber_count()

    @pytest.mark.asyncio
    async def test_preview_draft(self, post_handler, mock_client):
        """Test preview_draft tool with draft post"""
        # Mock draft data
        mock_draft = {
            "id": "post-123",
            "draft_title": "Test Draft",
            "slug": "test-draft",
            "post_date": None,  # Not published
            "published": False,
        }

        mock_client.get_draft.return_value = mock_draft

        # Call the method
        result = await post_handler.preview_draft("post-123")

        # Verify
        assert result["post_id"] == "post-123"
        assert result["title"] == "Test Draft"
        assert result["is_published"] is False
        assert "/publish/post/post-123" in result["preview_url"]
        assert "back=%2Fpublish%2Fposts%2Fdrafts" in result["preview_url"]
        assert "Author-only preview link" in result["message"]
        assert "not shareable" in result["message"]
        mock_client.get_draft.assert_called_once_with("post-123")

    @pytest.mark.asyncio
    async def test_preview_draft_minimal_data(self, post_handler, mock_client):
        """Test preview_draft with no slug (fallback to edit URL)"""
        # Mock draft with no slug
        mock_draft = {
            "id": "draft-456",
            "draft_title": "Draft Without Slug",
            "slug": None,
            "draft_slug": None,
            "post_date": None,
        }

        mock_client.get_draft.return_value = mock_draft
        mock_client.prepublish_draft.return_value = {}  # No slug from prepublish either

        # Call the method
        result = await post_handler.preview_draft("draft-456")

        # Verify it still generates author-only URL using post ID
        assert result["post_id"] == "draft-456"
        assert "/publish/post/draft-456" in result["preview_url"]
        assert "back=%2Fpublish%2Fposts%2Fdrafts" in result["preview_url"]
        assert "Author-only preview link" in result["message"]

    @pytest.mark.asyncio
    async def test_preview_draft_with_url_in_response(self, post_handler, mock_client):
        """Test preview_draft with published post (no draft_id parameter)"""
        # Mock published post
        mock_post = {
            "id": "post-789",
            "title": "Published Post",
            "slug": "published-post",
            "post_date": "2024-01-01T00:00:00Z",  # Published
            "published": True,
        }

        mock_client.get_draft.return_value = mock_post

        # Call the method
        result = await post_handler.preview_draft("post-789")

        # Verify published URL (no preview parameters)
        assert result["post_id"] == "post-789"
        assert result["title"] == "Published Post"
        assert result["is_published"] is True
        assert "?postPreview=" not in result["preview_url"]
        assert result["preview_url"] == "https://test.substack.com/p/published-post"
        assert "Published post link" in result["message"]

    @pytest.mark.asyncio
    async def test_preview_draft_uses_shareable_preview_url_when_available(
        self, post_handler, mock_client
    ):
        """Test preview_draft prefers shareable preview links from prepublish data."""
        mock_client.get_draft.return_value = {
            "id": "draft-shareable",
            "draft_title": "Shareable Draft",
            "draft_slug": "shareable-draft",
            "post_date": None,
        }
        mock_client.prepublish_draft.return_value = {
            "preview_url": "https://test.substack.com/p/shareable-draft?postPreview=abc123"
        }

        result = await post_handler.preview_draft("draft-shareable")

        assert "?postPreview=abc123" in result["preview_url"]
        assert "share for feedback" in result["message"]

    @pytest.mark.asyncio
    async def test_preview_draft_rejects_invalid_draft_response(
        self, post_handler, mock_client
    ):
        """Test preview_draft fails fast on invalid draft payloads."""
        mock_client.get_draft.return_value = "draft"

        with pytest.raises(
            ValueError,
            match="Failed to generate preview for post broken: Invalid draft response",
        ):
            await post_handler.preview_draft("broken")

    # Additional edge case tests

    @pytest.mark.asyncio
    async def test_get_post_content_missing_fields(self, post_handler, mock_client):
        """Test get_post_content with missing optional fields"""
        # Mock post with minimal fields
        mock_post = {
            "id": "minimal-123",
            "draft_title": "Minimal Post",
            # No subtitle, no body, no audience
        }

        mock_client.get_draft.return_value = mock_post

        result = await post_handler.get_post_content("minimal-123")

        assert result["id"] == "minimal-123"
        assert result["title"] == "Minimal Post"
        assert result["subtitle"] == ""
        assert result["content"] == ""  # Empty content when no body
        assert result["audience"] == "everyone"  # Default audience

    @pytest.mark.asyncio
    async def test_duplicate_post_with_draft_fields(self, post_handler, mock_client):
        """Test duplicate_post when original has draft_ prefixed fields"""
        # Mock draft with draft_ prefixed fields
        mock_draft = {
            "id": "draft-original",
            "draft_title": "Draft Title",
            "draft_subtitle": "Draft Subtitle",
            "audience": "only_paid",
            "draft_body": {
                "blocks": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "content": "Draft content"}],
                    }
                ]
            },
        }

        mock_client.get_draft.return_value = mock_draft
        mock_client.post_draft.return_value = {
            "id": "copy-123",
            "draft_title": "Copy of Draft Title",
        }

        result = await post_handler.duplicate_post("draft-original")

        assert result["id"] == "copy-123"
        # Verify it correctly extracted draft fields
        call_args = mock_client.post_draft.call_args[0][0]
        assert "Copy of Draft Title" in str(call_args)

    @pytest.mark.asyncio
    async def test_get_post_content_with_links(self, post_handler, mock_client):
        """Test get_post_content correctly formats links"""
        mock_post = {
            "id": "link-post",
            "title": "Post with Links",
            "body": {
                "blocks": [
                    {
                        "type": "paragraph",
                        "content": [
                            {"type": "text", "content": "Check out "},
                            {
                                "type": "text",
                                "content": "this link",
                                "marks": [
                                    {"type": "link", "href": "https://example.com"}
                                ],
                            },
                            {"type": "text", "content": " and "},
                            {
                                "type": "text",
                                "content": "another one",
                                "marks": [{"type": "link", "href": "https://test.com"}],
                            },
                        ],
                    }
                ]
            },
        }

        mock_client.get_draft.return_value = mock_post

        result = await post_handler.get_post_content("link-post")

        assert "[this link](https://example.com)" in result["content"]
        assert "[another one](https://test.com)" in result["content"]

    @pytest.mark.asyncio
    async def test_get_post_content_with_code_inline(self, post_handler, mock_client):
        """Test get_post_content with inline code"""
        mock_post = {
            "id": "code-post",
            "title": "Code Post",
            "body": {
                "blocks": [
                    {
                        "type": "paragraph",
                        "content": [
                            {"type": "text", "content": "Use "},
                            {
                                "type": "text",
                                "content": "print('hello')",
                                "marks": [{"type": "code"}],
                            },
                            {"type": "text", "content": " to output text"},
                        ],
                    }
                ]
            },
        }

        mock_client.get_draft.return_value = mock_post

        result = await post_handler.get_post_content("code-post")

        assert "`print('hello')`" in result["content"]

    @pytest.mark.asyncio
    async def test_get_post_rejects_non_dict_response(self, post_handler, mock_client):
        """Test get_post rejects non-dictionary API responses."""
        mock_client.get_draft.return_value = "not-a-dict"

        with pytest.raises(
            ValueError, match="Post lookup response was not a dictionary"
        ):
            await post_handler.get_post("post-bad")

    def test_extract_readable_content_handles_json_and_plain_text_fallbacks(
        self, post_handler
    ):
        """Test _extract_readable_content across JSON string formats and invalid bodies."""
        doc_body = json.dumps(
            {
                "type": "doc",
                "content": [
                    {
                        "type": "heading",
                        "attrs": {"level": 2},
                        "content": [{"type": "text", "text": "Section"}],
                    },
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": "Body copy"}],
                    },
                ],
            }
        )

        plain_text = post_handler._extract_readable_content({"draft_body": "raw text"})
        from_doc = post_handler._extract_readable_content({"draft_body": doc_body})
        non_dict = post_handler._extract_readable_content({"draft_body": 123})

        assert plain_text == "raw text"
        assert "## Section" in from_doc
        assert "Body copy" in from_doc
        assert non_dict == ""

    def test_extract_readable_content_handles_nested_lists_and_images(
        self, post_handler
    ):
        """Test _extract_readable_content for list_item and attrs-based image structures."""
        body = {
            "body": {
                "blocks": [
                    {
                        "type": "bullet_list",
                        "content": [
                            {
                                "type": "list_item",
                                "content": [
                                    {
                                        "type": "paragraph",
                                        "content": [
                                            {"type": "text", "text": "Nested bullet"}
                                        ],
                                    }
                                ],
                            }
                        ],
                    },
                    {"type": "ordered-list", "content": [{"text": "Ordered entry"}]},
                    {
                        "type": "captionedImage",
                        "content": {
                            "attrs": {
                                "src": "https://example.com/img.jpg",
                                "alt": "Nested image",
                            }
                        },
                    },
                ]
            }
        }

        content = post_handler._extract_readable_content(body)

        assert "• Nested bullet" in content
        assert "1. Ordered entry" in content
        assert "![Nested image](https://example.com/img.jpg)" in content

    def test_clean_publication_url_removes_api_suffixes(self, post_handler):
        """Test publication URL cleanup for API-style URLs."""
        assert (
            post_handler._clean_publication_url("https://test.substack.com/api/v1/")
            == "https://test.substack.com"
        )
        assert (
            post_handler._clean_publication_url("https://test.substack.com/api/v1")
            == "https://test.substack.com"
        )


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])
