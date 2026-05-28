"""Wall-line cleanup: dedupe, snap, and merge collinear segments.

Operates on :class:`NormLine` objects from ``vector_anchor.py`` so this
module composes with the rest of the ingest pipeline.  Input is a noisy
set of segments produced by vectorizing a CAD PDF; output is a clean,
de-duplicated, snapped set ready for planar-graph construction.

Three stages, applied in this order:

  1. **Dedupe** — identical or nearly-identical segments are collapsed
     into a single representative.  An architectural CAD file often
     contains the same wall edge drawn multiple times (once as wall,
     once as hatch boundary, once as line-type definition).
  2. **Snap** — endpoints are rounded to a tolerance grid so that two
     lines that *should* meet at the same corner actually share a vertex.
     Without this, planar-graph construction will leave hairline gaps
     and the face-finder will produce one giant outer face instead of
     individual rooms.
  3. **Merge** — collinear adjacent segments are joined into one.
     Walls are often drafted as two or three short segments; we want
     one segment per visible wall.

All operations are O(N²) worst-case; for a typical floor plan with a few
thousand segments this is fast (< 1 second).  If performance becomes a
concern we can swap in a spatial index later.
"""

from __future__ import annotations

import logging
import math
from typing import Iterable

from ..vector_anchor import NormLine

logger = logging.getLogger(__name__)


def dedupe_lines(
    lines: Iterable[NormLine],
    *,
    endpoint_tol: float = 0.0005,   # 0.05% of image dimension
    angle_tol_deg: float = 1.0,
) -> list[NormLine]:
    """Remove duplicate / overlapping segments.

    Two segments are considered duplicates when:
      * both endpoints are within ``endpoint_tol`` of each other (either
        same-order or reversed-order), OR
      * they are collinear (angles within ``angle_tol_deg``) AND one's
        projection is fully contained inside the other's.

    The longer of the two wins; the shorter is dropped.
    """
    lines = list(lines)
    keep = [True] * len(lines)

    for i in range(len(lines)):
        if not keep[i]:
            continue
        a = lines[i]
        ax0, ay0, ax1, ay1 = a.x0, a.y0, a.x1, a.y1
        a_len = a.length()
        a_ang = a.angle_deg()
        for j in range(i + 1, len(lines)):
            if not keep[j]:
                continue
            b = lines[j]

            # Identical endpoints (same direction)
            if (abs(b.x0 - ax0) < endpoint_tol and abs(b.y0 - ay0) < endpoint_tol
                and abs(b.x1 - ax1) < endpoint_tol and abs(b.y1 - ay1) < endpoint_tol):
                keep[j] = True if b.length() > a_len else False
                if b.length() > a_len:
                    keep[i] = False
                    break
                continue

            # Identical endpoints (reversed)
            if (abs(b.x0 - ax1) < endpoint_tol and abs(b.y0 - ay1) < endpoint_tol
                and abs(b.x1 - ax0) < endpoint_tol and abs(b.y1 - ay0) < endpoint_tol):
                keep[j] = False
                continue

            # Collinear overlap test
            b_ang = b.angle_deg()
            d_ang = abs(a_ang - b_ang)
            d_ang = min(d_ang, 180 - d_ang)
            if d_ang > angle_tol_deg:
                continue
            # Perpendicular distance of b midpoint to line through a
            mid_bx = (b.x0 + b.x1) / 2.0
            mid_by = (b.y0 + b.y1) / 2.0
            if a_len < 1e-9:
                continue
            avx, avy = (ax1 - ax0) / a_len, (ay1 - ay0) / a_len
            nx, ny = -avy, avx
            sep = abs((mid_bx - ax0) * nx + (mid_by - ay0) * ny)
            if sep > endpoint_tol:
                continue
            # Projections of b endpoints onto a
            t0 = ((b.x0 - ax0) * avx + (b.y0 - ay0) * avy) / a_len
            t1 = ((b.x1 - ax0) * avx + (b.y1 - ay0) * avy) / a_len
            tmin, tmax = min(t0, t1), max(t0, t1)
            if tmin >= -endpoint_tol and tmax <= 1.0 + endpoint_tol:
                # b is inside a
                keep[j] = False
                continue
            # a inside b — drop a, keep b
            if 0 >= tmin - endpoint_tol and 1.0 <= tmax + endpoint_tol:
                keep[i] = False
                break

    out = [l for k, l in zip(keep, lines) if k]
    logger.info("Dedupe: %d -> %d segments", len(lines), len(out))
    return out


