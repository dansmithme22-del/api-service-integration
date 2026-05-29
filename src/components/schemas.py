"""Component schemas — Pydantic models for every BIM-style component.

These models intentionally carry **everything a tradesperson, estimator, or
specifier would need to actually build the item.** Compositions are
expressed as ordered layer lists; finishes name the actual product family
where possible.

Defaults are populated for unspecified fields so a half-detected component
still produces a complete schedule row.
"""

from __future__ import annotations

import math
from enum import Enum

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Common building blocks
# ---------------------------------------------------------------------------

class ComponentKind(str, Enum):
    WALL = "Wall"
    DOOR = "Door"
    WINDOW = "Window"
    FLOOR = "Floor"
    CEILING = "Ceiling"
    STAIR = "Stair"
    DECK = "Deck"


class AssemblyLayer(BaseModel):
    """One layer in a composition (wall, floor, ceiling, etc.).

    Layers are ordered face-to-face — for walls that means interior face
    to exterior face; for floors that means top finish to substrate.
    """
    name: str                       # e.g. "Gypsum Board, Type X"
    material_class: str = ""        # e.g. "Gypsum", "Wood", "Steel", "Concrete"
    thickness_in: float = 0.0
    function: str = ""              # e.g. "Finish", "Substrate", "Insulation", "Vapor Barrier"
    fire_contribution: str = ""     # e.g. "1HR", "2HR", "N/A"
    notes: str = ""


class Point2D(BaseModel):
    x: float
    y: float


# ---------------------------------------------------------------------------
# Base component
# ---------------------------------------------------------------------------

class Component(BaseModel):
    """Base class — every component has a mark, kind, AIA layer, CSI division.

    Subclasses add their own typed property fields.  The geometry list
    holds the *SVG-paintable* primitives (in real-world inches, plan
    coordinates) that draw the component; the exporter turns these into
    ``<line>`` / ``<rect>`` / ``<polyline>`` elements inside the
    component's ``<g>``.
    """
    id: str
    mark: str                       # schedule mark, e.g. "W101A", "D001"
    kind: ComponentKind
    name: str = ""                  # display name, e.g. "Interior Stud Wall 2x6"
    aia_layer: str = ""
    csi_division: str = ""
    sheets: list[str] = Field(default_factory=list)
    notes: str = ""

    # Geometry — list of dicts the exporter renders. Each dict has
    # {"kind": "line"|"rect"|"polyline"|"arc", "points": [...]}
    geometry: list[dict] = Field(default_factory=list)

    # Free-form additional properties (manufacturer, model, spec section…).
    extras: dict = Field(default_factory=dict)

    def describe(self) -> dict:
        """Flat property dict for the SVG ``data-properties`` attribute."""
        d = self.model_dump(mode="json")
        d.pop("geometry", None)
        return d


# ---------------------------------------------------------------------------
# Walls
# ---------------------------------------------------------------------------

class WallComponent(Component):
    kind: ComponentKind = ComponentKind.WALL
    aia_layer: str = "A-WALL-EXST"
    csi_division: str = "09"

    # Geometry
    start: Point2D
    end: Point2D
    thickness_in: float = 6.0
    height_in: float = 108.0        # 9'-0" default ceiling
    length_in: float = 0.0

    # Build-up
    wall_type: str = "Interior Stud"  # "Interior Stud" | "Exterior Stud" | "CMU" | "Concrete" | "Demising"
    composition: list[AssemblyLayer] = Field(default_factory=list)
    structural: bool = False
    load_bearing: bool = False
    fire_rating: str = ""           # "1HR", "2HR", "" (none)
    sound_rating_stc: int = 0       # 0 = unrated
    insulation_r_value: float = 0.0

    # Finishes
    finish_side_a: str = "GWB, Painted"     # "interior" side
    finish_side_b: str = "GWB, Painted"     # the other side
    base_side_a: str = "Rubber Cove 4\""
    base_side_b: str = "Rubber Cove 4\""

    # Status
    status: str = "Existing"        # "Existing" | "Demolition" | "New Construction"

    # Code references
    code_references: list[str] = Field(default_factory=list)

    def __init__(self, **data):
        super().__init__(**data)
        # Derive length if not provided
        if not self.length_in:
            self.length_in = round(math.hypot(
                self.end.x - self.start.x, self.end.y - self.start.y), 1)
        # Sensible default composition for an interior stud wall
        if not self.composition and self.wall_type == "Interior Stud":
            stud_w = max(2.0, self.thickness_in - 1.25)
            self.composition = [
                AssemblyLayer(name="GWB 5/8\" Type X (Side A)",
                              material_class="Gypsum", thickness_in=0.625, function="Finish"),
                AssemblyLayer(name=f"Steel Stud {stud_w:.1f}\" @ 16\" o.c.",
                              material_class="Steel", thickness_in=stud_w, function="Substrate"),
                AssemblyLayer(name="GWB 5/8\" Type X (Side B)",
                              material_class="Gypsum", thickness_in=0.625, function="Finish"),
            ]


