# ADR-003: Golden Dataset for LLMOps Evaluation

## Status

Accepted

## Context

The test asks how to measure agent success (Faithfulness, Answer Relevance) and prevent model drift. Most candidates will describe the strategy in prose. We will build it.

## Decision

**Build a mini golden dataset with 10 test cases + automated RAGAS scoring.**

The golden dataset lives in `data/golden_dataset.json` with test cases covering:
- Simple ERP lookups
- Tool chaining scenarios
- RAG retrieval queries
- Edge cases (missing data, ambiguous queries)
- Security boundary tests (role violations, injection attempts)

A scoring script runs the agent against all test cases and produces Faithfulness, Answer Relevance, and Context Precision scores. This serves as:
1. The LLMOps evaluation answer (Part 1, Q2)
2. The golden dataset for incident management (Part 4, Q1)
3. A regression test for model updates

## Consequences

- **Positive:** Demonstrates eval lifecycle knowledge, doubles as regression test, concrete deliverable
- **Negative:** ~50 lines of eval code + 10 test cases to write
- **Mitigation:** Use RAGAS library for scoring (don't reinvent metrics)
