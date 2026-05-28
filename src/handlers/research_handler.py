# ABOUTME: ResearchHandler discovers and analyzes Substack posts/publications
# ABOUTME: Uses hybrid search providers with page extraction and lightweight synthesis

import asyncio
import html
import logging
import re
import time
from collections import Counter
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, quote_plus, unquote, urljoin, urlparse
from urllib.robotparser import RobotFileParser

import aiohttp
from bs4 import BeautifulSoup, Tag

from src.version import SERVER_VERSION

logger = logging.getLogger(__name__)

STOP_WORDS = {
    "a",
    "about",
    "after",
    "all",
    "also",
    "an",
    "and",
    "any",
    "are",
    "as",
    "at",
    "be",
    "because",
    "been",
    "before",
    "being",
    "between",
    "both",
    "but",
    "by",
    "can",
    "could",
    "for",
    "from",
    "get",
    "got",
    "had",
    "has",
    "have",
    "how",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "just",
    "may",
    "more",
    "most",
    "new",
    "not",
    "of",
    "on",
    "or",
    "our",
    "out",
    "over",
    "so",
    "some",
    "such",
    "than",
    "that",
    "the",
    "their",
    "them",
    "there",
    "these",
    "they",
    "this",
    "to",
    "up",
    "use",
    "using",
    "was",
    "we",
    "were",
    "what",
    "when",
    "which",
    "who",
    "why",
    "will",
    "with",
    "you",
    "your",
}

NOISE_WORDS = {
    "amp",
    "article",
    "articles",
    "button",
    "buttons",
    "click",
    "com",
    "draft",
    "editor",
    "embed",
    "footer",
    "header",
    "home",
    "html",
    "http",
    "https",
    "newsletter",
    "page",
    "pages",
    "post",
    "posts",
    "published",
    "publication",
    "read",
    "section",
    "sections",
    "substack",
    "untitled",
    "www",
}

BLOCKED_PATH_PREFIXES = ("/api/", "/signin", "/sign-in", "/account", "/publish")
SEARCH_RESULT_HOSTS = {"duckduckgo.com", "html.duckduckgo.com"}
BLACKLISTED_RESULT_HOSTS = {"enable-javascript.com"}
BLACKLISTED_RESULT_PHRASES = {
    "turn on javascript",
    "enable javascript",
    "javascript required",
    "this site requires javascript",
    "browser settings",
}


