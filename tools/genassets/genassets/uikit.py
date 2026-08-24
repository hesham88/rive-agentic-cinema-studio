"""Authors a Rive UI kit — buttons, toggles, sliders, fields, tabs, panels.

Why this exists
---------------
The studio's own interface is built from Rive rather than from DOM widgets, so
the kit has to be a real `.riv` file with a real interface. This module builds
it end to end over MCP: artboards, geometry, view models and data binds.

The animation contract
----------------------
Each widget exposes its **visual channels** as view-model numbers in the units
the editor uses — opacity and scale as 0-100 percentages, positions and sizes in
pixels, rotation in degrees. It does NOT ship a state machine full of hand-drawn
transitions.

That is a deliberate split, not a shortcut:

  * Rive renders. It is far better at drawing resolution-independent vector art
    with correct fills, corners and gradients than CSS is.
  * The engine animates. `rive-engine`'s `approach()` is frame-rate independent
    (`1 - (1-s)^dt`), so the same easing maths that drives the camera engine
    drives a button's hover lift. One motion system, not two.

The consequence a caller must know: a widget at rest looks correct, but nothing
moves until something drives its channels. `packages/rive-engine/src/react/ui`
is what drives them.

Coordinates
-----------
Parametric shapes take a CENTRE x/y in the parent's space, while `originx`/
`originy` (0..1, on the *path*) decide the point a scale grows from. A fill bar
that must grow rightwards therefore needs `originx = 0` and a left-edge centre
offset, which is why the slider maths below looks fussier than it reads.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from .rivemcp import RiveMCP

__all__ = ["KEY", "PALETTE", "WIDGETS", "build_kit", "Widget"]

# Property keys, read off a live object with `query_property_keys`. These are
# stable core identifiers, not per-file ids.
KEY = {
    "x": 13,
    "y": 14,
    "rotation": 15,
    "scaleX": 16,
    "scaleY": 17,
    "opacity": 18,
    "width": 20,
    "height": 21,
    "originX": 123,
    "originY": 124,
    "cornerRadius": 31,
    "linkCornerRadius": 164,
    "name": 4,
}

# The studio palette, in Rive's #aarrggbb order. Sampled from the artwork the
# generative pipeline produced, so the kit and the scenes share one world.
PALETTE = {
    "void": "#ff070a18",
    "deep": "#ff0b1026",
    "mid": "#ff1b2a5e",
    "rive": "#ff2a3895",
    "ignite": "#ffea5a20",
    "flame": "#fff9d366",
    "paper": "#fff2f5fa",
    "slate": "#ff7d8aa3",
    "clear": "#00000000",
    # Glass, as pigment: a light film over whatever sits behind it.
    "glass": "#26ffffff",
    "hairline": "#1fffffff",
    "edge": "#59ffffff",
}


@dataclass
class Widget:
    """One artboard in the kit."""

    name: str
    width: int
    height: int
    view_model: str
    #: property name -> Rive DataType understood by `viewmodel_editor`.
    properties: dict[str, str]
    #: Builds the geometry; returns {channel: (objectId, propertyKey)} to bind.
    build: Callable[["KitBuilder", str], dict[str, tuple[str, int]]]
    #: Starting values for channels, so the widget looks right before anything
    #: drives it. Without these a glow sits at full opacity on first paint.
    rest: dict[str, float] = field(default_factory=dict)


class KitBuilder:
    """Thin, chatty wrapper over the MCP calls this module needs."""

    def __init__(self, mcp: RiveMCP, *, verbose: bool = True):
        self.mcp = mcp
        self.verbose = verbose

    def log(self, msg: str) -> None:
        if self.verbose:
            print(f"  {msg}", flush=True)

    # ------------------------------------------------------------- primitives

    def artboard(self, name: str, width: int, height: int) -> str:
        r = self.mcp.call(
            "open_file_editor",
            {
                "command": "createArtboard",
                "data": {"createArtboard": [{"name": name, "width": width, "height": height}]},
            },
        )
        ab = r["artboards"][0]["id"]
        self.mcp.call(
            "open_file_editor",
            {"command": "focusArtboard", "data": {"focusArtboard": {"artboardId": ab}}},
        )
        self.log(f"artboard {name} -> {ab}")
        return ab

    def rect(
        self,
        parent: str,
        name: str,
        *,
        x: float,
        y: float,
        w: float,
        h: float,
        radius: float = 0,
        color: str = PALETTE["glass"],
        stroke: str | None = None,
        stroke_width: float = 1,
    ) -> tuple[str, str]:
        """Returns (shapeId, pathId). Paints are attached at creation."""
        paints: list[dict[str, Any]] = [{"paintType": "fill", "color": color}]
        if stroke:
            paints.append(
                {"paintType": "stroke", "color": stroke, "thickness": stroke_width}
            )
        r = self.mcp.call(
            "path_editor",
            {
                "command": "createParametricShapes",
                "data": {
                    "createParametricShapes": {
                        "shapes": [
                            {
                                "primitive": "rectangle",
                                "name": name,
                                "parentId": parent,
                                "x": x,
                                "y": y,
                                "width": w,
                                "height": h,
                                "cornerRadius": radius,
                                "paints": paints,
                            }
                        ]
                    }
                },
            },
        )
        s = r["shapes"][0]
        return s["id"], s["pathId"]

    def ellipse(
        self,
        parent: str,
        name: str,
        *,
        x: float,
        y: float,
        w: float,
        h: float,
        color: str,
    ) -> tuple[str, str]:
        r = self.mcp.call(
            "path_editor",
            {
                "command": "createParametricShapes",
                "data": {
                    "createParametricShapes": {
                        "shapes": [
                            {
                                "primitive": "ellipse",
                                "name": name,
                                "parentId": parent,
                                "x": x,
                                "y": y,
                                "width": w,
                                "height": h,
                                "paints": [{"paintType": "fill", "color": color}],
                            }
                        ]
                    }
                },
            },
        )
        s = r["shapes"][0]
        return s["id"], s["pathId"]

    def set(self, values: dict[str, dict[int, Any]]) -> None:
        self.mcp.call("set_property_values", {"propertyValues": values})

    def anchor_left(self, path_id: str) -> None:
        """Make a shape scale/resize from its left edge instead of its centre."""
        self.set({path_id: {KEY["originX"]: 0}})

    def transparent_artboard(self, artboard_id: str) -> None:
        """Clear the editor's default #282828 artboard fill.

        A generated widget is composited over a page, so an opaque artboard
        background paints a grey slab behind every rounded corner. The fill
        object is a `SolidColor` under the artboard's own `Fill`, which is the
        first Fill in the hierarchy.
        """
        h = self.mcp.call("get_artboard_hierarchy", {"artboardId": artboard_id})
        for obj in h.get("objects", []):
            if "SolidColor" in obj.get("types", []):
                # `colorValue` is key 37 on SolidColor; set via the paint API to
                # stay independent of that key's stability.
                self.set({obj["id"]: {37: PALETTE["clear"]}})
                self.log(f"artboard {artboard_id} background cleared")
                return
        self.log(f"artboard {artboard_id} had no solid background to clear")


# --------------------------------------------------------------------------- #
# Widget geometry
#
# Each builder returns the channels it wants bound: a channel name mapped to the
# object and property key that channel drives.
# --------------------------------------------------------------------------- #


def _button(b: KitBuilder, ab: str) -> dict[str, tuple[str, int]]:
    # Back to front: the glow sits under the surface so it reads as light
    # escaping from behind the control rather than a highlight painted on top.
    glow, _ = b.rect(ab, "glow", x=110, y=30, w=214, h=52, radius=16, color=PALETTE["ignite"])
    surface, _ = b.rect(
        ab,
        "surface",
        x=110,
        y=28,
        w=220,
        h=56,
        radius=16,
        color=PALETTE["glass"],
        stroke=PALETTE["edge"],
    )
    tint, _ = b.rect(ab, "tint", x=110, y=28, w=220, h=56, radius=16, color=PALETTE["flame"])
    return {
        "glow": (glow, KEY["opacity"]),
        "tint": (tint, KEY["opacity"]),
        "scaleX": (surface, KEY["scaleX"]),
        "scaleY": (surface, KEY["scaleY"]),
        "lift": (surface, KEY["y"]),
    }


def _toggle(b: KitBuilder, ab: str) -> dict[str, tuple[str, int]]:
    b.rect(ab, "track", x=34, y=18, w=68, h=36, radius=18, color=PALETTE["glass"],
           stroke=PALETTE["hairline"])
    on, _ = b.rect(ab, "track-on", x=34, y=18, w=68, h=36, radius=18, color=PALETTE["ignite"])
    knob, _ = b.ellipse(ab, "knob", x=18, y=18, w=26, h=26, color=PALETTE["paper"])
    return {
        "on": (on, KEY["opacity"]),
        "knobX": (knob, KEY["x"]),
    }


def _slider(b: KitBuilder, ab: str) -> dict[str, tuple[str, int]]:
    # Track spans x 14..226 (212 wide) with a 6px bar, centred vertically.
    b.rect(ab, "track", x=120, y=18, w=212, h=6, radius=3, color=PALETTE["hairline"])
    fill, fill_path = b.rect(ab, "fill", x=14, y=18, w=212, h=6, radius=3,
                             color=PALETTE["ignite"])
    # Centre at the LEFT end plus origin 0 means width grows rightwards.
    b.anchor_left(fill_path)
    thumb, _ = b.ellipse(ab, "thumb", x=14, y=18, w=18, h=18, color=PALETTE["paper"])
    return {
        "fillW": (fill_path, KEY["width"]),
        "thumbX": (thumb, KEY["x"]),
    }


def _field(b: KitBuilder, ab: str) -> dict[str, tuple[str, int]]:
    ring, _ = b.rect(ab, "ring", x=150, y=26, w=300, h=52, radius=12,
                     color=PALETTE["clear"], stroke=PALETTE["flame"], stroke_width=2)
    b.rect(ab, "surface", x=150, y=26, w=296, h=48, radius=11,
           color=PALETTE["glass"], stroke=PALETTE["hairline"])
    caret, _ = b.rect(ab, "caret", x=22, y=26, w=2, h=22, radius=1, color=PALETTE["flame"])
    return {
        "ring": (ring, KEY["opacity"]),
        "caret": (caret, KEY["opacity"]),
        "caretX": (caret, KEY["x"]),
    }


def _select(b: KitBuilder, ab: str) -> dict[str, tuple[str, int]]:
    b.rect(ab, "surface", x=110, y=26, w=220, h=52, radius=12,
           color=PALETTE["glass"], stroke=PALETTE["hairline"])
    # Two bars rotated into a chevron; rotating the group opens it downwards.
    chevron, _ = b.rect(ab, "chevron", x=192, y=26, w=12, h=2, radius=1,
                        color=PALETTE["paper"])
    return {
        "chevron": (chevron, KEY["rotation"]),
        "panel": (chevron, KEY["opacity"]),
    }


def _tabs(b: KitBuilder, ab: str) -> dict[str, tuple[str, int]]:
    b.rect(ab, "trough", x=165, y=22, w=330, h=44, radius=14,
           color=PALETTE["glass"], stroke=PALETTE["hairline"])
    ind, ind_path = b.rect(ab, "indicator", x=4, y=22, w=106, h=36, radius=11,
                           color=PALETTE["paper"])
    b.anchor_left(ind_path)
    return {
        "indX": (ind, KEY["x"]),
        "indW": (ind_path, KEY["width"]),
    }


def _progress(b: KitBuilder, ab: str) -> dict[str, tuple[str, int]]:
    b.rect(ab, "track", x=120, y=5, w=240, h=10, radius=5, color=PALETTE["hairline"])
    fill, fill_path = b.rect(ab, "fill", x=0, y=5, w=240, h=10, radius=5,
                             color=PALETTE["ignite"])
    b.anchor_left(fill_path)
    shimmer, _ = b.rect(ab, "shimmer", x=0, y=5, w=48, h=10, radius=5,
                        color=PALETTE["flame"])
    return {
        "fillW": (fill_path, KEY["width"]),
        "shimmerX": (shimmer, KEY["x"]),
        "shimmer": (shimmer, KEY["opacity"]),
    }


def _panel(b: KitBuilder, ab: str) -> dict[str, tuple[str, int]]:
    b.rect(ab, "surface", x=170, y=110, w=340, h=220, radius=18,
           color=PALETTE["glass"], stroke=PALETTE["hairline"])
    # A narrow bright band that travels across the top edge — the highlight a
    # real pane of glass catches when it moves under a light.
    sheen, _ = b.rect(ab, "sheen", x=40, y=1, w=90, h=2, color=PALETTE["edge"])
    edge, _ = b.rect(ab, "edge", x=170, y=110, w=340, h=220, radius=18,
                     color=PALETTE["clear"], stroke=PALETTE["ignite"], stroke_width=1.5)
    return {
        "sheenX": (sheen, KEY["x"]),
        "sheen": (sheen, KEY["opacity"]),
        "edge": (edge, KEY["opacity"]),
    }


WIDGETS: list[Widget] = [
    Widget("ui/button", 220, 56, "ButtonVM",
           {"glow": "number", "tint": "number", "scaleX": "number",
            "scaleY": "number", "lift": "number"},
           _button,
           rest={"glow": 0, "tint": 0, "scaleX": 100, "scaleY": 100, "lift": 28}),
    Widget("ui/toggle", 68, 36, "ToggleVM",
           {"on": "number", "knobX": "number"},
           _toggle, rest={"on": 0, "knobX": 18}),
    Widget("ui/slider", 240, 36, "SliderVM",
           {"fillW": "number", "thumbX": "number"},
           _slider, rest={"fillW": 0, "thumbX": 14}),
    Widget("ui/field", 300, 52, "FieldVM",
           {"ring": "number", "caret": "number", "caretX": "number"},
           _field, rest={"ring": 0, "caret": 0, "caretX": 22}),
    Widget("ui/select", 220, 52, "SelectVM",
           {"chevron": "number", "panel": "number"},
           _select, rest={"chevron": 0, "panel": 100}),
    Widget("ui/tabs", 330, 44, "TabsVM",
           {"indX": "number", "indW": "number"},
           _tabs, rest={"indX": 4, "indW": 106}),
    Widget("ui/progress", 240, 10, "ProgressVM",
           {"fillW": "number", "shimmerX": "number", "shimmer": "number"},
           _progress, rest={"fillW": 0, "shimmerX": 0, "shimmer": 0}),
    Widget("ui/panel", 340, 220, "PanelVM",
           {"sheenX": "number", "sheen": "number", "edge": "number"},
           _panel, rest={"sheenX": 40, "sheen": 0, "edge": 0}),
]


KIT_VIEW_MODEL = "KitVM"


def _channel_union() -> list[str]:
    """Every channel any widget declares, deduplicated, in declaration order.

    Names repeat across widgets on purpose — a slider and a progress bar both
    call their bar `fillW` — and sharing the name is safe because each artboard
    is instanced separately at runtime, so two widgets never see each other's
    values.
    """
    seen: dict[str, None] = {}
    for w in WIDGETS:
        for name in w.properties:
            seen.setdefault(name, None)
    return list(seen)


def ensure_kit_view_model(mcp: RiveMCP, *, verbose: bool = True) -> tuple[str, dict[str, str]]:
    """Returns (viewModelId, {channel: propertyId}) for the shared kit model.

    Why one shared view model rather than one per widget:

    `viewmodel_editor.createViewModels` returns a perfectly good ViewModel
    object with an id, properties and instances — and the editor will happily
    bind it to an artboard and data-bind its properties. But it is never added
    to the FILE's view-model registry: `listViewModels` does not report it, and,
    fatally, the runtime exporter walks that registry, so the whole view model
    is dropped from the `.riv`. The result is a file that behaves correctly in
    the editor and reports no view model at all at runtime.

    View models that are already in the registry work, and `addProperties` can
    extend them. So the kit reuses the registry entry every Rive file is born
    with (`ViewModel1`), renames it, and hangs every widget's channels off it.
    """
    b = KitBuilder(mcp, verbose=verbose)
    listed = mcp.call(
        "viewmodel_editor", {"command": "listViewModels", "data": {"listViewModels": {}}}
    )["viewModels"]

    vm = next((v for v in listed if v["name"] == KIT_VIEW_MODEL), None)
    if vm is None:
        # `ViewModel1` is the empty model a new Rive file ships with. Claiming
        # it is the only route to a registered view model over MCP today.
        seed = next(
            (v for v in listed if v["name"] == "ViewModel1"),
            next((v for v in listed if not v["viewModelProperties"]), None),
        )
        if seed is None:
            raise RuntimeError(
                "no empty registered view model to claim; create one in the editor "
                "and re-run (see this function's docstring for why)"
            )
        # `viewmodel_editor` has no rename command, so set the name property
        # (key 557) directly. Renaming rather than creating is the whole point:
        # the registry entry is what survives export.
        b.set({seed["id"]: {557: KIT_VIEW_MODEL}})
        vm = {**seed, "name": KIT_VIEW_MODEL}
        b.log(f"claimed {seed['name']} -> {KIT_VIEW_MODEL}")

    vm_id = vm["id"]
    have = {p["name"] for p in vm["viewModelProperties"]}
    missing = [c for c in _channel_union() if c not in have]
    if missing:
        mcp.call(
            "viewmodel_editor",
            {"command": "addProperties", "data": {"addProperties": {"viewModels": [
                {"viewModelId": vm_id,
                 "viewModelProperties": [
                     {"name": c, "propertyType": "number"} for c in missing]}]}}},
        )
        b.log(f"added {len(missing)} channels to {KIT_VIEW_MODEL}")

    listed = mcp.call(
        "viewmodel_editor", {"command": "listViewModels", "data": {"listViewModels": {}}}
    )["viewModels"]
    vm = next(v for v in listed if v["id"] == vm_id)
    return vm_id, {p["name"]: p["id"] for p in vm["viewModelProperties"]}


def build_kit(mcp: RiveMCP, *, only: list[str] | None = None,
              verbose: bool = True) -> dict[str, Any]:
    """Builds every widget into the currently open file.

    Idempotency is NOT claimed: running twice creates a second set of artboards.
    The file is the source of truth, so delete the old ones first if rebuilding.
    """
    b = KitBuilder(mcp, verbose=verbose)
    vm_id, prop_ids = ensure_kit_view_model(mcp, verbose=verbose)

    instances = mcp.call(
        "viewmodel_editor",
        {"command": "listViewModelInstances",
         "data": {"listViewModelInstances": {"viewModelId": vm_id}}},
    )["instances"]
    instance_id = instances[0]["id"]

    made: dict[str, Any] = {}
    for w in WIDGETS:
        if only and w.name not in only:
            continue
        print(f"[{w.name}]", flush=True)
        ab = b.artboard(w.name, w.width, w.height)
        b.transparent_artboard(ab)
        channels = w.build(b, ab)

        bound = mcp.call(
            "viewmodel_editor",
            {"command": "bindViewModelToArtboard", "data": {"bindViewModelToArtboard": {
                "artboardId": ab, "viewModelId": vm_id,
                "viewModelInstanceId": instance_id}}},
        )
        if not bound.get("viewModelInstance"):
            raise RuntimeError(f"{w.name}: artboard binding did not report an instance")

        bindings = []
        for channel, (obj_id, prop_key) in channels.items():
            if channel not in prop_ids:
                raise RuntimeError(f"{w.name}: no kit channel named {channel}")
            bindings.append({"objectId": obj_id, "propertyKey": prop_key,
                             "viewModelPropertyId": prop_ids[channel]})
        mcp.call("viewmodel_editor", {"command": "databind", "data": {"databind": {
            "viewModelId": vm_id, "bindings": bindings}}})
        b.log(f"bound {len(bindings)} channels")

        # Resting values, so the widget is correct on first paint.
        for channel, value in w.rest.items():
            if channel in channels:
                obj_id, prop_key = channels[channel]
                b.set({obj_id: {prop_key: value}})

        made[w.name] = {"artboardId": ab, "channels": list(channels)}

    made["_viewModel"] = {"id": vm_id, "instanceId": instance_id}
    return made


# --------------------------------------------------------------------------- #
# Export
# --------------------------------------------------------------------------- #

#: Artboards produced by `build_kit`, in the order they are declared.
KIT_ARTBOARD_NAMES = [w.name for w in WIDGETS]


def bind_all(mcp: RiveMCP, pairs: dict[str, tuple[str, str]], *,
             verbose: bool = True) -> None:
    """Re-bind each artboard to its view model's named instance.

    `pairs` maps artboard name -> (artboardId, viewModelId). Use this to repair
    a file built before the binding step was fixed; `build_kit` already does it.
    """
    b = KitBuilder(mcp, verbose=verbose)
    for name, (ab, vm_id) in pairs.items():
        instances = mcp.call(
            "viewmodel_editor",
            {"command": "listViewModelInstances",
             "data": {"listViewModelInstances": {"viewModelId": vm_id}}},
        )["instances"]
        default = next((i for i in instances if i["name"] == "Default"), instances[0])
        r = mcp.call(
            "viewmodel_editor",
            {"command": "bindViewModelToArtboard", "data": {"bindViewModelToArtboard": {
                "artboardId": ab, "viewModelId": vm_id,
                "viewModelInstanceId": default["id"]}}},
        )
        if not r.get("viewModelInstance"):
            raise RuntimeError(f"{name}: binding did not report an instance")
        b.log(f"{name} -> {r['viewModel']['name']} / {r['viewModelInstance']['name']}")


def export_kit(mcp: RiveMCP, destination: str, *, verbose: bool = True) -> str:
    """Exports ONLY the kit artboards to a `.riv`, then restores the flags.

    Rive's export includes every artboard whose `includeinexport` flag (property
    key 802) is set, so a file that also holds scenes would ship them inside the
    UI kit. This flips the flags, exports, and puts them back — leaving the
    document as it found it even when the export fails.
    """
    b = KitBuilder(mcp, verbose=verbose)
    boards = mcp.call("list_artboards")["artboards"]
    kit_ids = [a["id"] for a in boards if a["name"] in KIT_ARTBOARD_NAMES]
    other_ids = [a["id"] for a in boards if a["name"] not in KIT_ARTBOARD_NAMES]

    before = mcp.call(
        "query_property_values",
        {"objectIds": [a["id"] for a in boards],
         "propertyKeys": {a["id"]: [802] for a in boards}},
    )["values"]

    mcp.call("set_property_values", {"propertyValues": {
        **{i: {802: True} for i in kit_ids},
        **{i: {802: False} for i in other_ids},
    }})
    try:
        r = mcp.call("export_file", {"format": "riv", "destination": destination})
        b.log(f"exported {r['bytes']} bytes -> {r['path']}")
        return r["path"]
    finally:
        mcp.call("set_property_values", {"propertyValues": {
            oid: {802: bool(v.get("802", False))} for oid, v in before.items()
        }})
        b.log("export flags restored")
