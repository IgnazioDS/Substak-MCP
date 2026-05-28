# ABOUTME: Unit tests for AuthHandler class that manages Substack authentication
# ABOUTME: Tests both email/password and session token authentication methods

import pytest
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch, AsyncMock
from src.handlers.auth_handler import AuthHandler
from src.utils.api_wrapper import APIWrapper


class TestAuthHandler:
    """Test suite for AuthHandler class"""

    def setup_method(self):
        """Set up test fixtures"""
        self._temp_home = tempfile.TemporaryDirectory()
        self._home_patcher = patch(
            "src.simple_auth_manager.Path.home",
            return_value=Path(self._temp_home.name),
        )
        self._home_patcher.start()
        AuthHandler._client_cache.clear()

        # Clear any existing env vars
        for key in [
            "SUBSTACK_EMAIL",
            "SUBSTACK_PASSWORD",
            "SUBSTACK_SESSION_TOKEN",
            "SUBSTACK_PUBLICATION_URL",
        ]:
            if key in os.environ:
                del os.environ[key]

    def teardown_method(self):
        """Clean up test fixtures"""
        self._home_patcher.stop()
        self._temp_home.cleanup()
        AuthHandler._client_cache.clear()
        AuthHandler._cookie_client_resources.clear()

    def test_init_with_email_password(self):
        """Test initialization with email and password"""
        with patch.dict(
            os.environ,
            {
                "SUBSTACK_EMAIL": "test@example.com",
                "SUBSTACK_PASSWORD": "testpass123",
                "SUBSTACK_PUBLICATION_URL": "https://test.substack.com",
            },
        ):
            handler = AuthHandler()
            assert handler.email == "test@example.com"
            assert handler.password == "testpass123"
            assert handler.publication_url == "https://test.substack.com"
            assert handler.env_session_token is None

    def test_init_with_session_token(self):
        """Test initialization with session token"""
        with patch.dict(
            os.environ,
            {
                "SUBSTACK_SESSION_TOKEN": "test-session-token",
                "SUBSTACK_PUBLICATION_URL": "https://test.substack.com",
            },
        ):
            handler = AuthHandler()
            assert handler.email is None
            assert handler.password is None
            assert handler.env_session_token == "test-session-token"
            assert handler.publication_url == "https://test.substack.com"

    def test_init_missing_credentials(self):
        """Test initialization with missing credentials raises error"""
        with patch.dict(
            os.environ, {"SUBSTACK_PUBLICATION_URL": "https://test.substack.com"}
        ):
            with pytest.raises(ValueError, match="No authentication found"):
                AuthHandler()

    def test_init_missing_publication_url(self):
        """Test initialization without publication URL raises error"""
        with patch.dict(
            os.environ,
            {"SUBSTACK_EMAIL": "test@example.com", "SUBSTACK_PASSWORD": "testpass123"},
        ):
            with pytest.raises(
                ValueError, match="SUBSTACK_PUBLICATION_URL must be provided"
            ):
                AuthHandler()

    def test_init_invalid_publication_url(self):
        """Test initialization rejects malformed publication URLs."""
        with patch.dict(
            os.environ,
            {
                "SUBSTACK_EMAIL": "test@example.com",
                "SUBSTACK_PASSWORD": "testpass123",
                "SUBSTACK_PUBLICATION_URL": "not-a-url",
            },
        ):
            with pytest.raises(ValueError, match="Invalid publication URL format"):
                AuthHandler()

    @pytest.mark.asyncio
    async def test_authenticate_with_email_password(self):
        """Test authentication using email and password"""
        with patch.dict(
            os.environ,
            {
                "SUBSTACK_EMAIL": "test@example.com",
                "SUBSTACK_PASSWORD": "testpass123",
                "SUBSTACK_PUBLICATION_URL": "https://test.substack.com",
            },
        ):
            handler = AuthHandler()

            # Mock the Substack client
            mock_client = Mock()

            with patch(
                "src.handlers.auth_handler.SubstackApi", return_value=mock_client
            ) as mock_api:
                client = await handler.authenticate()

                assert isinstance(client, APIWrapper)
                mock_api.assert_called_once_with(
                    email="test@example.com",
                    password=handler.password,
                    publication_url="https://test.substack.com",
                )

    @pytest.mark.asyncio
    async def test_authenticate_uses_fresh_cached_client(self):
        """Cached clients should be reused while inside the cache window."""
        with patch.dict(
            os.environ,
            {
                "SUBSTACK_SESSION_TOKEN": "test-session-token",
                "SUBSTACK_PUBLICATION_URL": "https://test.substack.com",
            },
        ):
            handler = AuthHandler()
            cached_client = Mock()
            handler._client_cache[handler.publication_url] = (
                cached_client,
                datetime.utcnow(),
            )

            client = await handler.authenticate()

            assert client is cached_client

    @pytest.mark.asyncio
    async def test_authenticate_discards_expired_cached_client(self):
        """Expired cached clients should be evicted before re-authentication."""
        with patch.dict(
            os.environ,
            {
                "SUBSTACK_SESSION_TOKEN": "test-session-token",
                "SUBSTACK_PUBLICATION_URL": "https://test.substack.com",
            },
        ):
            handler = AuthHandler()
            handler._client_cache[handler.publication_url] = (
                Mock(),
                datetime.utcnow() - handler._cache_duration - timedelta(seconds=1),
            )
            handler._cookie_client_resources[handler.publication_url] = Mock()

            session_client = Mock()
            with patch.object(
                handler, "_create_session_client", return_value=session_client
            ) as create_session_client:
                client = await handler.authenticate()

            create_session_client.assert_called_once_with("test-session-token")
            assert isinstance(client, APIWrapper)

    @pytest.mark.asyncio
    async def test_authenticate_with_session_token(self):
        """Test authentication using session token"""
        with patch.dict(
            os.environ,
            {
                "SUBSTACK_SESSION_TOKEN": "test-session-token",
                "SUBSTACK_PUBLICATION_URL": "https://test.substack.com",
            },
        ):
            handler = AuthHandler()

            # Mock creating a client with session
            mock_client = Mock()

            with patch.object(
                handler, "_create_session_client", return_value=mock_client
            ):
                client = await handler.authenticate()

                assert isinstance(client, APIWrapper)

    @pytest.mark.asyncio
    async def test_authenticate_clears_stored_token_on_auth_failure(self):
        """Stored browser cookies should be cleared on confirmed auth failures."""
        with patch.dict(
            os.environ,
            {
                "SUBSTACK_EMAIL": "test@example.com",
                "SUBSTACK_PASSWORD": "testpass123",
                "SUBSTACK_PUBLICATION_URL": "https://test.substack.com",
            },
        ):
            handler = AuthHandler()
            handler.auth_manager.get_session_cookies = Mock(
                return_value={"substack.sid": "stored-cookie"}
            )
            handler.auth_manager.clear_token = Mock()

            with patch.object(
                handler,
                "_create_cookie_client",
                side_effect=Exception("401 invalid cookie"),
            ):
                with patch(
                    "src.handlers.auth_handler.SubstackApi", return_value=Mock()
                ):
                    client = await handler.authenticate()

            assert isinstance(client, APIWrapper)
            handler.auth_manager.clear_token.assert_called_once()

    @pytest.mark.asyncio
    async def test_authenticate_email_fallback_to_session(self):
        """Test fallback to session token when email auth fails"""
        with patch.dict(
            os.environ,
            {
                "SUBSTACK_EMAIL": "test@example.com",
                "SUBSTACK_PASSWORD": "wrongpass",
                "SUBSTACK_SESSION_TOKEN": "fallback-token",
                "SUBSTACK_PUBLICATION_URL": "https://test.substack.com",
            },
        ):
            handler = AuthHandler()

            # Mock failed email auth and successful session auth
            mock_session_client = Mock()

            with patch(
                "src.handlers.auth_handler.SubstackApi",
                side_effect=Exception("Invalid credentials"),
            ):
                with patch.object(
                    handler, "_create_session_client", return_value=mock_session_client
                ):
                    client = await handler.authenticate()

                    assert isinstance(client, APIWrapper)

    @pytest.mark.asyncio
    async def test_authenticate_session_token_falls_back_to_email_password(self):
        """If session-token auth fails, email/password auth should still run."""
        with patch.dict(
            os.environ,
            {
                "SUBSTACK_EMAIL": "test@example.com",
                "SUBSTACK_PASSWORD": "testpass123",
                "SUBSTACK_SESSION_TOKEN": "broken-token",
                "SUBSTACK_PUBLICATION_URL": "https://test.substack.com",
            },
        ):
            handler = AuthHandler()
            with patch.object(
                handler, "_create_session_client", side_effect=Exception("broken")
            ):
                with patch(
                    "src.handlers.auth_handler.SubstackApi", return_value=Mock()
                ) as mock_api:
                    client = await handler.authenticate()

            assert isinstance(client, APIWrapper)
            mock_api.assert_called_once()

    @pytest.mark.asyncio
    async def test_authenticate_all_methods_fail(self):
        """Test when all authentication methods fail"""
        # Mock the auth manager to prevent loading real tokens
        with patch("src.handlers.auth_handler.SimpleAuthManager") as mock_auth_manager:
            mock_auth_manager.return_value.get_token.return_value = None
            mock_auth_manager.return_value.get_session_cookies.return_value = None

            # First create the handler with required env vars
            with patch.dict(
                os.environ,
                {
                    "SUBSTACK_EMAIL": "test@example.com",
                    "SUBSTACK_PASSWORD": "wrongpass",
                    "SUBSTACK_PUBLICATION_URL": "https://test.substack.com",
                },
                clear=True,
            ):  # Clear all env vars to ensure no session token
                handler = AuthHandler()
                # Clear the client cache that might be populated from other tests
                handler._client_cache.clear()

                # Mock failed email auth
                with patch(
                    "src.handlers.auth_handler.SubstackApi",
                    side_effect=Exception("Invalid credentials"),
                ):
                    with pytest.raises(Exception, match="Invalid credentials"):
                        await handler.authenticate()

    @pytest.mark.asyncio
    async def test_authenticate_captcha_error_is_reworded(self):
        """Captcha failures should be remapped to setup guidance."""
        with patch.dict(
            os.environ,
            {
                "SUBSTACK_EMAIL": "test@example.com",
                "SUBSTACK_PASSWORD": "testpass123",
                "SUBSTACK_PUBLICATION_URL": "https://test.substack.com",
            },
        ):
            handler = AuthHandler()

            with patch(
                "src.handlers.auth_handler.SubstackApi",
                side_effect=Exception("captcha required"),
            ):
                with pytest.raises(Exception, match="CAPTCHA detected"):
                    await handler.authenticate()

    def test_get_headers_with_session(self):
        """Test getting headers for session-based authentication"""
        with patch.dict(
            os.environ,
            {
                "SUBSTACK_SESSION_TOKEN": "test-session-token",
                "SUBSTACK_PUBLICATION_URL": "https://test.substack.com",
            },
        ):
            handler = AuthHandler()
            headers = handler.get_headers()

            assert headers["Cookie"] == "substack.sid=test-session-token"
            assert headers["User-Agent"].startswith("substack-mcp/")
            assert "Content-Type" in headers

    def test_create_session_client(self):
        """Test creating a session-based client"""
        with patch.dict(
            os.environ,
            {
                "SUBSTACK_SESSION_TOKEN": "test-session-token",
                "SUBSTACK_PUBLICATION_URL": "https://test.substack.com",
            },
        ):
            handler = AuthHandler()

            # This would typically create a custom client
            # For now, we'll just verify the method exists
            assert hasattr(handler, "_create_session_client")

    def test_should_clear_stored_token_detects_auth_failures(self):
        with patch.dict(
            os.environ,
            {
                "SUBSTACK_SESSION_TOKEN": "test-session-token",
                "SUBSTACK_PUBLICATION_URL": "https://test.substack.com",
            },
        ):
            handler = AuthHandler()
            assert handler._should_clear_stored_token(Exception("403 invalid cookie"))
            assert not handler._should_clear_stored_token(Exception("timeout"))

    @pytest.mark.asyncio
    async def test_cookie_file_persists_until_cache_clear(self):
        """Cookie tempfiles should live for the cached client's lifetime."""
        with patch.dict(
            os.environ,
            {
                "SUBSTACK_SESSION_TOKEN": "test-session-token",
                "SUBSTACK_PUBLICATION_URL": "https://test.substack.com",
            },
        ):
            handler = AuthHandler()
            mock_client = Mock()

            with patch(
                "src.handlers.auth_handler.SubstackApi", return_value=mock_client
            ):
                await handler.authenticate()

            resource = AuthHandler._cookie_client_resources[handler.publication_url]
            assert resource.cookies_path.exists() is True

            handler.clear_cache()

            assert resource.cookies_path.exists() is False

    def test_get_headers_with_stored_cookie_jar(self):
        """Test headers include every stored browser auth cookie"""
        with patch.dict(
            os.environ,
            {
                "SUBSTACK_SESSION_TOKEN": "test-session-token",
                "SUBSTACK_PUBLICATION_URL": "https://test.substack.com",
            },
        ):
            handler = AuthHandler()
            handler.auth_manager.get_session_cookies = Mock(
                return_value={
                    "substack.sid": "test-session-token",
                    "substack.lli": "login-state",
                }
            )

            headers = handler.get_headers()

            assert (
                headers["Cookie"]
                == "substack.sid=test-session-token; substack.lli=login-state"
            )

    def test_publication_name_extraction(self):
        """Test extracting publication name from URL"""
        test_cases = [
            ("https://test.substack.com", "test"),
            ("https://example.substack.com/", "example"),
            ("https://my-publication.substack.com/about", "my-publication"),
        ]

        for url, expected_name in test_cases:
            with patch.dict(
                os.environ,
                {
                    "SUBSTACK_EMAIL": "test@example.com",
                    "SUBSTACK_PASSWORD": "testpass",
                    "SUBSTACK_PUBLICATION_URL": url,
                },
            ):
                handler = AuthHandler()
                assert handler.publication_name == expected_name

    def test_extract_publication_name_supports_custom_domains(self):
        with patch.dict(
            os.environ,
            {
                "SUBSTACK_EMAIL": "test@example.com",
                "SUBSTACK_PASSWORD": "testpass",
                "SUBSTACK_PUBLICATION_URL": "https://letters.example.com",
            },
        ):
            handler = AuthHandler()
            assert handler.publication_name == "letters"

    def test_create_cookie_client_cleans_up_when_substack_api_init_fails(self):
        with patch.dict(
            os.environ,
            {
                "SUBSTACK_SESSION_TOKEN": "test-session-token",
                "SUBSTACK_PUBLICATION_URL": "https://test.substack.com",
            },
        ):
            handler = AuthHandler()

            with patch(
                "src.handlers.auth_handler.SubstackApi",
                side_effect=Exception("bad cookies"),
            ):
                with pytest.raises(Exception, match="bad cookies"):
                    handler._create_cookie_client({"substack.sid": "cookie"})

            assert AuthHandler._cookie_client_resources == {}

    @pytest.mark.asyncio
    async def test_refresh_token_background_logs_errors(self):
        with patch.dict(
            os.environ,
            {
                "SUBSTACK_SESSION_TOKEN": "test-session-token",
                "SUBSTACK_PUBLICATION_URL": "https://test.substack.com",
            },
        ):
            handler = AuthHandler()
            with patch(
                "src.handlers.auth_handler.logger.info",
                side_effect=Exception("log fail"),
            ):
                with patch("src.handlers.auth_handler.logger.error") as logger_error:
                    await handler._refresh_token_background()

            logger_error.assert_called_once()
