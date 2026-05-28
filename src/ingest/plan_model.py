"""PlanGraph — the structured intermediate between a PDF page and an Archicad model.

Everything in this module is pure data (Pydantic). The ingest layer produces a
PlanGraph; the build layer consumes it. Units are always **inches** unless a
field name says otherwise — the geometry normalizer converts at the boundary.

Coordinate system:
  * Origin (0, 0) is bottom-left of the page bounding box of all walls.
  * +X points right, +Y points up.
  * All coordinates in inches at real-world scale (post-scale-inference).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class OpeningKind(str, Enum):
    DOOR = "Door"
    WINDOW = "Window"
    OPENING = "Opening"          # cased / no-leaf opening
    UNKNOWN = "Unknown"


class FixtureKind(str, Enum):
    """Built-in / stationary item categories. NOT movable furniture."""
    CASEWORK = "Casework"            # built-in cabinets, counters, shelving
    PLUMBING = "Plumbing Fixture"    # sink, toilet, tub, eye-wash, mop sink
    EQUIPMENT = "Equipment"          # fixed equipment (autoclave, oxygen mount)
    APPLIANCE = "Appliance"          # built-in fridge, dishwasher, washer/dryer
    RECEPTION = "Reception Desk"
    EXAM = "Exam Table"              # if built-in
    KENNEL = "Kennel Run"            # built-in animal housing
    COLUMN = "Column"                # structural columns / posts
    STAIR = "Stair"
    OTHER = "Other Built-in"


class WallStatus(str, Enum):
    """Maps 1:1 onto the existing renovation Phase enum in models.data_model."""
    EXISTING = "Existing"
    DEMOLITION = "Demolition"
    NEW = "New Construction"
    UNKNOWN = "Unknown"


class IngestSource(str, Enum):
    VECTOR = "vector"
    VISION = "vision"
    HYBRID = "hybrid"
    MANUAL = "manual"


# ---------------------------------------------------------------------------
# Geometric primitives
# ---------------------------------------------------------------------------

class Point(BaseModel):
    x: float
    y: float

    def as_tuple(self) -> tuple[float, float]:
        return (self.x, self.y)


# ---------------------------------------------------------------------------
# Plan elements
# ---------------------------------------------------------------------------

class Wall(BaseModel):
    """A single straight wall segment.

    Walls are represented by their *centerline* — start point, end point, and a
    thickness. The build layer turns this into an Archicad wall element.
    """
    id: str
    start: Point
    end: Point
    thickness_in: float = 4.5
    height_in: float = 108.0
    status: WallStatus = WallStatus.EXISTING
    confidence: float = 1.0          # 0..1 — used to flag low-trust segments
    source_note: str = ""            # optional provenance: "line pair #42" etc.


class Opening(BaseModel):
    """A door, window, or framed opening hosted on a wall."""
    id: str
    wall_id: str                     # parent wall.id
    distance_along_wall_in: float    # measured from wall.start
    width_in: float = 36.0
    height_in: float = 80.0
    sill_height_in: float = 0.0      # 0 for doors, >0 for windows
    kind: OpeningKind = OpeningKind.DOOR
    swing_direction: Optional[str] = None     # "left" | "right" | None
    confidence: float = 1.0


class Room(BaseModel):
    """A bounded polygonal area — becomes an Archicad Zone."""
    id: str
    name: str = ""                   # "Reception", "Treatment 1", etc.
    polygon: list[Point] = Field(default_factory=list)
    area_sqft: float = 0.0
    use: str = ""                    # building-code use group (e.g. "B", "A-3")
    floor_finish: str = ""           # "LVT", "Tile", "Carpet", "Wood", "Concrete", "Rubber"
    ceiling_finish: str = ""         # "ACT", "GWB Painted", "Open Structure"
    ceiling_height_in: float = 0.0
    confidence: float = 1.0


class Fixture(BaseModel):
    """A built-in / stationary item — included if it would appear on a demo plan.

    Coordinates: ``bbox`` is the axis-aligned bounding box in real-world inches
    (origin matches the PlanGraph). ``rotation_deg`` is CCW from +X.
    """
    id: str
    kind: FixtureKind = FixtureKind.OTHER
    name: str = ""                   # "Reception Desk", "Exam Sink", "Lab Counter"
    bbox_min: Point = Field(default_factory=lambda: Point(x=0.0, y=0.0))
    bbox_max: Point = Field(default_factory=lambda: Point(x=0.0, y=0.0))
    rotation_deg: float = 0.0
    height_in: float = 36.0          # default counter height
    room_id: str = ""                # parent room (resolved at normalize time)
    will_be_removed: bool = False    # marked True if revise stage demolishes this
    notes: str = ""
    confidence: float = 1.0


class Annotation(BaseModel):
    """Free-floating text on the plan — dimensions, labels, leaders."""
    id: str
    text: str
    position: Point
    kind: str = "label"              # "label" | "dimension" | "note" | "leader"


class DimensionCallout(BaseModel):
    """A dimension callout the model claims spans between two specific points.

    Used by the accuracy checker: extract the dimension text (e.g. "12'-6\\""),
    plus the two endpoints the dimension line runs between, then compare
    against the measured Euclidean distance in the PlanGraph.
    """
    id: str
    text: str                        # raw callout, e.g. "12'-6\\""
    value_in: float                  # parsed real-world inches
    point_a: Point                   # one endpoint of the dimensioned span
    point_b: Point                   # the other endpoint
    label_position: Point            # where the text label sits
    axis: str = "any"                # "x" | "y" | "any"


class AccuracyCheck(BaseModel):
    """Result of comparing one callout's claimed value to measured geometry."""
    callout_text: str
    claimed_in: float
    measured_in: float
    delta_in: float
    delta_pct: float
    status: str                      # "pass" | "warn" | "fail"
    notes: str = ""


class AccuracyReport(BaseModel):
    """Aggregate accuracy assessment for the ingested plan."""
    n_checked: int = 0
    n_passed: int = 0
    n_warned: int = 0
    n_failed: int = 0
    median_pct_error: float = 0.0
    worst_pct_error: float = 0.0
    checks: list[AccuracyCheck] = Field(default_factory=list)
    overall_status: str = "unknown"   # "pass" | "warn" | "fail" | "unknown"
    notes: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Page-level container
# ---------------------------------------------------------------------------

class PageMeta(BaseModel):
    """What the ingest layer learned about a single PDF page."""
    page_index: int
    source_pdf: str
    width_in: float                  # real-world page width after scale inference
    height_in: float
    scale_factor_in_per_pdf_unit: float = 1.0
    detected_scale_text: str = ""    # e.g. "1/4\" = 1'-0\""
    is_vector: bool = True
    confidence: float = 1.0
    # Drawing-area pixel anchor — populated by the vision parser. Lets the
    # review HTML position the SVG overlay exactly over the floor plan in
    # the source image, regardless of title-block or margin offsets.
    drawing_area_norm_bbox: Optional[list[float]] = None  # [x0, y0, x1, y1] in [0,1]
    image_width_px: int = 0
    image_height_px: int = 0
    # Calibration — when geometry was extracted in image-normalized space and
    # converted to inches via a known dimension, these fields let the review
    # HTML render an overlay aligned to the source PDF pixel-for-pixel.
    inches_per_norm: float = 0.0     # one real-world inch per unit of image-norm
    geom_norm_bbox: Optional[list[float]] = None  # [x0, y0, x1, y1] of geometry in image-norm
    calibration_dim_text: str = ""   # e.g. "27'-5\\""
    calibration_dim_in: float = 0.0  # real-world value of the calibration dim


class PlanGraph(BaseModel):
    """The unified output of the ingest layer.

    A PlanGraph holds one *level* of a building — walls, openings, rooms, and
    annotations — in a real-world coordinate system. Multi-level projects
    produce one PlanGraph per level.
    """
    project_name: str = ""
    level_name: str = "Level 1"
    units: str = "imperial"
    generated_at: datetime = Field(default_factory=datetime.now)
    source: IngestSource = IngestSource.VECTOR
    page: Optional[PageMeta] = None

    walls: list[Wall] = Field(default_factory=list)
    openings: list[Opening] = Field(default_factory=list)
    rooms: list[Room] = Field(default_factory=list)
    fixtures: list[Fixture] = Field(default_factory=list)
    annotations: list[Annotation] = Field(default_factory=list)
    dimension_callouts: list["DimensionCallout"] = Field(default_factory=list)

    warnings: list[str] = Field(default_factory=list)
    accuracy_report: Optional["AccuracyReport"] = None

    # ----- convenience -----

    def bbox(self) -> tuple[float, float, float, float]:
        """Return (min_x, min_y, max_x, max_y) over all wall endpoints."""
        if not self.walls:
            return (0.0, 0.0, 0.0, 0.0)
        xs = [p.x for w in self.walls for p in (w.start, w.end)]
        ys = [p.y for w in self.walls for p in (w.start, w.end)]
        return (min(xs), min(ys), max(xs), max(ys))

    def summary(self) -> dict:
        return {
            "walls": len(self.walls),
            "openings": len(self.openings),
            "rooms": len(self.rooms),
            "annotations": len(self.annotations),
            "warnings": len(self.warnings),
            "source": self.source.value,
            "level": self.level_name,
        }
