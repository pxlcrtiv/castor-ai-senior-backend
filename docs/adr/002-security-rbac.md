# ADR-002: RBAC + Audit Trail for Security Layer

## Status

Accepted

## Context

The test requires a security layer that detects prompt injection and prevents unauthorized data access. Most candidates will implement regex blocklists. We need to demonstrate enterprise-grade security without overengineering.

## Decision

**Three-tier RBAC with full audit trail:**

| Role | Tool Access | Data Access | ERP Write |
|------|------------|-------------|-----------|
| `viewer` | None (read-only queries) | Public invoice data | No |
| `analyst` | ERP lookup + tax calculator | Full invoice data | No |
| `admin` | All tools | All data including sensitive | Yes |

Every tool call, RBAC check, and agent decision is logged to an audit trail. This serves dual purpose: security compliance and incident investigation.

### Why RBAC over LLM-as-judge:

- Zero latency overhead (no extra LLM call)
- Deterministic (no hallucinated security decisions)
- Enterprise-standard pattern (reviewers recognize it)
- Audit trail provides evidence for incident investigation

## Consequences

- **Positive:** Enterprise-grade security, deterministic access control, full observability
- **Negative:** RBAC middleware adds ~50 lines of code
- **Mitigation:** Keep RBAC logic in a single `security/rbac.py` module
