# ABOUTME: Detects whether live Substack credentials are present for auth-required tests.
# ABOUTME: Keeps requires_auth integration tests out of default local runs without secrets.

import os


def has_substack_auth_env() -> bool:
    """Return True when the environment can run live auth tests."""
    publication_url = os.getenv("SUBSTACK_PUBLICATION_URL")
    session_token = os.getenv("SUBSTACK_SESSION_TOKEN")
    email = os.getenv("SUBSTACK_EMAIL")
    password = os.getenv("SUBSTACK_PASSWORD")

    has_session_flow = bool(publication_url and session_token)
    has_password_flow = bool(publication_url and email and password)
    return has_session_flow or has_password_flow


def has_substack_write_auth_env() -> bool:
    """Return True when live write tests are explicitly enabled."""
    opt_in = os.getenv("SUBSTACK_MCP_ENABLE_WRITE_TESTS", "").strip().lower()
    return has_substack_auth_env() and opt_in in {"1", "true", "yes", "on"}
