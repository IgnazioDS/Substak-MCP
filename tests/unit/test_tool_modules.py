# ABOUTME: Unit tests for the thin MCP tool wrapper classes in src/tools.
# ABOUTME: Verifies metadata, validation, and delegation to the server post_handler.

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.tools.create_formatted_post import CreateFormattedPostTool
from src.tools.list_drafts import ListDraftsTool
from src.tools.publish_post import PublishPostTool
from src.tools.update_post import UpdatePostTool


@pytest.fixture
def mock_server():
    return SimpleNamespace(post_handler=SimpleNamespace())


@pytest.mark.asyncio
async def test_create_formatted_post_tool_executes_with_defaults(mock_server):
    mock_server.post_handler.create_draft = AsyncMock(
        return_value={
            "id": "draft-1",
            "title": "Title",
            "subtitle": "Subtitle",
            "url": "https://example.com/draft-1",
        }
    )
    tool = CreateFormattedPostTool(mock_server)

    result = await tool.execute({"title": "Title", "content": "Hello"})

    mock_server.post_handler.create_draft.assert_awaited_once_with(
        title="Title",
        content="Hello",
        subtitle=None,
        content_type="markdown",
    )
    assert result["success"] is True
    assert result["post_id"] == "draft-1"
    assert result["message"] == "Successfully created draft post: Title"


@pytest.mark.asyncio
async def test_create_formatted_post_tool_requires_title_and_content(mock_server):
    tool = CreateFormattedPostTool(mock_server)

    with pytest.raises(ValueError, match="Title and content are required"):
        await tool.execute({"title": "Only title"})


@pytest.mark.asyncio
async def test_list_drafts_tool_formats_response(mock_server):
    mock_server.post_handler.list_drafts = AsyncMock(
        return_value=[
            {
                "id": "draft-1",
                "title": "First",
                "subtitle": "One",
                "created_at": "2026-01-01",
                "updated_at": "2026-01-02",
                "word_count": 120,
                "url": "https://example.com/draft-1",
                "extra": "ignored",
            }
        ]
    )
    tool = ListDraftsTool(mock_server)

    result = await tool.execute({"limit": 5})

    mock_server.post_handler.list_drafts.assert_awaited_once_with(limit=5)
    assert result == {
        "success": True,
        "drafts": [
            {
                "id": "draft-1",
                "title": "First",
                "subtitle": "One",
                "created_at": "2026-01-01",
                "updated_at": "2026-01-02",
                "word_count": 120,
                "url": "https://example.com/draft-1",
            }
        ],
        "count": 1,
        "message": "Found 1 draft(s)",
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("limit", ["5", 0, 51])
async def test_list_drafts_tool_validates_limit(mock_server, limit):
    tool = ListDraftsTool(mock_server)

    with pytest.raises(ValueError, match="limit must be an integer between 1 and 50"):
        await tool.execute({"limit": limit})


@pytest.mark.asyncio
async def test_publish_post_tool_executes(mock_server):
    mock_server.post_handler.publish_draft = AsyncMock(
        return_value={
            "id": "draft-1",
            "published": True,
            "url": "https://example.com/p/post",
        }
    )
    tool = PublishPostTool(mock_server)

    result = await tool.execute({"post_id": "draft-1"})

    mock_server.post_handler.publish_draft.assert_awaited_once_with(post_id="draft-1")
    assert result["success"] is True
    assert result["post_id"] == "draft-1"
    assert result["message"] == "Successfully published post draft-1"


@pytest.mark.asyncio
async def test_publish_post_tool_requires_post_id(mock_server):
    tool = PublishPostTool(mock_server)

    with pytest.raises(ValueError, match="post_id is required"):
        await tool.execute({})


@pytest.mark.asyncio
async def test_update_post_tool_executes(mock_server):
    mock_server.post_handler.update_draft = AsyncMock(
        return_value={
            "id": "draft-1",
            "title": "Updated",
            "subtitle": "Sub",
            "url": "https://example.com/draft-1",
        }
    )
    tool = UpdatePostTool(mock_server)

    result = await tool.execute(
        {
            "post_id": "draft-1",
            "title": "Updated",
            "content": "New body",
            "subtitle": "Sub",
            "content_type": "html",
        }
    )

    mock_server.post_handler.update_draft.assert_awaited_once_with(
        post_id="draft-1",
        title="Updated",
        content="New body",
        subtitle="Sub",
        content_type="html",
    )
    assert result["success"] is True
    assert result["post_id"] == "draft-1"
    assert result["message"] == "Successfully updated post: draft-1"


@pytest.mark.asyncio
async def test_update_post_tool_requires_at_least_one_change(mock_server):
    tool = UpdatePostTool(mock_server)

    with pytest.raises(
        ValueError, match="At least one of title, content, or subtitle must be provided"
    ):
        await tool.execute({"post_id": "draft-1"})


@pytest.mark.asyncio
async def test_update_post_tool_requires_post_id(mock_server):
    tool = UpdatePostTool(mock_server)

    with pytest.raises(ValueError, match="post_id is required"):
        await tool.execute({"title": "Updated"})
