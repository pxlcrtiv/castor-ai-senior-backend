# ADR-001: Multi-Agent Architecture with AutoGen

## Status

Accepted

## Context

We need a multi-agent system for ERP invoice reconciliation that processes natural language queries, chains tool calls, integrates RAG, and maintains session state. The test explicitly asks for a "multi-agent" system — not a single agent with tools.

## Decision

**Use Microsoft AutoGen as the orchestration framework** with a three-agent topology:

1. **Conciliator** — receives user queries, decomposes tasks, delegates to specialists, synthesizes responses
2. **ERP Analyst** — handles SQL lookups, tax calculations, invoice management
3. **Compliance Officer** — handles RAG-based regulation lookup with metadata filtering

### Why AutoGen over alternatives:

| Framework | Agent Count | Tool Chaining | Human-in-Loop | Streaming | Verdict |
|-----------|-------------|---------------|---------------|-----------|---------|
| AutoGen | Multi-agent native | Built-in | Built-in | Custom wrapper | ✅ Selected |
| LangChain | Single agent + tools | Excellent | Manual | Native SSE | ❌ Single-agent |
| Raw OpenAI SDK | Manual orchestration | Manual | Manual | Native | ❌ Too much work |
| LlamaIndex | Query engine focus | RAG-native | Limited | Limited | ❌ Wrong paradigm |

### Streaming Strategy:

Hybrid approach — AutoGen handles multi-agent orchestration, but the final response streams via raw OpenAI SDK. This uses each tool where it's strongest.

## Consequences

- **Positive:** True multi-agent separation of concerns, built-in human-in-the-loop support, matches test requirements
- **Negative:** No native streaming — requires hybrid approach with raw OpenAI SDK
- **Mitigation:** Custom async wrapper that bridges AutoGen responses to SSE streaming
