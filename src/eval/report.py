"""Evaluation report generator.

Aggregates scored results into a summary with:
- Pass/fail counts and rate
- Average keyword recall
- Per-category breakdown
- Worst category identification
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from src.eval.scorer import ScoredResult


class EvalReport:
    """Generate evaluation report from scored results."""

    def __init__(self, results: list[ScoredResult]):
        self._results = results

    def generate(self) -> dict:
        """Generate summary report.

        Returns:
            Dict with total, passed, failed, pass_rate,
            avg_keyword_recall, per_category, worst_category.
        """
        if not self._results:
            return {"total": 0, "passed": 0, "failed": 0, "pass_rate": 0.0}

        total = len(self._results)
        passed = sum(1 for r in self._results if r.passed)
        failed = total - passed

        avg_recall = (
            sum(r.keyword_recall for r in self._results) / total
        )

        # Per-category breakdown
        by_category: dict[str, list[ScoredResult]] = defaultdict(list)
        for r in self._results:
            by_category[r.category].append(r)

        category_scores = {}
        for cat, results in by_category.items():
            cat_avg = sum(r.keyword_recall for r in results) / len(results)
            cat_passed = sum(1 for r in results if r.passed)
            category_scores[cat] = {
                "count": len(results),
                "avg_recall": round(cat_avg, 3),
                "passed": cat_passed,
                "failed": len(results) - cat_passed,
            }

        # Worst category (lowest avg recall)
        worst_category = min(
            category_scores,
            key=lambda c: category_scores[c]["avg_recall"],
        )

        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": round(passed / total, 3),
            "avg_keyword_recall": round(avg_recall, 3),
            "per_category": category_scores,
            "worst_category": worst_category,
        }