# ---------------------------------------------------------------------------
# Doors
# ---------------------------------------------------------------------------

class DoorComponent(Component):
    kind: ComponentKind = ComponentKind.DOOR
    aia_layer: str = "A-DOOR"
    csi_division: str = "08"

    # Geometry
    position: Point2D               # center on host wall
    host_wall_id: str = ""

    # Size
    width_in: float = 36.0
    height_in: float = 80.0
    leaf_thickness_in: float = 1.75

    # Type
    door_type: str = "Single Swing"  # "Single Swing" | "Double Swing" | "Sliding"
                                     # | "Pocket" | "Folding" | "Overhead"
    swing_direction: str = "RHR"     # IBC: LHR / RHR / LH / RH
    operation: str = "Active"        # "Active" | "Inactive" | "Both"

    # Material
    leaf_material: str = "Solid Core Wood"    # "Solid Core Wood" | "Hollow Metal"
                                              # | "Aluminum" | "FRP" | "Glass"
    leaf_finish: str = "Stain, Sealed"
    frame_material: str = "Hollow Metal"
    frame_finish: str = "Paint"
    frame_profile: str = "Standard 5-3/4\""

    # Hardware
    hardware_set: str = "HW-1"
    lockset_type: str = "Lever Latch"
    closer: bool = False
    threshold: bool = False
    weatherstripping: bool = False
    kick_plate: str = ""             # e.g. "10\" Stainless Steel"

    # Ratings
    fire_rating: str = ""            # "20-min" / "45-min" / "60-min" / "90-min" / "3HR"
    smoke_rated: bool = False
    acoustic_rating_stc: int = 0

    # Glazing (if applicable)
    has_vision_panel: bool = False
    vision_panel_size: str = ""
    glazing_type: str = ""           # "Tempered" / "Wired" / "Laminated"

    # ADA
    ada_compliant: bool = True
    clear_opening_width_in: float = 32.0
    threshold_height_in: float = 0.5


# ---------------------------------------------------------------------------
# Windows
# ---------------------------------------------------------------------------

class WindowComponent(Component):
    kind: ComponentKind = ComponentKind.WINDOW
    aia_layer: str = "A-GLAZ"
    csi_division: str = "08"

    # Geometry
    position: Point2D               # center on host wall
    host_wall_id: str = ""

    # Size
    rough_opening_width_in: float = 36.0
    rough_opening_height_in: float = 48.0
    sill_height_in: float = 30.0

    # Type
    window_type: str = "Fixed"      # "Fixed" | "Double-Hung" | "Single-Hung"
                                    # | "Casement" | "Awning" | "Sliding" | "Picture"
    operable: bool = False
    n_lites: int = 1
    grille_pattern: str = ""

    # Glazing
    glazing_type: str = "IGU"       # "IGU" | "Single" | "Laminated" | "Tempered"
    glass_thickness_in: float = 1.0   # total for IGU
    inner_pane_thickness_in: float = 0.25
    outer_pane_thickness_in: float = 0.25
    gas_fill: str = "Argon"         # "Air" | "Argon" | "Krypton"
    low_e_coating: str = "Low-E 366"

    # Performance
    u_factor: float = 0.30           # Btu/hr·ft²·°F
    shgc: float = 0.27               # Solar Heat Gain Coefficient
    vt: float = 0.6                  # Visible Transmittance

    # Frame
    frame_material: str = "Aluminum, Thermally Broken"
    frame_finish: str = "Powder Coat"
    frame_color: str = "Black"
    frame_thickness_in: float = 2.0

    # Trim / Sill
    sill_material: str = "Aluminum"
    head_trim: str = "Aluminum Cap Flashing"

    # Code / ratings
    egress_qualified: bool = False
    impact_rated: bool = False
    safety_glazing_required: bool = False


# ---------------------------------------------------------------------------
# Floors
# ---------------------------------------------------------------------------

