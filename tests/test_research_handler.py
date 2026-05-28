import pytest
from itertools import chain, repeat
from unittest.mock import AsyncMock

from bs4 import BeautifulSoup
from src.handlers.research_handler import ResearchHandler
from src.version import SERVER_VERSION


def test_user_agent_is_transparent():
    handler = ResearchHandler()

    assert f"substack-mcp-research/{SERVER_VERSION}" in handler.USER_AGENT
    assert "github.com/IgnazioDS/Substak-MCP" in handler.USER_AGENT


def test_is_researchable_substack_url_filters_internal_paths():
    handler = ResearchHandler()

    assert handler._is_researchable_substack_url("https://example.substack.com/p/post")
    assert handler._is_researchable_substack_url(
        "https://www.oneusefulthing.org/p/change-blindness"
    )
    assert handler._is_researchable_substack_url("https://www.oneusefulthing.org")
    assert not handler._is_researchable_substack_url("https://substack.com/sign-in")
    assert not handler._is_researchable_substack_url(
        "https://substack.com/api/v1/search"
    )
    assert not handler._is_researchable_substack_url(
        "https://substack.com/publish/post/123"
    )


def test_extract_themes_surfaces_repeated_topic_words():
    handler = ResearchHandler()
    results = [
        {
            "title": "AI agents for product teams",
            "snippet": "How teams use AI agents in workflow systems",
            "description": "",
            "body_excerpt": "",
        },
        {
            "title": "AI workflow design on Substack",
            "snippet": "Workflow ideas for AI research and writing",
            "description": "",
            "body_excerpt": "",
        },
    ]

    themes = handler._extract_themes(results)
    theme_names = {item["theme"] for item in themes}

    assert "ai" in theme_names
    assert "workflow" in theme_names


def test_extract_themes_filters_web_noise_tokens():
    handler = ResearchHandler()
    results = [
        {
            "title": "SwiftUI async image caching",
            "snippet": "https://example.com embed com post swiftui asyncimage caching",
            "description": "",
            "body_excerpt": "",
        }
    ]

    themes = handler._extract_themes(results)
    theme_names = {item["theme"] for item in themes}

    assert "swiftui" in theme_names
    assert "https" not in theme_names
    assert "com" not in theme_names
    assert "embed" not in theme_names
    assert "post" not in theme_names


def test_looks_like_junk_result_rejects_enable_javascript_pages():
    handler = ResearchHandler()

    assert handler._looks_like_junk_result(
        "https://enable-javascript.com/",
        "turn on JavaScript | enable-javascript.com",
        "This site requires javascript to run correctly.",
    )


def test_build_recommendations_prefers_richer_post_results():
    handler = ResearchHandler()
    results = [
        {
            "title": "Thin result",
            "url": "https://alpha.substack.com/",
            "publication": "alpha",
            "page_type": "publication",
            "provider": "duckduckgo_html",
        },
        {
            "title": "Rich post",
            "url": "https://beta.substack.com/p/rich-post",
            "publication": "beta",
            "page_type": "post",
            "provider": "substack_direct",
            "description": "Deep write-up",
            "body_excerpt": "A substantial excerpt about the niche.",
            "author": "Beta Author",
        },
    ]

    recommendations = handler._build_recommendations(results)

    assert recommendations[0]["publication"] == "beta"
    assert recommendations[0]["score"] > recommendations[1]["score"]


def test_normalize_candidate_url_unwraps_duckduckgo_redirect():
    handler = ResearchHandler()

    url = "https://duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.oneusefulthing.org%2Fp%2Fchange-blindness"

    assert (
        handler._normalize_candidate_url(url)
        == "https://www.oneusefulthing.org/p/change-blindness"
    )


