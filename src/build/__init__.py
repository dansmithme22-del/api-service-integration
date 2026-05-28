"""PlanGraph -> Archicad elements.

The build layer takes a normalized PlanGraph (in inches, real-world coords)
and creates walls, doors, windows, and zones in a running Archicad instance
through the JSON API.

If Archicad is not available, the builder can emit an "Archicad command tape"
JSON file that can be replayed later — useful for offline review.
"""

from .archicad_builder import ArchicadBuilder, build_plan_in_archicad

__all__ = ["ArchicadBuilder", "build_plan_in_archicad"]
