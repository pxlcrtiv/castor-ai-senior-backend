"""RAG pipeline with metadata filtering for ERP documents.

Uses ChromaDB directly (no LangChain wrapper) for:
- Metadata filtering (year, region, document type)
- Vector similarity search
- Context window management to avoid context stuffing
"""

from __future__ import annotations

from dataclasses import dataclass, field

import chromadb
from chromadb.config import Settings as ChromaSettings


# ---------------------------------------------------------------------------
# Query model
# ---------------------------------------------------------------------------

@dataclass
class RAGQuery:
    """Structured RAG query with metadata filters."""

    query: str
    year: int | None = None
    region: str | None = None
    doc_type: str | None = None  # "invoice", "regulation", "manual"
    max_results: int = 5


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

class ERPRAGPipeline:
    """RAG pipeline optimized for ERP data retrieval.

    Uses ChromaDB with metadata filtering to prevent noise
    and avoid context stuffing.
    """

    def __init__(self, collection_name: str = "erp_docs"):
        self._client = chromadb.Client(ChromaSettings(anonymized_telemetry=False))
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        self._initialized = False

    def initialize(self, documents: list[dict] | None = None):
        """Initialize with documents. Skips if already populated."""
        if self._initialized:
            return

        if documents is None:
            documents = self._mock_documents()

        # Batch insert
        self._collection.add(
            ids=[d["id"] for d in documents],
            documents=[d["content"] for d in documents],
            metadatas=[d["metadata"] for d in documents],
        )
        self._initialized = True

    def query(self, rag_query: RAGQuery) -> list[dict]:
        """Query with metadata filtering.

        Returns:
            List of {content, metadata, relevance_score} dicts.
        """
        if not self._initialized:
            self.initialize()

        where_filter = self._build_filter(rag_query)

        kwargs = {
            "query_texts": [rag_query.query],
            "n_results": min(rag_query.max_results, self._collection.count() or 1),
        }
        if where_filter:
            kwargs["where"] = where_filter

        results = self._collection.query(**kwargs)

        # Unpack single-query results
        docs = results["documents"][0] if results["documents"] else []
        metas = results["metadatas"][0] if results["metadatas"] else []
        distances = results["distances"][0] if results["distances"] else []

        return [
            {
                "content": doc,
                "metadata": meta,
                "relevance_score": 1.0 - dist,  # cosine distance → similarity
            }
            for doc, meta, dist in zip(docs, metas, distances)
        ]

    def _build_filter(self, rag_query: RAGQuery) -> dict | None:
        """Build ChromaDB where clause from query."""
        conditions = []

        if rag_query.year is not None:
            conditions.append({"year": rag_query.year})
        if rag_query.region is not None:
            conditions.append({"region": rag_query.region})
        if rag_query.doc_type is not None:
            conditions.append({"doc_type": rag_query.doc_type})

        if len(conditions) == 0:
            return None
        if len(conditions) == 1:
            return conditions[0]
        return {"$and": conditions}

    def _mock_documents(self) -> list[dict]:
        """Mock ERP documents for demonstration."""
        return [
            {
                "id": "doc_001",
                "content": (
                    "Artículo 5-A del Código Fiscal de la Federación: "
                    "Las personas físicas y morales están obligadas a llevar "
                    "contabilidad conforme a las disposiciones fiscales. "
                    "El IVA se calculará sobre el valor total de la operación."
                ),
                "metadata": {
                    "source": "código_fiscal_2024.pdf",
                    "year": 2024,
                    "doc_type": "regulation",
                    "region": "CDMX",
                },
            },
            {
                "id": "doc_002",
                "content": (
                    "Manual de procedimientos de conciliación fiscal - Capítulo 3: "
                    "Todas las facturas de logística deben conciliarse con las "
                    "órdenes de compra correspondientes dentro de los 30 días "
                    "siguientes a la fecha de emisión. Las discrepancias superiores "
                    "al 5% requieren aprobación gerencial."
                ),
                "metadata": {
                    "source": "manual_conciliacion_2024.pdf",
                    "year": 2024,
                    "doc_type": "manual",
                    "region": "all",
                },
            },
            {
                "id": "doc_003",
                "content": (
                    "Resolución miscelánea fiscal 2024 - Estímulos fiscales "
                    "para la región sur: Los contribuyentes ubicados en Oaxaca, "
                    "Chiapas y Tabasco podrán aplicar una tasa reducida del 8% "
                    "en operaciones de comercio internacional."
                ),
                "metadata": {
                    "source": "resolucion_fiscal_2024.pdf",
                    "year": 2024,
                    "doc_type": "regulation",
                    "region": "Oaxaca",
                },
            },
            {
                "id": "doc_004",
                "content": (
                    "Guía de aprobación de notas de crédito: "
                    "1) Verificar monto original de la factura. "
                    "2) Confirmar motivo con el proveedor. "
                    "3) Calcular impacto fiscal. "
                    "4) Aprobación automática si el monto es menor a $10,000 MXN. "
                    "5) Revisión manual para montos superiores."
                ),
                "metadata": {
                    "source": "guia_creditos_2023.pdf",
                    "year": 2023,
                    "doc_type": "manual",
                    "region": "all",
                },
            },
            {
                "id": "doc_005",
                "content": (
                    "Protocolo de auditoría interna 2024: "
                    "Todas las operaciones de conciliación deben ser auditadas "
                    "mensualmente. El sistema debe generar un reporte automático "
                    "de discrepancias para revisión del departamento financiero."
                ),
                "metadata": {
                    "source": "protocolo_auditoria_2024.pdf",
                    "year": 2024,
                    "doc_type": "regulation",
                    "region": "all",
                },
            },
        ]
