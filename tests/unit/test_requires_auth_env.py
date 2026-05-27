# ABOUTME: Tests the auth-environment detection used for live Substack integration tests.
# ABOUTME: Ensures requires_auth gating only enables live tests when credentials are complete.

from tests.auth_env import has_substack_auth_env, has_substack_write_auth_env


def test_has_substack_auth_env_accepts_email_password_flow(monkeypatch):
    monkeypatch.setenv("SUBSTACK_PUBLICATION_URL", "https://example.substack.com")
    monkeypatch.setenv("SUBSTACK_EMAIL", "test@example.com")
    monkeypatch.setenv("SUBSTACK_PASSWORD", "secret")
    monkeypatch.delenv("SUBSTACK_SESSION_TOKEN", raising=False)

    assert has_substack_auth_env() is True


def test_has_substack_auth_env_accepts_session_token_flow(monkeypatch):
    monkeypatch.setenv("SUBSTACK_PUBLICATION_URL", "https://example.substack.com")
    monkeypatch.setenv("SUBSTACK_SESSION_TOKEN", "session-token")
    monkeypatch.delenv("SUBSTACK_EMAIL", raising=False)
    monkeypatch.delenv("SUBSTACK_PASSWORD", raising=False)

    assert has_substack_auth_env() is True


def test_has_substack_auth_env_rejects_partial_credentials(monkeypatch):
    monkeypatch.setenv("SUBSTACK_PUBLICATION_URL", "https://example.substack.com")
    monkeypatch.setenv("SUBSTACK_EMAIL", "test@example.com")
    monkeypatch.delenv("SUBSTACK_PASSWORD", raising=False)
    monkeypatch.delenv("SUBSTACK_SESSION_TOKEN", raising=False)

    assert has_substack_auth_env() is False


def test_has_substack_write_auth_env_requires_base_auth_and_opt_in(monkeypatch):
    monkeypatch.setenv("SUBSTACK_PUBLICATION_URL", "https://example.substack.com")
    monkeypatch.setenv("SUBSTACK_SESSION_TOKEN", "session-token")
    monkeypatch.delenv("SUBSTACK_EMAIL", raising=False)
    monkeypatch.delenv("SUBSTACK_PASSWORD", raising=False)
    monkeypatch.delenv("SUBSTACK_MCP_ENABLE_WRITE_TESTS", raising=False)

    assert has_substack_write_auth_env() is False

    monkeypatch.setenv("SUBSTACK_MCP_ENABLE_WRITE_TESTS", "true")
    assert has_substack_write_auth_env() is True


def test_has_substack_write_auth_env_rejects_opt_in_without_auth(monkeypatch):
    monkeypatch.delenv("SUBSTACK_PUBLICATION_URL", raising=False)
    monkeypatch.delenv("SUBSTACK_SESSION_TOKEN", raising=False)
    monkeypatch.delenv("SUBSTACK_EMAIL", raising=False)
    monkeypatch.delenv("SUBSTACK_PASSWORD", raising=False)
    monkeypatch.setenv("SUBSTACK_MCP_ENABLE_WRITE_TESTS", "1")

    assert has_substack_write_auth_env() is False
