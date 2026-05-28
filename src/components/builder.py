"""Convert PlanGraph elements into BIM-style components.

Each PlanGraph wall / opening / room / fixture maps to one component
instance with a full property set populated from sensible defaults plus
whatever the ingest pipeline actually measured.

This stage is *purely deterministic* — no AI, no inference. It exists to
turn the geometry-+-labels output of ingest into a build-ready,
schedule-ready, BIM-aligned list of components.
"""

from __future__ import annotations

import logging
import math
import uuid
from typing import Optional

from ..ingest.plan_model import (
    Fixture,
    FixtureKind,
    Opening,
    OpeningKind,
    PlanGraph,
    Room,
    Wall,
    WallStatus,
)
from .schemas import (
    AssemblyLayer,
    CeilingComponent,
    Component,
    ComponentKind,
    DeckComponent,
    DoorComponent,
    FloorComponent,
    Point2D,
    StairComponent,
    WallComponent,
    WindowComponent,
)

logger = logging.getLogger(__name__)


def build_components_from_plan(
    plan: PlanGraph,
    *,
    default_ceiling_height_in: float = 108.0,
    default_floor_thickness_in: float = 4.0,
) -> list[Component]:
    """Return one component per ingest element with full property defaults."""
    components: list[Component] = []

    # Walls --------------------------------------------------------------
    for i, w in enumerate(plan.walls, start=1):
        components.append(_wall_component(w, i, default_ceiling_height_in))

    # Doors / Windows / Cased openings ----------------------------------
    door_idx = window_idx = 0
    for o in plan.openings:
        host = next((w for w in plan.walls if w.id == o.wall_id), None)
        if o.kind == OpeningKind.DOOR:
            door_idx += 1
            components.append(_door_component(o, host, door_idx))
        elif o.kind == OpeningKind.WINDOW:
            window_idx += 1
            components.append(_window_component(o, host, window_idx))
        else:
            door_idx += 1
            components.append(_door_component(o, host, door_idx, cased_opening=True))

    # Floors --------------------------------------------------------------
    # One floor per room polygon — gives us area-accurate floor components.
    for i, r in enumerate(plan.rooms, start=1):
        if len(r.polygon) < 3:
            continue
        components.append(_floor_component(r, i, default_floor_thickness_in))

    # Ceilings ------------------------------------------------------------
    # Same polygon as the floor by default — interior plan view.
    for i, r in enumerate(plan.rooms, start=1):
        if len(r.polygon) < 3:
            continue
        components.append(_ceiling_component(r, i, default_ceiling_height_in))

    # Stairs (from fixtures with kind=Stair) -----------------------------
    stair_idx = 0
    for fx in plan.fixtures or []:
        kind_val = fx.kind.value if hasattr(fx.kind, "value") else str(fx.kind)
        if kind_val == "Stair":
            stair_idx += 1
            components.append(_stair_component(fx, stair_idx))

    # Decks — currently no detection; placeholder hook for later. ---------

    logger.info(
        "Built %d components: %d walls, %d doors, %d windows, %d floors, %d ceilings, %d stairs",
        len(components),
        sum(1 for c in components if c.kind == ComponentKind.WALL),
        sum(1 for c in components if c.kind == ComponentKind.DOOR),
        sum(1 for c in components if c.kind == ComponentKind.WINDOW),
        sum(1 for c in components if c.kind == ComponentKind.FLOOR),
        sum(1 for c in components if c.kind == ComponentKind.CEILING),
        sum(1 for c in components if c.kind == ComponentKind.STAIR),
    )
    return components


# ---------------------------------------------------------------------------
# Individual factories
# ---------------------------------------------------------------------------

def _wall_component(w: Wall, idx: int, ceiling_height_in: float) -> WallComponent:
    status_str = w.status.value if hasattr(w.status, "value") else str(w.status)
    aia_layer = {
        "Existing":           "A-WALL-EXST",
        "Demolition":         "A-WALL-DEMO",
        "New Construction":   "A-WALL-NEWW",
    }.get(status_str, "A-WALL-EXST")

    # Type inference from thickness — practical defaults.
    if w.thickness_in >= 11.0:
        wt = "Exterior CMU"
        comp = _exterior_cmu_composition(w.thickness_in)
        structural = True
    elif w.thickness_in >= 8.0:
        wt = "Exterior Stud"
        comp = _exterior_stud_composition(w.thickness_in)
        structural = True
    elif w.thickness_in >= 5.5:
        wt = "Interior Stud 2x6"
        comp = _interior_stud_composition(w.thickness_in)
        structural = False
    else:
        wt = "Interior Stud 2x4"
        comp = _interior_stud_composition(w.thickness_in)
        structural = False

    height = w.height_in or ceiling_height_in
    return WallComponent(
        id=w.id,
        mark=f"W{idx:03d}",
        name=f"{wt} {w.thickness_in:.1f}\" thk",
        aia_layer=aia_layer,
        csi_division="09" if "New" in status_str else "02",
        start=Point2D(x=w.start.x, y=w.start.y),
        end=Point2D(x=w.end.x, y=w.end.y),
        thickness_in=round(w.thickness_in, 1),
        height_in=round(height, 1),
        wall_type=wt,
        composition=comp,
        structural=structural,
        load_bearing=structural,
        status=status_str,
        geometry=[_wall_geometry(w)],
    )