def snap_endpoints(
    lines: Iterable[NormLine],
    *,
    snap_tol: float = 0.0015,     # ~0.15% of image dimension
) -> list[NormLine]:
    """Snap each endpoint to a tolerance grid.

    All endpoints within ``snap_tol`` of each other are clustered and
    replaced with the cluster centroid.  Without this step, two walls
    that should share a corner end up with hairline gaps that prevent
    planar-graph face enumeration from closing rooms.

    Implementation: round each endpoint to a grid of size ``snap_tol``,
    then take the mean of all original endpoints in the same grid cell.
    """
    lines = list(lines)
    if not lines:
        return []

    # First pass: bucket every endpoint by grid cell.
    grid: dict[tuple[int, int], list[tuple[float, float]]] = {}
    for l in lines:
        for x, y in ((l.x0, l.y0), (l.x1, l.y1)):
            key = (round(x / snap_tol), round(y / snap_tol))
            grid.setdefault(key, []).append((x, y))

    # Cell -> snapped representative (centroid).
    rep: dict[tuple[int, int], tuple[float, float]] = {}
    for key, pts in grid.items():
        mx = sum(p[0] for p in pts) / len(pts)
        my = sum(p[1] for p in pts) / len(pts)
        rep[key] = (mx, my)

    out: list[NormLine] = []
    for l in lines:
        k0 = (round(l.x0 / snap_tol), round(l.y0 / snap_tol))
        k1 = (round(l.x1 / snap_tol), round(l.y1 / snap_tol))
        sx0, sy0 = rep[k0]
        sx1, sy1 = rep[k1]
        # Drop zero-length segments produced by snapping.
        if math.hypot(sx1 - sx0, sy1 - sy0) < snap_tol:
            continue
        out.append(NormLine(
            x0=sx0, y0=sy0, x1=sx1, y1=sy1, width_norm=l.width_norm,
        ))
    logger.info("Snap: %d -> %d segments (tol=%.4f)",
                len(lines), len(out), snap_tol)
    return out


def merge_collinear(
    lines: Iterable[NormLine],
    *,
    angle_tol_deg: float = 1.0,
    join_tol: float = 0.002,
) -> list[NormLine]:
    """Merge collinear segments that share or nearly share an endpoint.

    For each pair (a, b):
      * same angle within ``angle_tol_deg``
      * perpendicular distance between the lines under ``join_tol``
      * at least one endpoint of b is within ``join_tol`` of an endpoint of a

    The two are replaced with the single segment spanning their extreme
    endpoints.
    """
    lines = list(lines)
    changed = True
    iterations = 0
    while changed and iterations < 8:
        changed = False
        iterations += 1
        out: list[NormLine] = []
        used = [False] * len(lines)
        for i, a in enumerate(lines):
            if used[i]:
                continue
            a_ang = a.angle_deg()
            a_len = a.length() or 1e-9
            avx, avy = (a.x1 - a.x0) / a_len, (a.y1 - a.y0) / a_len
            nx, ny = -avy, avx
            merged = a
            for j in range(i + 1, len(lines)):
                if used[j]:
                    continue
                b = lines[j]
                d_ang = abs(a_ang - b.angle_deg())
                d_ang = min(d_ang, 180 - d_ang)
                if d_ang > angle_tol_deg:
                    continue
                # Perpendicular distance from b endpoints to line a
                sep0 = abs((b.x0 - a.x0) * nx + (b.y0 - a.y0) * ny)
                sep1 = abs((b.x1 - a.x0) * nx + (b.y1 - a.y0) * ny)
                if max(sep0, sep1) > join_tol:
                    continue
                # Check endpoint adjacency
                a_pts = [(merged.x0, merged.y0), (merged.x1, merged.y1)]
                b_pts = [(b.x0, b.y0), (b.x1, b.y1)]
                adjacent = any(
                    math.hypot(ap[0] - bp[0], ap[1] - bp[1]) <= join_tol
                    for ap in a_pts for bp in b_pts
                )
                if not adjacent:
                    continue
                # Merge: take the two extreme endpoints along a's direction.
                ts = [
                    ((merged.x0 - a.x0) * avx + (merged.y0 - a.y0) * avy),
                    ((merged.x1 - a.x0) * avx + (merged.y1 - a.y0) * avy),
                    ((b.x0 - a.x0) * avx + (b.y0 - a.y0) * avy),
                    ((b.x1 - a.x0) * avx + (b.y1 - a.y0) * avy),
                ]
                t_lo, t_hi = min(ts), max(ts)
                merged = NormLine(
                    x0=a.x0 + t_lo * avx, y0=a.y0 + t_lo * avy,
                    x1=a.x0 + t_hi * avx, y1=a.y0 + t_hi * avy,
                    width_norm=max(merged.width_norm, b.width_norm),
                )
                used[j] = True
                changed = True
            out.append(merged)
            used[i] = True
        lines = out
    logger.info("Merge: -> %d segments after %d iterations",
                len(lines), iterations)
    return lines


def clean_pipeline(
    lines: Iterable[NormLine],
    *,
    snap_tol: float = 0.0015,
    angle_tol_deg: float = 1.0,
) -> list[NormLine]:
    """Run dedupe → snap → merge in the correct order."""
    lines = list(lines)
    n0 = len(lines)
    lines = dedupe_lines(lines, endpoint_tol=snap_tol, angle_tol_deg=angle_tol_deg)
    lines = snap_endpoints(lines, snap_tol=snap_tol)
    lines = merge_collinear(lines, angle_tol_deg=angle_tol_deg, join_tol=snap_tol * 1.5)
    logger.info("Clean pipeline: %d -> %d segments", n0, len(lines))
    return lines
