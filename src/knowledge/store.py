"""ChromaDB-backed knowledge store with local sentence-transformers embeddings.

By default the store uses **local embeddings** (sentence-transformers
all-MiniLM-L6-v2) so it works offline with no API key. The embedding backend
can be swapped via the ``EMBEDDING_BACKEND`` environment variable or the
``backend`` constructor argument:

  * ``local`` (default) — sentence-transformers
  * ``openai`` — OpenAI text-embedding-3-small (requires OPENAI_API_KEY)
  * ``voyage`` — Voyage voyage-3-lite (requires VOYAGE_API_KEY)
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Optional

from .schema import KnowledgeItem, KnowledgeKind, KnowledgeLayer, SearchResult

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_DIR = REPO_ROOT / "knowledge_db"
COLLECTION_NAME = "plan_knowledge"


class KnowledgeStore:
    """Wrap ChromaDB with our typed KnowledgeItem schema."""

    def __init__(
        self,
        db_dir: Optional[Path] = None,
        *,
        backend: Optional[str] = None,
        embedding_model: Optional[str] = None,
    ):
        self.db_dir = Path(db_dir) if db_dir else DEFAULT_DB_DIR
        self.db_dir.mkdir(parents=True, exist_ok=True)
        self.backend = (backend
                        or os.environ.get("EMBEDDING_BACKEND", "local")).lower()
        self.embedding_model = embedding_model
        self._client = None
        self._collection = None
        self._embedder = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @property
    def client(self):
        if self._client is None:
            try:
                import chromadb
            except ImportError as exc:
                raise ImportError(
                    "chromadb is required. Run: pip install chromadb"
                ) from exc
            self._client = chromadb.PersistentClient(path=str(self.db_dir))
        return self._client

    @property
    def collection(self):
        if self._collection is None:
            self._collection = self.client.get_or_create_collection(
                name=COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collection

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts using the configured backend."""
        if self.backend == "openai":
            return self._embed_openai(texts)
        if self.backend == "voyage":
            return self._embed_voyage(texts)
        return self._embed_local(texts)

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def add(self, items: list[KnowledgeItem]) -> int:
        """Embed and insert items. Existing IDs are upserted (replaced)."""
        if not items:
            return 0
        texts = [it.embedding_text() for it in items]
        vectors = self.embed(texts)
        ids = [it.id for it in items]
        metadatas = [_to_metadata(it) for it in items]
        documents = [it.embedding_text() for it in items]
        self.collection.upsert(
            ids=ids,
            embeddings=vectors,
            metadatas=metadatas,
            documents=documents,
        )
        logger.info("Indexed %d knowledge items (backend=%s).", len(items), self.backend)
        return len(items)

    def search(
        self,
        query: str,
        *,
        k: int = 8,
        layers: Optional[list[KnowledgeLayer]] = None,
        kinds: Optional[list[KnowledgeKind]] = None,
        permit_mode: bool = False,
    ) -> list[SearchResult]:
        """Find the top-k items semantically closest to ``query``.

        Visibility:
          * ``permit_mode=False``: items with permit_only=True are filtered out.
          * ``layers``: restrict to those layers if provided.
          * ``kinds``: restrict to those kinds if provided.
        """
        qvec = self.embed([query])[0]

        # Build a "where" filter for Chroma. Chroma supports $and / $eq / $in.
        clauses: list[dict] = []
        if not permit_mode:
            clauses.append({"permit_only": {"$eq": False}})
        if layers:
            clauses.append({"layer": {"$in": [l.value for l in layers]}})
        if kinds:
            clauses.append({"kind": {"$in": [k_.value for k_ in kinds]}})
        where: Optional[dict] = None
        if len(clauses) == 1:
            where = clauses[0]
        elif clauses:
            where = {"$and": clauses}

        res = self.collection.query(
            query_embeddings=[qvec],
            n_results=k,
            where=where,
        )
        out: list[SearchResult] = []
        for i in range(len(res["ids"][0])):
            md = res["metadatas"][0][i]
            item = _from_metadata(md, res["documents"][0][i])
            distance = res["distances"][0][i]      # cosine distance
            score = 1.0 - distance                 # higher is better
            out.append(SearchResult(item=item, score=score))
        return out

    def count(self) -> int:
        return self.collection.count()

    def reset(self) -> None:
        """Drop and recreate the collection — useful when reseeding."""
        try:
            self.client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass
        self._collection = None
        _ = self.collection  # touch to recreate

    # ------------------------------------------------------------------
    # Embedding backends
    # ------------------------------------------------------------------

    def _embed_local(self, texts: list[str]) -> list[list[float]]:
        if self._embedder is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise ImportError(
                    "sentence-transformers is required for local embeddings. "
                    "Run: pip install sentence-transformers"
                ) from exc
            model_name = self.embedding_model or "all-MiniLM-L6-v2"
            logger.info("Loading local embedder %s …", model_name)
            self._embedder = SentenceTransformer(model_name)
        vecs = self._embedder.encode(texts, normalize_embeddings=True).tolist()
        return vecs

    def _embed_openai(self, texts: list[str]) -> list[list[float]]:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY required for openai embedding backend.")
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        model = self.embedding_model or "text-embedding-3-small"
        resp = client.embeddings.create(model=model, input=texts)
        return [d.embedding for d in resp.data]

    def _embed_voyage(self, texts: list[str]) -> list[list[float]]:
        api_key = os.environ.get("VOYAGE_API_KEY")
        if not api_key:
            raise RuntimeError("VOYAGE_API_KEY required for voyage embedding backend.")
        import voyageai
        client = voyageai.Client(api_key=api_key)
        model = self.embedding_model or "voyage-3-lite"
        resp = client.embed(texts, model=model, input_type="document")
        return resp.embeddings


# ---------------------------------------------------------------------------
# Metadata conversion (ChromaDB only supports flat str/int/float/bool values)
# ---------------------------------------------------------------------------

def _to_metadata(item: KnowledgeItem) -> dict:
    return {
        "kind": item.kind.value,
        "layer": item.layer.value,
        "name": item.name,
        "code": item.code,
        "csi_division": item.csi_division,
        "sheets": ",".join(item.sheets),
        "aliases": ",".join(item.aliases),
        "permit_only": item.permit_only,
        "payload_json": json.dumps(item.payload, default=str),
        "description": item.description,
    }


def _from_metadata(md: dict, doc: str) -> KnowledgeItem:
    try:
        payload = json.loads(md.get("payload_json", "{}"))
    except (TypeError, ValueError):
        payload = {}
    return KnowledgeItem(
        id="",  # ChromaDB ids live alongside metadatas; not stored here
        kind=KnowledgeKind(md["kind"]),
        layer=KnowledgeLayer(md["layer"]),
        name=md.get("name", ""),
        description=md.get("description", doc),
        code=md.get("code", ""),
        csi_division=md.get("csi_division", ""),
        sheets=[s for s in md.get("sheets", "").split(",") if s],
        aliases=[a for a in md.get("aliases", "").split(",") if a],
        permit_only=bool(md.get("permit_only", False)),
        payload=payload,
    )
