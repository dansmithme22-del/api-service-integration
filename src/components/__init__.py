"""BIM-style components — Revit-Family / SketchUp-Component analogue in 2D.

A *component* is one indivisible building element with a complete property
set describing how it would be built in real life. Components are the
deliverable: every line/curve in the output SVG belongs to exactly one
component, and that component carries every field someone needs to actually
construct or specify the item.

Component types implemented in this baseline:

  * :class:`WallComponent`     — interior or exterior walls
  * :class:`DoorComponent`     — single / double / sliding / pocket doors
  * :class:`WindowComponent`   — fixed / operable windows
  * :class:`FloorComponent`    — floor assemblies (slab / framed)
  * :class:`CeilingComponent`  — ceiling assemblies
  * :class:`StairComponent`    — stair runs
  * :class:`DeckComponent`     — exterior decks / balconies

Each component subclasses :class:`Component` and adds its own typed fields.
The :func:`describe` method renders the property set as a key/value list
suitable for the SVG's ``data-properties`` attribute.
"""

from .schemas import (
    Component,
    ComponentKind,
    WallComponent,
    DoorComponent,
    WindowComponent,
    FloorComponent,
    CeilingComponent,
    StairComponent,
    DeckComponent,
    AssemblyLayer,
)
from .builder import build_components_from_plan
from .svg_export import export_components_svg

__all__ = [
    "Component",
    "ComponentKind",
    "WallComponent",
    "DoorComponent",
    "WindowComponent",
    "FloorComponent",
    "CeilingComponent",
    "StairComponent",
    "DeckComponent",
    "AssemblyLayer",
    "build_components_from_plan",
    "export_components_svg",
]
