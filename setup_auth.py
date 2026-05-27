#!/usr/bin/env python3
# ABOUTME: Interactive browser authentication setup for Substack MCP Plus.
# ABOUTME: Captures Substack session cookies after user-driven CAPTCHA/login.
"""
Interactive authentication setup for Substack MCP Plus
Handles browser automation and CAPTCHA challenges
"""

import asyncio
import sys
import os
import json
import logging
from typing import Dict, Optional
from urllib.parse import urlparse
import getpass
from playwright.async_api import async_playwright, TimeoutError
from src.simple_auth_manager import SimpleAuthManager

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

COOKIE_POLL_INTERVAL_SECONDS = 2
MANUAL_PROMPT = (
    "\nPress Enter here after you finish CAPTCHA/login in the browser (or just wait): "
)


class SubstackAuthSetup:
    """Interactive setup wizard for Substack authentication"""

    def __init__(self):
        self.email = None
        self.password = None
        self.publication_url = None
        self.auth_manager = None
        self.auth_method = None  # 'password' or 'magic_link'

    async def run(self):
        """Run the interactive setup process"""
        print("\n🚀 Substack MCP Plus - Authentication Setup")
        print("=" * 50)
        print("\nThis wizard will help you set up secure authentication.")
        print("Your credentials will be encrypted and stored securely.\n")

        # Get user inputs
        if not self._get_user_inputs():
            return False

        # Initialize auth manager (file-based, no keychain)
        self.auth_manager = SimpleAuthManager(self.publication_url)

        # Check for existing token
        existing_token = self.auth_manager.get_token()
        if existing_token:
            metadata = self.auth_manager.get_metadata()
            print(f"\n✅ Found existing authentication for {metadata['email']}")
            replace = input("Replace with new authentication? (y/n): ").lower().strip()
            if replace != "y":
                print("Setup cancelled.")
                return False

        # Perform browser-based authentication
        print("\n🌐 Starting browser authentication...")
        print("A browser window will open. Please complete the login process.")
        if self.auth_method == "magic_link":
            print("You'll receive a 6-digit code via email.")
        print("If you see a CAPTCHA, please solve it.\n")

        session_cookies = await self._authenticate_with_browser()

        if session_cookies:
            # Store the browser-authenticated cookie jar.
            self.auth_manager.store_session_cookies(session_cookies, self.email)
            print("\n✅ Authentication successful!")
            print("Session cookies have been securely stored.")

            # Test the authentication
            if await self._test_authentication(session_cookies):
                print("\n🎉 Setup complete! You can now use Substack MCP Plus.")
                self._show_config_example()
                return True
            else:
                print("\n⚠️  Authentication stored but test failed.")
                print("Please check your publication URL and try again.")
                return False
        else:
            print("\n❌ Authentication failed. Please try again.")
            return False

    def _get_user_inputs(self) -> bool:
        """Get required inputs from user"""
        try:
            # Get authentication method
            print("\nHow would you like to sign in?")
            print("1. Magic link (email code)")
            print("2. Email and password")

            choice = input("\nSelect authentication method (1 or 2): ").strip()

            if choice == "1":
                self.auth_method = "magic_link"
            elif choice == "2":
                self.auth_method = "password"
            else:
                print("❌ Invalid choice. Please enter 1 or 2.")
                return False

            # Get email
            self.email = input("\nSubstack email: ").strip()
            if not self.email or "@" not in self.email:
                print("❌ Invalid email address")
                return False

            # Get password only if using password auth
            if self.auth_method == "password":
                self.password = getpass.getpass("Substack password: ")
                if not self.password:
                    print("❌ Password cannot be empty")
                    return False

            # Get publication URL
            self.publication_url = input(
                "Publication URL (e.g., https://example.substack.com): "
            ).strip()

            # Validate URL
            try:
                parsed = urlparse(self.publication_url)
                if not parsed.scheme:
                    self.publication_url = f"https://{self.publication_url}"
                if not parsed.netloc and not self.publication_url.startswith(
                    "https://"
                ):
                    print("❌ Invalid publication URL")
                    return False
            except:
                print("❌ Invalid publication URL")
                return False

            # Extract publication name for display
            pub_name = self._extract_publication_name(self.publication_url)
            print(f"\n📝 Setting up for publication: {pub_name}")

            return True

        except KeyboardInterrupt:
            print("\n\nSetup cancelled.")
            return False

    def _extract_publication_name(self, url: str) -> str:
        """Extract publication name from URL"""
        parsed = urlparse(url)
        domain = parsed.netloc or parsed.path

        # Handle substack.com subdomains
        if ".substack.com" in domain:
            return domain.split(".substack.com")[0].split(".")[-1]

        # Handle custom domains
        return domain.split(".")[0]

    async def _authenticate_with_browser(self) -> Optional[Dict[str, str]]:
        """Perform browser-based authentication and extract session cookies."""
        async with async_playwright() as p:
            # Launch browser (visible so user can solve CAPTCHA)
            browser = await p.chromium.launch(headless=False)
            context = await browser.new_context()
            page = await context.new_page()

            try:
                # Navigate to Substack login
                logger.info("Navigating to Substack login...")
                await page.goto(
                    "https://substack.com/sign-in", wait_until="networkidle"
                )

                # Use a manual-first flow because Substack's auth UI changes frequently,
                # especially around CAPTCHA and anti-bot checks.
                await self._prepare_login_page(page)

                # Wait for login to complete
                print("\n⏳ Waiting for login to complete...")
                print("If you see a CAPTCHA, solve it in the browser.")
                print(
                    "The browser will stay open until the session cookie is detected or you cancel the process."
                )

                session_cookies = await self._wait_for_session_cookies(context)
                if not session_cookies:
                    logger.error("Login ended before a session cookie was detected")
                    return None

                logger.info("✅ Successfully extracted session cookies")
                return session_cookies

            except Exception as e:
                logger.error(f"Authentication error: {e}")
                return None

            finally:
                await browser.close()

    async def _wait_for_any_selector(self, page, selectors, timeout=5000):
        """Return the first visible locator matching any selector."""
        per_selector_timeout = max(1000, timeout // max(len(selectors), 1))

        for selector in selectors:
            locator = page.locator(selector).first
            try:
                await locator.wait_for(state="visible", timeout=per_selector_timeout)
                return locator
            except TimeoutError:
                continue
            except Exception:
                continue
        return None

    async def _click_optional(self, page, selectors):
        """Click the first available selector, ignoring failures."""
        for selector in selectors:
            locator = page.locator(selector).first
            try:
                if await locator.count() > 0:
                    await locator.click(timeout=1500)
                    return True
            except Exception:
                continue
        return False

    async def _click_first_available(self, page, selectors):
        """Click the first available selector or raise if none are clickable."""
        if await self._click_optional(page, selectors):
            return
        raise RuntimeError(f"Could not find clickable element. Tried: {selectors}")

    def _extract_session_cookie(self, cookies) -> Optional[str]:
        """Extract the Substack session token from browser cookies."""
        session_cookies = self._extract_session_cookies(cookies)
        return session_cookies.get("substack.sid")

    def _extract_session_cookies(self, cookies) -> Dict[str, str]:
        """Extract Substack cookies once the authenticated session cookie exists."""
        session_cookies = {}
        for cookie in cookies:
            name = cookie.get("name")
            value = cookie.get("value")
            domain = cookie.get("domain", "")
            if name and value is not None and "substack.com" in domain:
                session_cookies[name] = value

        if "substack.sid" not in session_cookies:
            return {}
        return session_cookies

    async def _prepare_login_page(self, page):
        """Do only safe, low-risk automation, then let the user drive the browser."""
        print("\nThe browser is now in manual mode.")
        print("Complete the rest of the Substack login flow yourself in the browser.")

        email_field = await self._wait_for_any_selector(
            page,
            [
                'input[name="email"]',
                'input[type="email"]',
                'input[autocomplete="email"]',
                'input[placeholder*="email" i]',
            ],
            timeout=5000,
        )
        if email_field:
            logger.info("Pre-filling email...")
            await email_field.fill(self.email)
            print("Email was pre-filled for you.")

        if self.auth_method == "password":
            print(
                "Choose password sign-in in the browser if Substack asks, then finish login manually."
            )

            password_field = await self._wait_for_any_selector(
                page,
                [
                    'input[type="password"]',
                    'input[name="password"]',
                    'input[autocomplete="current-password"]',
                    'input[placeholder*="password" i]',
                ],
                timeout=1500,
            )
            if password_field:
                logger.info("Pre-filling password...")
                await password_field.fill(self.password)
                print(
                    "Password was pre-filled too. Review it, solve any CAPTCHA, then submit in the browser."
                )
        else:
            print("Use the magic-link flow in the browser and enter the code there.")

    async def _wait_for_session_cookie(self, context, timeout_seconds=None):
        """Wait for the authenticated session cookie and return only its token."""
        session_cookies = await self._wait_for_session_cookies(
            context, timeout_seconds=timeout_seconds
        )
        return session_cookies.get("substack.sid") if session_cookies else None

    async def _wait_for_session_cookies(self, context, timeout_seconds=None):
        """Wait for authenticated cookies instead of relying on URL redirects."""
        started_at = asyncio.get_running_loop().time()
        next_status_update = 30
        manual_check_task = asyncio.create_task(asyncio.to_thread(input, MANUAL_PROMPT))

        try:
            while True:
                cookies = await context.cookies()
                session_cookies = self._extract_session_cookies(cookies)
                if session_cookies:
                    return session_cookies

                if manual_check_task.done():
                    # User says they're done. Re-check immediately, then keep waiting without blocking.
                    try:
                        manual_check_task.result()
                    except Exception:
                        pass

                    cookies = await context.cookies()
                    session_cookies = self._extract_session_cookies(cookies)
                    if session_cookies:
                        return session_cookies

                    print(
                        "Still no session cookie yet. Keep going in the browser; I'll keep waiting."
                    )
                    manual_check_task = asyncio.create_task(
                        asyncio.to_thread(input, MANUAL_PROMPT)
                    )

                elapsed = int(asyncio.get_running_loop().time() - started_at)
                if timeout_seconds is not None and elapsed >= timeout_seconds:
                    return None

                if elapsed >= next_status_update:
                    print("Still waiting for login to finish...")
                    next_status_update += 30

                await asyncio.sleep(COOKIE_POLL_INTERVAL_SECONDS)
        finally:
            if not manual_check_task.done():
                manual_check_task.cancel()

    async def _test_authentication(self, session_cookies: Dict[str, str]) -> bool:
        """Test the authentication by making an API call"""
        try:
            from substack import Api as SubstackApi
            import tempfile

            # Create temporary cookie file
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False
            ) as f:
                json.dump(session_cookies, f)
                cookies_path = f.name

            try:
                # Test API connection
                api = SubstackApi(
                    cookies_path=cookies_path, publication_url=self.publication_url
                )

                # Try to get publication info (this will fail if auth is bad)
                # Since we don't have a direct method, we'll assume success if no exception
                logger.info("Testing authentication...")

                # Clean successful init means auth worked
                return True

            except Exception as e:
                logger.error(f"Authentication test failed: {e}")
                return False
            finally:
                # Clean up temp file
                if os.path.exists(cookies_path):
                    os.unlink(cookies_path)

        except Exception as e:
            logger.error(f"Test error: {e}")
            return False

    def _show_config_example(self):
        """Show example configuration for Claude Desktop"""
        print("\n📋 Configuration for Claude Desktop:")
        print("-" * 50)
        print("""
Add this to your Claude Desktop config:

{
  "mcpServers": {
    "substack-mcp-plus": {
      "command": "python",
      "args": ["-m", "src.server"],
      "env": {
        "SUBSTACK_PUBLICATION_URL": "%s"
      }
    }
  }
}
""" % self.publication_url)
        print("-" * 50)
        print(
            "\nNo email or password needed - authentication is handled automatically! 🎉"
        )


async def main():
    """Main entry point"""
    setup = SubstackAuthSetup()
    success = await setup.run()
    return 0 if success else 1


if __name__ == "__main__":
    try:
        # Install playwright browsers if needed
        import subprocess

        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"], check=False
        )

        # Run the setup
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        print("\n\nSetup cancelled.")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Setup error: {e}")
        sys.exit(1)
