"""Tests for the RAG pipeline — metadata-filtered vector retrieval.

Seams under test:
1. ERPRAGPipeline.query(RAGQuery) → list of scored document chunks
2. Metadata filtering (year, region, doc_type) reduces noise
3. Empty query returns results from default corpus
4. No results for impossible filter combination
"""

import pytest

from src.rag.vector_store import ERPRAGPipeline, RAGQuery


# ---------------------------------------------------------------------------
# Pipeline initialization
# ---------------------------------------------------------------------------

class TestPipelineInit:

    def test_creates_without_error(self):
        pipeline = ERPRAGPipeline()
        assert pipeline is not None

    def test_initializes_with_mock_documents(self):
        pipeline = ERPRAGPipeline()
        pipeline.initialize()
        assert pipeline._collection.count() > 0


# ---------------------------------------------------------------------------
# Basic retrieval
# ---------------------------------------------------------------------------

class TestBasicRetrieval:

    def setup_method(self):
        self.pipeline = ERPRAGPipeline()
        self.pipeline.initialize()

    def test_query_returns_results(self):
        results = self.pipeline.query(RAGQuery(query="IVA impuesto"))
        assert len(results) > 0

    def test_results_have_required_fields(self):
        results = self.pipeline.query(RAGQuery(query="factura conciliación"))
        for r in results:
            assert "content" in r
            assert "metadata" in r
            assert "relevance_score" in r

    def test_results_are_sorted_by_relevance(self):
        results = self.pipeline.query(RAGQuery(query="impuesto fiscal"))
        scores = [r["relevance_score"] for r in results]
        # ChromaDB returns by distance (ascending) → similarity is descending
        assert scores == sorted(scores, reverse=True)

    def test_max_results_respected(self):
        results = self.pipeline.query(RAGQuery(query="regulación", max_results=2))
        assert len(results) <= 2


# ---------------------------------------------------------------------------
# Metadata filtering
# ---------------------------------------------------------------------------

class TestMetadataFiltering:

    def setup_method(self):
        self.pipeline = ERPRAGPipeline()
        self.pipeline.initialize()

    def test_filter_by_year(self):
        results = self.pipeline.query(RAGQuery(query="regulación", year=2024))
        for r in results:
            assert r["metadata"].get("year") == 2024

    def test_filter_by_region(self):
        results = self.pipeline.query(RAGQuery(query="impuesto", region="CDMX"))
        for r in results:
            assert r["metadata"].get("region") in ("CDMX", "all")

    def test_filter_by_doc_type(self):
        results = self.pipeline.query(RAGQuery(query="norma", doc_type="regulation"))
        for r in results:
            assert r["metadata"].get("doc_type") == "regulation"

    def test_combined_filters(self):
        results = self.pipeline.query(
            RAGQuery(query="fiscal", year=2024, doc_type="regulation")
        )
        for r in results:
            assert r["metadata"].get("year") == 2024
            assert r["metadata"].get("doc_type") == "regulation"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:

    def setup_method(self):
        self.pipeline = ERPRAGPipeline()
        self.pipeline.initialize()

    def test_impossible_filter_returns_empty(self):
        results = self.pipeline.query(
            RAGQuery(query="test", year=1999, region="Marte")
        )
        assert results == [] or len(results) == 0

    def test_no_filter_returns_all_relevant(self):
        results = self.pipeline.query(RAGQuery(query="documento"))
        assert len(results) > 0
