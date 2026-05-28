"""Detect door swing arcs from PDF curve geometry.

In a properly drafted plan, every door is drawn as a leaf (straight line)
plus a swing arc (90° quarter-circle). The arc's center is the door
hinge; the arc's radius equals the door width.

Algorithm:

  1. For each PDF curve, fit a circle through three sample points (the
     vector_parser already does this).
  2. Filter to arcs whose radius is a typical door width — 24" to 48"
     (2'-0" to 4'-0"), with 36" being the common default.
  3. Filter to arcs that span ~90° (door swing) — between 60° and 120°.
  4. Snap each arc's hinge center to the nearest wall endpoint.

The output is a list of :class:`DoorArc` records the vector-truth
pipeline can convert into :class:`Opening` objects with the correct
position, width, and wall attachment.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class DoorArc:
    """A door swing arc in image-norm coordinates."""
    center_x: float
    center_y: float
    radius_norm: float       # = door width in image-norm units
    start_angle_deg: float
    end_angle_deg: float
    sweep_deg: float


def detect_door_arcs(
    arc_records: list,
    *,
    min_door_width_in: float = 24.0,
    max_door_width_in: float = 48.0,
    sweep_min_deg: float = 60.0,
    sweep_max_deg: float = 120.0,
    inches_per_norm: float = 1.0,
) -> list[DoorArc]:
    """Filter raw arcs to those that look like door swings.

    ``arc_records`` items must expose ``cx``, ``cy``, ``radius``,
    ``start_angle_deg``, ``end_angle_deg`` (matches ``vector_parser.RawArc``).

    ``inches_per_norm`` is used to bracket the door radius — without it
    we cannot filter by physical door size.
    """
    if inches_per_norm <= 0:
        logger.warning("Inches-per-norm unset; cannot filter arcs by door width.")
        return []

    min_r_norm = min_door_width_in / inches_per_norm
    max_r_norm = max_door_width_in / inches_per_norm

    out: list[DoorArc] = []
    for a in arc_records:
        r = float(getattr(a, "radius", 0.0))
        if r < min_r_norm or r > max_r_norm:
            continue
        s = float(getattr(a, "start_angle_deg", 0.0))
        e = float(getattr(a, "end_angle_deg", 0.0))
        sweep = abs(e - s) % 360.0
        sweep = min(sweep, 360.0 - sweep)
        if sweep < sweep_min_deg or sweep > sweep_max_deg:
            continue
        out.append(DoorArc(
            center_x=float(getattr(a, "cx", 0.0)),
            center_y=float(getattr(a, "cy", 0.0)),
            radius_norm=r,
            start_angle_deg=s,
            end_angle_deg=e,
            sweep_deg=sweep,
        ))
    logger.info("Detected %d door arcs from %d raw arcs (door-width filter %.2f-%.2f in)",
                len(out), len(arc_records), min_door_width_in, max_door_width_in)
    return out


def snap_arc_to_wall(
    arc: DoorArc,
    walls: list,        # objects with .start, .end (each .x, .y)
    *,
    max_snap_norm: float = 0.005,
) -> tuple[str, float]:
    """Return (wall_id, distance_along_wall_norm) of the closest wall, or ('', 0)."""
    best_id = ""
    best_dist = math.inf
    best_t = 0.0
    for w in walls:
        ax, ay = w.start.x, w.start.y
        bx, by = w.end.x, w.end.y
        wx, wy = bx - ax, by - ay
        wlen_sq = wx * wx + wy * wy
        if wlen_sq < 1e-12:
            continue
        t = max(0.0, min(1.0, ((arc.center_x - ax) * wx +
                              (arc.center_y - ay) * wy) / wlen_sq))
        px = ax + t * wx
        py = ay + t * wy
        d = math.hypot(arc.center_x - px, arc.center_y - py)
        if d < best_dist:
            best_dist = d
            best_id = getattr(w, "id", "")
            best_t = t * math.sqrt(wlen_sq)
    if best_dist > max_snap_norm:
        return "", 0.0
    return best_id, best_t
