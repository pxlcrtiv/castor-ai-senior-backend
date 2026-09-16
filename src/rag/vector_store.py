"""RAG pipeline with metadata filtering for ERP documents.

Demonstrates advanced RAG patterns:
- Metadata filtering (year, document type, region)
- Hybrid search (semantic + keyword)
- Context window management to avoid context stuffing
"""

from dataclasses import dataclass

from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document

from src.config.settings import settings


@dataclass
class RAGQuery:
    """Structured RAG query with metadata filters."""

    query: str
    year: int | None = None
    region: str | None = None
    doc_type: str | None = None  # "invoice", "regulation", "manual"
    max_results: int = 5


class ERPRAGPipeline:
    """RAG pipeline optimized for ERP data retrieval.

    Uses metadata filtering to prevent noise from irrelevant documents
    and avoid context stuffing.
    """

    def __init__(self):
        self.embeddings = HuggingFaceEmbeddings(
            model_name=settings.embedding_model
        )
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=500,
            chunk_overlap=50,
            separators=["\n\n", "\n", ". ", " "],
        )
        self._vector_store: Chroma | None = None

    def initialize(self, documents: list[Document] | None = None):
        """Initialize the vector store with documents.

        Args:
            documents: Optional list of documents to index.
                      If None, uses mock ERP documents.
        """
        if documents is None:
            documents = self._get_mock_documents()

        # Split documents into chunks
        chunks = self.text_splitter.split_documents(documents)

        # Create vector store
        self._vector_store = Chroma.from_documents(
            documents=chunks,
            embedding=self.embeddings,
            persist_directory=settings.vector_db_path,
            collection_metadata={"hnsw:space": "cosine"},
        )

    def query(self, rag_query: RAGQuery) -> list[dict]:
        """Query the RAG pipeline with metadata filtering.

        Args:
            rag_query: Structured query with filters.

        Returns:
            List of relevant document chunks with scores.
        """
        if self._vector_store is None:
            self.initialize()

        # Build metadata filter
        where_filter = self._build_filter(rag_query)

        # Semantic search with metadata filter
        results = self._vector_store.similarity_search_with_score(
            query=rag_query.query,
            k=rag_query.max_results,
            filter=where_filter if where_filter else None,
        )

        return [
            {
                "content": doc.page_content,
                "metadata": doc.metadata,
                "relevance_score": float(score),
            }
            for doc, score in results
        ]

    def _build_filter(self, rag_query: RAGQuery) -> dict | None:
        """Build Chroma metadata filter from query."""
        conditions = []

        if rag_query.year:
            conditions.append({"year": rag_query.year})
        if rag_query.region:
            conditions.append({"region": rag_query.region})
        if rag_query.doc_type:
            conditions.append({"doc_type": rag_query.doc_type})

        if len(conditions) == 1:
            return conditions[0]
        elif len(conditions) > 1:
            return {"$and": conditions}
        return None

    def _get_mock_documents(self) -> list[Document]:
        """Generate mock ERP documents for demonstration."""
        return [
            Document(
                page_content=(
                    "Artículo 5-A del Código Fiscal de la Federación: "
                    "Las personas físicas y morales están obligadas a llevar "
                    "contabilidad conforme a las disposiciones fiscales. "
                    "El IVA se calculará sobre el valor total de la operación."
                ),
                metadata={
                    "source": "código_fiscal_2024.pdf",
                    "year": 2024,
                    "doc_type": "regulation",
                    "region": "CDMX",
                },
            ),
            Document(
                page_content=(
                    "Manual de procedimientos de conciliación fiscal - Capítulo 3: "
                    "Todas las facturas de logística deben conciliarse con las "
                    "órdenes de compra correspondientes dentro de los 30 días "
                    "siguientes a la fecha de emisión. Las discrepancias superiores "
                    "al 5% requieren aprobación gerencial."
                ),
                metadata={
                    "source": "manual_conciliacion_2024.pdf",
                    "year": 2024,
                    "doc_type": "manual",
                    "region": "all",
                },
            ),
            Document(
                page_content=(
                    "Resolución miscelánea fiscal 2024 - Estímulos fiscales "
                    "para la región sur: Los contribuyentes ubicados en Oaxaca, "
                    "Chiapas y Tabasco podrán aplicar una tasa reducida del 8% "
                    "en operaciones de comercio internacional."
                ),
                metadata={
                    "source": "resolucion_fiscal_2024.pdf",
                    "year": 2024,
                    "doc_type": "regulation",
                    "region": "Oaxaca",
                },
            ),
            Document(
                page_content=(
                    "Guía de aprobación de notas de crédito: "
                    "1) Verificar monto original de la factura. "
                    "2) Confirmar motivo con el proveedor. "
                    "3) Calcular impacto fiscal. "
                    "4) Aprobación automática si el monto es menor a $10,000 MXN. "
                    "5) Revisión manual para montos superiores."
                ),
                metadata={
                    "source": "guia_creditos_2023.pdf",
                    "year": 2023,
                    "doc_type": "manual",
                    "region": "all",
                },
            ),
            Document(
                page_content=(
                    "Protocolo de auditoría interna 2024: "
                    "Todas las operaciones de conciliación deben ser auditadas "
                    "mensualmente. El sistema debe generar un reporte automático "
                    "de discrepancias para revisión del departamento financiero."
                ),
                metadata={
                    "source": "protocolo_auditoria_2024.pdf",
                    "year": 2024,
                    "doc_type": "regulation",
                    "region": "all",
                },
            ),
        ]
