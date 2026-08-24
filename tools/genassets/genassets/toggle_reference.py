"""Author the parity reference toggle in the Rive editor, over MCP.

Why this exists
---------------
`packages/rive-engine/src/core/riv/toggle.ts` writes a `.riv` byte by byte. That
it *loads* proves very little — a file can parse cleanly and still draw the
wrong picture. The only honest check is to build the same widget in the editor,
export it, and compare what the runtime renders from each.

This script builds that reference. It is deliberately **additive**: it creates
one new artboard and never deletes, renames or re-parents anything already in
the open document, which is a shared file.

Requires the Rive desktop app running with a file OPEN and focused — MCP reports
"No file context available" otherwise, and no amount of retrying fixes it from
here.

    python -m genassets.toggle_reference [--export DIR]
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import Any

from .rivemcp import RiveMCP, RiveMCPError
from .uikit import KEY, KitBuilder, ensure_kit_view_model

__all__ = ["build_reference_toggle", "ARTBOARD_NAME"]

ARTBOARD_NAME = "ref/toggle"

#: The boolean the reference exposes.
#:
#: Not `checked`: the shared kit view model already carries a NUMERIC `checked`
#: from an earlier run, property types cannot be changed in place, and this is
#: the owner's document — so a distinct name is used rather than deleting
#: something of theirs. The parity test maps the two names.
PROPERTY_NAME = "isChecked"

#: Must match `DEFAULT_TOGGLE` in toggle.ts, or the comparison measures the
#: wrong thing — a difference in styling rather than a difference in encoding.
WIDTH = 68
HEIGHT = 36
TRACK_OFF = "#ff2a3140"
TRACK_ON = "#ffea5a20"
KNOB = "#fff2f5fa"


def build_reference_toggle(mcp: RiveMCP, *, verbose: bool = True) -> dict[str, Any]:
    """Create `ref/toggle` in the open document and return its ids.

    Mirrors the encoder's geometry exactly: a pill track the full artboard size
    with a corner radius of half its height, and a knob inset by half the height
    so it sits flush at either end.
    """
    b = KitBuilder(mcp, verbose=verbose)
    inset = HEIGHT / 2

    ab = b.artboard(ARTBOARD_NAME, WIDTH, HEIGHT)
    b.transparent_artboard(ab)

    track_shape, _ = b.rect(
        ab, "track",
        x=WIDTH / 2, y=HEIGHT / 2, w=WIDTH, h=HEIGHT,
        radius=HEIGHT / 2, color=TRACK_OFF,
    )
    knob_shape, _ = b.ellipse(
        ab, "knob",
        x=inset, y=HEIGHT / 2, w=HEIGHT - 8, h=HEIGHT - 8, color=KNOB,
    )

    # The contract: one boolean, named exactly as the encoder names it.
    #
    # `checked` must be a BOOLEAN. The shared kit model creates channels as
    # numbers by default — a first run of this script created a numeric
    # `checked`, and the parity test caught it: the property name was right and
    # the runtime typed it wrong, so the reference exposed a slider where the
    # encoder exposes a switch.
    #
    # Property TYPE cannot be changed in place, and this is the owner's shared
    # document, so the numeric one is left alone rather than deleted.
    vm_id, prop_ids = ensure_kit_view_model(
        mcp,
        extra=[PROPERTY_NAME],
        extra_types={PROPERTY_NAME: "boolean"},
        verbose=verbose,
    )
    instances = mcp.call(
        "viewmodel_editor",
        {"command": "listViewModelInstances",
         "data": {"listViewModelInstances": {"viewModelId": vm_id}}},
    )["instances"]
    default = next((i for i in instances if i["name"] == "Default"), instances[0])

    bound = mcp.call(
        "viewmodel_editor",
        {"command": "bindViewModelToArtboard", "data": {"bindViewModelToArtboard": {
            "artboardId": ab, "viewModelId": vm_id,
            "viewModelInstanceId": default["id"]}}},
    )
    if not bound.get("viewModelInstance"):
        raise RiveMCPError(f"{ARTBOARD_NAME}: artboard binding reported no instance")

    b.log(f"reference toggle built on {ab}, bound to {bound['viewModel']['name']}")
    return {
        "artboardId": ab,
        "viewModelId": vm_id,
        "track": track_shape,
        "knob": knob_shape,
        "knobTravel": (inset, WIDTH - inset),
        "keys": {"x": KEY["x"]},
    }


def export_reference(mcp: RiveMCP, destination: str, *, verbose: bool = True) -> str:
    """Export ONLY the reference artboard, then restore every export flag.

    Rive ships every artboard whose `includeinexport` (key 802) is set, so a
    naive export would bundle the owner's other work into the parity fixture.
    The restore runs in a `finally` so an export failure still leaves the
    document as it was found.
    """
    b = KitBuilder(mcp, verbose=verbose)
    boards = mcp.call("list_artboards")["artboards"]
    before = mcp.call(
        "query_property_values",
        {"objectIds": [a["id"] for a in boards],
         "propertyKeys": {a["id"]: [802] for a in boards}},
    )["values"]

    mcp.call("set_property_values", {"propertyValues": {
        a["id"]: {802: a["name"] == ARTBOARD_NAME} for a in boards
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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--export", metavar="DIR", help="directory to export the .riv into")
    args = ap.parse_args()

    mcp = RiveMCP()
    mcp.connect()

    session = mcp.call("session_info")
    if not session.get("activeFileId"):
        tabs = ", ".join(t.get("name", "?") for t in session.get("openTabs", [])) or "none"
        print(
            "No file is active in the Rive editor, so MCP has nowhere to build.\n"
            f"  Open tabs: {tabs}\n"
            "  Click the file's tab in the desktop app to focus it, then re-run.",
            file=sys.stderr,
        )
        return 2

    result = build_reference_toggle(mcp)
    if args.export:
        os.makedirs(args.export, exist_ok=True)
        result["exportedTo"] = export_reference(mcp, os.path.normpath(args.export))
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
