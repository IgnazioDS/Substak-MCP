# ABOUTME: AuthHandler class for managing Substack authentication
# ABOUTME: Supports automatic token management, refresh, and multiple auth methods

import asyncio
import atexit
import json
import logging
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict
from urllib.parse import urlparse

from substack import Api as SubstackApi

from src.simple_auth_manager import SimpleAuthManager
from src.utils.api_wrapper import APIWrapper

logger = logging.getLogger(__name__)


@dataclass
class _CookieClientResource:
    """Keep the cookie tempfile alive for a cached authenticated client."""

    client: SubstackApi
    cookies_path: Path

    def cleanup(self) -> None:
        """Delete the cookie tempfile if it still exists."""
        if self.cookies_path.exists():
            self.cookies_path.unlink()


class AuthHandler:
    """Handles authentication for Substack API access with automatic token management"""

    # Cache for authenticated clients (in-memory for session)
    _client_cache: Dict[str, tuple[SubstackApi, datetime]] = {}
    _cookie_client_resources: Dict[str, _CookieClientResource] = {}
    _cache_duration = timedelta(minutes=30)  # Cache clients for 30 minutes
    _atexit_registered = False

    def __init__(self) -> None:
        """Initialize the auth handler with automatic token management"""
        # Get publication URL (required)
        publication_url = os.getenv("SUBSTACK_PUBLICATION_URL")
        if not publication_url:
            raise ValueError("SUBSTACK_PUBLICATION_URL must be provided")
        self.publication_url: str = publication_url

        # Validate URL format
        if not isinstance(self.publication_url, str):
            raise ValueError("Publication URL must be a string")

        try:
            parsed = urlparse(self.publication_url)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError("Invalid publication URL format")
        except Exception:
            raise ValueError("Invalid publication URL format")

        # Initialize auth manager for secure token storage (file-based, no keychain)
        self.auth_manager = SimpleAuthManager(self.publication_url)
        self._register_atexit_cleanup()

        # Get credentials from environment (fallback)
        self.email = os.getenv("SUBSTACK_EMAIL")
        self.password = os.getenv("SUBSTACK_PASSWORD")
        self.env_session_token = os.getenv("SUBSTACK_SESSION_TOKEN")

        # Extract publication name from URL
        self.publication_name = self._extract_publication_name(self.publication_url)

        # Check if we have any valid auth method
        stored_cookies = self.auth_manager.get_session_cookies()
        has_stored_auth = isinstance(stored_cookies, dict) and bool(
            stored_cookies.get("substack.sid")
        )
        has_env_auth = (self.email and self.password) or self.env_session_token

        if not has_stored_auth and not has_env_auth:
            raise ValueError(
                "No authentication found. Please run 'substack-mcp-setup' to configure authentication, "
                "or provide SUBSTACK_EMAIL/SUBSTACK_PASSWORD or SUBSTACK_SESSION_TOKEN environment variables."
            )

        logger.info(f"AuthHandler initialized for {self.publication_name}")

    def _extract_publication_name(self, url: str) -> str:
        """Extract the publication name from the Substack URL

        Args:
            url: The publication URL (e.g., https://example.substack.com)

        Returns:
            The publication name (e.g., 'example')

        Raises:
            ValueError: If URL parsing fails
        """
        if not url or not isinstance(url, str):
            raise ValueError("URL must be a non-empty string")
        parsed = urlparse(url)
        hostname = parsed.hostname or parsed.path

        # Remove .substack.com suffix if present
        if hostname.endswith(".substack.com"):
            return hostname[:-13]  # Remove '.substack.com'

        # Handle custom domains or other formats
        return hostname.split(".")[0]

    def _should_clear_stored_token(self, error: Exception) -> bool:
        """Only clear stored auth on likely auth failures, not transient network issues."""
        message = str(error).lower()
        auth_markers = [
            "unauthorized",
            "authentication",
            "forbidden",
            "invalid token",
            "invalid cookie",
            "401",
            "403",
        ]
        return any(marker in message for marker in auth_markers)

    @classmethod
    def _register_atexit_cleanup(cls) -> None:
        """Register global cookie tempfile cleanup once per process."""
        if not cls._atexit_registered:
            atexit.register(cls._cleanup_all_cookie_resources)
            cls._atexit_registered = True

    @classmethod
    def _cleanup_cookie_resource(cls, cache_key: str) -> None:
        """Clean up one cached cookie resource by cache key."""
        resource = cls._cookie_client_resources.pop(cache_key, None)
        if resource is not None:
            resource.cleanup()

    @classmethod
    def _cleanup_all_cookie_resources(cls) -> None:
        """Clean up all cached cookie tempfiles."""
        for cache_key in list(cls._cookie_client_resources):
            cls._cleanup_cookie_resource(cache_key)

    async def authenticate(self) -> SubstackApi:
        """Authenticate and return a Substack client with automatic token management

        Returns:
            An authenticated Substack client

        Raises:
            Exception: If all authentication methods fail
        """
        # Check cache first
        cache_key = self.publication_url
        if cache_key in self._client_cache:
            client, cached_at = self._client_cache[cache_key]
            if datetime.utcnow() - cached_at < self._cache_duration:
                logger.debug("Using cached client")
                return client
            else:
                # Remove expired cache
                del self._client_cache[cache_key]
                self._cleanup_cookie_resource(cache_key)

        # Try stored token first (from AuthManager)
        stored_cookies = self.auth_manager.get_session_cookies()
        if isinstance(stored_cookies, dict) and stored_cookies.get("substack.sid"):
            try:
                logger.info("Authenticating with stored session cookies")
                resource = self._create_cookie_client(stored_cookies)
                client = resource.client

                # Wrap the client for better error handling
                wrapped_client = APIWrapper(client)

                # Cache the wrapped client
                self._client_cache[cache_key] = (wrapped_client, datetime.utcnow())
                self._cookie_client_resources[cache_key] = resource

                # Check if token needs refresh
                if self.auth_manager.needs_refresh():
                    logger.info("Token approaching expiry, scheduling refresh")
                    asyncio.create_task(self._refresh_token_background())

                return wrapped_client

            except Exception as e:
                logger.warning(f"Stored token authentication failed: {e}")
                if self._should_clear_stored_token(e):
                    logger.warning("Clearing stored token after confirmed auth failure")
                    self.auth_manager.clear_token()

        # Try environment variable session token
        if self.env_session_token:
            try:
                logger.info("Authenticating with environment session token")
                session_client = self._create_session_client(self.env_session_token)
                resource = (
                    session_client
                    if isinstance(session_client, _CookieClientResource)
                    else None
                )
                client = session_client.client if resource else session_client

                # Wrap the client for better error handling
                wrapped_client = APIWrapper(client)

                # Cache the wrapped client
                self._client_cache[cache_key] = (wrapped_client, datetime.utcnow())
                if resource is not None:
                    self._cookie_client_resources[cache_key] = resource

                # Optionally store this token for future use
                if self.email:  # Only if we know the email
                    self.auth_manager.store_token(self.env_session_token, self.email)

                return wrapped_client

            except Exception as e:
                logger.warning(f"Environment session token failed: {e}")

        # Try email/password authentication
        if self.email and self.password:
            try:
                logger.info("Authenticating with email/password")
                client = SubstackApi(
                    email=self.email,
                    password=self.password,
                    publication_url=self.publication_url,
                )

                # Wrap the client for better error handling
                wrapped_client = APIWrapper(client)

                # Cache the wrapped client
                self._client_cache[cache_key] = (wrapped_client, datetime.utcnow())
                self._cleanup_cookie_resource(cache_key)

                # Try to extract and store the session token for future use
                # This would require inspecting the client's session, which may not be exposed
                # For now, we just use the client as-is

                return wrapped_client

            except Exception as e:
                logger.error(f"Email/password authentication failed: {e}")
                if "captcha" in str(e).lower():
                    raise Exception(
                        "CAPTCHA detected. Please run 'substack-mcp-setup' to authenticate "
                        "through the browser and set up automatic token management."
                    )
                raise

        raise Exception(
            "No valid authentication method available. "
            "Please run 'substack-mcp-setup' to configure authentication."
        )

    def _create_session_client(self, session_token: str) -> _CookieClientResource:
        """Create a client using session token authentication

        Args:
            session_token: The session token to use

        Returns:
            A Substack client configured with session authentication
        """
        return self._create_cookie_client({"substack.sid": session_token})

    def _create_cookie_client(self, cookies: Dict[str, str]) -> _CookieClientResource:
        """Create a client using browser-authenticated cookies.

        Args:
            cookies: Cookie name/value pairs to use

        Returns:
            A Substack client configured with cookie authentication
        """

        # Save cookies to temporary file with secure permissions
        fd, cookies_path = tempfile.mkstemp(suffix=".json", text=True)
        try:
            # Set secure permissions (readable/writable by owner only)
            os.chmod(cookies_path, 0o600)

            # Write cookies to the file
            with os.fdopen(fd, "w") as f:
                json.dump(cookies, f)
        except Exception:
            os.close(fd)
            os.unlink(cookies_path)
            raise

        try:
            client = SubstackApi(
                cookies_path=cookies_path, publication_url=self.publication_url
            )
            return _CookieClientResource(client=client, cookies_path=Path(cookies_path))
        except Exception:
            if os.path.exists(cookies_path):
                os.unlink(cookies_path)
            raise

    async def _refresh_token_background(self) -> None:
        """Background task to refresh token before expiry"""
        try:
            # This would require re-authenticating through the browser
            # For now, we just log that refresh is needed
            logger.info(
                "Token refresh needed - user should run substack-mcp-setup again"
            )

            # In a future enhancement, we could:
            # 1. Notify the user through the MCP interface
            # 2. Attempt automatic re-authentication if we have stored credentials
            # 3. Use a refresh token if Substack provides one

        except Exception as e:
            logger.error(f"Error in token refresh: {e}")

    def get_headers(self) -> Dict[str, str]:
        """Get headers for session-based authentication

        Returns:
            Headers dict with authentication cookies
        """
        headers = {
            "User-Agent": "substack-mcp/2.0.0",
            "Content-Type": "application/json",
        }

        # Try to get token from storage or environment
        token = self.auth_manager.get_token() or self.env_session_token

        cookies = self.auth_manager.get_session_cookies()
        if isinstance(cookies, dict) and cookies.get("substack.sid"):
            headers["Cookie"] = "; ".join(
                f"{name}={value}" for name, value in cookies.items()
            )
        elif token:
            headers["Cookie"] = f"substack.sid={token}"

        return headers

    def clear_cache(self) -> None:
        """Clear the client cache"""
        self._client_cache.clear()
        self._cleanup_all_cookie_resources()
        logger.info("Client cache cleared")