def _door_component(o: Opening, host: Optional[Wall], idx: int,
                    *, cased_opening: bool = False) -> DoorComponent:
    pos = _opening_center(o, host)
    width = o.width_in or 36.0
    height = o.height_in or 80.0
    is_double = width >= 60
    door_type = (
        "Cased Opening" if cased_opening else
        "Double Swing" if is_double else
        "Single Swing"
    )
    swing = {
        "left": "LHR", "right": "RHR",
    }.get((o.swing_direction or "").lower(), "RHR")

    return DoorComponent(
        id=o.id,
        mark=f"D{idx:03d}",
        name=f"{door_type} {width:.0f}\"x{height:.0f}\"",
        position=Point2D(x=pos[0], y=pos[1]),
        host_wall_id=host.id if host else "",
        width_in=width,
        height_in=height,
        leaf_thickness_in=1.75,
        door_type=door_type,
        swing_direction=swing,
        leaf_material="Hollow Metal" if width >= 36 else "Solid Core Wood",
        frame_material="Hollow Metal",
        hardware_set="HW-1",
        clear_opening_width_in=max(32.0, width - 2.5),
        geometry=[_door_geometry(o, host)] if host else [],
    )


def _window_component(o: Opening, host: Optional[Wall], idx: int) -> WindowComponent:
    pos = _opening_center(o, host)
    width = o.width_in or 36.0
    height = o.height_in or 48.0
    sill = o.sill_height_in or 30.0
    # Type heuristic from aspect ratio
    aspect = width / height if height else 1.0
    if aspect > 1.6:
        wtype = "Sliding"
        operable = True
    elif height > 60:
        wtype = "Double-Hung"
        operable = True
    else:
        wtype = "Fixed"
        operable = False
    return WindowComponent(
        id=o.id,
        mark=f"W{idx:03d}",
        name=f"{wtype} {width:.0f}\"x{height:.0f}\"",
        position=Point2D(x=pos[0], y=pos[1]),
        host_wall_id=host.id if host else "",
        rough_opening_width_in=width,
        rough_opening_height_in=height,
        sill_height_in=sill,
        window_type=wtype,
        operable=operable,
        glazing_type="IGU",
        glass_thickness_in=1.0,
        inner_pane_thickness_in=0.25,
        outer_pane_thickness_in=0.25,
        gas_fill="Argon",
        low_e_coating="Low-E 366",
        u_factor=0.30,
        shgc=0.27,
        frame_material="Aluminum, Thermally Broken",
        geometry=[_window_geometry(o, host)] if host else [],
    )


def _floor_component(r: Room, idx: int, thickness_in: float) -> FloorComponent:
    finish = r.floor_finish or "Polished Concrete"
    comp = _floor_composition(thickness_in, finish)
    return FloorComponent(
        id=f"flr-{idx:03d}-{r.id[-4:]}",
        mark=f"FL{idx:03d}",
        name=f"Floor — {finish} — {r.name or 'Room'}",
        polygon=[Point2D(x=p.x, y=p.y) for p in r.polygon],
        area_sqft=r.area_sqft,
        floor_type="Slab on Grade",
        structure_depth_in=thickness_in,
        composition=comp,
        finish_top=finish,
        finish_thickness_in=_finish_thickness(finish),
        geometry=[_polygon_geometry(r.polygon)],
    )


def _ceiling_component(r: Room, idx: int, height_in: float) -> CeilingComponent:
    finish = r.ceiling_finish or "ACT 2x2 Tegular"
    return CeilingComponent(
        id=f"clg-{idx:03d}-{r.id[-4:]}",
        mark=f"CL{idx:03d}",
        name=f"Ceiling — {finish} — {r.name or 'Room'}",
        polygon=[Point2D(x=p.x, y=p.y) for p in r.polygon],
        area_sqft=r.area_sqft,
        ceiling_type="ACT 2x2" if "ACT" in finish else finish,
        height_in=r.ceiling_height_in or height_in,
        finish=finish,
        composition=_ceiling_composition(finish),
        geometry=[_polygon_geometry(r.polygon)],
    )