@pytest.mark.asyncio
async def test_research_substack_clamps_limits_and_filters_noncredible_results(
    monkeypatch,
):
    handler = ResearchHandler()
    captured = {}

    class DummySession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    async def fake_search(session, query, max_results):
        captured["query"] = query
        captured["max_results"] = max_results
        return [
            {
                "title": "Alpha",
                "url": "https://alpha.substack.com/p/post",
                "publication": "alpha",
                "snippet": "Alpha snippet",
                "provider": "substack_direct",
                "page_type": "post",
            },
            {
                "title": "Alpha duplicate",
                "url": "https://alpha.substack.com/p/post/",
                "publication": "alpha",
                "snippet": "Duplicate",
                "provider": "substack_direct",
                "page_type": "post",
            },
            {
                "title": "Bravo",
                "url": "https://bravo.substack.com/",
                "publication": "bravo",
                "snippet": "Bravo snippet",
                "provider": "duckduckgo_html",
                "page_type": "publication",
            },
        ]

    async def fake_enrich(session, results):
        captured["enrichment_targets"] = [result["url"] for result in results]
        return {
            "https://alpha.substack.com/p/post": {
                "resolved_title": "Alpha resolved",
                "resolved_url": "https://alpha.substack.com/p/post",
                "description": "Alpha description",
                "body_excerpt": "Alpha excerpt",
                "publication": "alpha",
            },
            "https://bravo.substack.com/": {},
        }

    def fake_credible(result, enriched):
        return result["url"] != "https://bravo.substack.com/"

    monkeypatch.setattr(
        "src.handlers.research_handler.aiohttp.ClientSession",
        lambda **kwargs: DummySession(),
    )
    monkeypatch.setattr(handler, "_search", fake_search)
    monkeypatch.setattr(handler, "_enrich_results", fake_enrich)
    monkeypatch.setattr(handler, "_result_is_credible", fake_credible)

    result = await handler.research_substack(
        "operators", max_results=99, deep_read_count=99
    )

    assert captured["query"] == "operators"
    assert captured["max_results"] == 30
    assert captured["enrichment_targets"] == [
        "https://alpha.substack.com/p/post",
        "https://bravo.substack.com/",
    ]
    assert result["results_found"] == 1
    assert result["results"][0]["title"] == "Alpha"
    assert result["results"][0]["summary"] == "Alpha description Alpha excerpt"
    assert result["publication_leaders"] == [{"publication": "alpha", "mentions": 1}]
    assert result["warnings"] == []


