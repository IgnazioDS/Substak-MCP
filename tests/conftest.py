# ABOUTME: Pytest hooks for repository-wide test behavior and live auth gating.
# ABOUTME: Skips requires_auth tests unless full Substack credentials are present.

import pytest

from src.handlers.auth_handler import AuthHandler
from tests.auth_env import has_substack_auth_env, has_substack_write_auth_env


def pytest_collection_modifyitems(config, items):
    """Skip live auth tests when the local environment has no credentials."""
    for item in items:
        if "requires_auth" in item.keywords and not has_substack_auth_env():
            item.add_marker(
                pytest.mark.skip(
                    reason="requires live Substack credentials in the environment"
                )
            )
        if "requires_auth_write" in item.keywords and not has_substack_write_auth_env():
            item.add_marker(
                pytest.mark.skip(
                    reason="requires live Substack credentials plus SUBSTACK_MCP_ENABLE_WRITE_TESTS"
                )
            )


@pytest.fixture(autouse=True)
def clear_auth_handler_cache():
    """Keep auth client caching from leaking state across tests."""
    AuthHandler._client_cache.clear()
    for cache_key in list(AuthHandler._cookie_client_resources):
        AuthHandler._cleanup_cookie_resource(cache_key)

    yield

    AuthHandler._client_cache.clear()
    for cache_key in list(AuthHandler._cookie_client_resources):
        AuthHandler._cleanup_cookie_resource(cache_key)
