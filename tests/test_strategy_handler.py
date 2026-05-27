from src.handlers.strategy_handler import StrategyHandler
from unittest.mock import AsyncMock
import pytest


def test_analyze_post_collection_filters_url_and_embed_noise():
    handler = StrategyHandler()

    posts = [
        {
            "title": "SwiftUI async image loading",
            "content": (
                "Here is the real lesson about AsyncImage caching. "
                "https://cdn.example.com/embed/post and com embed post should not dominate. "
                "SwiftUI image caching matters for scrolling performance."
            ),
        }
    ]

    result = handler.analyze_post_collection(posts)
    theme_names = {item["theme"] for item in result["themes"]}

    assert "swiftui" in theme_names
    assert "https" not in theme_names
    assert "com" not in theme_names
    assert "embed" not in theme_names
    assert "post" not in theme_names
    assert "button" not in theme_names
    assert "editor" not in theme_names
    assert "published" not in theme_names


def test_study_topic_on_substack_surfaces_empty_result_warning():
    handler = StrategyHandler()

    result = handler.study_topic_on_substack(
        "AI for work",
        {
            "themes": [],
            "recommended_to_study": [],
            "warnings": [
                "No credible public Substack results were found for this query from the available discovery providers."
            ],
        },
    )

    assert result["study_order"] == []
    assert result["warnings"]
    assert "No strong Substack sources" in result["warnings"][-1]


@pytest.mark.asyncio
async def test_research_post_url_summarizes_inspected_post():
    handler = StrategyHandler()
    handler.research_handler.inspect_url = AsyncMock(
        return_value={
            "resolved_title": "How to ship calmly",
            "resolved_url": "https://example.com/p/ship-calmly",
            "publication": "Calm Builder",
            "author": "A Builder",
            "published_at": "2026-01-01",
            "summary": "A practical post about shipping habits.",
            "description": "This is why disciplined shipping matters.",
            "body_excerpt": "Example-driven advice for developers.",
        }
    )

    result = await handler.research_post_url("https://example.com/original")

    assert result["title"] == "How to ship calmly"
    assert result["url"] == "https://example.com/p/ship-calmly"
    assert result["publication"] == "Calm Builder"
    assert "Educational hook" in result["hook_analysis"]
    assert result["cta_analysis"] == "soft/no-explicit-cta"
    assert result["study_notes"]


@pytest.mark.asyncio
async def test_research_publication_url_extracts_positioning_and_audience():
    handler = StrategyHandler()
    handler.research_handler.inspect_url = AsyncMock(
        return_value={
            "title": "Founder Systems",
            "resolved_url": "https://example.com/archive",
            "publication": "Founder Systems",
            "summary": "Systems for startup operators.",
            "description": "A startup founder newsletter for developer operators.",
            "body_excerpt": "Developer workflows, startup strategy, and execution.",
        }
    )

    result = await handler.research_publication_url("https://example.com")

    assert result["title"] == "Founder Systems"
    assert result["url"] == "https://example.com/archive"
    assert result["themes"]
    assert "Likely positioned around" in result["positioning_guess"]
    assert result["who_it_is_for"] == "Founders and startup operators"


def test_generate_post_ideas_clamps_count_and_creates_angles():
    handler = StrategyHandler()

    ideas = handler.generate_post_ideas(
        "developer workflow",
        {"themes": [{"theme": "swiftui"}, {"theme": "performance"}]},
        {"themes": [{"theme": "caching"}, {"theme": "tooling"}]},
        count=2,
    )

    assert len(ideas) == 3
    assert all("title" in idea for idea in ideas)
    assert all(
        "angle" in idea and "builder experience" in idea["angle"] for idea in ideas
    )
    assert all("suggested_hook" in idea for idea in ideas)


@pytest.mark.parametrize(
    ("target_format", "expected_fragment"),
    [
        ("twitter_thread", "1/"),
        ("linkedin_post", "The part people underestimate:"),
        ("youtube_outline", "Intro hook"),
        ("email_blurb", "Most people overcomplicate"),
    ],
)
def test_repurpose_post_outputs_expected_format(target_format, expected_fragment):
    handler = StrategyHandler()

    result = handler.repurpose_post(
        "Shipping lessons",
        "Most people overcomplicate execution. Here is the practical version. Share it.",
        target_format=target_format,
    )

    assert result["target_format"] == target_format
    assert expected_fragment in result["repurposed"]


def test_content_gap_analysis_finds_market_only_themes():
    handler = StrategyHandler()

    result = handler.content_gap_analysis(
        {"themes": [{"theme": "swiftui"}, {"theme": "performance"}]},
        {
            "themes": [
                {"theme": "performance"},
                {"theme": "caching"},
                {"theme": "testing"},
            ]
        },
    )

    assert result["shared_themes"] == ["performance"]
    assert result["market_only_themes"] == ["caching", "testing"]
    assert any("caching" in item for item in result["opportunities"])


def test_optimize_title_and_hook_clamps_count():
    handler = StrategyHandler()

    result = handler.optimize_title_and_hook(
        "AsyncImage caching",
        "AsyncImage caching matters for scrolling performance and app feel.",
        count=10,
    )

    assert len(result["title_options"]) == 5
    assert len(result["hook_options"]) == 5
    assert all(isinstance(title, str) and title for title in result["title_options"])
    assert all(isinstance(hook, str) and hook for hook in result["hook_options"])


def test_series_plan_clamps_and_numbers_parts():
    handler = StrategyHandler()

    result = handler.series_plan("Caching", count=2)

    assert len(result) == 3
    assert result[0]["part"] == 1
    assert result[-1]["part"] == 3
    assert result[0]["title"].startswith("Caching:")


def test_extract_coding_lessons_uses_resolved_metadata():
    handler = StrategyHandler()

    result = handler.extract_coding_lessons(
        {
            "results": [
                {
                    "resolved_title": "SwiftUI caching guide",
                    "resolved_url": "https://example.com/p/swiftui-caching",
                    "summary": "Implementation tradeoffs for image caching and performance.",
                }
            ]
        }
    )

    assert result[0]["source"] == "SwiftUI caching guide"
    assert result[0]["url"] == "https://example.com/p/swiftui-caching"
    assert (
        "implementation" in result[0]["lesson"].lower()
        or "caching" in result[0]["lesson"].lower()
    )
