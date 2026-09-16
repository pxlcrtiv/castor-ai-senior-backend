# ADR-001: Agent Architecture Pattern

## Status

Proposed

## Context

We need to build a multi-agent system for ERP invoice reconciliation that:

1. Processes natural language queries
2. Chains multiple tool calls (ERP lookup + tax calculation)
3. Integrates RAG for regulatory document retrieval
4. Maintains conversation context across sessions

## Decision

**Use LangChain with ReAct (Reasoning + Acting) pattern** as the primary orchestration framework.

### Why ReAct over alternatives:

| Pattern | Pros | Cons | Verdict |
|---------|------|------|---------|
| ReAct (LangChain) | Proven tool chaining, streaming support, large ecosystem | Slightly more overhead | ✅ Selected |
| AutoGen | Great for multi-agent debate | Overkill for single-agent with tools | ❌ |
| LlamaIndex | Superior RAG | Weaker agent orchestration | ❌ |
| Custom (raw API) | Full control | High implementation cost | ❌ |

### Architecture Layers:

```
┌─────────────────────────────────────────┐
│         FastAPI + SSE Streaming         │  ← API Layer
├─────────────────────────────────────────┤
│      ReAct Agent (LangChain)           │  ← Orchestration
├─────────────────────────────────────────┤
│  ┌──────────┐  ┌────────────────────┐  │
│  │ ERP Mock │  │ RAG (ChromaDB)     │  │  ← Tools Layer
│  │ Tools    │  │ Metadata Filtering │  │
│  └──────────┘  └────────────────────┘  │
├─────────────────────────────────────────┤
│    Security (Prompt Validation)        │  ← Guardrails
│    PII Detection + Injection Defense   │
└─────────────────────────────────────────┘
```

## Consequences

- **Positive:** Battle-tested framework, easy to swap LLM providers (model-agnostic)
- **Negative:** LangChain dependency; may need abstraction layer for migration
- **Mitigation:** Keep tools as pure async functions; wrap LangChain at boundary only

## Alternatives Considered

- **Azure AI Agent Service:** Would lock us to Azure ecosystem
- **Semantic Kernel:** Good but smaller community than LangChain
- **CrewAI:** Designed for multi-agent, but we only need one agent with tools
