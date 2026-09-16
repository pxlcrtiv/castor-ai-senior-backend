"""Tests for the golden dataset and evaluation pipeline.

Seams under test:
1. GoldenDataset.load() → list of test cases with expected outputs
2. EvalScorer.score(result, expected) → scored metrics dict
3. EvalReport.generate(results) → summary with pass/fail per metric
4. Dataset validation (all required fields present)
"""

import json
import os
import pytest

from src.eval.golden_dataset import GoldenDataset, TestCase
from src.eval.scorer import EvalScorer, ScoredResult
from src.eval.report import EvalReport


# ---------------------------------------------------------------------------
# Test case model
# ---------------------------------------------------------------------------

class TestCaseModel:

    def test_has_required_fields(self):
        tc = TestCase(
            id="tc_001",
            query="¿Cuál es el estado de la factura #4402?",
            expected_keywords=["4402", "pendiente"],
            category="erp_lookup",
            role="analyst",
        )
        assert tc.id == "tc_001"
        assert tc.category == "erp_lookup"

    def test_optional_fields_default(self):
        tc = TestCase(
            id="tc_002",
            query="test",
            expected_keywords=["x"],
            category="test",
        )
        assert tc.role == "analyst"  # default
        assert tc.max_tool_calls == 3  # default


# ---------------------------------------------------------------------------
# Golden dataset loading
# ---------------------------------------------------------------------------

class TestGoldenDataset:

    def test_loads_from_file(self, tmp_path):
        data = [
            {
                "id": "tc_001",
                "query": "test query",
                "expected_keywords": ["keyword1", "keyword2"],
                "category": "test",
                "role": "analyst",
            }
        ]
        path = tmp_path / "dataset.json"
        path.write_text(json.dumps(data))

        dataset = GoldenDataset(path=str(path))
        cases = dataset.load()
        assert len(cases) == 1
        assert cases[0].id == "tc_001"

    def test_validates_required_fields(self, tmp_path):
        data = [
            {"id": None, "query": "test", "expected_keywords": [], "category": "t"}
        ]
        path = tmp_path / "bad.json"
        path.write_text(json.dumps(data))

        dataset = GoldenDataset(path=str(path))
        with pytest.raises(ValueError):
            dataset.load()

    def test_default_dataset_has_cases(self):
        dataset = GoldenDataset()  # uses built-in mock
        cases = dataset.load()
        assert len(cases) >= 8

    def test_dataset_covers_all_categories(self):
        dataset = GoldenDataset()
        cases = dataset.load()
        categories = {c.category for c in cases}
        assert "erp_lookup" in categories
        assert "tool_chaining" in categories
        assert "rag_query" in categories
        assert "security" in categories

    def test_dataset_covers_all_roles(self):
        dataset = GoldenDataset()
        cases = dataset.load()
        roles = {c.role for c in cases}
        assert "viewer" in roles
        assert "analyst" in roles
        assert "admin" in roles


# ---------------------------------------------------------------------------
# Scorer
# ---------------------------------------------------------------------------

class TestScorer:

    def setup_method(self):
        self.scorer = EvalScorer()

    def test_keyword_match_scoring(self):
        result = "La factura #4402 tiene estado pendiente de revisión"
        expected = TestCase(
            id="test", query="test",
            expected_keywords=["4402", "pendiente"],
            category="test",
        )
        score = self.scorer.score(result, expected)
        assert score.keyword_recall == 1.0  # both keywords found

    def test_partial_keyword_match(self):
        result = "La factura #4402 está aprobada"
        expected = TestCase(
            id="test", query="test",
            expected_keywords=["4402", "pendiente"],
            category="test",
        )
        score = self.scorer.score(result, expected)
        assert 0.0 < score.keyword_recall < 1.0

    def test_no_keyword_match(self):
        result = "No tengo esa información"
        expected = TestCase(
            id="test", query="test",
            expected_keywords=["4402", "pendiente"],
            category="test",
        )
        score = self.scorer.score(result, expected)
        assert score.keyword_recall == 0.0

    def test_blocked_query_scored_correctly(self):
        result = "⛔ Consulta bloqueada: Prompt injection attempt"
        expected = TestCase(
            id="test", query="test",
            expected_keywords=["bloqueada"],
            category="security",
        )
        score = self.scorer.score(result, expected)
        assert score.keyword_recall == 1.0

    def test_blocked_query_scored_correctly(self):
        result = "⛔ Consulta bloqueada: Prompt injection attempt"
        expected = TestCase(
            id="test", query="test",
            expected_keywords=["bloqueada"],
            category="security",
        )
        score = self.scorer.score(result, expected)
        assert score.keyword_recall == 1.0


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

class TestReport:

    def test_report_generates_summary(self):
        from src.eval.scorer import ScoredResult

        results = [
            ScoredResult(
                test_id="tc_001", query="q1", response="r1",
                keyword_recall=1.0, passed=True, tool_calls=1,
            ),
            ScoredResult(
                test_id="tc_002", query="q2", response="r2",
                keyword_recall=0.5, passed=False, tool_calls=2,
            ),
        ]
        report = EvalReport(results)
        summary = report.generate()

        assert summary["total"] == 2
        assert summary["passed"] == 1
        assert summary["failed"] == 1
        assert summary["pass_rate"] == 0.5
        assert summary["avg_keyword_recall"] == 0.75

    def test_report_identifies_worst_category(self):
        from src.eval.scorer import ScoredResult

        results = [
            ScoredResult(
                test_id="tc_001", query="q", response="r",
                keyword_recall=0.2, passed=False, tool_calls=0,
                category="security",
            ),
            ScoredResult(
                test_id="tc_002", query="q", response="r",
                keyword_recall=0.9, passed=True, tool_calls=1,
                category="erp_lookup",
            ),
        ]
        report = EvalReport(results)
        summary = report.generate()
        assert summary["worst_category"] == "security"
