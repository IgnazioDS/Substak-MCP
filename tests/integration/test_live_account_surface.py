# ABOUTME: Live authenticated smoke tests for the shipped MCP account surface.
# ABOUTME: Separates read-only account checks from opt-in write checks for release audits.

import time
from uuid import uuid4

import pytest

from src.handlers.auth_handler import AuthHandler
from src.handlers.post_handler import PostHandler


@pytest.mark.requires_auth
@pytest.mark.asyncio
async def test_live_account_read_only_surface_smoke():
    """Authenticate and exercise safe read-only account operations."""
    client = await AuthHandler().authenticate()
    post_handler = PostHandler(client)

    drafts = await post_handler.list_drafts(limit=5)
    published = await post_handler.list_published(limit=5)
    sections = await post_handler.get_sections()
    subscriber_stats = await post_handler.get_subscriber_count()

    assert isinstance(drafts, list)
    assert isinstance(published, list)
    assert isinstance(sections, list)
    assert isinstance(subscriber_stats, dict)
    assert "publication_url" in subscriber_stats


@pytest.mark.requires_auth_write
@pytest.mark.asyncio
async def test_live_account_create_preview_delete_smoke():
    """Create a disposable draft, verify preview generation, then delete it."""
    client = await AuthHandler().authenticate()
    post_handler = PostHandler(client)

    title = f"MCP Smoke Draft {int(time.time())}-{uuid4().hex[:8]}"
    created = await post_handler.create_draft(
        title=title,
        content="Smoke-test draft for release verification.",
        subtitle="Disposable smoke test",
        content_type="plain",
    )
    post_id = str(created["id"])

    try:
        preview = await post_handler.preview_draft(post_id)
        fetched = await post_handler.get_post(post_id)

        assert preview["post_id"] == post_id
        assert preview.get("preview_url")
        assert isinstance(fetched, dict)
    finally:
        client.delete_draft(post_id)
