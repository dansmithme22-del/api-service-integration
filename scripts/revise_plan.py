#!/usr/bin/env python3
"""Apply a natural-language revision request to a previously-ingested PlanGraph.

Usage:
    python scripts/revise_plan.py ingest_output/southbend_plan.json \\
        --request "Remove the wall between Reception and Office. Add a 36-inch door between Treatment 1 and the corridor."

    python scripts/revise_plan.py ingest_output/southbend_plan.json --request-file revision.txt

Outputs:
    <plan>_revised.json
    <plan>_changelog.json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(REPO_ROOT / ".env", override=True)
except ImportError:
    pass

from src.ingest.plan_model import PlanGraph
from src.revise import apply_revision_request

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger("revise_plan")


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply NL revision to a PlanGraph JSON.")
    parser.add_argument("plan_json", type=Path)
    parser.add_argument("--request", type=str, default="")
    parser.add_argument("--request-file", type=Path, default=None)
    parser.add_argument("--model", type=str, default="gemini-2.5-pro")
    args = parser.parse_args()

    if args.request_file:
        revision_text = args.request_file.read_text()
    else:
        revision_text = args.request

    if not revision_text.strip():
        logger.error("No revision text provided. Use --request or --request-file.")
        sys.exit(1)

    plan = PlanGraph.model_validate_json(args.plan_json.read_text())
    logger.info("Loaded plan with %d walls, %d openings, %d rooms.",
                len(plan.walls), len(plan.openings), len(plan.rooms))

    new_plan, log = apply_revision_request(plan, revision_text, model=args.model)
    logger.info("Applied %d change(s). %d note(s).", len(log.entries), len(log.notes))

    rev_path = args.plan_json.with_name(args.plan_json.stem + "_revised.json")
    log_path = args.plan_json.with_name(args.plan_json.stem + "_changelog.json")

    rev_path.write_text(new_plan.model_dump_json(indent=2))
    log_path.write_text(json.dumps(
        {"entries": [vars(e) for e in log.entries], "notes": log.notes},
        indent=2,
    ))
    print(f"\n✓ Revised plan: {rev_path}")
    print(f"✓ Change log:   {log_path}\n")


if __name__ == "__main__":
    main()
