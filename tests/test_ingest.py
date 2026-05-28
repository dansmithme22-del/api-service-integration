"""Offline tests for the ingest layer.

These tests do NOT touch the filesystem PDFs or call Gemini. They exercise the
pure geometry / data-model code so the pipeline can be CI'd cheaply.
"""

from __future__ import annotations

import pytest

from src.ingest.geometry_normalizer import (
    _normalize_scale,
    _perpendicular_distance,
    _segments_overlap,
    infer_scale,
    pair_walls,
)
from src.ingest.plan_model import (
    OpeningKind,
    PlanGraph,
    Point,
    Wall,
    WallStatus,
)
from src.ingest.vector_parser import RawLine, RawPageGeometry, RawText


# ---------------------------------------------------------------------------
# Geometry primitives
# ---------------------------------------------------------------------------

def test_raw_line_length_and_angle():
    horiz = RawLine(0, 0, 10, 0)
    assert horiz.length() == pytest.approx(10.0)
    assert horiz.angle_deg() == pytest.approx(0.0)

    vert = RawLine(0, 0, 0, 10)
    assert vert.length() == pytest.approx(10.0)
    assert vert.angle_deg() == pytest.approx(90.0)

    diag = RawLine(0, 0, 3, 4)
    assert diag.length() == pytest.approx(5.0)


def test_segments_overlap_parallel_offset():
    a = RawLine(0, 0, 10, 0)
    b = RawLine(2, 1, 8, 1)
    assert _segments_overlap(a, b)

    far = RawLine(20, 0, 30, 0)
    assert not _segments_overlap(a, far)


def test_perpendicular_distance_parallel_pair():
    a = RawLine(0, 0, 10, 0)
    b = RawLine(0, 5, 10, 5)
    assert _perpendicular_distance(a, b) == pytest.approx(5.0)


# ---------------------------------------------------------------------------
# Scale inference
# ---------------------------------------------------------------------------

def test_scale_inference_picks_quarter_inch():
    geom = RawPageGeometry(
        page_index=0,
        width_pt=612.0, height_pt=792.0,
        texts=[RawText(text="SCALE: 1/4\" = 1'-0\"", x=0, y=0, size=10.0)],
    )
    s = infer_scale(geom)
    # 1/4" = 1'-0"  →  48 real-in per PDF-in  →  48/72 in/pt = 0.6667
    assert s.inches_per_pt == pytest.approx(48.0 / 72.0, rel=1e-3)
    assert s.confidence > 0.8


def test_scale_inference_falls_back_when_no_scale_text():
    geom = RawPageGeometry(page_index=0, width_pt=612.0, height_pt=792.0)
    s = infer_scale(geom)
    assert s.confidence < 0.5
    assert "default" in s.source


def test_normalize_scale_canonical_form():
    out = _normalize_scale('1/4" = 1\'-0"')
    assert out == "1/4\" = 1'-0\""


# ---------------------------------------------------------------------------
# Wall pairing
# ---------------------------------------------------------------------------

def test_pair_walls_finds_simple_parallel_pair():
    # Two parallel lines 5pt apart, both 100pt long.
    lines = [
        RawLine(0, 0, 100, 0),
        RawLine(0, 5, 100, 5),
    ]
    pairs = pair_walls(
        lines,
        min_wall_len_pt=50,
        max_thickness_pt=10,
        pair_max_sep_pt=10,
    )
    assert len(pairs) == 1


def test_pair_walls_ignores_perpendicular_pair():
    lines = [
        RawLine(0, 0, 100, 0),     # horizontal
        RawLine(0, 0, 0, 100),     # vertical
    ]
    pairs = pair_walls(
        lines,
        min_wall_len_pt=50,
        max_thickness_pt=10,
        pair_max_sep_pt=10,
    )
    assert pairs == []


def test_pair_walls_respects_max_separation():
    lines = [
        RawLine(0, 0, 100, 0),
        RawLine(0, 50, 100, 50),    # 50pt apart — too far
    ]
    pairs = pair_walls(
        lines,
        min_wall_len_pt=50,
        max_thickness_pt=10,
        pair_max_sep_pt=10,
    )
    assert pairs == []


# ---------------------------------------------------------------------------
# PlanGraph data model
# ---------------------------------------------------------------------------

def test_plangraph_summary_counts():
    plan = PlanGraph(
        walls=[Wall(id="w1", start=Point(x=0, y=0), end=Point(x=10, y=0))],
        openings=[],
        rooms=[],
    )
    s = plan.summary()
    assert s["walls"] == 1
    assert s["openings"] == 0


def test_plangraph_bbox_handles_empty():
    plan = PlanGraph()
    assert plan.bbox() == (0.0, 0.0, 0.0, 0.0)


def test_plangraph_bbox_computed_correctly():
    plan = PlanGraph(walls=[
        Wall(id="w1", start=Point(x=0, y=0), end=Point(x=10, y=0)),
        Wall(id="w2", start=Point(x=10, y=0), end=Point(x=10, y=8)),
    ])
    assert plan.bbox() == (0.0, 0.0, 10.0, 8.0)


def test_plangraph_serialises_round_trip():
    plan = PlanGraph(
        project_name="Test",
        walls=[Wall(id="w1", start=Point(x=0, y=0), end=Point(x=12, y=0),
                    thickness_in=6.0, status=WallStatus.NEW)],
    )
    blob = plan.model_dump_json()
    rebuilt = PlanGraph.model_validate_json(blob)
    assert rebuilt.project_name == "Test"
    assert rebuilt.walls[0].status == WallStatus.NEW


# ---------------------------------------------------------------------------
# Builder tape format (no live Archicad needed)
# ---------------------------------------------------------------------------

def test_archicad_builder_produces_tape(tmp_path):
    from src.build import build_plan_in_archicad

    plan = PlanGraph(walls=[
        Wall(id="w1", start=Point(x=0, y=0), end=Point(x=120, y=0),
             thickness_in=4.5, status=WallStatus.NEW),
        Wall(id="w2", start=Point(x=120, y=0), end=Point(x=120, y=96),
             thickness_in=4.5, status=WallStatus.EXISTING),
    ])
    tape = tmp_path / "tape.json"
    result = build_plan_in_archicad(plan, conn=None, tape_out=tape)

    assert tape.exists()
    assert result.walls_created == 0  # no live conn => not counted
    assert result.tape_path == str(tape)

    import json
    entries = json.loads(tape.read_text())
    assert len(entries) == 2
    assert entries[0]["kind"] == "wall"
    assert entries[0]["element"]["type"] == "Wall"
    # First wall is new, should map to NewElement renovation status.
    assert entries[0]["element"]["wallData"]["renovationStatus"] == "NewElement"
