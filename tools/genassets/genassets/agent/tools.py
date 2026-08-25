"""Pipeline steps exposed as ADK function tools.

Each function here is a step the Director agent can call. They are deliberately
plain Python with typed signatures and docstrings, because ADK derives the tool
schema the model sees from exactly those — the docstring IS the tool description
the LLM reads, so it is written for the model, not for a human skimming code.

Design rules for this module:
  * every tool returns a JSON-serialisable dict, never an object
  * every tool reports its own failure in the return value rather than raising,
    so a failed step becomes something the agent can reason about and retry
  * nothing here imports ADK — these stay unit-testable and reusable
"""

from __future__ import annotations

import pathlib
from typing import Any

__all__ = [
    "DETAIL_LEVELS",
    "research_style",
    "generate_artwork",
    "vectorize_artwork",
    "build_rive_payload",
]

# Where generated assets land. Kept inside the repo so a run is inspectable.
WORKDIR = pathlib.Path(__file__).resolve().parents[4] / "assets" / "generated"


def _ok(**kw: Any) -> dict:
    return {"ok": True, **kw}


def _fail(error: str, **kw: Any) -> dict:
    return {"ok": False, "error": error, **kw}


#: Rendering detail, basic through extreme.
#:
#: The ceiling here is set by the VECTORIZER, not by the image model: every
#: extra colour and soft edge becomes more vector paths, and past roughly 120
#: paths a file stops being editable in Rive. So each level names a colour
#: budget and asks for a style the tracer can actually carry.
#:
#: The Disney/Pixar reference is deliberate and specific. Their appeal comes
#: from bold silhouettes, confident shape language and warm palettes — none of
#: which cost paths. Detail buys richness; it does not buy appeal, and a
#: cluttered "extreme" render is usually worse than a confident "standard" one.
DETAIL_LEVELS: dict[str, dict] = {
    "basic": {
        "colors": 4,
        "prompt": (
            "Bold, simple, iconic. Three or four flat colours, hard edges, one "
            "clear silhouette readable at a glance. The shape language of a "
            "well-designed app icon."
        ),
    },
    "standard": {
        "colors": 8,
        "prompt": (
            "Clean flat illustration in the modern animated-feature style: "
            "confident shapes, a warm limited palette, and a single flat shadow "
            "tone per form to give volume. Hard edges throughout."
        ),
    },
    "advanced": {
        "colors": 16,
        "prompt": (
            "Rich character illustration in the spirit of a Disney or Pixar "
            "feature: appealing, slightly exaggerated proportions, a strong "
            "silhouette, layered flat tones for light and shadow, a bounced "
            "light accent on the shadow side, and a rim highlight separating "
            "the subject from the background. Flat colour areas only."
        ),
    },
    "extreme": {
        "colors": 28,
        "prompt": (
            "Highly detailed stylised illustration with the polish of a "
            "feature-animation key frame: expressive posing, secondary details "
            "such as folds, tufts and small props, several layered tones per "
            "form, a warm key light with cool bounce, rim light, and considered "
            "colour harmony. Still built from FLAT colour areas with crisp "
            "boundaries — banded tonal steps, never smooth gradients."
        ),
    },
}


def research_style(subject: str, medium: str = "flat vector illustration") -> dict:
    """Research how a subject is actually depicted before any art is generated.

    Use this FIRST, before generate_artwork. It searches the live web for real
    reference — colour palettes, composition, stylistic conventions — and returns
    grounding text to pass into the image prompt. Art generated without this step
    tends to look generic.

    Args:
        subject: What is being depicted, e.g. "a paper airplane" or "a sleeping fox".
        medium: The intended rendering style, e.g. "flat vector illustration".

    Returns:
        ok, context (grounding text for the image prompt), sources (list of URLs),
        result_count.
    """
    try:
        from ..parallel import ParallelClient

        brief = ParallelClient().research_visual_style(subject, medium=medium)
        return _ok(
            context=brief.as_prompt_context(),
            sources=brief.sources,
            result_count=len(brief.results),
        )
    except Exception as e:  # surfaced to the agent, not raised
        return _fail(str(e), context="", sources=[])


