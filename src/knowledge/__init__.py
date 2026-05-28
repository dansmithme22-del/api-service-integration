"""Knowledge stack: CSI MasterFormat, IBC, reference CD sets, office patterns.

The knowledge stack is a semantic-embeddings database that lets the rest of
the pipeline reason against industry-standard sources.

  * **CSI MasterFormat** is the under-the-hood logic — every item routes to a
    CSI division and one or more sheet codes.
  * **Reference CD sets** (e.g. Anne Arundel) supply gold-standard patterns
    that ingestion can match against.
  * **IBC** (use groups, egress, fire ratings) is layered on top — visible
    only when ``--permit-mode`` is on.
  * **Office patterns** are firm-specific overrides learned from past
    projects (added incrementally, lowest priority).

Use::

    from src.knowledge import KnowledgeStore

    store = KnowledgeStore()
    store.seed_from_canonical()   # CSI + IBC + reference
    results = store.search("exam room with sink and lab counter", k=5)
"""

from .schema import (
    KnowledgeItem,
    KnowledgeKind,
    KnowledgeLayer,
    SearchResult,
)
from .store import KnowledgeStore

__all__ = [
    "KnowledgeStore",
    "KnowledgeItem",
    "KnowledgeKind",
    "KnowledgeLayer",
    "SearchResult",
]
