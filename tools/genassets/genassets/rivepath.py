"""SVG path data -> Rive path commands.

Rive's MCP `path_editor.createShapes` does NOT accept SVG `d` strings. It takes
structured commands:

    {"commandType": "moveTo",  "x":..,  "y":..}
    {"commandType": "lineTo",  "x":..,  "y":..}
    {"commandType": "cubicTo", "control1X":.., "control1Y":..,
                               "control2X":.., "control2Y":.., "endX":.., "endY":..}
    {"commandType": "close"}

So a traced SVG cannot be handed to Rive directly — its `d` attributes have to be
parsed and re-expressed. This module is that translation, and it is deliberately
pure: no I/O, no Rive, no network, so it is fully unit-testable.

Every SVG command is supported. Since Rive has only line and cubic segments,
quadratics and arcs are converted exactly (quadratic) or by standard decomposition
(arc -> up to 4 cubics).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Iterator

__all__ = ["parse_path", "to_rive_commands", "svg_color_to_rive", "PathBudgetExceeded"]

_TOKEN = re.compile(r"[MmZzLlHhVvCcSsQqTtAa]|[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?")

# Argument count per SVG command.
_ARITY = {
    "M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "T": 2, "A": 7, "Z": 0
}


class PathBudgetExceeded(ValueError):
    """Raised when a conversion would produce more commands than Rive should carry."""


@dataclass
class _Pen:
    x: float = 0.0
    y: float = 0.0
    start_x: float = 0.0
    start_y: float = 0.0
    # Reflection points for the S/T shorthand commands.
    last_cubic_ctrl: tuple[float, float] | None = None
    last_quad_ctrl: tuple[float, float] | None = None
    out: list[dict] = field(default_factory=list)

    def move_to(self, x: float, y: float) -> None:
        self.out.append({"commandType": "moveTo", "x": x, "y": y})
        self.x, self.y = x, y
        self.start_x, self.start_y = x, y
        self.last_cubic_ctrl = self.last_quad_ctrl = None

    def line_to(self, x: float, y: float) -> None:
        self.out.append({"commandType": "lineTo", "x": x, "y": y})
        self.x, self.y = x, y
        self.last_cubic_ctrl = self.last_quad_ctrl = None

    def cubic_to(self, c1x, c1y, c2x, c2y, x, y) -> None:
        self.out.append({
            "commandType": "cubicTo",
            "control1X": c1x, "control1Y": c1y,
            "control2X": c2x, "control2Y": c2y,
            "endX": x, "endY": y,
        })
        self.x, self.y = x, y
        self.last_cubic_ctrl = (c2x, c2y)
        self.last_quad_ctrl = None

    def quad_to(self, qx, qy, x, y) -> None:
        # Exact degree elevation: a quadratic is a cubic whose controls sit
        # two-thirds of the way from each endpoint toward the quadratic control.
        c1x = self.x + 2.0 / 3.0 * (qx - self.x)
        c1y = self.y + 2.0 / 3.0 * (qy - self.y)
        c2x = x + 2.0 / 3.0 * (qx - x)
        c2y = y + 2.0 / 3.0 * (qy - y)
        self.cubic_to(c1x, c1y, c2x, c2y, x, y)
        self.last_quad_ctrl = (qx, qy)

    def close(self) -> None:
        self.out.append({"commandType": "close"})
        self.x, self.y = self.start_x, self.start_y
        self.last_cubic_ctrl = self.last_quad_ctrl = None


def _tokens(d: str) -> Iterator[str]:
    return iter(_TOKEN.findall(d))


def _arc_to_cubics(x0, y0, rx, ry, phi_deg, large_arc, sweep, x1, y1):
    """Endpoint-parameterised arc -> cubic segments (SVG 2 implementation notes F.6)."""
    if rx == 0 or ry == 0 or (x0 == x1 and y0 == y1):
        return [("line", x1, y1)]

    rx, ry = abs(rx), abs(ry)
    phi = math.radians(phi_deg % 360.0)
    cos_p, sin_p = math.cos(phi), math.sin(phi)

    dx2, dy2 = (x0 - x1) / 2.0, (y0 - y1) / 2.0
    x1p = cos_p * dx2 + sin_p * dy2
    y1p = -sin_p * dx2 + cos_p * dy2

    # Scale radii up if they are too small to span the endpoints.
    lam = (x1p * x1p) / (rx * rx) + (y1p * y1p) / (ry * ry)
    if lam > 1:
        s = math.sqrt(lam)
        rx, ry = rx * s, ry * s

    num = rx * rx * ry * ry - rx * rx * y1p * y1p - ry * ry * x1p * x1p
    den = rx * rx * y1p * y1p + ry * ry * x1p * x1p
    coef = math.sqrt(max(0.0, num / den)) if den else 0.0
    if large_arc == sweep:
        coef = -coef
    cxp = coef * rx * y1p / ry
    cyp = -coef * ry * x1p / rx

    cx = cos_p * cxp - sin_p * cyp + (x0 + x1) / 2.0
    cy = sin_p * cxp + cos_p * cyp + (y0 + y1) / 2.0

    def angle(ux, uy, vx, vy):
        dot = ux * vx + uy * vy
        n = math.hypot(ux, uy) * math.hypot(vx, vy)
        if n == 0:
            return 0.0
        a = math.acos(max(-1.0, min(1.0, dot / n)))
        return -a if (ux * vy - uy * vx) < 0 else a

    theta1 = angle(1, 0, (x1p - cxp) / rx, (y1p - cyp) / ry)
    dtheta = angle((x1p - cxp) / rx, (y1p - cyp) / ry, (-x1p - cxp) / rx, (-y1p - cyp) / ry)
    if not sweep and dtheta > 0:
        dtheta -= 2 * math.pi
    elif sweep and dtheta < 0:
        dtheta += 2 * math.pi

    segs = max(1, int(math.ceil(abs(dtheta) / (math.pi / 2))))
    delta = dtheta / segs
    t = 4.0 / 3.0 * math.tan(delta / 4.0)

    out = []
    th = theta1
    px, py = x0, y0
    for _ in range(segs):
        th2 = th + delta
        cos1, sin1 = math.cos(th), math.sin(th)
        cos2, sin2 = math.cos(th2), math.sin(th2)

        def pt(c, s):
            return (cx + rx * cos_p * c - ry * sin_p * s,
                    cy + rx * sin_p * c + ry * cos_p * s)

        ex, ey = pt(cos2, sin2)
        d1x, d1y = (-rx * cos_p * sin1 - ry * sin_p * cos1,
                    -rx * sin_p * sin1 + ry * cos_p * cos1)
        d2x, d2y = (-rx * cos_p * sin2 - ry * sin_p * cos2,
                    -rx * sin_p * sin2 + ry * cos_p * cos2)
        out.append(("cubic", px + t * d1x, py + t * d1y, ex - t * d2x, ey - t * d2y, ex, ey))
        px, py, th = ex, ey, th2
    return out


def parse_path(d: str, *, max_commands: int | None = None) -> list[dict]:
    """Parse an SVG `d` string into Rive path commands.

    Supports every SVG command including relative forms, the S/T shorthands, and
    elliptical arcs. Raises PathBudgetExceeded when `max_commands` is exceeded.
    """
    pen = _Pen()
    toks = list(_tokens(d))
    i = 0
    cmd: str | None = None

    while i < len(toks):
        tok = toks[i]
        if tok.isalpha():
            cmd = tok
            i += 1
            if cmd in "Zz":
                pen.close()
                cmd = None
                continue
        elif cmd is None:
            raise ValueError(f"path data starts with a number, not a command: {d[:40]!r}")
        else:
            # Repeated coordinate set: an implicit repeat of the last command,
            # except that a repeated moveto means lineto (SVG spec).
            if cmd == "M":
                cmd = "L"
            elif cmd == "m":
                cmd = "l"

        upper = cmd.upper()
        rel = cmd.islower()
        n = _ARITY[upper]
        if i + n > len(toks):
            raise ValueError(f"truncated {cmd!r} command in path data")
        args = [float(t) for t in toks[i:i + n]]
        i += n

        px, py = pen.x, pen.y
        if upper == "M":
            x, y = (px + args[0], py + args[1]) if rel else (args[0], args[1])
            pen.move_to(x, y)
        elif upper == "L":
            x, y = (px + args[0], py + args[1]) if rel else (args[0], args[1])
            pen.line_to(x, y)
        elif upper == "H":
            pen.line_to(px + args[0] if rel else args[0], py)
        elif upper == "V":
            pen.line_to(px, py + args[0] if rel else args[0])
        elif upper == "C":
            v = [px + a if k % 2 == 0 else py + a for k, a in enumerate(args)] if rel else args
            pen.cubic_to(*v)
        elif upper == "S":
            rx_, ry_ = pen.last_cubic_ctrl or (px, py)
            c1x, c1y = 2 * px - rx_, 2 * py - ry_
            v = [px + a if k % 2 == 0 else py + a for k, a in enumerate(args)] if rel else args
            pen.cubic_to(c1x, c1y, v[0], v[1], v[2], v[3])
        elif upper == "Q":
            v = [px + a if k % 2 == 0 else py + a for k, a in enumerate(args)] if rel else args
            pen.quad_to(*v)
        elif upper == "T":
            qx_, qy_ = pen.last_quad_ctrl or (px, py)
            cx_, cy_ = 2 * px - qx_, 2 * py - qy_
            v = [px + args[0], py + args[1]] if rel else args
            pen.quad_to(cx_, cy_, v[0], v[1])
        elif upper == "A":
            ex = px + args[5] if rel else args[5]
            ey = py + args[6] if rel else args[6]
            for seg in _arc_to_cubics(px, py, args[0], args[1], args[2],
                                      bool(args[3]), bool(args[4]), ex, ey):
                if seg[0] == "line":
                    pen.line_to(seg[1], seg[2])
                else:
                    pen.cubic_to(*seg[1:])

        if max_commands is not None and len(pen.out) > max_commands:
            raise PathBudgetExceeded(
                f"path produced more than {max_commands} commands"
            )

    return pen.out


def svg_color_to_rive(color: str, opacity: float = 1.0) -> str:
    """Normalize an SVG fill to Rive's #aarrggbb.

    Rive expects alpha FIRST; passing a web #rrggbb silently misreads the channels.
    """
    c = (color or "").strip()
    if c.startswith("rgb"):
        nums = re.findall(r"[\d.]+", c)
        if len(nums) >= 3:
            r, g, b = (int(float(n)) for n in nums[:3])
            if len(nums) >= 4:
                opacity *= float(nums[3])
            c = f"#{r:02x}{g:02x}{b:02x}"
    c = c.lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    if len(c) == 8:
        return f"#{c.lower()}"
    if len(c) != 6:
        raise ValueError(f"unsupported color: {color!r}")
    a = max(0, min(255, round(opacity * 255)))
    return f"#{a:02x}{c.lower()}"


def to_rive_commands(d: str, *, max_commands: int | None = None) -> list[dict]:
    """Alias kept for call-site readability."""
    return parse_path(d, max_commands=max_commands)
