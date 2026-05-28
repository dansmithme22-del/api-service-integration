"""Pure-geometry computations for the vector-truth ingest pipeline.

Each module operates on geometric primitives (points, segments, polygons)
in image-norm coordinates without any reference to BIM semantics.  The
result of this layer is a clean planar graph that the vector-truth
pipeline turns into walls + rooms.
"""

from .snap import dedupe_lines, snap_endpoints, merge_collinear, clean_pipeline
from .planar_graph import (
    PlanarGraph,
    build_planar_graph,
    enumerate_faces,
    Face,
)
from .arc_detector import detect_door_arcs, DoorArc

__all__ = [
    "dedupe_lines",
    "snap_endpoints",
    "merge_collinear",
    "clean_pipeline",
    "PlanarGraph",
    "build_planar_graph",
    "enumerate_faces",
    "Face",
    "detect_door_arcs",
    "DoorArc",
]
