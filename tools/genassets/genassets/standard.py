"""The house standard for generated art, and the gate that enforces it.

Why this module exists
----------------------
Every asset this project shipped before 2026-08-24 was rejected by the owner as
"primitive and basic". The pipeline was not incapable — it was asked for
primitive output and complied silently. Three separate quality knobs were set to
their lowest value at the call site, and nothing anywhere compared the result
against a standard, because no standard was written down.

So this file writes it down, in numbers, and provides `grade()` so a traced
asset is measured before it can be imported. A shipped asset with 2 paths and 2
colours is now a hard failure with a named reason, not a quiet success.

Provenance
----------
The bands below are not taste. They come from a cited Parallel research task
(`core` processor, 11 sources, 2026-08-24) recorded in full at
`_OPERATIONS/study/craft/09-prompting-for-vectorisable-art.md`. Sources include
Rive's own bones and mesh documentation and Adobe's Image Trace guidance.

The central finding is that looking good and tracing well are NOT opposed, but
the instruction that satisfies both is narrow: ban continuous gradients while
explicitly demanding a fixed number of discrete tonal steps. Banning "shading"
outright — which is what this project did — removes the tonal steps too, and
that single word is what produced the flat two-colour marks.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "COLOUR_BAND", "PATH_BAND", "PATH_REVIEW", "PATH_MAX", "TONAL_STEPS",
    "REQUIRED_CLAUSES", "ANTI_CLAUSES", "Grade", "grade", "house_prompt",
]

#: Distinct flat colours for a complete hero character. Roughly 12-18 base
#: materials, 6-10 shadow and cool bounce, 4-6 highlight and rim, 2-4 identity.
COLOUR_BAND = (24, 36)

#: Closed filled paths for a hero. About 8-20 silhouette and body structure,
#: 20-60 clothing and secondary forms, 30-80 tonal facets and facial detail.
PATH_BAND = (80, 160)

#: Above this, look at it before importing.
PATH_REVIEW = 200
#: Above this, a real-time asset needs profiling to justify itself.
PATH_MAX = 300

#: Discrete tonal steps per major rounded form: base, shadow, halftone/bounce,
#: highlight. A fifth is allowed only for a deliberately graphic rim light —
#: never as another smooth intermediate.
TONAL_STEPS = 4

#: Clauses that must appear in every art prompt. These are what make the art
#: look like a feature key frame rather than a diagram.
REQUIRED_CLAUSES = (
    f"exactly {TONAL_STEPS} discrete tonal levels per major rounded form: "
    "base local colour, broad cool shadow, warm halftone, and small bright highlight",
    "flat opaque colour fills, clean hard-edged tonal facets, controlled posterised shading",
    f"limited production palette of {COLOUR_BAND[0]}-{COLOUR_BAND[1]} distinct flat colours, "
    "warm key light from upper front-left, cool blue-violet bounce from lower right",
    "narrow opaque rim-light facets along selected outer edges only",
    "layered cut-paper construction: body, clothing, shadow, highlight and rim-light "
    "are separate shapes, every region a clean closed boundary",
    "appealing exaggerated proportions, clear gesture, strong readable silhouette",
    "limbs visibly separated from the torso and from one another, no accidental tangency",
    "plain solid background in a colour absent from the subject, no scenery, no cast shadow, "
    "5% margin around every extremity",
)

#: Wording that destroys traceability. "no shading" is deliberately ABSENT —
#: banning shading is the mistake that flattened every earlier asset. Ban the
#: continuous rendering, keep the discrete steps.
ANTI_CLAUSES = (
    "photorealistic", "cinematic photographic lighting", "highly detailed skin texture",
    "subsurface scattering", "soft airbrush shading", "smooth gradients", "volumetric fog",
    "atmospheric perspective", "film grain", "watercolour bleeding", "glowing aura",
    "lens flare", "depth of field", "bokeh", "complex environment", "dense foliage",
    "smoke", "dust", "hair-by-hair detail", "micro-texture", "noise", "dither",
    "many tiny highlights", "intricate ornamental pattern", "thin line-art strokes",
    "open sketch lines", "ambiguous overlapping limbs", "cropped hands or feet",
    "one continuous fused body silhouette", "transparent wispy edges",
    "cast shadow attached to the subject", "full-tone rendering", "high-fidelity photo",
)


def house_prompt(subject: str, *, extra: str = "") -> str:
    """Build an art prompt that satisfies the standard.

    The subject is what varies; everything else is fixed, so a careless call
    site cannot quietly ask for something simpler. That is the whole point —
    the previous failure was a call site overriding a standard that existed.
    """
    parts = [subject.strip().rstrip(".") + "."]
    parts += [c + "." for c in REQUIRED_CLAUSES]
    if extra:
        parts.append(extra.strip().rstrip(".") + ".")
    parts.append("Avoid: " + ", ".join(ANTI_CLAUSES) + ".")
    return " ".join(parts)


@dataclass(frozen=True)
class Grade:
    """The verdict on one traced asset."""

    paths: int
    colours: int
    passed: bool
    reasons: tuple[str, ...]

    def __str__(self) -> str:
        head = "PASS" if self.passed else "FAIL"
        return f"{head}  {self.paths} paths / {self.colours} colours" + (
            "\n  - " + "\n  - ".join(self.reasons) if self.reasons else ""
        )


def grade(paths: int, colours: int, *, strict: bool = True) -> Grade:
    """Measure a traced asset against the standard.

    `strict=False` downgrades band misses to warnings, for deliberate
    exceptions such as a simple UI glyph that genuinely needs eight paths. It
    still reports them, so an exception is visible rather than assumed.
    """
    reasons: list[str] = []
    fatal = False

    lo, hi = PATH_BAND
    if paths < lo:
        fatal = True
        reasons.append(
            f"only {paths} paths; a hero needs {lo}-{hi}. This is the signature of "
            f"art generated at too low a detail level, or a prompt that banned shading "
            f"outright instead of banning gradients."
        )
    elif paths > PATH_MAX:
        fatal = True
        reasons.append(f"{paths} paths exceeds the {PATH_MAX} ceiling for a real-time asset")
    elif paths > PATH_REVIEW:
        reasons.append(f"{paths} paths is past the {PATH_REVIEW} review threshold — look at it")
    elif paths > hi:
        reasons.append(f"{paths} paths is above the {lo}-{hi} target but under review threshold")

    clo, chi = COLOUR_BAND
    if colours < clo:
        fatal = True
        reasons.append(
            f"only {colours} colours; a hero needs {clo}-{chi} to carry "
            f"{TONAL_STEPS} tonal steps per form plus rim light"
        )
    elif colours > chi:
        reasons.append(f"{colours} colours is above the {clo}-{chi} target; near-duplicates "
                       f"become redundant paths — quantise by perceptual distance")

    return Grade(paths=paths, colours=colours,
                 passed=not (fatal and strict), reasons=tuple(reasons))