def _stair_component(fx: Fixture, idx: int) -> StairComponent:
    w_in = abs(fx.bbox_max.x - fx.bbox_min.x)
    d_in = abs(fx.bbox_max.y - fx.bbox_min.y)
    run = max(w_in, d_in)
    width = min(w_in, d_in)
    n_risers = max(8, int(round(108.0 / 7.5)))
    return StairComponent(
        id=fx.id,
        mark=f"ST{idx:03d}",
        name=f"Stair Run — {n_risers}R",
        polygon=[
            Point2D(x=fx.bbox_min.x, y=fx.bbox_min.y),
            Point2D(x=fx.bbox_max.x, y=fx.bbox_min.y),
            Point2D(x=fx.bbox_max.x, y=fx.bbox_max.y),
            Point2D(x=fx.bbox_min.x, y=fx.bbox_max.y),
        ],
        run_in=run,
        width_in=width,
        total_rise_in=108.0,
        num_risers=n_risers,
        riser_height_in=round(108.0 / n_risers, 2),
        num_treads=n_risers - 1,
        tread_depth_in=round(run / max(n_risers - 1, 1), 1),
        geometry=[_polygon_geometry([
            Point2D(x=fx.bbox_min.x, y=fx.bbox_min.y),
            Point2D(x=fx.bbox_max.x, y=fx.bbox_min.y),
            Point2D(x=fx.bbox_max.x, y=fx.bbox_max.y),
            Point2D(x=fx.bbox_min.x, y=fx.bbox_max.y),
        ])],
    )


# ---------------------------------------------------------------------------
# Composition presets
# ---------------------------------------------------------------------------

def _interior_stud_composition(thickness_in: float) -> list[AssemblyLayer]:
    stud_w = max(2.0, thickness_in - 1.25)
    stud_label = "Steel Stud" if stud_w >= 3.0 else "Wood Stud"
    return [
        AssemblyLayer(name="GWB 5/8\" Type X (Side A)",
                      material_class="Gypsum", thickness_in=0.625, function="Finish"),
        AssemblyLayer(name=f"{stud_label} {stud_w:.1f}\" @ 16\" o.c.",
                      material_class=("Steel" if stud_label == "Steel Stud" else "Wood"),
                      thickness_in=stud_w, function="Substrate"),
        AssemblyLayer(name="GWB 5/8\" Type X (Side B)",
                      material_class="Gypsum", thickness_in=0.625, function="Finish"),
    ]


def _exterior_stud_composition(thickness_in: float) -> list[AssemblyLayer]:
    stud_w = max(3.5, thickness_in - 3.0)
    return [
        AssemblyLayer(name="GWB 5/8\" Type X (Interior)",
                      material_class="Gypsum", thickness_in=0.625, function="Finish"),
        AssemblyLayer(name=f"Steel Stud {stud_w:.1f}\" @ 16\" o.c.",
                      material_class="Steel", thickness_in=stud_w, function="Substrate"),
        AssemblyLayer(name="Mineral Wool Insulation R-21",
                      material_class="Mineral Wool", thickness_in=stud_w, function="Insulation"),
        AssemblyLayer(name="Exterior Sheathing 5/8\" Gypsum",
                      material_class="Gypsum", thickness_in=0.625, function="Substrate"),
        AssemblyLayer(name="Air & Water Barrier",
                      material_class="WRB", thickness_in=0.05, function="Vapor/Air Barrier"),
        AssemblyLayer(name="Continuous Insulation R-10",
                      material_class="Mineral Wool", thickness_in=2.0, function="Insulation"),
        AssemblyLayer(name="Exterior Cladding",
                      material_class="Metal Panel", thickness_in=0.75, function="Finish"),
    ]


def _exterior_cmu_composition(thickness_in: float) -> list[AssemblyLayer]:
    cmu_w = max(7.625, thickness_in - 4.0)
    return [
        AssemblyLayer(name="GWB 5/8\" Type X (Interior)",
                      material_class="Gypsum", thickness_in=0.625, function="Finish"),
        AssemblyLayer(name="Furring Channel 3/4\"",
                      material_class="Steel", thickness_in=0.75, function="Substrate"),
        AssemblyLayer(name=f"CMU {cmu_w:.2f}\" Standard Block",
                      material_class="Concrete Masonry", thickness_in=cmu_w,
                      function="Structure"),
        AssemblyLayer(name="Air & Water Barrier",
                      material_class="WRB", thickness_in=0.05, function="Vapor/Air Barrier"),
        AssemblyLayer(name="Continuous Insulation R-10",
                      material_class="Mineral Wool", thickness_in=2.0, function="Insulation"),
        AssemblyLayer(name="Exterior Cladding",
                      material_class="Metal Panel", thickness_in=0.75, function="Finish"),
    ]


