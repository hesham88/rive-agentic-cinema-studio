"""Run the Director agent on a brief, from the command line.

    python -m genassets.agent.run "a paper airplane icon in bold flat colours"

Reads GEMINI_API_KEY / GOOGLE_API_KEY and PARALLEL_API_KEY from the environment
(load them from .env, which is gitignored).
"""

from __future__ import annotations

import asyncio
import os
import sys


def _load_env() -> None:
    """Load .env from the repo root if present. No dependency on python-dotenv."""
    import pathlib

    # .../tools/genassets/genassets/agent/run.py -> repo root is 4 levels up.
    root = pathlib.Path(__file__).resolve().parents[4]
    env = root / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

    # ADK reads GOOGLE_API_KEY; the pipeline reads GEMINI_API_KEY. Same key.
    if "GEMINI_API_KEY" in os.environ:
        os.environ.setdefault("GOOGLE_API_KEY", os.environ["GEMINI_API_KEY"])
    os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "FALSE")


async def run_brief(brief: str, *, verbose: bool = True) -> str:
    from google.adk.runners import InMemoryRunner
    from google.genai import types

    from .director import build_director

    runner = InMemoryRunner(agent=build_director(), app_name="rive-studio")
    session = await runner.session_service.create_session(
        app_name="rive-studio", user_id="cli"
    )

    final = ""
    async for event in runner.run_async(
        user_id="cli",
        session_id=session.id,
        new_message=types.Content(role="user", parts=[types.Part(text=brief)]),
    ):
        if verbose and event.content and event.content.parts:
            for part in event.content.parts:
                if getattr(part, "function_call", None):
                    fc = part.function_call
                    print(f"  -> {fc.name}({', '.join(sorted(fc.args or {}))})")
                elif getattr(part, "function_response", None):
                    resp = part.function_response.response or {}
                    ok = resp.get("ok")
                    detail = resp.get("error") if ok is False else ""
                    print(f"  <- {part.function_response.name}: ok={ok} {detail}"[:160])
        if event.is_final_response() and event.content and event.content.parts:
            final = "".join(p.text or "" for p in event.content.parts)
    return final


def main() -> int:
    _load_env()
    brief = " ".join(sys.argv[1:]).strip()
    if not brief:
        print(__doc__)
        return 2
    print(f"BRIEF: {brief}\n")
    result = asyncio.run(run_brief(brief))
    print("\n--- DIRECTOR ---")
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