def direct_art(subject: str, medium: str = "2D vector illustration") -> dict:
    """Research how a subject is really drawn, as CITED STRUCTURED data.

    Stronger than research_visual_style: that returns prose excerpts a model has
    to interpret, while this returns typed fields the pipeline consumes directly
    — a palette the vectoriser can quantise to, a silhouette the art has to pass,
    a detail level that picks the colour budget. Every field carries the URLs it
    came from, so a generated asset can show its own provenance.

    Slower (about a minute) because it is doing multi-hop research rather than
    one search round trip. Worth it once per asset; use research_visual_style
    for a quick look.

    Args:
        subject: What is being depicted, e.g. "a paper airplane".
        medium: The intended rendering style.

    Returns:
        ok, palette, silhouette, shape_language, conventions, detail_level,
        context (grounding text for the image prompt), sources, citations.
    """
    try:
        from ..parallel import ParallelClient

        report = ParallelClient().direct_art(subject, medium=medium)
        c = report.content if isinstance(report.content, dict) else {}
        return _ok(
            palette=c.get("palette", []),
            silhouette=c.get("silhouette", ""),
            shape_language=c.get("shape_language", ""),
            conventions=c.get("conventions", []),
            detail_level=c.get("detail_level", "standard"),
            context=report.as_prompt_context(),
            sources=report.sources,
            citations={f.field_name: [c2.url for c2 in f.citations] for f in report.basis},
            seconds=report.seconds,
        )
    except Exception as e:
        return _fail(str(e), palette=[], context="", sources=[])


def direct_motion(subject: str) -> dict:
    """Research how a subject is really ANIMATED, in frames we can key.

    Returns beat durations at 60fps — anticipation, action, overshoot, settle —
    that map onto the motion engine's generators, plus easing, secondary motion
    and how much (if any) the subject should squash.

    That last field is the one that most changes output. Asked about a paper
    airplane it answered "0% by default: keep the silhouette rigid", which is
    correct and is the opposite of the instinct to deform everything.

    Args:
        subject: What is moving, e.g. "a paper airplane gliding".

    Returns:
        ok, primary_motion, frame_timings, easing, secondary_motion,
        squash_stretch, sources, citations.
    """
    try:
        from ..parallel import ParallelClient

        report = ParallelClient().direct_motion(subject)
        c = report.content if isinstance(report.content, dict) else {}
        return _ok(
            primary_motion=c.get("primary_motion", ""),
            frame_timings=c.get("frame_timings", {}),
            easing=c.get("easing", ""),
            secondary_motion=c.get("secondary_motion", []),
            squash_stretch=c.get("squash_stretch", ""),
            sources=report.sources,
            citations={f.field_name: [c2.url for c2 in f.citations] for f in report.basis},
            seconds=report.seconds,
        )
    except Exception as e:
        return _fail(str(e), frame_timings={}, sources=[])


def read_pages(urls: list[str]) -> dict:
    """Read public web pages as clean markdown, including JavaScript-rendered ones.

    A plain fetch returns nothing useful for the Rive marketplace, YouTube, and
    several design references — they render client-side. This handles those, and
    PDFs, up to 20 URLs per call.

    Args:
        urls: Up to 20 public URLs.

    Returns:
        ok, pages (url, title, text), count.
    """
    try:
        from ..parallel import ParallelClient

        results = ParallelClient().extract(urls)
        return _ok(
            pages=[
                {"url": r.url, "title": r.title, "text": r.summary(2000)}
                for r in results
            ],
            count=len(results),
        )
    except Exception as e:
        return _fail(str(e), pages=[], count=0)


def generate_artwork(prompt: str, name: str, reference_context: str = "",
                     detail: str = "standard") -> dict:
    """Generate a raster image from a prompt, then normalise it for tracing.

    The image model returns JPEG regardless of filename, and JPEG artifacts around
    hard edges become spurious vector paths later — so this always decodes by
    content and re-encodes as a true PNG, quantising to suppress ringing.

    Args:
        prompt: The subject and composition. Do NOT describe shading or colour
            count here — the detail level supplies those, and the two fight.
        name: Short slug used for the output filename, e.g. "paper-plane".
        reference_context: Grounding text from research_style. Strongly recommended.
        detail: Rendering richness — "basic", "standard", "advanced" or
            "extreme". Higher levels give Disney/Pixar-style layered tones, rim
            light and secondary detail, at the cost of more vector paths. Choose
            by use: a UI icon wants "basic", a hero character wants "advanced".
            "extreme" can exceed the path budget; if vectorize_artwork reports
            too many paths, regenerate one level lower rather than retracing.

    Returns:
        ok, png_path, source_format, color_count, detail, and the image_class
        hint ("flat", "illustration" or "photo") that vectorize_artwork will use.
    """
    try:
        from ..gemini import client as gemini_client
        from ..normalize import normalize
        from ..vectorize import classify

        WORKDIR.mkdir(parents=True, exist_ok=True)
        level = DETAIL_LEVELS.get(detail, DETAIL_LEVELS["standard"])

        sections = [prompt, "", f"Style: {level['prompt']}"]
        if reference_context:
            sections += ["", "Ground the design in these real references:",
                         reference_context]
        sections += [
            "",
            f"Use at most {level['colors']} distinct flat colours, with crisp "
            f"boundaries between colour areas. No gradients, no soft shadows, "
            f"no texture, no noise — these become vector paths, and a soft edge "
            f"becomes hundreds of unusable ones.",
        ]
        full = "\n".join(sections)

        raw = WORKDIR / f"{name}.raw"
        gemini_client().generate_image(full, raw)

        # Quantize to the level's own budget. This is what collapses JPEG
        # ringing back into the flat regions it surrounds, so the tracer sees
        # the artwork rather than the compression around it.
        png = WORKDIR / f"{name}.png"
        info = normalize(raw, png, quantize_colors=level["colors"])
        return _ok(
            png_path=str(png),
            source_format=info.source_format,
            color_count=info.color_count,
            detail=detail,
            image_class=classify(info.color_count).value,
        )
    except Exception as e:
        return _fail(str(e))