class FloorComponent(Component):
    kind: ComponentKind = ComponentKind.FLOOR
    aia_layer: str = "A-FLOR"
    csi_division: str = "09"

    # Footprint
    polygon: list[Point2D] = Field(default_factory=list)
    area_sqft: float = 0.0

    # Structure
    floor_type: str = "Slab on Grade"  # "Slab on Grade" | "Wood Framed" | "Steel Framed"
                                       # | "Concrete Suspended"
    structure_depth_in: float = 4.0
    joist_size: str = ""               # e.g. "2x10"
    joist_spacing_in: float = 0.0
    joist_span_in: float = 0.0

    # Composition (top finish to substrate)
    composition: list[AssemblyLayer] = Field(default_factory=list)
    finish_top: str = "Polished Concrete"   # "LVT" | "Tile" | "Carpet" | etc.
    finish_thickness_in: float = 0.125

    # Performance
    moisture_barrier: bool = True
    insulation_r_value: float = 0.0
    sound_rating_iic: int = 0
    sound_rating_stc: int = 0
    radiant_heat: bool = False


# ---------------------------------------------------------------------------
# Ceilings
# ---------------------------------------------------------------------------

class CeilingComponent(Component):
    kind: ComponentKind = ComponentKind.CEILING
    aia_layer: str = "A-CLNG"
    csi_division: str = "09"

    # Footprint
    polygon: list[Point2D] = Field(default_factory=list)
    area_sqft: float = 0.0

    # Type
    ceiling_type: str = "ACT 2x2"   # "ACT 2x2" | "ACT 2x4" | "GWB Painted"
                                    # | "Open Structure" | "Wood Plank" | "Metal"
    height_in: float = 108.0        # AFF
    finish: str = "Tegular ACT, White"

    # Build-up
    composition: list[AssemblyLayer] = Field(default_factory=list)
    grid_size: str = "2x2"           # for ACT
    support: str = "Suspended Wire"
    plenum_depth_in: float = 18.0

    # Performance
    fire_rating: str = ""
    sound_absorption_nrc: float = 0.0
    light_reflectance: float = 0.85


# ---------------------------------------------------------------------------
# Stairs
# ---------------------------------------------------------------------------

class StairComponent(Component):
    kind: ComponentKind = ComponentKind.STAIR
    aia_layer: str = "A-FLOR-STRS"
    csi_division: str = "06"

    # Footprint
    polygon: list[Point2D] = Field(default_factory=list)
    run_in: float = 0.0
    width_in: float = 44.0           # min code 44 for occupancy >50

    # Geometry
    stair_type: str = "Straight"     # "Straight" | "L-Shape" | "U-Shape" | "Switchback" | "Spiral"
    total_rise_in: float = 108.0     # floor-to-floor 9'-0"
    num_risers: int = 14
    riser_height_in: float = 7.7     # 108/14 ≈ 7.71"
    num_treads: int = 13             # always one fewer than risers
    tread_depth_in: float = 11.0
    nosing_in: float = 1.0
    landing_count: int = 0

    # Material
    tread_material: str = "Concrete"
    riser_material: str = "Concrete"
    stringer_material: str = ""      # only for open stairs
    handrail_material: str = "Steel, Painted"

    # Railings
    handrail_height_in: float = 36.0  # IBC 1014.2
    guardrail_height_in: float = 42.0
    baluster_spacing_in: float = 4.0  # IBC <4" sphere

    # Code compliance
    code_compliant_ibc: bool = True
    code_compliant_ada: bool = True
    code_references: list[str] = Field(default_factory=lambda: ["IBC 1011", "IBC 1014"])


# ---------------------------------------------------------------------------
# Decks
# ---------------------------------------------------------------------------

class DeckComponent(Component):
    kind: ComponentKind = ComponentKind.DECK
    aia_layer: str = "A-FLOR"        # NCS keeps decks on the floor family
    csi_division: str = "06"         # Wood typical; override for steel/composite

    polygon: list[Point2D] = Field(default_factory=list)
    area_sqft: float = 0.0

    # Structure
    deck_type: str = "Wood Frame"    # "Wood Frame" | "Steel Frame" | "Concrete"
    joist_size: str = "2x10"
    joist_spacing_in: float = 16.0
    joist_span_in: float = 0.0
    beam_size: str = "(2) 2x10"
    post_size: str = "6x6"
    post_spacing_in: float = 96.0

    # Decking surface
    decking_material: str = "Composite"   # "Composite" | "Pressure Treated Wood" | "Ipe" | "Cedar"
    decking_thickness_in: float = 1.0
    decking_pattern: str = "Parallel to Long Edge"

    # Railings
    guardrail_height_in: float = 36.0     # 42" if >30" above grade
    baluster_spacing_in: float = 4.0
    railing_material: str = "Composite"

    # Waterproofing / drainage
    waterproof_membrane: str = ""
    drainage_slope_percent: float = 1.0

    # Connection to building
    ledger_size: str = "2x10"
    ledger_attachment: str = "Lag Bolts to Rim Joist"
    flashing: str = "Aluminum Step Flashing"

    # Code
    code_compliant_ibc: bool = True
    code_references: list[str] = Field(default_factory=lambda: ["IRC R507"])
