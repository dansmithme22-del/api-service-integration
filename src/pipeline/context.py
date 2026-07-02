"""RunContext — the per-run object threaded through every stage.

Phase A.1 keeps this deliberately minimal. The cache handle lands in
A.4, the telemetry handle in A.5, and the cost-cap tracker in A.5 as
well. Stages already get ``ctx`` so we don't change every signature
later when those fields appear.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class RunContext:
    """Per-run state. One instance per pipeline invocation.

    Attributes
    ----------
    run_id
        Stable identifier for this run. Used as the directory name
        under ``runs/`` and as the join key in telemetry.
    run_dir
        ``runs/<run_id>/`` — where manifest.json, telemetry.jsonl, and
        per-stage outputs land. Created lazily by the runner.
    started_at
        UTC timestamp at runner construction. Captured for the manifest.
    extras
        Free-form dict for forward-compat. Future fields (cache, tele
        sink, cost meter) get keys here until they earn dedicated slots.
    """

    run_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    run_dir: Path = field(init=False)
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    extras: dict[str, object] = field(default_factory=dict)

    # Caller can override the base ``runs/`` directory (e.g. tests).
    runs_root: Path = field(default_factory=lambda: Path("runs"))

    def __post_init__(self) -> None:
        self.run_dir = self.runs_root / self.run_id

    def ensure_run_dir(self) -> Path:
        """Create the run directory on demand. Idempotent."""
        self.run_dir.mkdir(parents=True, exist_ok=True)
        return self.run_dir