def _floor_composition(thickness_in: float, finish: str) -> list[AssemblyLayer]:
    finish_thk = _finish_thickness(finish)
    return [
        AssemblyLayer(name=finish, material_class=_material_class_for_finish(finish),
                      thickness_in=finish_thk, function="Finish"),
        AssemblyLayer(name="Underlayment", material_class="Foam",
                      thickness_in=0.125, function="Substrate"),
        AssemblyLayer(name=f"Concrete Slab {thickness_in:.0f}\"",
                      material_class="Concrete", thickness_in=thickness_in,
                      function="Structure"),
        AssemblyLayer(name="Vapor Barrier",
                      material_class="Polyethylene", thickness_in=0.05,
                      function="Vapor Barrier"),
        AssemblyLayer(name="Compacted Gravel 4\"",
                      material_class="Aggregate", thickness_in=4.0,
                      function="Substrate"),
    ]


def _ceiling_composition(finish: str) -> list[AssemblyLayer]:
    if "ACT" in finish:
        return [
            AssemblyLayer(name=finish, material_class="Mineral Fibre",
                          thickness_in=0.625, function="Finish"),
            AssemblyLayer(name="Suspension Grid 15/16\" T-Bar",
                          material_class="Steel", thickness_in=0.9375,
                          function="Substrate"),
        ]
    if "GWB" in finish:
        return [
            AssemblyLayer(name="GWB 5/8\" Type X, Painted",
                          material_class="Gypsum", thickness_in=0.625, function="Finish"),
            AssemblyLayer(name="Hat Channel 7/8\" @ 16\" o.c.",
                          material_class="Steel", thickness_in=0.875, function="Substrate"),
        ]
    return []


def _finish_thickness(finish: str) -> float:
    return {
        "Carpet": 0.5, "LVT": 0.2, "Tile": 0.375, "Wood": 0.75,
        "Polished Concrete": 0.05, "Epoxy": 0.0625, "Rubber": 0.125,
        "Concrete": 0.05,
    }.get(finish, 0.125)


def _material_class_for_finish(finish: str) -> str:
    return {
        "Carpet": "Textile", "LVT": "PVC", "Tile": "Ceramic", "Wood": "Wood",
        "Polished Concrete": "Concrete", "Epoxy": "Coating", "Rubber": "Rubber",
        "Concrete": "Concrete",
    }.get(finish, "Composite")


# ---------------------------------------------------------------------------
# Geometry payload builders
# ---------------------------------------------------------------------------

def _wall_geometry(w: Wall) -> dict:
    """Return SVG primitives that draw the wall (centerline + thickness)."""
    return {
        "kind": "wall_pair",
        "start_x": w.start.x, "start_y": w.start.y,
        "end_x":   w.end.x,   "end_y":   w.end.y,
        "thickness_in": w.thickness_in,
    }


def _door_geometry(o: Opening, host: Wall) -> dict:
    """Door leaf + swing arc."""
    return {
        "kind": "door_swing",
        "center_x": _opening_center(o, host)[0],
        "center_y": _opening_center(o, host)[1],
        "wall_dx": host.end.x - host.start.x,
        "wall_dy": host.end.y - host.start.y,
        "wall_id": host.id,
        "width_in": o.width_in,
        "swing": o.swing_direction or "right",
    }


def _window_geometry(o: Opening, host: Wall) -> dict:
    cx, cy = _opening_center(o, host)
    return {
        "kind": "window_segment",
        "center_x": cx, "center_y": cy,
        "wall_dx": host.end.x - host.start.x,
        "wall_dy": host.end.y - host.start.y,
        "width_in": o.width_in,
    }


def _polygon_geometry(polygon) -> dict:
    return {
        "kind": "polygon",
        "points": [(p.x, p.y) for p in polygon],
    }


def _opening_center(o: Opening, host: Optional[Wall]) -> tuple[float, float]:
    if host is None:
        return (0.0, 0.0)
    dx = host.end.x - host.start.x
    dy = host.end.y - host.start.y
    length = math.hypot(dx, dy) or 1.0
    t = max(0.0, min(1.0, o.distance_along_wall_in / length))
    return (host.start.x + t * dx, host.start.y + t * dy)