def vectorize_artwork(png_path: str, name: str, image_class: str = "flat",
    strict: bool = True) -> dict:
    """Trace a normalised PNG into SVG, choosing tracer settings by image class.

    One setting profile cannot serve all art: the profile that renders an icon
    perfectly destroys an illustration, and photographs cannot be vectorised at a
    usable path count at all. Pass the image_class from generate_artwork.

    Args:
        png_path: Path returned by generate_artwork.
        name: Short slug for the output filename.
        image_class: "flat", "illustration", or "photo". Photos are refused —
            import those as bitmaps instead.

    Returns:
        ok, svg_path, paths, colors, kb, meets_standard, grade, notes.

        `meets_standard` is False when the trace is too sparse to be a hero
        asset. Do NOT import a failing trace — regenerate the art at a higher
        detail level instead. Pass strict=False only for a deliberately simple
        mark such as a UI glyph.
    """
    try:
        from ..vectorize import ImageClass, vectorize

        WORKDIR.mkdir(parents=True, exist_ok=True)
        svg = WORKDIR / f"{name}.svg"
        result = vectorize(png_path, svg, image_class=ImageClass(image_class))

        # Grade before anything downstream can import it. An asset that traces
        # to a handful of paths is the failure this project actually shipped,
        # and it shipped because nothing ever measured the result.
        from ..standard import grade
        verdict = grade(result.paths, result.colors, strict=strict)
        return _ok(
            svg_path=str(svg),
            paths=result.paths,
            colors=result.colors,
            kb=round(result.kb, 1),
            meets_standard=verdict.passed,
            grade=str(verdict),
            notes=list(verdict.reasons),
        )
    except Exception as e:
        return _fail(str(e))


def build_rive_payload(
    svg_path: str,
    artboard_width: int = 500,
    artboard_height: int = 500,
    animate_together: bool = True,
    motion: str = "static",
) -> dict:
    """Convert a traced SVG into the shape payload the Rive editor accepts.

    Rive does not accept SVG path strings — it needs structured moveTo/lineTo/
    cubicTo/close commands and #aarrggbb colours with alpha first. This performs
    that translation, drops the tracer's background plate, simplifies away
    per-pixel tracer vertices, and fits the art to the artboard.

    Args:
        svg_path: Path returned by vectorize_artwork.
        artboard_width: Target artboard width in pixels.
        artboard_height: Target artboard height in pixels.
        animate_together: Give every shape a shared origin. Required if the
            shapes will rotate or scale as one body — otherwise each spins about
            its own centre and the artwork tears apart.
        motion: What this art will DO once animated, which decides how much of
            the artboard to leave empty. The artboard clips, so art fitted
            edge-to-edge loses pieces the moment it moves.

            "static"     — never moves; fills 92% of the frame
            "ui-widget"  — presses and hovers in place; 85%
            "swim-cycle" — undulates without travelling; 71%
            "tumble"     — rotates end over end; 65%
            "hero-glide" — travels an arc and banks into it; 57%

            Declare the real motion. Naming "static" for art that then banks 18
            degrees is exactly the bug this parameter exists to prevent.

    Returns:
        ok, shapes (the createShapes payload), shape_count, command_count.
    """
    try:
        from ..svgdoc import (
            parse_svg_document,
            simplify_commands,
            to_create_shapes_payload,
        )

        svg_text = pathlib.Path(svg_path).read_text(encoding="utf-8")
        payload = to_create_shapes_payload(
            parse_svg_document(svg_text),
            artboard_width=artboard_width,
            artboard_height=artboard_height,
            envelope=motion,
            shared_origin=animate_together,
        )
        total = 0
        for shape in payload:
            shape["x"], shape["y"] = round(shape["x"]), round(shape["y"])
            cmds = simplify_commands(shape["paths"][0]["commands"], tolerance=1.2)
            for c in cmds:
                for k, v in list(c.items()):
                    if isinstance(v, float):
                        c[k] = round(v)
            shape["paths"][0]["commands"] = cmds
            total += len(cmds)

        return _ok(shapes=payload, shape_count=len(payload), command_count=total)
    except Exception as e:
        return _fail(str(e))
