"""ADK agent layer — Gemini-driven orchestration of the asset pipeline."""

from .tools import (
    build_rive_payload,
    generate_artwork,
    research_style,
    vectorize_artwork,
)

__all__ = [
    "research_style",
    "generate_artwork",
    "vectorize_artwork",
    "build_rive_payload",
    "build_director",
]


def __getattr__(name: str):
    # build_director pulls in google.adk, which is a heavy import. Deferred so
    # `from genassets.agent import research_style` stays fast.
    if name == "build_director":
        from .director import build_director
        return build_director
    raise AttributeError(name)
