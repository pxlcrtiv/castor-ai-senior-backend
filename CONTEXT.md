# Castor AI Reconciliation Agent

Multi-agent system for automated invoice reconciliation between logistics invoices and ERP systems. Built for a senior AI backend engineer technical test.

## Language

**Conciliator**:
The main orchestrator agent. Receives natural language queries from users, decomposes them into sub-tasks, delegates to specialist agents, and synthesizes responses.
_Avoid_: Router, dispatcher, main agent

**ERP Analyst**:
Specialist agent that handles SQL queries, data lookups, and tax calculations. Has access to ERP tools (get_erp_data, calculate_tax_discrepancy, list_pending_invoices).
_Avoid_: Data agent, SQL agent

**Compliance Officer**:
Specialist agent that handles regulation lookup via RAG. Consults indexed PDF manuals and fiscal codes to provide legal context for decisions.
_Avoid_: RAG agent, knowledge agent

**Discrepancy**:
A mismatch between the invoice amount in the ERP and the expected amount based on tax calculations or other business rules. The core problem this system solves.
_Avoid_: Variance, difference, mismatch

**Reconciliation**:
The process of identifying and resolving discrepancies between logistics invoices and ERP records. The system's primary function.
_Avoid_: Matching, alignment

**Metadata Filtering**:
Filtering RAG results by document attributes (year, region, document type) to prevent noise in retrieved information. Critical for avoiding context stuffing.
_Avoid_: Document filtering, retrieval filtering

**Golden Dataset**:
A curated set of test cases with expected outputs, used to evaluate agent performance and detect model drift after updates.
_Avoid_: Test set, benchmark

**Audit Trail**:
Complete log of every agent decision, tool call, and RBAC check. Used for incident investigation and compliance.
_Avoid_: Logging, trace