def sanitize_text_for_topics(text: str) -> str:
    """Strip low-signal web and markdown noise before token analysis."""
    cleaned = html.unescape(text or "")
    cleaned = re.sub(r"https?://\S+", " ", cleaned)
    cleaned = re.sub(r"www\.\S+", " ", cleaned)
    cleaned = re.sub(r"\[[^\]]*\]\([^)]+\)", " ", cleaned)
    cleaned = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", cleaned)
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)
    cleaned = re.sub(r"`{1,3}[^`]*`{1,3}", " ", cleaned)
    cleaned = re.sub(r"[#/\\|_*~>\-]+", " ", cleaned)
    cleaned = re.sub(r"\b[a-z0-9-]+\.(com|org|net|io|dev|app|co)\b", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def extract_meaningful_tokens(text: str) -> List[str]:
    """Extract topic-like tokens while filtering boilerplate and editor sludge."""
    tokens = re.findall(
        r"[a-zA-Z][a-zA-Z0-9-]{1,}", sanitize_text_for_topics(text).lower()
    )
    filtered = []
    for token in tokens:
        if token in STOP_WORDS or token in NOISE_WORDS:
            continue
        if token.endswith(("jpg", "jpeg", "png", "gif", "webp")):
            continue
        if token.isdigit():
            continue
        filtered.append(token)
    return filtered


class ResearchHandler:
    """Discovers and summarizes Substack research results."""

    USER_AGENT = (
        f"substack-mcp-research/{SERVER_VERSION} "
        "(+https://github.com/IgnazioDS/Substak-MCP)"
    )

    def __init__(self) -> None:
        self._robots_cache: Dict[str, RobotFileParser | None] = {}
        self._last_request_by_host: Dict[str, float] = {}

    async def research_substack(
        self,
        query: str,
        max_results: int = 25,
        deep_read_count: int = 5,
    ) -> Dict[str, Any]:
        """Search Substack content, fetch top pages, and synthesize findings."""
        if not query or not isinstance(query, str):
            raise ValueError("query must be a non-empty string")

        max_results = max(5, min(max_results, 30))
        deep_read_count = max(1, min(deep_read_count, 5))

        async with aiohttp.ClientSession(
            headers={"User-Agent": self.USER_AGENT},
            timeout=aiohttp.ClientTimeout(total=25),
        ) as session:
            raw_results = await self._search(session, query, max_results)
            normalized_results = self._dedupe_results(raw_results)[:max_results]

            enrichment_targets = normalized_results[
                : max(deep_read_count * 2, deep_read_count)
            ]
            enriched_lookup = await self._enrich_results(session, enrichment_targets)

        final_results = []
        for result in normalized_results:
            enriched = enriched_lookup.get(result["url"], {})
            if not self._result_is_credible(result, enriched):
                continue
            final_results.append(
                {
                    **result,
                    **enriched,
                    "summary": self._build_result_summary(result, enriched),
                }
            )

        themes = self._extract_themes(final_results)
        recommendations = self._build_recommendations(final_results)
        publication_candidates = self._publication_leaders(final_results)

        return {
            "query": query,
            "search_strategy": "direct_substack_then_html_search_fallbacks",
            "results_found": len(final_results),
            "results": final_results,
            "themes": themes,
            "recommended_to_study": recommendations,
            "publication_leaders": publication_candidates,
            "warnings": self._research_warnings(final_results),
        }

    async def inspect_url(self, url: str) -> Dict[str, Any]:
        """Fetch and normalize details for a specific Substack URL."""
        normalized_input_url = self._normalize_candidate_url(url)
        if not normalized_input_url:
            raise ValueError("Please provide a public Substack post or publication URL")

        async with aiohttp.ClientSession(
            headers={"User-Agent": self.USER_AGENT},
            timeout=aiohttp.ClientTimeout(total=25),
        ) as session:
            details = await self._fetch_page_details(session, normalized_input_url)

        base = {
            "title": details.get("resolved_title") or normalized_input_url,
            "url": normalized_input_url,
            **details,
        }
        base["summary"] = self._build_result_summary(base, details)
        return base

    async def _search(
        self, session: aiohttp.ClientSession, query: str, max_results: int
    ) -> List[Dict[str, Any]]:
        direct_results = await self._direct_substack_search(session, query, max_results)
        if direct_results:
            return direct_results

        duckduckgo_results = await self._duckduckgo_search(session, query, max_results)
        if duckduckgo_results:
            return duckduckgo_results

        return await self._bing_search(session, query, max_results)

    async def _direct_substack_search(
        self, session: aiohttp.ClientSession, query: str, max_results: int
    ) -> List[Dict[str, Any]]:
        urls = [
            f"https://substack.com/search?query={quote_plus(query)}",
            f"https://substack.com/search/{quote_plus(query)}",
        ]

        for url in urls:
            try:
                status, html_text = await self._fetch_text(session, url)
                if status != 200:
                    continue
                results = self._parse_substack_search_html(html_text)
                if results:
                    logger.info(
                        "Direct Substack search returned %s results", len(results)
                    )
                    return results[:max_results]
            except Exception as exc:
                logger.debug("Direct Substack search failed for %s: %s", url, exc)
                continue
        return []

    def _parse_substack_search_html(self, html_text: str) -> List[Dict[str, Any]]:
        soup = BeautifulSoup(html_text, "html.parser")
        results: List[Dict[str, Any]] = []

        for anchor in soup.select("a[href]"):
            href = self._normalize_candidate_url(self._tag_attr(anchor, "href").strip())
            if not self._is_researchable_substack_url(href):
                continue
            title = self._clean_text(anchor.get_text(" ", strip=True))
            if not title:
                continue
            snippet = self._nearest_text(anchor)
            if self._looks_like_junk_result(href, title, snippet):
                continue
            results.append(
                {
                    "title": title,
                    "url": href,
                    "publication": self._publication_from_url(href),
                    "snippet": snippet,
                    "provider": "substack_direct",
                    "page_type": self._classify_url(href),
                }
            )
        return results

    async def _duckduckgo_search(
        self, session: aiohttp.ClientSession, query: str, max_results: int
    ) -> List[Dict[str, Any]]:
        search_urls = [
            (
                "duckduckgo_html",
                "https://html.duckduckgo.com/html/?q="
                + quote_plus(f"site:substack.com OR inurl:/p/ {query}"),
            ),
            (
                "duckduckgo_html_alt",
                "https://duckduckgo.com/html/?q="
                + quote_plus(f"site:substack.com OR inurl:/p/ {query}"),
            ),
        ]
        recoverable_statuses = {202, 429, 503}
        last_status: Optional[int] = None

        for provider_name, search_url in search_urls:
            try:
                last_status, html_text = await self._fetch_text(session, search_url)
                if last_status in recoverable_statuses:
                    logger.warning(
                        "%s returned recoverable status %s for query %r",
                        provider_name,
                        last_status,
                        query,
                    )
                    continue
                if last_status != 200:
                    logger.warning(
                        "%s returned status %s for query %r",
                        provider_name,
                        last_status,
                        query,
                    )
                    continue
            except Exception as exc:
                logger.warning("%s failed for query %r: %s", provider_name, query, exc)
                continue

            results = self._parse_duckduckgo_html(html_text, provider_name, max_results)
            if results:
                return results

        if last_status in recoverable_statuses:
            logger.warning(
                "DuckDuckGo search providers were rate-limited or deferred for query %r",
                query,
            )
        return []

    async def _bing_search(
        self, session: aiohttp.ClientSession, query: str, max_results: int
    ) -> List[Dict[str, Any]]:
        search_url = "https://www.bing.com/search?q=" + quote_plus(
            f"site:substack.com OR inurl:/p/ {query}"
        )
        try:
            status, html_text = await self._fetch_text(session, search_url)
            if status != 200:
                logger.warning(
                    "Bing search returned status %s for query %r",
                    status,
                    query,
                )
                return []
        except Exception as exc:
            logger.warning("Bing search failed for query %r: %s", query, exc)
            return []

        soup = BeautifulSoup(html_text, "html.parser")
        results: List[Dict[str, Any]] = []
        for item in soup.select("li.b_algo"):
            link = item.select_one("h2 a")
            if not link:
                continue
            href = self._normalize_candidate_url(self._tag_attr(link, "href").strip())
            if not self._is_researchable_substack_url(href):
                continue
            title = self._clean_text(link.get_text(" ", strip=True))
            snippet_node = item.select_one(".b_caption p")
            snippet = (
                self._clean_text(snippet_node.get_text(" ", strip=True))
                if snippet_node
                else ""
            )
            if self._looks_like_junk_result(href, title, snippet):
                continue
            results.append(
                {
                    "title": title or href,
                    "url": href,
                    "publication": self._publication_from_url(href),
                    "snippet": snippet,
                    "provider": "bing_html",
                    "page_type": self._classify_url(href),
                }
            )
            if len(results) >= max_results:
                break
        return results

    def _parse_duckduckgo_html(
        self, html_text: str, provider_name: str, max_results: int
    ) -> List[Dict[str, Any]]:
        soup = BeautifulSoup(html_text, "html.parser")
        results: List[Dict[str, Any]] = []

        for item in soup.select(".result"):
            link = item.select_one(".result__title a")
            if not link:
                continue

            href = self._normalize_candidate_url(self._tag_attr(link, "href").strip())
            if not self._is_researchable_substack_url(href):
                continue

            title = self._clean_text(link.get_text(" ", strip=True))
            snippet_node = item.select_one(".result__snippet")
            snippet = (
                self._clean_text(snippet_node.get_text(" ", strip=True))
                if snippet_node
                else ""
            )
            if self._looks_like_junk_result(href, title, snippet):
                continue
            results.append(
                {
                    "title": title or href,
                    "url": href,
                    "publication": self._publication_from_url(href),
                    "snippet": snippet,
                    "provider": provider_name,
                    "page_type": self._classify_url(href),
                }
            )
            if len(results) >= max_results:
                break

        return results

    def _looks_like_junk_result(self, url: str, title: str, snippet: str) -> bool:
        host = urlparse(url).netloc.lower().replace("www.", "")
        if host in BLACKLISTED_RESULT_HOSTS:
            return True

        haystack = " ".join(filter(None, [title, snippet, url])).lower()
        return any(phrase in haystack for phrase in BLACKLISTED_RESULT_PHRASES)

    async def _enrich_results(
        self, session: aiohttp.ClientSession, results: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        enriched: Dict[str, Dict[str, Any]] = {}
        for result in results:
            try:
                enriched[result["url"]] = await self._fetch_page_details(
                    session, result["url"]
                )
            except Exception as exc:
                logger.debug("Failed to enrich %s: %s", result["url"], exc)
                enriched[result["url"]] = {}
        return enriched

    async def _fetch_page_details(
        self, session: aiohttp.ClientSession, url: str
    ) -> Dict[str, Any]:
        status, html_text = await self._fetch_text(session, url, allow_redirects=True)
        if status != 200:
            raise RuntimeError(f"Page fetch failed with status {status}")

        soup = BeautifulSoup(html_text, "html.parser")
        title = self._meta_content(soup, "property", "og:title") or self._meta_content(
            soup, "name", "twitter:title"
        )
        description = self._meta_content(
            soup, "name", "description"
        ) or self._meta_content(soup, "property", "og:description")
        author = self._meta_content(soup, "name", "author")
        canonical = self._canonical_url(soup) or url
        if not self._page_looks_like_substack(soup, canonical, url):
            raise ValueError("URL does not appear to be a public Substack page")
        published_at = self._meta_content(soup, "property", "article:published_time")
        body_excerpt = self._body_excerpt(soup)

        return {
            "resolved_url": canonical,
            "resolved_title": title,
            "description": description,
            "author": author,
            "published_at": published_at,
            "body_excerpt": body_excerpt,
            "page_type": self._classify_url(canonical),
            "publication": self._publication_from_url(canonical),
        }

    async def _rate_limit_host(self, host: str) -> None:
        """Enforce a 1 request/second pace per host."""
        now = time.monotonic()
        last_request = self._last_request_by_host.get(host)
        if last_request is not None:
            delay = 1.0 - (now - last_request)
            if delay > 0:
                await asyncio.sleep(delay)
                now = time.monotonic()
        self._last_request_by_host[host] = now

    async def _is_allowed_by_robots(
        self, session: aiohttp.ClientSession, url: str
    ) -> bool:
        """Check robots.txt for the target URL."""
        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        parser = self._robots_cache.get(base_url)
        if parser is None:
            parser = RobotFileParser()
            robots_url = f"{base_url}/robots.txt"
            try:
                await self._rate_limit_host(parsed.netloc)
                async with session.get(robots_url) as response:
                    if response.status != 200:
                        self._robots_cache[base_url] = None
                        return True
                    parser.parse((await response.text()).splitlines())
                    self._robots_cache[base_url] = parser
            except Exception:
                self._robots_cache[base_url] = None
                return True

        cached_parser = self._robots_cache.get(base_url)
        if cached_parser is None:
            return True
        return cached_parser.can_fetch(self.USER_AGENT, url)

    async def _fetch_text(
        self,
        session: aiohttp.ClientSession,
        url: str,
        *,
        allow_redirects: bool = False,
    ) -> tuple[int, str]:
        """Fetch a page after robots and rate-limit checks."""
        parsed = urlparse(url)
        if not await self._is_allowed_by_robots(session, url):
            raise ValueError(f"robots.txt disallows fetching {url}")

        await self._rate_limit_host(parsed.netloc)
        async with session.get(url, allow_redirects=allow_redirects) as response:
            return response.status, await response.text()

    def _dedupe_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        deduped = []
        seen = set()
        for result in results:
            normalized_url = result["url"].rstrip("/")
            if normalized_url in seen:
                continue
            seen.add(normalized_url)
            deduped.append(result)
        return deduped

    def _extract_themes(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        token_counter: Counter[str] = Counter()
        for result in results[:12]:
            source_text = " ".join(
                filter(
                    None,
                    [
                        result.get("title"),
                        result.get("snippet"),
                        result.get("description"),
                        result.get("body_excerpt"),
                    ],
                )
            )
            token_counter.update(self._theme_tokens(source_text))

        themes = []
        for token, count in token_counter.most_common(8):
            themes.append(
                {
                    "theme": token,
                    "mentions": count,
                }
            )
        return themes

    def _build_recommendations(
        self, results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        ranked = []
        for result in results:
            score = 0
            if result.get("description"):
                score += 2
            if result.get("body_excerpt"):
                score += 2
            if result.get("author"):
                score += 1
            if result.get("page_type") == "post":
                score += 2
            if result.get("page_type") == "publication":
                score += 1
            if result.get("provider") == "substack_direct":
                score += 1

            rationale_parts = []
            if result.get("page_type") == "post":
                rationale_parts.append("specific post with enough text to analyze")
            if result.get("page_type") == "publication":
                rationale_parts.append("publication-level source worth tracking")
            if result.get("description"):
                rationale_parts.append("clear description metadata")
            if result.get("author"):
                rationale_parts.append(f"author visible: {result['author']}")

            ranked.append(
                {
                    "title": result.get("resolved_title") or result.get("title"),
                    "url": result.get("resolved_url") or result.get("url"),
                    "publication": result.get("publication"),
                    "why_study": ", ".join(rationale_parts) or "high-signal result",
                    "score": score,
                }
            )

        ranked.sort(key=lambda item: float(item.get("score") or 0), reverse=True)
        return ranked[:5]

    def _publication_leaders(
        self, results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        counts: Counter[str] = Counter()
        for result in results:
            publication = result.get("publication")
            if publication:
                counts[publication] += 1

        leaders = []
        for publication, mentions in counts.most_common(5):
            leaders.append({"publication": publication, "mentions": mentions})
        return leaders

    def _build_result_summary(
        self, result: Dict[str, Any], enriched: Dict[str, Any]
    ) -> str:
        parts = []
        snippet = enriched.get("description") or result.get("snippet")
        if snippet:
            parts.append(snippet)
        excerpt = enriched.get("body_excerpt")
        if excerpt and excerpt not in parts:
            parts.append(excerpt)
        summary = " ".join(parts).strip()
        return summary[:320]

    def _research_warnings(self, results: List[Dict[str, Any]]) -> List[str]:
        if results:
            return []
        return [
            "No credible public Substack results were found for this query from the available discovery providers."
        ]

    def _result_is_credible(
        self, result: Dict[str, Any], enriched: Dict[str, Any]
    ) -> bool:
        url = result.get("url", "")
        title = result.get("resolved_title") or result.get("title", "")
        snippet = (
            result.get("summary")
            or result.get("description")
            or result.get("snippet", "")
        )

        if self._looks_like_junk_result(url, title, snippet):
            return False

        host = urlparse(url).netloc.lower()
        if host.endswith(".substack.com"):
            return True

        if enriched:
            return True

        return False

    def _theme_tokens(self, text: str) -> List[str]:
        return extract_meaningful_tokens(text)

    def _body_excerpt(self, soup: BeautifulSoup) -> str:
        paragraphs = []
        for node in soup.select("article p, main p, .body p, .available-content p"):
            text = self._clean_text(node.get_text(" ", strip=True))
            if len(text) >= 40:
                paragraphs.append(text)
            if len(paragraphs) >= 2:
                break
        return " ".join(paragraphs)[:280]

    def _meta_content(
        self, soup: BeautifulSoup, attr_name: str, attr_value: str
    ) -> str:
        tag = soup.find("meta", attrs={attr_name: attr_value})
        if tag and tag.get("content"):
            return self._clean_text(self._tag_attr(tag, "content"))
        return ""

    def _canonical_url(self, soup: BeautifulSoup) -> str:
        canonical = soup.find("link", rel="canonical")
        if canonical and canonical.get("href"):
            return self._tag_attr(canonical, "href").strip()
        return ""

    def _clean_text(self, text: str) -> str:
        normalized = html.unescape(text or "")
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized

    def _nearest_text(self, anchor: Tag) -> str:
        parent = anchor.parent
        if not parent:
            return ""
        text = self._clean_text(parent.get_text(" ", strip=True))
        anchor_text = self._clean_text(anchor.get_text(" ", strip=True))
        text = text.replace(anchor_text, "", 1).strip(" -:\n")
        return text[:220]

    def _publication_from_url(self, url: str) -> str:
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        if host.endswith(".substack.com"):
            return host.split(".substack.com")[0]
        return host.replace("www.", "")

    def _classify_url(self, url: str) -> str:
        parsed = urlparse(url)
        path = parsed.path.strip("/")
        if not path:
            return "publication"
        if path.startswith("p/"):
            return "post"
        if path.startswith("@"):
            return "profile"
        if path.startswith("archive"):
            return "archive"
        return "publication_page"

    def _is_researchable_substack_url(self, url: str) -> bool:
        if not url:
            return False
        normalized = self._normalize_candidate_url(url)
        if not normalized:
            return False
        parsed = urlparse(normalized)
        path = parsed.path or "/"
        if path.startswith(BLOCKED_PATH_PREFIXES):
            return False
        host = parsed.netloc.lower()
        if host.endswith(".substack.com"):
            return True
        if host in SEARCH_RESULT_HOSTS:
            return False
        return self._looks_like_public_substack_path(path)

    def _looks_like_public_substack_path(self, path: str) -> bool:
        trimmed = path.strip("/")
        if not trimmed:
            return True
        return (
            trimmed.startswith("p/")
            or trimmed.startswith("archive")
            or trimmed.startswith("@")
        )

    def _normalize_candidate_url(self, url: str) -> str:
        if not url:
            return ""
        candidate = url.strip()
        if candidate.startswith("//"):
            candidate = f"https:{candidate}"
        if not candidate.startswith(("http://", "https://")):
            return ""

        parsed = urlparse(candidate)
        host = parsed.netloc.lower()
        if host in SEARCH_RESULT_HOSTS and parsed.path.startswith("/l/"):
            wrapped = parse_qs(parsed.query).get("uddg", [])
            if wrapped:
                return self._normalize_candidate_url(unquote(wrapped[0]))
        if host in SEARCH_RESULT_HOSTS:
            return ""

        normalized = parsed._replace(fragment="").geturl()
        if normalized.endswith("/") and parsed.path not in ("", "/"):
            normalized = normalized.rstrip("/")
        return normalized

    def _page_looks_like_substack(
        self, soup: BeautifulSoup, resolved_url: str, original_url: str
    ) -> bool:
        generator = self._meta_content(soup, "name", "generator").lower()
        if "substack" in generator:
            return True

        if "substack.com" in urlparse(resolved_url).netloc.lower():
            return True
        if "substack.com" in urlparse(original_url).netloc.lower():
            return True

        for tag in soup.select("script[src], link[href]"):
            asset_url = self._tag_attr(tag, "src") or self._tag_attr(tag, "href")
            absolute = urljoin(resolved_url or original_url, asset_url)
            if "substack.com" in absolute:
                return True

        for anchor in soup.select("a[href]"):
            href = self._tag_attr(anchor, "href")
            absolute = urljoin(resolved_url or original_url, href)
            if "substack.com" in absolute:
                return True

        visible_text = self._clean_text(soup.get_text(" ", strip=True)).lower()
        substack_text_markers = [
            "start your substack",
            "this site requires javascript to run correctly",
            "substack is the home for great culture",
        ]
        if any(marker in visible_text for marker in substack_text_markers):
            return True

        return False

    def _tag_attr(self, tag: Tag, attribute: str) -> str:
        """Return a BeautifulSoup attribute as a plain string."""
        value = tag.get(attribute, "")
        if isinstance(value, list):
            return " ".join(str(item) for item in value)
        return str(value or "")
