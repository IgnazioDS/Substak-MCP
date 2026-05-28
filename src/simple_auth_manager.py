# ABOUTME: SimpleAuthManager handles encrypted local auth storage without keychain use.
# ABOUTME: It prefers the current auth directory and reuses the legacy one when present.

import base64
import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)


class SimpleAuthManager:
    """Manages authentication tokens with local file storage (no keychain)"""

    def __init__(self, publication_url: str):
        """Initialize the auth manager

        Args:
            publication_url: The Substack publication URL
        """
        self.publication_url = publication_url

        # Prefer the current config directory but reuse the legacy one so
        # existing installs keep working after the rename.
        home_dir = Path.home()
        legacy_config_dir = home_dir / ".substack-mcp-plus"
        current_config_dir = home_dir / ".substack-mcp"
        self.config_dir = (
            legacy_config_dir
            if legacy_config_dir.exists() and not current_config_dir.exists()
            else current_config_dir
        )
        self.config_dir.mkdir(exist_ok=True)
        os.chmod(self.config_dir, 0o700)

        self.auth_file = self.config_dir / "auth.json"
        self.key_file = self.config_dir / ".key"

        self._missing_key_file = False
        self.cipher = self._get_or_create_cipher()

    def _create_new_cipher(self) -> Fernet:
        """Create and persist a new Fernet key for future writes."""
        key = Fernet.generate_key()
        self.key_file.write_bytes(key)
        os.chmod(self.key_file, 0o600)
        self._missing_key_file = False
        return Fernet(key)

    def _get_or_create_cipher(self) -> Optional[Fernet]:
        """Get or create an encryption cipher for secure storage"""
        if self.key_file.exists():
            key = self.key_file.read_bytes()
            return Fernet(key)

        if self.auth_file.exists():
            logger.error("Auth file exists but encryption key file is missing")
            self._missing_key_file = True
            return None

        return self._create_new_cipher()

    def store_token(self, token: str, email: str, expires_in_days: int = 30) -> None:
        """Store an authentication token securely

        Args:
            token: The session token to store
            email: The email associated with the token
            expires_in_days: Number of days until token expires
        """
        self.store_session_cookies(
            {"substack.sid": token}, email, expires_in_days=expires_in_days
        )

    def store_session_cookies(
        self, cookies: Dict[str, str], email: str, expires_in_days: int = 30
    ) -> None:
        """Store a complete browser-authenticated Substack cookie jar securely.

        Args:
            cookies: Cookie name/value pairs captured after browser authentication
            email: The email associated with the cookies
            expires_in_days: Number of days until cookies expire locally
        """
        normalized_cookies = {
            str(name): str(value)
            for name, value in cookies.items()
            if name and value is not None
        }
        token = normalized_cookies.get("substack.sid")
        if not token:
            raise ValueError("substack.sid cookie is required")

        if self.cipher is None:
            self.cipher = self._create_new_cipher()

        # Encrypt the token
        encrypted_token = self.cipher.encrypt(token.encode())
        encrypted_cookies = self.cipher.encrypt(json.dumps(normalized_cookies).encode())

        # Store auth data
        auth_data = {
            "token": base64.b64encode(encrypted_token).decode(),
            "cookies": base64.b64encode(encrypted_cookies).decode(),
            "email": email,
            "stored_at": datetime.utcnow().isoformat(),
            "expires_at": (
                datetime.utcnow() + timedelta(days=expires_in_days)
            ).isoformat(),
            "publication_url": self.publication_url,
        }

        # Write to file with restrictive permissions
        self.auth_file.write_text(json.dumps(auth_data, indent=2))
        os.chmod(self.auth_file, 0o600)

        logger.info(f"Token stored securely for {email} at {self.publication_url}")

    def _get_valid_auth_data(self) -> Optional[Dict[str, Any]]:
        """Read stored auth metadata if the local expiry window is still valid."""
        if not self.auth_file.exists():
            logger.debug("No stored token found")
            return None

        try:
            raw_auth_data = json.loads(self.auth_file.read_text())
            if not isinstance(raw_auth_data, dict):
                logger.error("Stored authentication data is not a JSON object")
                return None
            auth_data: Dict[str, Any] = {
                str(key): value for key, value in raw_auth_data.items()
            }

            stored_publication_url = auth_data.get("publication_url")
            if stored_publication_url != self.publication_url:
                logger.info(
                    "Reusing stored session token across publication URL change: %s -> %s",
                    stored_publication_url,
                    self.publication_url,
                )

            expires_at = datetime.fromisoformat(auth_data["expires_at"])

            # Check if token is expired
            if datetime.utcnow() > expires_at:
                logger.info("Stored token has expired")
                self.clear_token()
                return None

            return auth_data

        except Exception as e:
            logger.error(f"Error retrieving token: {e}")
            return None

    def get_token(self) -> Optional[str]:
        """Retrieve the stored session token if valid

        Returns:
            The decrypted token if valid, None otherwise
        """
        auth_data = self._get_valid_auth_data()
        if not auth_data:
            return None

        try:
            if self.cipher is None:
                logger.error("Cannot retrieve token without encryption key")
                return None
            # Decrypt and return token
            encrypted_token = base64.b64decode(auth_data["token"].encode())
            token = self.cipher.decrypt(encrypted_token).decode()

            logger.info(f"Retrieved valid token for {auth_data['email']}")
            return token

        except Exception as e:
            logger.error(f"Error retrieving token: {e}")
            return None

    def get_session_cookies(self) -> Optional[Dict[str, str]]:
        """Retrieve the stored browser cookie jar if valid.

        Returns:
            Cookie name/value pairs, or None when no valid auth exists
        """
        auth_data = self._get_valid_auth_data()
        if not auth_data:
            return None

        try:
            if self.cipher is None:
                logger.error("Cannot retrieve session cookies without encryption key")
                return None
            encrypted_cookies = auth_data.get("cookies")
            if encrypted_cookies:
                cookie_payload = base64.b64decode(encrypted_cookies.encode())
                cookies = json.loads(self.cipher.decrypt(cookie_payload).decode())
                if isinstance(cookies, dict) and cookies.get("substack.sid"):
                    return {str(name): str(value) for name, value in cookies.items()}
                logger.error("Stored cookie jar is missing substack.sid")
                return None

            token = self.get_token()
            if token:
                return {"substack.sid": token}
            return None

        except Exception as e:
            logger.error(f"Error retrieving session cookies: {e}")
            return None

    def clear_token(self) -> None:
        """Clear stored token"""
        if self.auth_file.exists():
            self.auth_file.unlink()
        logger.info("Cleared stored authentication data")

    def get_metadata(self) -> Optional[Dict[str, Any]]:
        """Get token metadata

        Returns:
            Token metadata dict or None
        """
        if not self.auth_file.exists():
            return None

        try:
            auth_data = json.loads(self.auth_file.read_text())
            return {
                "email": auth_data.get("email"),
                "stored_at": auth_data.get("stored_at"),
                "expires_at": auth_data.get("expires_at"),
                "publication_url": auth_data.get("publication_url"),
            }
        except:
            return None

    def needs_refresh(self, days_before_expiry: int = 7) -> bool:
        """Check if token needs refresh

        Args:
            days_before_expiry: Days before expiry to trigger refresh

        Returns:
            True if token needs refresh or doesn't exist
        """
        metadata = self.get_metadata()
        if not metadata:
            return True

        try:
            expires_at = datetime.fromisoformat(metadata["expires_at"])
            refresh_threshold = expires_at - timedelta(days=days_before_expiry)
            return datetime.utcnow() > refresh_threshold
        except:
            return True
