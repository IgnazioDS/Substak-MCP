# ABOUTME: Regression tests for browser-based Substack authentication setup.
# ABOUTME: Verifies session cookie capture without requiring real credentials.

import asyncio

from setup_auth import SubstackAuthSetup


class FakeContext:
    def __init__(self, cookies_sequence):
        self._cookies_sequence = list(cookies_sequence)
        self._last = []

    async def cookies(self):
        if self._cookies_sequence:
            self._last = self._cookies_sequence.pop(0)
        return self._last


def test_extract_session_cookie_returns_substack_session():
    setup = SubstackAuthSetup()
    cookies = [
        {"name": "other", "value": "123", "domain": ".substack.com"},
        {"name": "substack.sid", "value": "secret-token", "domain": ".substack.com"},
    ]

    assert setup._extract_session_cookie(cookies) == "secret-token"


def test_extract_session_cookie_ignores_non_substack_domains():
    setup = SubstackAuthSetup()
    cookies = [
        {"name": "substack.sid", "value": "wrong-domain", "domain": ".example.com"},
    ]

    assert setup._extract_session_cookie(cookies) is None


def test_extract_session_cookies_keeps_full_substack_cookie_jar():
    setup = SubstackAuthSetup()
    cookies = [
        {"name": "substack.sid", "value": "session-token", "domain": ".substack.com"},
        {"name": "substack.lli", "value": "login-state", "domain": ".substack.com"},
        {"name": "analytics", "value": "ignore-me", "domain": ".example.com"},
    ]

    assert setup._extract_session_cookies(cookies) == {
        "substack.sid": "session-token",
        "substack.lli": "login-state",
    }


def test_wait_for_session_cookie_detects_cookie(monkeypatch):
    setup = SubstackAuthSetup()
    context = FakeContext(
        [
            [],
            [{"name": "substack.sid", "value": "token", "domain": ".substack.com"}],
        ]
    )

    async def fake_sleep(_seconds):
        return None

    async def fake_to_thread(_func, *_args, **_kwargs):
        await asyncio.sleep(3600)

    async def run_test():
        monkeypatch.setattr("setup_auth.COOKIE_POLL_INTERVAL_SECONDS", 0)
        monkeypatch.setattr("setup_auth.asyncio.sleep", fake_sleep)
        monkeypatch.setattr("setup_auth.asyncio.to_thread", fake_to_thread)
        return await setup._wait_for_session_cookie(context, timeout_seconds=1)

    assert asyncio.run(run_test()) == "token"


def test_wait_for_session_cookies_detects_full_cookie_jar(monkeypatch):
    setup = SubstackAuthSetup()
    context = FakeContext(
        [
            [],
            [
                {
                    "name": "substack.sid",
                    "value": "token",
                    "domain": ".substack.com",
                },
                {
                    "name": "substack.lli",
                    "value": "login-state",
                    "domain": ".substack.com",
                },
            ],
        ]
    )

    async def fake_sleep(_seconds):
        return None

    async def fake_to_thread(_func, *_args, **_kwargs):
        await asyncio.sleep(3600)

    async def run_test():
        monkeypatch.setattr("setup_auth.COOKIE_POLL_INTERVAL_SECONDS", 0)
        monkeypatch.setattr("setup_auth.asyncio.sleep", fake_sleep)
        monkeypatch.setattr("setup_auth.asyncio.to_thread", fake_to_thread)
        return await setup._wait_for_session_cookies(context, timeout_seconds=1)

    assert asyncio.run(run_test()) == {
        "substack.sid": "token",
        "substack.lli": "login-state",
    }
