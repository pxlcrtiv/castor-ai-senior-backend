"""Scorer for agent evaluation results.

Computes keyword recall (how many expected keywords appear in the response)
and basic response metrics. No LLM dependency — deterministic scoring.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.eval.golden_dataset import TestCase


@dataclass
class ScoredResult:
    """Scored output for one test case."""

    test_id: str
    query: str
    response: str
    keyword_recall: float  # 0.0 - 1.0
    passed: bool
    tool_calls: int = 0
    category: str = ""
    expected_tools: list[str] | None = None
    actual_tools: list[str] | None = None


class EvalScorer:
    """Score agent responses against expected outputs."""

    def __init__(self, pass_threshold: float = 0.5):
        self._threshold = pass_threshold

    def score(self, response: str, expected: TestCase) -> ScoredResult:
        """Score a single response against expected test case.

        Args:
            response: The agent's response text.
            expected: The test case with expected keywords.

        Returns:
            ScoredResult with metrics.
        """
        # Keyword recall: fraction of expected keywords found in response
        response_lower = response.lower()
        keywords_found = sum(
            1 for kw in expected.expected_keywords
            if kw.lower() in response_lower
        )
        keyword_recall = (
            keywords_found / len(expected.expected_keywords)
            if expected.expected_keywords
            else 1.0
        )

        # Blocked queries: if should_block, check for block signal
        if expected.should_block:
            blocked = any(
                term in response_lower
                for term in ["bloqueada", "blocked", "denied", "no autorizado"]
            )
            keyword_recall = 1.0 if blocked else 0.0

        passed = keyword_recall >= self._threshold

        return ScoredResult(
            test_id=expected.id,
            query=expected.query,
            response=response,
            keyword_recall=keyword_recall,
            passed=passed,
            category=expected.category,
            expected_tools=expected.expected_tools,
        )
