"""CSI division processors.

Importing this package auto-registers every division processor under
its 2-digit CSI code. Callers use :func:`registry.all_processors` /
:func:`registry.get_by_code` to reach into the registry.

Launch coverage per decision §13.8:

- Full: 02, 06, 08, 09, 11, 22
- Stub: 03, 05, 07, 23, 26

New divisions land as a new subdirectory + one import line here.
No other file changes.
"""

# Full processors ----------------------------------------------------------
from src.divisions.div_02_existing_conditions import processor as _div_02  # noqa: F401
from src.divisions.div_03_concrete import processor as _div_03  # noqa: F401
from src.divisions.div_05_metals import processor as _div_05  # noqa: F401
from src.divisions.div_06_wood_plastics import processor as _div_06  # noqa: F401

# Stub processors ----------------------------------------------------------
from src.divisions.div_07_thermal_moisture import processor as _div_07  # noqa: F401
from src.divisions.div_08_openings import processor as _div_08  # noqa: F401
from src.divisions.div_09_finishes import processor as _div_09  # noqa: F401
from src.divisions.div_11_equipment import processor as _div_11  # noqa: F401
from src.divisions.div_22_plumbing import processor as _div_22  # noqa: F401
from src.divisions.div_23_hvac import processor as _div_23  # noqa: F401
from src.divisions.div_26_electrical import processor as _div_26  # noqa: F401
from src.divisions.registry import (
    all_processors,
    full_processors,
    get_by_code,
    known_codes,
    stub_processors,
)

__all__ = [
    "all_processors",
    "full_processors",
    "get_by_code",
    "known_codes",
    "stub_processors",
]
