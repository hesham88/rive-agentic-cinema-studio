"""Construction recipes: subjects expressed as primitives and ratios.

A recipe is the drawing instruction, not the drawing. Every dimension is a
multiple of one base unit, so the same recipe emits a 200 px icon or a 2000 px
hero without a second set of numbers, and a proportion can be read and argued
with instead of being buried in coordinates.

Ratios come from the `animation-craft` skill's construction and rigging tables.
Where the craft notes mark a figure `NR` — the sea turtle's stroke frequency,
for instance — the recipe carries the established *behaviour* instead and leaves
the timing to the caller. Inventing a number to fill an NR is the one thing the
notes explicitly forbid.

Anatomy that is asserted rather than guessed
--------------------------------------------
Two facts drive the turtle recipe and both are the opposite of the obvious
choice. The carapace is **rigid** — it is bone, it does not deform, and shading
it as a soft form is why generated turtles read as rubber. And the stroke is
**dorsoventral flapping**: a sea turtle flies underwater on its foreflippers,
and its hindflippers are rudders, not propulsors. Animating a rowing foreflipper
is named in the notes as the fundamental sea-turtle error.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from .construct import (
    KEY_UPPER_LEFT, PALETTES, Form, Light, Palette,
    clip_to, contact_shadow, ellipse, merge_near_duplicates, shade_form,
    smooth_polygon, tapered, tint, transform, union_outline, wedge,
)

__all__ = ["Recipe", "Built", "RECIPES", "build", "sea_turtle", "dolphin", "butterfly"]


@dataclass(frozen=True)
class Recipe:
    """A subject, its construction, and how it is meant to move."""

    name: str
    #: Palette key from `construct.PALETTES`.
    palette: str
    #: `svgdoc.ENVELOPES` key — how much artboard the motion needs.
    envelope: str
    #: Forms in draw order, back to front. Index 0 is drawn first.
    forms: list[Form]
    #: Bone plan: (bone name, parent or None). Emitted for the rigging stage.
    bones: list[tuple[str, str | None]] = field(default_factory=list)
    #: What the notes establish about the motion, in words, when the literature
    #: gives no number. Carried so the animation stage cannot silently guess.
    motion_notes: tuple[str, ...] = ()
    #: Footprint width for the contact shadow, in base units. 0 = none.
    footprint: float = 0.0


@dataclass(frozen=True)
class Built:
    """A recipe realised as shapes."""

    name: str
    shapes: list[dict]
    palette: Palette
    envelope: str
    bones: list[tuple[str, str | None]]
    motion_notes: tuple[str, ...]

    @property
    def path_count(self) -> int:
        return len(self.shapes)

    @property
    def colours(self) -> set[str]:
        return {s["paints"][0]["color"] for s in self.shapes}


def sea_turtle(u: float = 100.0) -> Recipe:
    """A green sea turtle in a gliding three-quarter view.

    `u` is the carapace half-length; every other dimension is a ratio of it.

    Foreflippers are set at the mid-downstroke of a flap, asymmetric by design:
    the near one leads, so the pair does not read as a twin. The craft rule is a
    phase offset of at least 15% of the cycle, and a symmetric pair is item 6 on
    the rejection checklist.

    Eight local materials, because a turtle is not one colour. Shell, scute,
    plastron, flipper skin, flipper edge, neck, beak and eye are eight different
    things before any light touches them.
    """
    P = PALETTES["underwater-shallow"]
    # Local materials, all shifted from the palette key so the set stays related.
    SHELL      = tint(P.key, hue=-22, sat=0.30, val=-0.40)
    SHELL_EDGE = tint(P.key, hue=-24, sat=0.26, val=-0.40)
    SCUTE      = tint(P.key, hue=-16, sat=0.22, val=-0.30)
    SCUTE_ALT  = tint(P.key, hue=-12, sat=0.16, val=-0.22)
    PLASTRON   = tint(P.key, hue=14, sat=-0.22, val=-0.06)
    SKIN       = tint(P.key, hue=-4, sat=0.16, val=-0.34)
    SKIN_DARK  = tint(P.key, hue=-6, sat=0.22, val=-0.46)
    BEAK       = tint(P.key, hue=26, sat=-0.16, val=-0.08)

    forms: list[Form] = []

    # --- far side first, so draw order does the occluding ------------------
    forms.append(Form("hindflipper-far",
                      tapered(-u * 0.70, -u * 0.26, -u * 1.12, -u * 0.40,
                              u * 0.42, u * 0.30), local=SKIN_DARK))
    forms.append(Form("foreflipper-far",
                      tapered(-u * 0.22, -u * 0.34, -u * 0.96, -u * 0.90,
                              u * 0.62, u * 0.40), local=SKIN_DARK))
    forms.append(Form("foreflipper-far-edge",
                      tapered(-u * 0.42, -u * 0.52, -u * 0.94, -u * 0.90,
                              u * 0.16, u * 0.11), local=SHELL_EDGE, shade=False))

    # --- carapace, the rigid mass ------------------------------------------
    forms.append(Form("carapace", ellipse(0, 0, u, u * 0.78, segments=18), local=SHELL))
    # A rim of marginal scutes reads as shell thickness. Rigid, so unshaded.
    forms.append(Form("carapace-margin",
                      ellipse(u * 0.03, u * 0.06, u * 0.98, u * 0.74, segments=16),
                      local=SHELL_EDGE, shade=False))
    forms.append(Form("carapace-face", ellipse(-u * 0.04, -u * 0.05, u * 0.90,
                                               u * 0.68, segments=16), local=SHELL))

    # Scutes: alternating tones so the pattern reads without outlines, which
    # the standard forbids. Sizes vary >20% so they are not siblings.
    for i, (sx, sy, sr, alt) in enumerate((
        (-0.44, -0.10, 0.30, 0), (-0.06, -0.34, 0.27, 1), (0.34, -0.16, 0.24, 0),
        (0.36, 0.20, 0.22, 1), (-0.04, 0.30, 0.29, 0), (-0.46, 0.24, 0.23, 1),
        (-0.04, -0.02, 0.26, 1),
    )):
        forms.append(Form(f"scute-{i + 1}",
                          ellipse(sx * u, sy * u, sr * u, sr * u * 0.62, segments=10),
                          local=SCUTE_ALT if alt else SCUTE, rim=False))

    # Plastron edge, just visible in three-quarter. The value contrast against
    # the shell is what makes the turtle read as a solid body rather than a disc.
    forms.append(Form("plastron",
                      ellipse(u * 0.14, u * 0.52, u * 0.58, u * 0.22, segments=12),
                      local=PLASTRON, rim=False))

    # --- neck and head -----------------------------------------------------
    forms.append(Form("neck", tapered(u * 0.74, u * 0.02, u * 1.06, -u * 0.10,
                                      u * 0.46, u * 0.40, round_end=False), local=SKIN))
    forms.append(Form("head", wedge((u * 1.52, -u * 0.12), (u * 0.90, -u * 0.38),
                                    (u * 0.90, u * 0.22), round_base=0.18), local=SKIN))
    forms.append(Form("head-crown", wedge((u * 1.40, -u * 0.22), (u * 0.96, -u * 0.34),
                                          (u * 1.06, -u * 0.14), round_base=0.14),
                      local=SKIN_DARK, rim=False))
    forms.append(Form("beak", wedge((u * 1.54, -u * 0.10), (u * 1.28, -u * 0.16),
                                    (u * 1.28, u * 0.08), round_base=0.10),
                      local=BEAK, shade=False))
    forms.append(Form("eye", ellipse(u * 1.15, -u * 0.17, u * 0.085, u * 0.095,
                                     segments=10), role="shadow", shade=False))
    forms.append(Form("eye-spec", ellipse(u * 1.12, -u * 0.20, u * 0.030, u * 0.033,
                                          segments=6), role="rim", shade=False))

    # --- near side, in front ------------------------------------------------
    forms.append(Form("hindflipper-near",
                      tapered(-u * 0.68, u * 0.30, -u * 1.16, u * 0.48,
                              u * 0.44, u * 0.32), local=SKIN))
    forms.append(Form("foreflipper-near",
                      tapered(-u * 0.14, u * 0.26, -u * 0.90, u * 1.02,
                              u * 0.70, u * 0.44), local=SKIN))
    # The thin trailing edge is where subsurface scatter shows on a real
    # flipper: 8-15% of the form width, on the backlit edge only.
    forms.append(Form("foreflipper-near-sss",
                      tapered(-u * 0.46, u * 0.56, -u * 0.88, u * 1.00,
                              u * 0.18, u * 0.12), local="#6FA58E", shade=False))

    return Recipe(
        name="sea-turtle", palette="underwater-shallow", envelope="swim-cycle",
        forms=forms,
        # 14-26 deform bones, root on the SHELL, 2-3 per flipper.
        bones=[
            ("root", None), ("carapace", "root"), ("neck", "carapace"), ("head", "neck"),
            ("foreflipper-near-1", "carapace"), ("foreflipper-near-2", "foreflipper-near-1"),
            ("foreflipper-near-3", "foreflipper-near-2"),
            ("foreflipper-far-1", "carapace"), ("foreflipper-far-2", "foreflipper-far-1"),
            ("foreflipper-far-3", "foreflipper-far-2"),
            ("hindflipper-near-1", "carapace"), ("hindflipper-near-2", "hindflipper-near-1"),
            ("hindflipper-far-1", "carapace"), ("hindflipper-far-2", "hindflipper-far-1"),
        ],
        motion_notes=(
            "Dorsoventral FLAPPING of the foreflippers - the turtle flies, it does "
            "not row. A rowing foreflipper is the fundamental sea-turtle error.",
            "Hindflippers are rudders, not propulsors: they steer and trail, and "
            "must never drive the body forward.",
            "The carapace is rigid. It does not deform, squash or bend.",
            "Stroke frequency is NR in the literature (Rivera & Wyneken, JEB 214, "
            "2011 quantified it but no figure was retrievable). Do NOT invent one - "
            "pick a stroke-and-glide rhythm and state that it is a convention.",
            "Stroke, then glide. Constant-rate motion is the machine tell in every "
            "aquatic animal.",
            "Near and far flippers are offset >=15% of the cycle. Never in phase.",
        ),
    )


def dolphin(u: float = 100.0) -> Recipe:
    """A bottlenose dolphin mid-glide. `u` is a quarter of body length.

    Unlike the turtle this body DOES deform: the peduncle drives a travelling
    wave, so the recipe emits a segmented torso for the bone chain to bend.
    """
    P = PALETTES["underwater-deep"]
    # Countershading is the dolphin's defining colour fact: dark dorsal, pale
    # ventral, with a soft flank between. Painting it one blue-grey is what
    # makes a generated dolphin read as a rubber toy.
    DORSAL  = tint(P.key, hue=-4, sat=0.20, val=-0.16)
    FLANK   = tint(P.key, hue=-2, sat=0.06, val=0.10)
    VENTRAL = tint(P.key, hue=6, sat=-0.30, val=0.34)
    FIN     = tint(P.key, hue=-6, sat=0.24, val=-0.24)
    FIN_FAR = tint(P.key, hue=-6, sat=0.28, val=-0.36)
    MELON   = tint(P.key, hue=2, sat=-0.06, val=0.16)
    ROSTRUM = tint(P.key, hue=-2, sat=0.10, val=-0.04)
    BODY_DARK = tint(P.key, hue=-8, sat=0.30, val=-0.40)

    forms: list[Form] = []
    forms.append(Form("pectoral-far",
                      tapered(-u * 0.10, u * 0.10, -u * 0.72, u * 0.66,
                              u * 0.30, u * 0.10), local=FIN_FAR))
    forms.append(Form("body", ellipse(0, 0, u * 1.55, u * 0.60, segments=20), local=FLANK,
                      group="body"))
    forms.append(Form("rostrum",
                      tapered(u * 1.30, u * 0.04, u * 2.16, u * 0.14,
                              u * 0.44, u * 0.16), local=ROSTRUM, group="body"))
    forms.append(Form("melon", ellipse(u * 1.06, -u * 0.20, u * 0.36, u * 0.24,
                                       segments=12), local=MELON, rim=False, group="body"))
    forms.append(Form("dorsal",
                      wedge((u * 0.16, -u * 1.16), (-u * 0.30, -u * 0.44),
                            (u * 0.42, -u * 0.46), round_base=0.12), local=FIN, group="body"))
    forms.append(Form("peduncle",
                      tapered(-u * 1.34, u * 0.02, -u * 2.02, -u * 0.06,
                              u * 0.46, u * 0.16, round_end=False), local=FLANK, group="body"))
    forms.append(Form("fluke-upper",
                      tapered(-u * 1.96, -u * 0.04, -u * 2.52, -u * 0.46,
                              u * 0.20, u * 0.30), local=FIN, group="body"))
    forms.append(Form("fluke-lower",
                      tapered(-u * 1.96, -u * 0.04, -u * 2.48, u * 0.40,
                              u * 0.20, u * 0.28), local=FIN, group="body"))
    forms.append(Form("pectoral-near",
                      tapered(u * 0.10, u * 0.28, -u * 0.62, u * 0.94,
                              u * 0.34, u * 0.12), local=FIN))
    forms.append(Form("pectoral-near-edge",
                      tapered(u * 0.02, u * 0.36, -u * 0.60, u * 0.90,
                              u * 0.10, u * 0.05), local=DORSAL,
                      shade=False, clip="pectoral-near"))
    forms.append(Form("pectoral-far-edge",
                      tapered(-u * 0.16, u * 0.16, -u * 0.70, u * 0.62,
                              u * 0.09, u * 0.045), local=BODY_DARK,
                      shade=False, clip="pectoral-far"))
    forms.append(Form("fluke-keel",
                      tapered(-u * 2.00, -u * 0.02, -u * 2.40, -u * 0.34,
                              u * 0.07, u * 0.04), local=DORSAL,
                      shade=False, clip="fluke-upper"))
    forms.insert(2, Form("cape", ellipse(-u * 0.04, -u * 0.34, u * 1.30, u * 0.26,
                                         segments=18), local=DORSAL, rim=False, clip="body"))
    forms.insert(3, Form("belly", ellipse(u * 0.06, u * 0.42, u * 1.06, u * 0.18,
                                          segments=18), local=VENTRAL, rim=False, clip="body"))
    # The eye patch and jaw stripe are the markings that make a bottlenose
    # recognisable; without them the head is a smooth cone.
    forms.append(Form("eye-patch", ellipse(u * 1.00, -u * 0.04, u * 0.22, u * 0.13,
                                           segments=10), local=DORSAL, rim=False, clip="body"))
    forms.append(Form("jaw-stripe",
                      tapered(u * 1.06, u * 0.16, u * 2.02, u * 0.20,
                              u * 0.16, u * 0.07), local=DORSAL, rim=False, clip="rostrum"))
    forms.append(Form("lower-jaw",
                      tapered(u * 1.24, u * 0.20, u * 2.06, u * 0.24,
                              u * 0.20, u * 0.09), local=VENTRAL, rim=False, clip="rostrum"))
    forms.append(Form("blowhole", ellipse(u * 0.86, -u * 0.42, u * 0.09, u * 0.05,
                                          segments=8), local=BODY_DARK, shade=False))
    # The melon crease and the blowhole ridge — small, but they are what stop a
    # dolphin's head reading as a smooth cone.
    forms.append(Form("melon-crease",
                      tapered(u * 1.24, -u * 0.06, u * 0.72, -u * 0.30,
                              u * 0.05, u * 0.03), local=DORSAL,
                      shade=False, clip="body"))
    forms.append(Form("blowhole-ridge",
                      ellipse(u * 0.86, -u * 0.36, u * 0.13, u * 0.04, segments=8),
                      local=DORSAL, shade=False, clip="body"))
    forms.append(Form("peduncle-keel",
                      tapered(-u * 1.40, u * 0.16, -u * 1.98, u * 0.06,
                              u * 0.16, u * 0.08), local=DORSAL, rim=False, clip="peduncle"))
    forms.append(Form("fluke-notch",
                      wedge((-u * 2.02, -u * 0.04), (-u * 2.22, -u * 0.18),
                            (-u * 2.20, u * 0.12), round_base=0.10),
                      local=FIN_FAR, shade=False))
    # Rake marks: the pale healed scars every wild bottlenose carries. Small,
    # irregular and asymmetric - which is also what stops the flank reading as
    # an airbrushed panel.
    # Merging the body into one silhouette costs the paths its parts used to
    # carry, so the detail that replaces them has to be real. A wild bottlenose
    # is covered in rake marks — healed scars from other dolphins' teeth — and
    # they run in near-parallel sets, at varying lengths, never evenly spaced.
    for j, (rx, ry, rl) in enumerate(((-0.30, -0.18, 0.34), (-0.12, -0.06, 0.28),
                                      (-0.44, 0.04, 0.24), (-0.26, -0.10, 0.30),
                                      (-0.08, -0.16, 0.22), (-0.38, -0.02, 0.26),
                                      (-0.18, 0.06, 0.20), (0.06, -0.12, 0.24),
                                      (-0.50, -0.08, 0.18), (-0.02, 0.02, 0.26))):
        forms.append(Form(
            f"rake-{j + 1}",
            tapered(u * rx, u * ry, u * (rx + rl), u * (ry + 0.06),
                    u * 0.028, u * 0.020),
            local=tint(P.key, hue=0, sat=-0.14, val=0.14), shade=False,
        ))
    forms.append(Form("throat-grooves",
                      tapered(u * 1.16, u * 0.30, u * 0.52, u * 0.44,
                              u * 0.10, u * 0.16), local=VENTRAL, rim=False, clip="body"))
    forms.append(Form("dorsal-edge",
                      tapered(u * 0.14, -u * 1.12, -u * 0.24, -u * 0.48,
                              u * 0.07, u * 0.13), local=DORSAL, rim=False, clip="dorsal"))
    # Speckling along the flank where countershading fades into the belly — a
    # real bottlenose marking, and the transition a hard-edged cape cannot make
    # on its own.
    for j, (sx, sy, sr) in enumerate(((-0.66, 0.22, 0.05), (-0.40, 0.28, 0.04),
                                      (-0.14, 0.30, 0.045), (0.14, 0.26, 0.035),
                                      (0.42, 0.20, 0.04), (-0.54, 0.14, 0.03),
                                      (-0.02, 0.18, 0.03), (0.30, 0.10, 0.035))):
        forms.append(Form(
            f"speckle-{j + 1}",
            ellipse(u * sx, u * sy, u * sr, u * sr * 0.8, segments=8),
            local=DORSAL, shade=False, clip="body",
        ))

    forms.append(Form("eye", ellipse(u * 1.02, -u * 0.06, u * 0.06, u * 0.07,
                                     segments=8), role="shadow", shade=False))

    return Recipe(
        name="dolphin", palette="underwater-deep", envelope="swim-cycle",
        forms=forms,
        bones=[
            ("root", None), ("torso_01", "root"), ("torso_02", "torso_01"),
            ("torso_03", "torso_02"), ("caudalPeduncle_01", "torso_03"),
            ("caudalPeduncle_02", "caudalPeduncle_01"), ("flukeRoot", "caudalPeduncle_02"),
            ("rostrum", "torso_01"),
            ("pectoral-near-1", "torso_01"), ("pectoral-near-2", "pectoral-near-1"),
            ("pectoral-far-1", "torso_01"), ("pectoral-far-2", "pectoral-far-1"),
            ("dorsal", "torso_02"),
        ],
        motion_notes=(
            "Fluke beat 1.75 +/- 0.43 Hz at low effort = 34 frames per cycle at "
            "60 fps (JEB jeb246228, 2024).",
            "Peak-to-peak fluke amplitude 33.8% of body length.",
            "Modulate FREQUENCY, hold amplitude. Faster does not mean a bigger "
            "sweep - changing both together is the standard error.",
            "Stroke then glide: fluke to accelerate, then extended glides.",
            "The fluke trailing edge lags the peduncle by 3-4 frames at 60 fps, "
            "amplitude falloff 100/60%.",
        ),
    )


def butterfly(u: float = 100.0) -> Recipe:
    """A butterfly with wings near the top of the downstroke.

    `u` is the forewing length. Wings are deliberately asymmetric in the
    three-quarter view: identical mirrored wings are the twinning error.
    """
    P = PALETTES["warm-optimism"]
    WING_NEAR = tint(P.key, hue=-6, sat=0.16, val=-0.04)
    WING_FAR  = tint(P.key, hue=-10, sat=0.24, val=-0.22)
    HIND_NEAR = tint(P.accent, hue=6, sat=-0.10, val=0.10)
    HIND_FAR  = tint(P.accent, hue=2, sat=0.00, val=-0.10)
    BAND      = tint(P.key, hue=-16, sat=0.34, val=-0.34)
    BODY      = tint(P.key, hue=-18, sat=0.30, val=-0.50)

    forms: list[Form] = []
    for side, sign, role in (("far", -1.0, WING_FAR), ("near", 1.0, WING_NEAR)):
        # Forewing: a broad triangle swept up and out.
        forms.append(Form(
            f"forewing-{side}",
            wedge((0.0, -u * 0.06),
                  (sign * u * 0.92, -u * 0.86),
                  (sign * u * 0.66, u * 0.16), round_base=0.22),
            local=role,
        ))
        # Wing-tip band: the marking that stops a butterfly reading as two
        # plain triangles. Sits INSIDE the wing, so no rim of its own.
        forms.append(Form(
            f"forewing-band-{side}",
            wedge((sign * u * 0.34, -u * 0.40),
                  (sign * u * 0.90, -u * 0.84),
                  (sign * u * 0.64, u * 0.12), round_base=0.18),
            local=BAND, rim=False,
        ))
        # Hindwing: smaller, lower, and a different shape - siblings must differ
        # by at least 20% in size or they read as twins.
        forms.append(Form(
            f"hindwing-{side}",
            wedge((0.0, u * 0.08),
                  (sign * u * 0.62, u * 0.20),
                  (sign * u * 0.34, u * 0.74), round_base=0.26),
            local=HIND_NEAR if side == "near" else HIND_FAR,
        ))

    # Veins. A butterfly wing without them is a paper triangle, and they are
    # also where the bones will sit, so they earn their paths twice.
    for sign, side in ((-1.0, "far"), (1.0, "near")):
        for j, (tx, ty) in enumerate(((0.86, -0.72), (0.74, -0.34), (0.56, 0.06))):
            forms.append(Form(
                f"vein-{side}-{j + 1}",
                tapered(sign * u * 0.05, -u * 0.02, sign * u * tx, u * ty,
                        u * 0.045, u * 0.016),
                local=BAND, shade=False,
            ))
        forms.append(Form(
            f"eyespot-{side}",
            ellipse(sign * u * 0.44, u * 0.36, u * 0.10, u * 0.13, segments=10),
            local=BODY, rim=False,
        ))

    # Marginal spots. Five per wing, varying in size so they are not a
    # repeated stamp - a uniform row is the machine tell.
    for sign, side in ((-1.0, "far"), (1.0, "near")):
        for j, (mx, my, mr) in enumerate(((0.80, -0.62, 0.052), (0.86, -0.40, 0.044),
                                          (0.80, -0.18, 0.058), (0.70, 0.02, 0.040))):
            forms.append(Form(
                f"spot-{side}-{j + 1}",
                ellipse(sign * u * mx, u * my, u * mr, u * mr * 0.86, segments=8),
                local=HIND_NEAR if j % 2 else BODY, shade=False,
            ))

    for sign, side in ((-1.0, "far"), (1.0, "near")):
        forms.append(Form(
            f"antenna-club-{side}",
            ellipse(sign * u * 0.30, -u * 0.52, u * 0.032, u * 0.045, segments=8),
            local=BODY, rim=False,
        ))

    forms.append(Form("thorax", ellipse(0, 0, u * 0.10, u * 0.22, segments=10),
                      local=BODY, rim=False))
    forms.append(Form("abdomen", tapered(0, u * 0.14, 0, u * 0.62,
                                         u * 0.13, u * 0.05), local=BODY))
    for j, (sy, sw) in enumerate(((0.24, 0.115), (0.36, 0.098), (0.48, 0.078))):
        forms.append(Form(
            f"abdomen-seg-{j + 1}",
            ellipse(0, u * sy, u * sw, u * 0.036, segments=8),
            local=BAND, rim=False,
        ))
    forms.append(Form("head", ellipse(0, -u * 0.16, u * 0.075, u * 0.070,
                                      segments=8), local=BODY, rim=False))
    for sign, side in ((-1.0, "far"), (1.0, "near")):
        forms.append(Form(
            f"eye-{side}",
            ellipse(sign * u * 0.045, -u * 0.175, u * 0.030, u * 0.032, segments=8),
            local=BAND, shade=False,
        ))
    for sign, side in ((-1.0, "far"), (1.0, "near")):
        forms.append(Form(
            f"antenna-{side}",
            tapered(sign * u * 0.03, -u * 0.16, sign * u * 0.30, -u * 0.52,
                    u * 0.035, u * 0.02),
            local=BODY, shade=False,
        ))

    return Recipe(
        name="butterfly", palette="warm-optimism", envelope="hero-glide",
        forms=forms,
        bones=[
            ("root", None), ("thorax", "root"), ("abdomen", "thorax"),
            ("forewing-near-root", "thorax"), ("forewing-near-tip", "forewing-near-root"),
            ("forewing-far-root", "thorax"), ("forewing-far-tip", "forewing-far-root"),
            ("hindwing-near-root", "thorax"), ("hindwing-near-tip", "hindwing-near-root"),
            ("hindwing-far-root", "thorax"), ("hindwing-far-tip", "hindwing-far-root"),
            ("antenna-near", "thorax"), ("antenna-far", "thorax"),
        ],
        motion_notes=(
            "Wingbeat 10 Hz (Chilasa clytia) = 6 frames per beat at 60 fps: "
            "3 down, 3 up. It CANNOT go on twos without strobing - animate on "
            "ones, or smear the wing.",
            "Stroke amplitude 120 +/- 10 degrees, lead-lag about 15 degrees.",
            "Wings are 3D paths with twist, not a flat up-down hinge.",
            "Antennae lag the thorax 3-5 frames at 60 fps, falloff 100/65/40%.",
        ),
    )


RECIPES = {"sea-turtle": sea_turtle, "dolphin": dolphin, "butterfly": butterfly}


def build(recipe: Recipe, *, light: Light = KEY_UPPER_LEFT,
          ground: bool = False, unit: float = 100.0,
          merge: float = 3.0) -> Built:
    """Realise a recipe into shaded shapes, back to front.

    `merge` is the CIE76 threshold for collapsing indistinguishable colours.
    Pass 0 to keep every generated tone, which is only useful for inspecting
    what the shader produced before quantisation.
    """
    palette = PALETTES[recipe.palette]
    shapes: list[dict] = []
    if ground and recipe.footprint:
        shapes.append(contact_shadow(0, unit * 0.9, recipe.footprint * unit,
                                     palette=palette))
    # The artwork's own width sets the threshold below which a form counts as a
    # small detail, so the rule scales with the subject instead of carrying a
    # pixel constant that is wrong at every other size.
    from .facet import polygon_from_commands
    span = 0.0
    for form in recipe.forms:
        fp = polygon_from_commands(form.commands)
        if fp:
            span = max(span, max(p[0] for p in fp) - min(p[0] for p in fp))

    # Cut every marking to the form it belongs to BEFORE shading, so its tonal
    # regions follow the clipped edge rather than the generous one it was drawn
    # with. Shading first and clipping after would leave highlights hanging in
    # the water where the overhang used to be.
    outlines = {f.name: polygon_from_commands(f.commands) for f in recipe.forms}
    # Group outlines are deliberately NOT clip targets. A merged body is
    # concave, and the clipper needs a convex parent; more to the point, a
    # marking belongs to the part it sits on — a jaw stripe to the rostrum, not
    # to the whole animal — so the individual primitive is also the right answer.
    resolved: list[Form] = []
    for form in recipe.forms:
        if form.clip:
            parent = outlines.get(form.clip)
            if parent is None:
                raise ValueError(
                    f"{form.name!r} clips to {form.clip!r}, which is not a form "
                    f"in this recipe; known: {sorted(outlines)}"
                )
            cut = clip_to(polygon_from_commands(form.commands), parent)
            if len(cut) < 3:
                # The marking missed its parent entirely. Silently dropping it
                # would hide a placement bug behind a slightly emptier drawing.
                raise ValueError(
                    f"{form.name!r} lies entirely outside {form.clip!r} - "
                    f"check the ratios that place it"
                )
            form = replace(form, commands=smooth_polygon(cut))
        resolved.append(form)

    # Merge each body group into ONE silhouette before shading.
    #
    # Shading the members separately is what made the first renders read as
    # parts arranged in the shape of an animal: a pectoral fin sharing no edge
    # with the flank got its own highlight, its own terminator and its own rim,
    # so it announced itself as a separate object. One outline gives one light.
    #
    # Order is preserved by emitting the merged form where its FIRST member sat,
    # since that member's depth is what the recipe reasoned about.
    merged: list[Form] = []
    seen: set[str] = set()
    for form in resolved:
        if not form.group:
            merged.append(form)
            continue
        if form.group in seen:
            continue
        seen.add(form.group)
        members = [f for f in resolved if f.group == form.group]
        outline = union_outline([polygon_from_commands(f.commands) for f in members])
        if len(outline) < 3:
            raise ValueError(
                f"group {form.group!r} merged to nothing - its members may not "
                f"overlap, and a group whose parts are disjoint is not a body"
            )
        merged.append(replace(form, name=form.group,
                              commands=smooth_polygon(outline, corner_angle=52),
                              group=None))

    for form in merged:
        shapes.extend(shade_form(form, light, palette, reference_span=span))
    shapes = merge_near_duplicates(shapes, threshold=merge)
    return Built(name=recipe.name, shapes=shapes, palette=palette,
                 envelope=recipe.envelope, bones=recipe.bones,
                 motion_notes=recipe.motion_notes)
