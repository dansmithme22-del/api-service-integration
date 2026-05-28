#!/usr/bin/env python3
"""Build (or rebuild) the knowledge vector database.

Usage:
    # Default — local embeddings, all canonical sources
    python scripts/build_knowledge_db.py

    # Drop and rebuild from scratch
    python scripts/build_knowledge_db.py --reset

    # OpenAI embeddings (requires OPENAI_API_KEY in .env)
    python scripts/build_knowledge_db.py --backend openai

    # Skip a source
    python scripts/build_knowledge_db.py --skip ibc

    # Test a query after building
    python scripts/build_knowledge_db.py --query "exam room with sink and cabinetry"
"""

from __future__ import annotations

import argparse
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

from src.knowledge import KnowledgeStore
from src.knowledge.seeders import (
    load_csi,
    load_drafting,
    load_ibc,
    load_reference_aacounty,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("build_knowledge_db")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the knowledge vector DB.")
    parser.add_argument("--reset", action="store_true",
                        help="Drop the collection and rebuild from scratch.")
    parser.add_argument("--backend", type=str, default=None,
                        choices=["local", "openai", "voyage"],
                        help="Embedding backend (default: local).")
    parser.add_argument("--skip", action="append", default=[],
                        choices=["csi", "drafting", "ibc", "reference"],
                        help="Skip a knowledge source.")
    parser.add_argument("--query", type=str, default=None,
                        help="After building, run a similarity test query.")
    parser.add_argument("--permit-mode", action="store_true",
                        help="When testing --query, include IBC items.")
    parser.add_argument("--top-k", type=int, default=8)
    args = parser.parse_args()

    store = KnowledgeStore(backend=args.backend)

    if args.reset:
        logger.info("Resetting collection …")
        store.reset()

    skip = set(args.skip)
    items = []
    if "csi" not in skip:
        items += load_csi()
    if "drafting" not in skip:
        items += load_drafting()
    if "ibc" not in skip:
        items += load_ibc()
    if "reference" not in skip:
        items += load_reference_aacounty()
    logger.info("Total items to index: %d", len(items))

    store.add(items)
    logger.info("Done. Total in collection: %d", store.count())

    if args.query:
        logger.info("Running test query: %r (permit_mode=%s)",
                    args.query, args.permit_mode)
        results = store.search(
            args.query,
            k=args.top_k,
            permit_mode=args.permit_mode,
        )
        print(f"\n=== Top {len(results)} matches ===")
        for r in results:
            print(f"  [{r.score:.3f}] {r.item.layer.value:9s} "
                  f"{r.item.kind.value:18s} {r.item.name}")


if __name__ == "__main__":
    main()
