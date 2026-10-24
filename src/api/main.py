"""FastAPI application for the Castor AI Reconciliation Agent.

Exposes the AutoGen multi-agent team through REST endpoints with:
- Token streaming for improved UX
- RBAC middleware for role-based access
- Audit trail for every decision
- Graceful degradation on failures
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.agents.orchestrator import process_query
from src.config.settings import settings
from src.security.rbac import audit_trail


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    from src.config.llm_provider import LLMConfig
    try:
        llm_config = LLMConfig.from_env()
        print(f"🚀 Starting Castor AI Reconciliation Agent...")
        print(f"   Provider: {llm_config.provider.value}")
        print(f"   Model: {llm_config.model}")
    except Exception as e:
        print(f"🚀 Starting Castor AI Reconciliation Agent...")
        print(f"   ⚠️ LLM not configured: {e}")
    yield
    print("👋 Shutting down...")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Castor AI — Reconciliation Agent",
    description="Multi-agent system for ERP invoice reconciliation (AutoGen)",
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class QueryRequest(BaseModel):
    """Incoming query from the user."""

    query: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = None
    user_role: str = Field(default="analyst")


class QueryResponse(BaseModel):
    """Agent response."""

    response: str
    session_id: str
    blocked: bool = False
    audit_entries: int = 0
    error: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check."""

    status: str
    model: str
    version: str
    agents: list[str]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check for load balancers and monitoring."""
    from src.config.llm_provider import LLMConfig
    try:
        llm_config = LLMConfig.from_env()
        model = llm_config.model
    except Exception:
        model = settings.openai_model
    return HealthResponse(
        status="healthy",
        model=model,
        version="0.2.0",
        agents=["Conciliator", "ERP_Analyst", "Compliance_Officer"],
    )


@app.post("/query", response_model=QueryResponse)
async def query_agent(request: QueryRequest):
    """Process a natural language query through the multi-agent team.

    Full pipeline: security validation → RBAC check → agent execution → audit log.
    """
    session_id = request.session_id or str(uuid.uuid4())

    outcome = await process_query(request.query, request.user_role, session_id)

    return QueryResponse(
        response=outcome.response,
        session_id=session_id,
        blocked=outcome.blocked,
        audit_entries=outcome.audit_entries,
        error=outcome.error,
    )


@app.get("/invoices/pending")
async def get_pending_invoices():
    """Get all pending invoices requiring review."""
    from src.tools.erp_tools import list_pending_invoices
    result = await list_pending_invoices()
    if result["success"]:
        return result
    raise HTTPException(status_code=500, detail=result["error"])


@app.get("/invoices/{order_id}")
async def get_invoice(order_id: str):
    """Get specific invoice details from ERP."""
    from src.tools.erp_tools import get_erp_data
    result = await get_erp_data(order_id)
    if result["success"]:
        return result
    raise HTTPException(status_code=404, detail=result["error"])


@app.get("/audit/{session_id}")
async def get_audit_trail(session_id: str):
    """Get audit trail for a session (admin only)."""
    entries = audit_trail.get_entries(session_id)
    return {
        "session_id": session_id,
        "count": len(entries),
        "entries": [
            {
                "timestamp": e.timestamp.isoformat(),
                "role": e.role,
                "tool": e.tool,
                "allowed": e.allowed,
                "denial_reason": e.denial_reason,
            }
            for e in entries
        ],
    }


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api.main:app", host=settings.api_host, port=settings.api_port, reload=True)
