"""Fetch cited study material from Wikipedia for student-created courses.

Only the MediaWiki API is used (no scraping). Every failure returns "no
material" instead of raising, because a course is still useful without it:
the student can upload their own notes.

Wikipedia text is CC BY-SA 4.0; each chunk keeps the article title and URL
as its source so answers can be traced back and attributed.
"""

import logging
from dataclasses import dataclass, replace

import requests

from app.core.config import settings

logger = logging.getLogger(__name__)

USER_AGENT = "AdaptiveAITutor/1.0 (educational project; https://github.com/Sharada-C/adaptive-ai-tutor)"
MIN_WORDS = 100
DISAMBIGUATION_MARKERS = ("may refer to", "can refer to", "may also refer to")


@dataclass(frozen=True)
class Article:
    title: str
    url: str
    text: str
    # Set when the article was found for one concept of the course.
    concept_name: str | None = None

    @property
    def source(self) -> str:
        return f"Wikipedia: {self.title} ({self.url})"[:255]


def _get(params: dict) -> dict:
    response = requests.get(
        settings.wikipedia_api_url,
        params={**params, "format": "json", "formatversion": "1"},
        headers={"User-Agent": USER_AGENT},
        timeout=settings.web_material_timeout_seconds,
    )
    response.raise_for_status()
    return response.json()


def _search(query: str, limit: int) -> list[str]:
    data = _get(
        {"action": "query", "list": "search", "srsearch": query, "srlimit": limit}
    )
    return [hit["title"] for hit in data.get("query", {}).get("search", [])]


def _fetch(title: str, max_words: int | None = None) -> Article | None:
    data = _get(
        {
            "action": "query",
            "prop": "extracts|info",
            "inprop": "url",
            "explaintext": 1,
            "exsectionformat": "plain",
            "redirects": 1,
            "titles": title,
        }
    )

    for page in data.get("query", {}).get("pages", {}).values():
        text = (page.get("extract") or "").strip()
        words = text.split()
        head = text[:300].lower()

        if len(words) < MIN_WORDS or any(m in head for m in DISAMBIGUATION_MARKERS):
            return None

        words = words[: min(max_words or 10**9, settings.web_material_max_words)]
        return Article(
            title=page.get("title", title),
            url=page.get("fullurl", ""),
            text=" ".join(words),
        )

    return None


def collect_material(topic: str, concept_names: list[str]) -> list[Article]:
    """Best-effort: top articles for the topic, then one article per concept
    (tagged with ``concept_name`` so it can ground that concept directly)."""

    if not settings.web_material_enabled:
        return []

    limit = settings.web_material_max_articles
    articles: list[Article] = []
    seen: set[str] = set()

    try:
        for title in _search(topic, 3):
            if len(articles) >= limit:
                return articles

            article = _fetch(title)

            if article is None or article.title in seen:
                continue

            seen.add(article.title)
            articles.append(article)

        for name in concept_names:
            if len(articles) >= limit:
                break

            for title in _search(f"{topic} {name}", 2):
                if title in seen:
                    continue

                article = _fetch(title, settings.web_material_concept_words)

                if article is None or article.title in seen:
                    continue

                seen.add(article.title)
                articles.append(replace(article, concept_name=name))
                break
    except (requests.RequestException, ValueError, KeyError) as error:
        logger.warning("Wikipedia lookup failed: %s", error)

    return articles
