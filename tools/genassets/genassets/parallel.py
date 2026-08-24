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

__all__ = [
    "ParallelClient", "ParallelError", "SearchResult", "ResearchBrief",
    "ResearchReport", "FieldBasis", "Citation", "PROCESSORS",
    "ART_DIRECTION_SCHEMA", "MOTION_SCHEMA",
]

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

    # ----------------------------------------------------------------- task API

    def _request(self, url: str, payload: dict | None, *, method: str = "POST",
                 timeout: int | None = None) -> dict:
        req = urllib.request.Request(
            url, method=method,
            data=json.dumps(payload).encode() if payload is not None else None,
            headers={"Content-Type": "application/json", "x-api-key": self._key},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout or self.timeout) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            detail = e.read()[:300].decode("utf-8", "replace")
            raise ParallelError(f"{method} {url} -> HTTP {e.code}: {detail}") from e
        except urllib.error.URLError as e:
            raise ParallelError(f"{method} {url} -> network error: {e.reason}") from e

    def research(
        self,
        objective: str,
        schema: dict | str,
        *,
        processor: str = "lite",
        poll_seconds: float = 3.0,
        max_wait: float = 300.0,
    ) -> ResearchReport:
        """Run a Task and return a structured, CITED answer.

        `schema` is either a JSON Schema (a dict) for machine-readable output, or
        a plain-English description for a prose report.

        Polls rather than blocking on one long request: a deep processor can run
        for minutes, and a socket held open that long is the first thing a proxy
        kills.
        """
        if processor not in PROCESSORS:
            raise ParallelError(f"unknown processor {processor!r}; expected one of {PROCESSORS}")

        spec = (
            {"output_schema": {"type": "json", "json_schema": schema}}
            if isinstance(schema, dict)
            else {"output_schema": schema}
        )
        t0 = time.time()
        run = self._request(TASK_URL, {
            "input": objective, "task_spec": spec, "processor": processor,
        })
        run_id = run["run_id"]

        while True:
            state = self._request(f"{TASK_URL}/{run_id}", None, method="GET")
            status = state.get("status")
            if status == "completed":
                break
            if status in ("failed", "cancelled"):
                raise ParallelError(f"task {run_id} {status}: {json.dumps(state)[:200]}")
            if time.time() - t0 > max_wait:
                raise ParallelError(
                    f"task {run_id} still {status} after {max_wait:.0f}s "
                    f"(processor={processor}; a deeper tier needs a longer max_wait)"
                )
            time.sleep(poll_seconds)

        result = self._request(f"{TASK_URL}/{run_id}/result", None, method="GET",
                               timeout=max(self.timeout, 120))
        out = result.get("output", {}) or {}
        elapsed = round(time.time() - t0, 2)
        self.calls.append({
            "objective": objective, "api": "task",
            "processor": processor, "seconds": elapsed,
        })

        basis = [
            FieldBasis(
                field_name=b.get("field", ""),
                reasoning=b.get("reasoning", ""),
                confidence=b.get("confidence"),
                citations=[
                    Citation(url=c.get("url", ""), excerpts=c.get("excerpts", []) or [])
                    for c in (b.get("citations") or [])
                ],
            )
            for b in (out.get("basis") or [])
        ]
        return ResearchReport(
            objective=objective, content=out.get("content", out),
            basis=basis, run_id=run_id, processor=processor, seconds=elapsed,
        )

    def extract(self, urls: list[str]) -> list[SearchResult]:
        """Turn public URLs into clean markdown excerpts.

        Handles JavaScript-rendered pages, which is what makes it worth having:
        the Rive marketplace, YouTube and several design references are all
        client-rendered and return nothing useful to a plain fetch.
        """
        if not urls:
            return []
        if len(urls) > 20:
            raise ParallelError(f"extract accepts at most 20 URLs, got {len(urls)}")
        body = self._request(EXTRACT_URL, {"urls": urls}, timeout=max(self.timeout, 90))
        self.calls.append({"api": "extract", "urls": len(urls)})
        return [
            SearchResult(
                url=item.get("url", ""),
                title=item.get("title", ""),
                excerpts=item.get("excerpts", []) or [],
                publish_date=item.get("publish_date"),
            )
            for item in body.get("results", [])
        ]

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

    def direct_art(self, subject: str, *, medium: str = "2D vector illustration",
                   processor: str = "lite") -> ResearchReport:
        """A cited art-direction brief the pipeline can act on directly.

        This is the research step that makes generated art reference-grounded
        rather than invented — principle 12, Appeal, implemented as a pipeline
        stage instead of a hope.
        """
        return self.research(
            f"How is {subject} actually drawn in high-quality {medium}? "
            f"Report the palette, silhouette, shape language and conventions used "
            f"by practitioners, citing real examples.",
            ART_DIRECTION_SCHEMA,
            processor=processor,
        )

    def direct_motion(self, subject: str, *, processor: str = "lite") -> ResearchReport:
        """A cited motion brief, in frames the motion engine can key."""
        return self.research(
            f"How is {subject} animated in professional 2D motion graphics? "
            f"Report the primary motion path, beat timings in frames at 60fps, "
            f"easing, secondary motion and any squash or stretch, citing sources.",
            MOTION_SCHEMA,
            processor=processor,
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


# --------------------------------------------------------------------------- #
# Task API — cited, structured research
#
# Search returns excerpts a human still has to read. The Task API returns a
# filled-in JSON schema with a `basis`: per-field citations naming the sources
# each value came from. That difference matters here for one specific reason —
# an art-direction brief that a generator consumes must be MACHINE-READABLE, and
# a brief a judge reads must be TRACEABLE. `basis` gives both at once.
#
# Verified against a live key on 2026-08-24:
#   POST /v1/tasks/runs            -> 202 {run_id, status}
#   GET  /v1/tasks/runs/{id}       -> {status}
#   GET  /v1/tasks/runs/{id}/result-> {output: {content, basis[]}}
# --------------------------------------------------------------------------- #

TASK_URL = "https://api.parallel.ai/v1/tasks/runs"
EXTRACT_URL = "https://api.parallel.ai/v1/extract"

#: Processor tiers, cheapest first. `lite` answered an art-direction question
#: with citations in ~57s; the deeper tiers trade latency for more hops.
PROCESSORS = ("lite", "base", "core", "pro", "ultra")


@dataclass(frozen=True)
class Citation:
    """One source backing one field of a structured answer."""

    url: str
    excerpts: list[str] = field(default_factory=list)


@dataclass
class FieldBasis:
    """Why a single field holds the value it does."""

    field_name: str
    reasoning: str
    citations: list[Citation] = field(default_factory=list)
    confidence: str | None = None


@dataclass
class ResearchReport:
    """A structured, cited answer — the output of a Task run.

    Unlike `ResearchBrief`, which carries prose excerpts for a prompt, this
    carries typed values a pipeline stage can act on directly: a palette it can
    paint with, a frame count it can key.
    """

    objective: str
    content: dict | str
    basis: list[FieldBasis] = field(default_factory=list)
    run_id: str = ""
    processor: str = ""
    seconds: float = 0.0

    @property
    def sources(self) -> list[str]:
        """Every distinct URL cited, in first-seen order."""
        seen: dict[str, None] = {}
        for b in self.basis:
            for c in b.citations:
                if c.url:
                    seen.setdefault(c.url, None)
        return list(seen)

    def cited(self, field_name: str) -> list[str]:
        """The URLs backing one field, for provenance in the UI."""
        for b in self.basis:
            if b.field_name == field_name:
                return [c.url for c in b.citations if c.url]
        return []

    def as_prompt_context(self, max_chars: int = 900) -> str:
        """Condense into grounding text for a generator prompt."""
        if isinstance(self.content, str):
            return self.content[:max_chars]
        lines = [f"Researched direction for: {self.objective}"]
        for k, v in self.content.items():
            rendered = ", ".join(map(str, v)) if isinstance(v, list) else str(v)
            lines.append(f"- {k}: {rendered}")
        return "\n".join(lines)[:max_chars]


# --------------------------------------------------------------------------- #
# Schemas
#
# Every field here exists because a downstream stage consumes it. A schema that
# returns prose the pipeline cannot act on is a lookup, not a research step —
# so `palette` feeds the vectoriser's colour quantiser, `frame_timings` feeds
# the motion engine's keyframe generators, `silhouette` is the check the art
# has to pass before it is traced.
# --------------------------------------------------------------------------- #

ART_DIRECTION_SCHEMA = {
    "type": "object",
    "properties": {
        "palette": {
            "type": "array", "items": {"type": "string"},
            "description": "5-8 hex colours characteristic of how this subject is "
                           "actually rendered. Ordered darkest to lightest.",
        },
        "silhouette": {
            "type": "string",
            "description": "What makes this subject readable as a solid black shape "
                           "at thumbnail size — the shapes that must survive.",
        },
        "shape_language": {
            "type": "string",
            "description": "Geometric vs organic, angular vs rounded, and the "
                           "proportions that read as correct.",
        },
        "conventions": {
            "type": "array", "items": {"type": "string"},
            "description": "Stylistic conventions this subject is usually drawn "
                           "with, and any that would read as wrong.",
        },
        "detail_level": {
            "type": "string",
            "description": "How much detail this subject needs to be recognisable: "
                           "basic, standard, advanced, or extreme.",
        },
    },
    "required": ["palette", "silhouette", "shape_language"],
}

MOTION_SCHEMA = {
    "type": "object",
    "properties": {
        "primary_motion": {
            "type": "string",
            "description": "How this subject characteristically moves — path shape, "
                           "whether it arcs, what leads and what follows.",
        },
        # Named explicitly rather than as a free-form map: the Task API
        # rejects an object with no `properties` ("Object 'properties' empty"),
        # and naming the beats is better anyway — these are exactly the four the
        # motion engine keys, so an answer maps straight onto generators.
        "frame_timings": {
            "type": "object",
            "description": "Beat durations in frames at 60fps.",
            "properties": {
                "anticipation": {"type": "number",
                                 "description": "Wind-up before the main action."},
                "action": {"type": "number",
                           "description": "The main move."},
                "overshoot": {"type": "number",
                              "description": "Passing the target before settling."},
                "settle": {"type": "number",
                           "description": "Coming to rest."},
            },
            "required": ["action"],
        },
        "easing": {
            "type": "string",
            "description": "The easing this motion wants, and where it overshoots.",
        },
        "secondary_motion": {
            "type": "array", "items": {"type": "string"},
            "description": "Parts that lag, drag or continue after the main mass "
                           "stops, with their offsets in frames.",
        },
        "squash_stretch": {
            "type": "string",
            "description": "Whether this subject deforms, and by how much. Real UI "
                           "squash is around 1-5%, not 15%.",
        },
    },
    "required": ["primary_motion", "frame_timings", "easing"],
}
