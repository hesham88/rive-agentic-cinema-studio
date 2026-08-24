"""Parallel Search — art direction research for the generator.

Why this exists: generated design looks generic when it is invented from
nothing. Good design work is reference-driven. This client lets the agent
*research before it generates* — find how a subject is actually rendered, which
typefaces are used in that context, what motion patterns the genre uses — and
feed that grounding into the image prompt.

Deliberately a plain REST client over `POST https://api.parallel.ai/v1/search`.
Parallel's docs suggest LangChain and the Vercel AI SDK, but the Agentic Cinema
rules prohibit third-party **agent frameworks**, so we call the API directly.

Endpoint verified against docs.parallel.ai on 2026-08-23:
    POST https://api.parallel.ai/v1/search
    header: x-api-key
    body:   {objective, search_queries, mode?}
    ->      {search_id, results[{url, title, publish_date, excerpts[]}],
             warnings, usage, session_id}
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

__all__ = ["ParallelClient", "ParallelError", "SearchResult", "ResearchBrief"]

API_URL = "https://api.parallel.ai/v1/search"


class ParallelError(RuntimeError):
    pass


@dataclass(frozen=True)
class SearchResult:
    url: str
    title: str
    excerpts: list[str]
    publish_date: str | None = None

    def summary(self, max_chars: int = 400) -> str:
        text = " ".join(self.excerpts).strip()
        return text[:max_chars]


@dataclass
class ResearchBrief:
    """What the agent learned before generating anything."""

    objective: str
    results: list[SearchResult] = field(default_factory=list)
    queries: list[str] = field(default_factory=list)

    def as_prompt_context(self, max_sources: int = 5, max_chars: int = 260) -> str:
        """Condense the research into grounding text for an image prompt.

        Kept short on purpose: the image model needs *direction*, not a corpus.
        Long context dilutes the subject and produces muddier art.
        """
        if not self.results:
            return ""
        lines = [f"Reference notes for: {self.objective}"]
        for r in self.results[:max_sources]:
            excerpt = r.summary(max_chars)
            if excerpt:
                lines.append(f"- {r.title.strip()}: {excerpt}")
        return "\n".join(lines)

    @property
    def sources(self) -> list[str]:
        return [r.url for r in self.results]


class ParallelClient:
    """Minimal, dependency-free Parallel Search client."""

    def __init__(self, api_key: str | None = None, *, timeout: int = 45,
                 default_mode: str = "turbo"):
        key = api_key or os.environ.get("PARALLEL_API_KEY")
        if not key:
            raise ParallelError(
                "PARALLEL_API_KEY is not set (see .env.example; .env is gitignored)"
            )
        self._key = key
        self.timeout = timeout
        # 'turbo' is ~200ms and $0.001/request; 'advanced' is ~3s and $0.005.
        # Art direction wants breadth over depth, so turbo is the default.
        self.default_mode = default_mode
        self.calls: list[dict] = []

    def search(
        self,
        objective: str,
        queries: list[str],
        *,
        mode: str | None = None,
    ) -> ResearchBrief:
        payload = {
            "objective": objective,
            "search_queries": queries,
            "mode": mode or self.default_mode,
        }
        req = urllib.request.Request(
            API_URL,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json", "x-api-key": self._key},
        )
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                body = json.load(r)
        except urllib.error.HTTPError as e:
            detail = e.read()[:300].decode("utf-8", "replace")
            raise ParallelError(f"search -> HTTP {e.code}: {detail}") from e
        except urllib.error.URLError as e:
            raise ParallelError(f"search -> network error: {e.reason}") from e

        self.calls.append({
            "objective": objective,
            "queries": len(queries),
            "mode": payload["mode"],
            "seconds": round(time.time() - t0, 2),
        })

        results = [
            SearchResult(
                url=item.get("url", ""),
                title=item.get("title", ""),
                excerpts=item.get("excerpts", []) or [],
                publish_date=item.get("publish_date"),
            )
            for item in body.get("results", [])
        ]
        return ResearchBrief(objective=objective, results=results, queries=queries)

    # ------------------------------------------------------------ art direction

    def research_visual_style(self, subject: str, *, medium: str = "illustration") -> ResearchBrief:
        """Ground a subject in how it is actually rendered in the wild."""
        return self.search(
            objective=(
                f"Visual and art-direction reference for creating a {medium} of {subject}: "
                f"characteristic colour palettes, shapes, composition, and stylistic conventions."
            ),
            queries=[
                f"{subject} {medium} style guide colour palette",
                f"{subject} flat vector illustration design",
                f"best {subject} {medium} examples composition",
            ],
        )

    def research_motion(self, subject: str) -> ResearchBrief:
        """Find how this kind of thing is animated — timing, easing, behaviour."""
        return self.search(
            objective=(
                f"Motion design reference for animating {subject}: timing, easing, "
                f"secondary motion, and the interaction patterns commonly used."
            ),
            queries=[
                f"{subject} animation timing easing motion design",
                f"{subject} micro-interaction animation principles",
                f"Rive {subject} interactive animation example",
            ],
        )

    def research_typography(self, context: str) -> ResearchBrief:
        """Typefaces actually used in a given context, not invented ones."""
        return self.search(
            objective=(
                f"Typography reference for {context}: typefaces used in practice, "
                f"pairings, weights, and why they suit this context."
            ),
            queries=[
                f"{context} typography typeface pairing in use",
                f"fonts used for {context} design",
            ],
        )