@pytest.mark.asyncio
async def test_research_substack_rejects_non_string_query():
    handler = ResearchHandler()

    with pytest.raises(ValueError, match="query must be a non-empty string"):
        await handler.research_substack(None)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_duckduckgo_search_gracefully_falls_back_after_202():
    handler = ResearchHandler()
    handler._is_allowed_by_robots = AsyncMock(return_value=True)

    class FakeResponse:
        def __init__(self, status, body):
            self.status = status
            self._body = body

        async def text(self):
            return self._body

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakeSession:
        def __init__(self):
            self.calls = 0

        def get(self, url, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return FakeResponse(202, "")
            return FakeResponse(
                200,
                """
                <div class="result">
                  <div class="result__title">
                    <a href="https://www.oneusefulthing.org/p/change-blindness">Change Blindness</a>
                  </div>
                  <div class="result__snippet">A Substack post on AI and perception.</div>
                </div>
                """,
            )

    results = await handler._duckduckgo_search(FakeSession(), "ai", 5)

    assert len(results) == 1
    assert results[0]["url"] == "https://www.oneusefulthing.org/p/change-blindness"
    assert results[0]["provider"] == "duckduckgo_html_alt"


@pytest.mark.asyncio
async def test_search_prefers_direct_results(monkeypatch):
    handler = ResearchHandler()

    async def fake_direct(session, query, max_results):
        return [{"url": "https://alpha.substack.com/p/post"}]

    async def fail_if_called(*args, **kwargs):
        raise AssertionError("fallback provider should not be called")

    monkeypatch.setattr(handler, "_direct_substack_search", fake_direct)
    monkeypatch.setattr(handler, "_duckduckgo_search", fail_if_called)
    monkeypatch.setattr(handler, "_bing_search", fail_if_called)

    results = await handler._search(object(), "alpha", 5)

    assert results == [{"url": "https://alpha.substack.com/p/post"}]


@pytest.mark.asyncio
async def test_search_prefers_duckduckgo_before_bing(monkeypatch):
    handler = ResearchHandler()

    async def fake_direct(session, query, max_results):
        return []

    async def fake_duckduckgo(session, query, max_results):
        return [{"url": "https://bravo.substack.com/p/post"}]

    async def fail_if_called(*args, **kwargs):
        raise AssertionError("bing should not be called when duckduckgo succeeds")

    monkeypatch.setattr(handler, "_direct_substack_search", fake_direct)
    monkeypatch.setattr(handler, "_duckduckgo_search", fake_duckduckgo)
    monkeypatch.setattr(handler, "_bing_search", fail_if_called)

    results = await handler._search(object(), "bravo", 5)

    assert results == [{"url": "https://bravo.substack.com/p/post"}]


@pytest.mark.asyncio
async def test_search_falls_back_to_bing_when_duckduckgo_is_empty(monkeypatch):
    handler = ResearchHandler()

    async def fake_direct(session, query, max_results):
        return []

    async def fake_duckduckgo(session, query, max_results):
        return []

    async def fake_bing(session, query, max_results):
        return [
            {
                "title": "SwiftUI Notes",
                "url": "https://builder.substack.com/p/swiftui-notes",
                "publication": "builder",
                "snippet": "Thoughts on SwiftUI performance.",
                "provider": "bing_html",
                "page_type": "post",
            }
        ]

    monkeypatch.setattr(handler, "_direct_substack_search", fake_direct)
    monkeypatch.setattr(handler, "_duckduckgo_search", fake_duckduckgo)
    monkeypatch.setattr(handler, "_bing_search", fake_bing)

    results = await handler._search(object(), "swiftui", 5)

    assert len(results) == 1
    assert results[0]["provider"] == "bing_html"


@pytest.mark.asyncio
async def test_direct_substack_search_uses_second_endpoint_after_first_failure(
    monkeypatch,
):
    handler = ResearchHandler()
    fetch_calls = []

    async def fake_fetch_text(session, url):
        fetch_calls.append(url)
        if len(fetch_calls) == 1:
            raise RuntimeError("temporary failure")
        return 200, "<html>results</html>"

    monkeypatch.setattr(handler, "_fetch_text", fake_fetch_text)
    monkeypatch.setattr(
        handler,
        "_parse_substack_search_html",
        lambda html_text: [
            {
                "title": "Parsed",
                "url": "https://alpha.substack.com/p/post",
                "publication": "alpha",
                "snippet": "Snippet",
                "provider": "substack_direct",
                "page_type": "post",
            }
        ],
    )

    results = await handler._direct_substack_search(object(), "alpha beta", 1)

    assert len(fetch_calls) == 2
    assert results == [
        {
            "title": "Parsed",
            "url": "https://alpha.substack.com/p/post",
            "publication": "alpha",
            "snippet": "Snippet",
            "provider": "substack_direct",
            "page_type": "post",
        }
    ]


def test_parse_substack_search_html_filters_blocked_and_empty_results():
    handler = ResearchHandler()
    html = """
    <html>
      <body>
        <a href="https://alpha.substack.com/p/valid-post">Alpha Post</a>
        <div>Deep analysis for operators</div>
        <a href="https://substack.com/sign-in">Sign in</a>
        <a href="https://beta.substack.com/p/empty">   </a>
      </body>
    </html>
    """

    results = handler._parse_substack_search_html(html)

    assert results == [
        {
            "title": "Alpha Post",
            "url": "https://alpha.substack.com/p/valid-post",
            "publication": "alpha",
            "snippet": "Deep analysis for operators Sign in",
            "provider": "substack_direct",
            "page_type": "post",
        }
    ]


@pytest.mark.asyncio
async def test_duckduckgo_search_returns_empty_after_recoverable_statuses():
    handler = ResearchHandler()
    handler._is_allowed_by_robots = AsyncMock(return_value=True)

    class FakeResponse:
        def __init__(self, status):
            self.status = status

        async def text(self):
            return ""

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakeSession:
        def __init__(self):
            self.calls = 0

        def get(self, url, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return FakeResponse(429)
            return FakeResponse(503)

    results = await handler._duckduckgo_search(FakeSession(), "operators", 5)

    assert results == []


@pytest.mark.asyncio
async def test_bing_search_parses_only_researchable_results(monkeypatch):
    handler = ResearchHandler()

    async def fake_fetch_text(session, url):
        return (
            200,
            """
            <ul>
              <li class="b_algo">
                <h2><a href="https://alpha.substack.com/p/valid-post">Alpha</a></h2>
                <div class="b_caption"><p>Useful post.</p></div>
              </li>
              <li class="b_algo">
                <h2><a href="https://substack.com/sign-in">Blocked</a></h2>
              </li>
              <li class="b_algo">
                <div class="b_caption"><p>No link here.</p></div>
              </li>
            </ul>
            """,
        )

    monkeypatch.setattr(handler, "_fetch_text", fake_fetch_text)

    results = await handler._bing_search(object(), "alpha", 5)

    assert results == [
        {
            "title": "Alpha",
            "url": "https://alpha.substack.com/p/valid-post",
            "publication": "alpha",
            "snippet": "Useful post.",
            "provider": "bing_html",
            "page_type": "post",
        }
    ]


def test_parse_duckduckgo_html_respects_filters_and_max_results():
    handler = ResearchHandler()
    html = """
    <div class="result">
      <div class="result__title">
        <a href="https://alpha.substack.com/p/one">Alpha One</a>
      </div>
      <div class="result__snippet">Useful alpha analysis.</div>
    </div>
    <div class="result">
      <div class="result__title">
        <a href="https://substack.com/sign-in">Blocked</a>
      </div>
      <div class="result__snippet">Should be ignored.</div>
    </div>
    <div class="result">
      <div class="result__title">
        <a href="https://bravo.substack.com/p/two">Bravo Two</a>
      </div>
      <div class="result__snippet">Useful bravo analysis.</div>
    </div>
    """

    results = handler._parse_duckduckgo_html(html, "duckduckgo_html", 1)

    assert results == [
        {
            "title": "Alpha One",
            "url": "https://alpha.substack.com/p/one",
            "publication": "alpha",
            "snippet": "Useful alpha analysis.",
            "provider": "duckduckgo_html",
            "page_type": "post",
        }
    ]


def test_result_is_not_credible_for_custom_domain_without_enrichment():
    handler = ResearchHandler()

    result = {
        "title": "turn on JavaScript | enable-javascript.com",
        "url": "https://enable-javascript.com/",
        "snippet": "This site requires JavaScript to run correctly.",
    }

    assert handler._result_is_credible(result, {}) is False


def test_result_is_credible_for_custom_domain_with_enrichment():
    handler = ResearchHandler()

    result = {
        "title": "Credible custom domain",
        "url": "https://www.oneusefulthing.org/p/change-blindness",
        "snippet": "A credible custom-domain post.",
    }

    assert handler._result_is_credible(result, {"resolved_title": "Change Blindness"})


@pytest.mark.asyncio
async def test_inspect_url_accepts_custom_domain_post(monkeypatch):
    handler = ResearchHandler()

    class DummySession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    async def fake_fetch_page_details(session, url):
        return {
            "resolved_url": url,
            "resolved_title": "Change Blindness",
            "description": "AI, cognition, and perception.",
            "author": "Ethan Mollick",
            "published_at": "2026-01-01T00:00:00Z",
            "body_excerpt": "Why smart people miss obvious changes.",
            "page_type": "post",
            "publication": "oneusefulthing.org",
        }

    monkeypatch.setattr(
        "src.handlers.research_handler.aiohttp.ClientSession",
        lambda **kwargs: DummySession(),
    )
    monkeypatch.setattr(handler, "_fetch_page_details", fake_fetch_page_details)

    result = await handler.inspect_url(
        "https://www.oneusefulthing.org/p/change-blindness"
    )

    assert result["url"] == "https://www.oneusefulthing.org/p/change-blindness"
    assert result["publication"] == "oneusefulthing.org"


@pytest.mark.asyncio
async def test_inspect_url_rejects_invalid_input():
    handler = ResearchHandler()

    with pytest.raises(
        ValueError, match="Please provide a public Substack post or publication URL"
    ):
        await handler.inspect_url("notaurl")


@pytest.mark.asyncio
async def test_rate_limit_host_sleeps_on_rapid_repeat(monkeypatch):
    handler = ResearchHandler()
    sleep_calls = []

    async def fake_sleep(delay):
        sleep_calls.append(delay)

    timestamps = chain([10.0, 10.2, 11.4, 12.0], repeat(13.0))
    monkeypatch.setattr("src.handlers.research_handler.asyncio.sleep", fake_sleep)
    monkeypatch.setattr(
        "src.handlers.research_handler.time.monotonic", lambda: next(timestamps)
    )

    await handler._rate_limit_host("example.com")
    await handler._rate_limit_host("example.com")

    assert sleep_calls == [pytest.approx(0.8)]


@pytest.mark.asyncio
async def test_robots_txt_blocks_disallowed_publish_paths():
    handler = ResearchHandler()

    class FakeResponse:
        def __init__(self, status, body):
            self.status = status
            self._body = body

        async def text(self):
            return self._body

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakeSession:
        def get(self, url):
            assert url == "https://example.substack.com/robots.txt"
            return FakeResponse(200, "User-agent: *\nDisallow: /publish\n")

    allowed = await handler._is_allowed_by_robots(
        FakeSession(),
        "https://example.substack.com/publish/post/123",
    )

    assert allowed is False


@pytest.mark.asyncio
async def test_robots_txt_non_200_and_fetch_errors_default_to_allowed(monkeypatch):
    handler = ResearchHandler()

    class FakeResponse:
        def __init__(self, status):
            self.status = status

        async def text(self):
            return ""

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class Non200Session:
        def get(self, url):
            return FakeResponse(404)

    class ErrorSession:
        def get(self, url):
            raise RuntimeError("network down")

    monkeypatch.setattr(handler, "_rate_limit_host", AsyncMock())

    assert (
        await handler._is_allowed_by_robots(
            Non200Session(),
            "https://example.substack.com/p/test-post",
        )
        is True
    )
    assert (
        await handler._is_allowed_by_robots(
            ErrorSession(),
            "https://error.substack.com/p/test-post",
        )
        is True
    )


@pytest.mark.asyncio
async def test_fetch_text_raises_when_robots_disallow(monkeypatch):
    handler = ResearchHandler()
    monkeypatch.setattr(handler, "_is_allowed_by_robots", AsyncMock(return_value=False))

    with pytest.raises(ValueError, match="robots.txt disallows fetching"):
        await handler._fetch_text(object(), "https://example.substack.com/p/post")


def test_page_looks_like_substack_from_footer_markers():
    handler = ResearchHandler()
    html = """
    <html>
      <body>
        <div>Ready for more?</div>
        <a href="https://substack.com/privacy">Privacy</a>
        <a href="https://substack.com/terms">Terms</a>
        <div>Start your Substack</div>
        <div>This site requires JavaScript to run correctly.</div>
      </body>
    </html>
    """

    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    assert (
        handler._page_looks_like_substack(
            soup,
            "https://www.oneusefulthing.org/p/change-blindness",
            "https://www.oneusefulthing.org/p/change-blindness",
        )
        is True
    )


def test_research_warnings_are_present_when_empty():
    handler = ResearchHandler()

    warnings = handler._research_warnings([])

    assert warnings
    assert "No credible public Substack results" in warnings[0]


@pytest.mark.asyncio
async def test_enrich_results_keeps_empty_dict_on_fetch_failure(monkeypatch):
    handler = ResearchHandler()

    async def fake_fetch_page_details(session, url):
        if "broken" in url:
            raise RuntimeError("boom")
        return {"resolved_url": url, "description": "ok"}

    monkeypatch.setattr(handler, "_fetch_page_details", fake_fetch_page_details)

    enriched = await handler._enrich_results(
        object(),
        [
            {"url": "https://alpha.substack.com/p/ok"},
            {"url": "https://alpha.substack.com/p/broken"},
        ],
    )

    assert enriched["https://alpha.substack.com/p/ok"]["description"] == "ok"
    assert enriched["https://alpha.substack.com/p/broken"] == {}


@pytest.mark.asyncio
async def test_fetch_page_details_extracts_metadata_and_excerpt(monkeypatch):
    handler = ResearchHandler()
    html = """
    <html>
      <head>
        <meta property="og:title" content="Alpha Post" />
        <meta name="description" content="Alpha description" />
        <meta name="author" content="Alpha Author" />
        <meta property="article:published_time" content="2026-05-01T00:00:00Z" />
        <meta name="generator" content="Substack" />
        <link rel="canonical" href="https://alpha.substack.com/p/alpha-post" />
      </head>
      <body>
        <article>
          <p>This is a sufficiently long paragraph for the body excerpt extractor.</p>
          <p>This is another long paragraph that should also appear in the excerpt.</p>
        </article>
      </body>
    </html>
    """

    async def fake_fetch_text(session, url, allow_redirects=False):
        assert allow_redirects is True
        return 200, html

    monkeypatch.setattr(handler, "_fetch_text", fake_fetch_text)

    details = await handler._fetch_page_details(
        object(), "https://alpha.substack.com/p/alpha-post"
    )

    assert details["resolved_title"] == "Alpha Post"
    assert details["description"] == "Alpha description"
    assert details["author"] == "Alpha Author"
    assert details["published_at"] == "2026-05-01T00:00:00Z"
    assert details["page_type"] == "post"
    assert details["publication"] == "alpha"
    assert "sufficiently long paragraph" in details["body_excerpt"]


@pytest.mark.asyncio
async def test_fetch_page_details_rejects_non_substack_pages(monkeypatch):
    handler = ResearchHandler()

    async def fake_fetch_text(session, url, allow_redirects=False):
        return 200, "<html><body><p>Plain site</p></body></html>"

    monkeypatch.setattr(handler, "_fetch_text", fake_fetch_text)

    with pytest.raises(
        ValueError, match="does not appear to be a public Substack page"
    ):
        await handler._fetch_page_details(object(), "https://example.com/post")


def test_helper_methods_cover_deduping_summary_and_url_classification():
    handler = ResearchHandler()
    soup = BeautifulSoup(
        """
        <html>
          <head>
            <meta name="description" content="  Alpha   description  " />
            <link rel="canonical" href="https://alpha.substack.com/p/alpha-post" />
          </head>
          <body>
            <div class="wrap">
              <a href="https://alpha.substack.com/p/alpha-post">Alpha title</a>
              Helpful trailing context for the anchor.
            </div>
            <script src="/static/substack.js"></script>
          </body>
        </html>
        """,
        "html.parser",
    )
    anchor = soup.select_one("a")
    assert anchor is not None
    script_tag = soup.select_one("script")
    assert script_tag is not None

    assert handler._dedupe_results(
        [
            {"url": "https://alpha.substack.com/p/post"},
            {"url": "https://alpha.substack.com/p/post/"},
            {"url": "https://bravo.substack.com/"},
        ]
    ) == [
        {"url": "https://alpha.substack.com/p/post"},
        {"url": "https://bravo.substack.com/"},
    ]
    assert handler._publication_leaders(
        [
            {"publication": "alpha"},
            {"publication": "alpha"},
            {"publication": "bravo"},
        ]
    ) == [
        {"publication": "alpha", "mentions": 2},
        {"publication": "bravo", "mentions": 1},
    ]
    assert (
        handler._build_result_summary(
            {"snippet": "Snippet"},
            {"description": "Description", "body_excerpt": "Excerpt"},
        )
        == "Description Excerpt"
    )
    assert handler._body_excerpt(soup) == ""
    assert handler._meta_content(soup, "name", "description") == "Alpha description"
    assert handler._canonical_url(soup) == "https://alpha.substack.com/p/alpha-post"
    assert "Helpful trailing context" in handler._nearest_text(anchor)
    assert handler._publication_from_url("https://www.oneusefulthing.org/p/post") == (
        "oneusefulthing.org"
    )
    assert handler._classify_url("https://alpha.substack.com/@author") == "profile"
    assert handler._classify_url("https://alpha.substack.com/archive") == "archive"
    assert (
        handler._classify_url("https://alpha.substack.com/about") == "publication_page"
    )
    assert handler._looks_like_public_substack_path("/p/alpha-post")
    assert not handler._looks_like_public_substack_path("/about")
    assert handler._normalize_candidate_url("//alpha.substack.com/p/alpha-post") == (
        "https://alpha.substack.com/p/alpha-post"
    )
    assert handler._normalize_candidate_url("javascript:void(0)") == ""
    assert (
        handler._page_looks_like_substack(
            soup,
            "https://alpha.substack.com/p/alpha-post",
            "https://alpha.substack.com/p/alpha-post",
        )
        is True
    )
    assert handler._tag_attr(script_tag, "class") == ""


def test_page_looks_like_substack_returns_false_without_markers():
    handler = ResearchHandler()
    soup = BeautifulSoup("<html><body><p>Plain site</p></body></html>", "html.parser")

    assert (
        handler._page_looks_like_substack(
            soup,
            "https://example.com/post",
            "https://example.com/post",
        )
        is False
    )
