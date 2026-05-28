# ABOUTME: StrategyHandler turns posts and research results into useful marketing and study outputs
# ABOUTME: Provides analysis, ideation, repurposing, gap analysis, and study plans

import re
from collections import Counter
from typing import Any, Dict, List

from src.handlers.research_handler import ResearchHandler, extract_meaningful_tokens


class StrategyHandler:
    """Heuristic content strategy and study helper for indie developers."""

    def __init__(self) -> None:
        self.research_handler = ResearchHandler()

    def analyze_post_collection(self, posts: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not posts:
            return {
                "total_posts": 0,
                "themes": [],
                "title_patterns": [],
                "cta_patterns": [],
                "recommended_focus": [],
            }

        theme_counter: Counter[str] = Counter()
        title_pattern_counter: Counter[str] = Counter()
        cta_pattern_counter: Counter[str] = Counter()

        for post in posts:
            text = " ".join(
                filter(None, [post.get("title", ""), post.get("content", "")])
            )
            theme_counter.update(self._theme_tokens(text))
            title_pattern_counter[self._title_pattern(post.get("title", ""))] += 1
            cta_pattern_counter[self._cta_pattern(post.get("content", ""))] += 1

        themes = [
            {"theme": theme, "mentions": count}
            for theme, count in theme_counter.most_common(8)
        ]
        title_patterns = [
            {"pattern": pattern, "count": count}
            for pattern, count in title_pattern_counter.most_common(5)
            if pattern
        ]
        cta_patterns = [
            {"pattern": pattern, "count": count}
            for pattern, count in cta_pattern_counter.most_common(5)
            if pattern
        ]

        recommended_focus = self._recommended_focus(themes, title_patterns)

        return {
            "total_posts": len(posts),
            "themes": themes,
            "title_patterns": title_patterns,
            "cta_patterns": cta_patterns,
            "recommended_focus": recommended_focus,
        }

    async def research_post_url(self, url: str) -> Dict[str, Any]:
        result = await self.research_handler.inspect_url(url)
        title = result.get("resolved_title") or result.get("title") or "Untitled"
        summary = result.get("summary") or result.get("description") or ""
        content = " ".join(
            filter(
                None, [result.get("description", ""), result.get("body_excerpt", "")]
            )
        )
        return {
            "title": title,
            "url": result.get("resolved_url") or url,
            "publication": result.get("publication"),
            "author": result.get("author"),
            "published_at": result.get("published_at"),
            "summary": summary,
            "hook_analysis": self._analyze_hook(title, content),
            "cta_analysis": self._cta_pattern(content),
            "study_notes": self._study_notes_from_text(title, content),
        }

    async def research_publication_url(self, url: str) -> Dict[str, Any]:
        result = await self.research_handler.inspect_url(url)
        content = " ".join(
            filter(
                None, [result.get("description", ""), result.get("body_excerpt", "")]
            )
        )
        tokens = self._theme_tokens(content)
        themes = [
            {"theme": theme, "mentions": count}
            for theme, count in Counter(tokens).most_common(6)
        ]
        return {
            "title": result.get("resolved_title") or result.get("title") or url,
            "url": result.get("resolved_url") or url,
            "publication": result.get("publication"),
            "summary": result.get("summary") or result.get("description") or "",
            "themes": themes,
            "positioning_guess": self._positioning_guess(content),
            "who_it_is_for": self._audience_guess(content),
        }

    def generate_post_ideas(
        self,
        query: str,
        my_post_analysis: Dict[str, Any],
        research_results: Dict[str, Any],
        count: int = 10,
    ) -> List[Dict[str, Any]]:
        count = max(3, min(count, 20))
        seeds = []

        seeds.extend(
            [theme["theme"] for theme in my_post_analysis.get("themes", [])[:4]]
        )
        seeds.extend(
            [theme["theme"] for theme in research_results.get("themes", [])[:6]]
        )
        seeds.extend(self._theme_tokens(query))

        unique_seeds = []
        for seed in seeds:
            if seed not in unique_seeds and len(seed) > 2:
                unique_seeds.append(seed)

        idea_templates = [
            "What {seed} taught me while building as an indie developer",
            "The mistake most people make with {seed}",
            "A practical guide to {seed} for busy builders",
            "How I would approach {seed} if I had to start over",
            "The boring truth about {seed} that actually matters",
        ]

        ideas = []
        for index in range(count):
            seed = unique_seeds[index % len(unique_seeds)] if unique_seeds else query
            template = idea_templates[index % len(idea_templates)]
            title = template.format(seed=seed)
            ideas.append(
                {
                    "title": title,
                    "angle": self._idea_angle(seed),
                    "why_now": f"{seed} is showing up across your own themes and researched Substack results.",
                    "suggested_hook": self._suggested_hook(title, seed),
                }
            )
        return ideas

    def repurpose_post(
        self, title: str, content: str, target_format: str = "twitter_thread"
    ) -> Dict[str, Any]:
        excerpt = self._sentences(content, 5)
        hooks = self.optimize_title_and_hook(title, content, 3)

        if target_format == "twitter_thread":
            body = [
                f"1/ {hooks['hook_options'][0]}",
                "2/ Here's the core idea:",
                f"3/ {excerpt[0] if excerpt else content[:180]}",
                f"4/ {excerpt[1] if len(excerpt) > 1 else 'This is the practical takeaway.'}",
                "5/ If you're building in public, steal the pattern, not the wording.",
            ]
        elif target_format == "linkedin_post":
            body = [
                hooks["hook_options"][0],
                "",
                excerpt[0] if excerpt else content[:220],
                "",
                "The part people underestimate:",
                excerpt[1] if len(excerpt) > 1 else "Execution beats cleverness.",
                "",
                "Curious how others are approaching this.",
            ]
        elif target_format == "youtube_outline":
            body = [
                f"Title idea: {hooks['title_options'][0]}",
                "Intro hook",
                "Problem setup",
                "What I tried",
                "What worked / what failed",
                "Actionable lessons",
                "CTA / next step",
            ]
        else:
            body = [
                hooks["hook_options"][0],
                excerpt[0] if excerpt else content[:220],
            ]

        return {
            "target_format": target_format,
            "title": title,
            "repurposed": "\n".join(body),
        }

    def content_gap_analysis(
        self, my_post_analysis: Dict[str, Any], research_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        my_themes = {item["theme"] for item in my_post_analysis.get("themes", [])}
        market_themes = {item["theme"] for item in research_results.get("themes", [])}

        gaps = sorted(market_themes - my_themes)[:8]
        overlaps = sorted(my_themes & market_themes)[:8]

        return {
            "market_only_themes": gaps,
            "shared_themes": overlaps,
            "opportunities": [
                f"You have not covered much around '{theme}' yet, but it appears repeatedly in Substack research."
                for theme in gaps[:5]
            ],
        }

    def optimize_title_and_hook(
        self, title: str, content: str, count: int = 5
    ) -> Dict[str, Any]:
        count = max(3, min(count, 8))
        seed = self._theme_tokens(f"{title} {content}")
        primary = seed[0] if seed else "this topic"

        title_options = [
            f"The honest take on {primary}",
            f"What {primary} actually looks like in practice",
            f"I underestimated {primary} until this happened",
            f"The indie developer's guide to {primary}",
            f"Why {primary} matters more than people think",
        ][:count]

        hook_options = [
            f"Most people overcomplicate {primary}. The useful version is much simpler.",
            f"I thought {primary} was a small detail. It turned out to be the whole game.",
            f"If you're building fast, {primary} is one of those things you can ignore exactly once.",
            f"The difference between vague advice and real progress usually shows up in {primary}.",
            f"Here's the version of {primary} I wish someone had handed me earlier.",
        ][:count]

        return {
            "title_options": title_options,
            "hook_options": hook_options,
        }

    def series_plan(self, topic: str, count: int = 5) -> List[Dict[str, Any]]:
        count = max(3, min(count, 10))
        stages = [
            "Why this matters",
            "Common mistakes",
            "My current approach",
            "Real examples",
            "Advanced lessons",
            "What I would do next",
            "Reader Q&A",
            "Tooling and workflow",
            "Case study",
            "Wrap-up and next steps",
        ]
        plan = []
        for index in range(count):
            stage = stages[index]
            plan.append(
                {
                    "part": index + 1,
                    "title": f"{topic}: {stage}",
                    "goal": f"Help readers understand {topic.lower()} through '{stage.lower()}'.",
                }
            )
        return plan

    def study_topic_on_substack(
        self, topic: str, research_results: Dict[str, Any]
    ) -> Dict[str, Any]:
        study_order = []
        for index, recommendation in enumerate(
            research_results.get("recommended_to_study", [])[:5], start=1
        ):
            study_order.append(
                {
                    "step": index,
                    "title": recommendation["title"],
                    "url": recommendation["url"],
                    "why": recommendation["why_study"],
                }
            )
        warnings = list(research_results.get("warnings", []))
        if not study_order:
            warnings.append(
                "No strong Substack sources were found for this topic yet, so the reading order is empty."
            )
        return {
            "topic": topic,
            "themes": research_results.get("themes", [])[:6],
            "study_order": study_order,
            "study_tip": "Read the top post first, then compare how the next two publications frame the same problem differently.",
            "warnings": warnings,
        }

    def extract_coding_lessons(
        self, research_results: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        lessons = []
        for result in research_results.get("results", [])[:5]:
            summary = result.get("summary", "")
            title = result.get("resolved_title") or result.get("title")
            tokens = self._theme_tokens(summary)
            lesson_focus = tokens[:3] if tokens else ["implementation", "tradeoffs"]
            lessons.append(
                {
                    "source": title,
                    "url": result.get("resolved_url") or result.get("url"),
                    "lesson": f"Study how this piece approaches {', '.join(lesson_focus)} and convert that into a concrete experiment in your codebase.",
                }
            )
        return lessons

    def _theme_tokens(self, text: str) -> List[str]:
        return extract_meaningful_tokens(text)

    def _title_pattern(self, title: str) -> str:
        lowered = title.lower()
        if lowered.startswith("how "):
            return "how-to"
        if lowered.startswith("why "):
            return "why"
        if "guide" in lowered:
            return "guide"
        if ":" in title:
            return "colon-title"
        return "statement"

    def _cta_pattern(self, content: str) -> str:
        lowered = content.lower()
        if "subscribe" in lowered:
            return "subscribe"
        if "reply" in lowered or "tell me" in lowered:
            return "reply"
        if "share" in lowered:
            return "share"
        if "follow" in lowered:
            return "follow"
        return "soft/no-explicit-cta"

    def _recommended_focus(
        self, themes: List[Dict[str, Any]], title_patterns: List[Dict[str, Any]]
    ) -> List[str]:
        output = []
        if themes:
            output.append(
                f"Double down on '{themes[0]['theme']}' because it shows up most across your posts."
            )
        if len(themes) > 1:
            output.append(
                f"Pair '{themes[0]['theme']}' with '{themes[1]['theme']}' for a stronger niche angle."
            )
        if title_patterns:
            output.append(
                f"Your strongest title pattern currently looks like '{title_patterns[0]['pattern']}'."
            )
        return output

    def _idea_angle(self, seed: str) -> str:
        return f"Teach a practical lesson around {seed} through your own builder experience."

    def _suggested_hook(self, title: str, seed: str) -> str:
        return f"If you're building fast, {seed} is probably costing you more than you think."

    def _analyze_hook(self, title: str, content: str) -> str:
        if any(word in title.lower() for word in ["how", "guide", "lesson"]):
            return "Educational hook. Strong for readers already problem-aware."
        if "?" in title:
            return "Question hook. Good curiosity signal if the answer is concrete."
        if content and len(content) > 120:
            return "Narrative/practical hook. Likely works best when paired with a strong first paragraph."
        return "Simple statement hook."

    def _study_notes_from_text(self, title: str, content: str) -> List[str]:
        notes = []
        if title:
            notes.append(f"Look at how the title frames the promise: '{title}'.")
        if "example" in content.lower():
            notes.append("The writer uses examples. Capture how concrete they get.")
        if "why" in content.lower():
            notes.append(
                "Notice how the piece transitions from explanation into argument."
            )
        if not notes:
            notes.append("Compare the structure, not just the topic.")
        return notes

    def _positioning_guess(self, content: str) -> str:
        tokens = self._theme_tokens(content)
        if not tokens:
            return "Broad publication with unclear positioning from available metadata."
        return f"Likely positioned around {', '.join(tokens[:3])}."

    def _audience_guess(self, content: str) -> str:
        lowered = content.lower()
        if "founder" in lowered or "startup" in lowered:
            return "Founders and startup operators"
        if "developer" in lowered or "engineer" in lowered:
            return "Developers and technical builders"
        if "writer" in lowered or "creator" in lowered:
            return "Writers and creators"
        return "General builders / knowledge workers"

    def _sentences(self, content: str, count: int) -> List[str]:
        parts = [
            part.strip() for part in re.split(r"(?<=[.!?])\s+", content) if part.strip()
        ]
        return parts[:count]
