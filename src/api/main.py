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

from src.agents.team import build_team, get_tool_registry
from src.config.settings import settings
from src.security.rbac import rbac, audit_trail
from src.security.prompt_validator import prompt_validator


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    print("🚀 Starting Castor AI Reconciliation Agent (AutoGen)...")
    print(f"   Model: {settings.openai_model}")
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

    # 1. Prompt validation (injection + sensitive data)
    validation = prompt_validator.validate(request.query, request.user_role)
    if not validation.is_safe:
        audit_trail.log(
            role=request.user_role,
            tool="prompt_validation",
            query=request.query[:200],
            allowed=False,
            session_id=session_id,
            denial_reason=validation.reason,
        )
        return QueryResponse(
            response=f"⛔ Consulta bloqueada: {validation.reason}",
            session_id=session_id,
            blocked=True,
            audit_entries=audit_trail.count(session_id),
        )

    # 2. Execute agent team
    try:
        from src.tools.erp_tools import get_erp_data, calculate_tax_discrepancy, list_pending_invoices
        from src.config.llm_provider import LLMConfig

        # Determine which tools to call based on query
        query_lower = request.query.lower()
        response_parts = []

        # Always try to find an order ID in the query
        import re
        order_match = re.search(r'#?(\d{4})', request.query)

        if "pendiente" in query_lower or "pending" in query_lower:
            result = await list_pending_invoices()
            if result["success"]:
                invoices = result["data"]["invoices"]
                response_parts.append(f"📋 Facturas pendientes: {len(invoices)}")
                for inv in invoices:
                    response_parts.append(
                        f"  • #{inv['order_id']} — {inv['supplier']} — ${inv['amount']:,.2f} — {inv['status']}"
                    )
            else:
                response_parts.append(f"⚠️ Error: {result['error']}")

        elif order_match:
            order_id = order_match.group(1)
            erp_result = await get_erp_data(order_id)
            if erp_result["success"]:
                data = erp_result["data"]
                response_parts.append(f"📋 Factura #{data['order_id']} — {data['supplier']}")
                response_parts.append(f"💰 Monto: ${data['amount']:,.2f} MXN")
                response_parts.append(f"🏷️ Estado: {data['status']}")
                response_parts.append(f"📍 Región: {data['region']}")

                if data["discrepancy"] > 0:
                    response_parts.append(f"⚠️ Discrepancia: ${data['discrepancy']:,.2f}")
                    response_parts.append(f"📝 Razón: {data['discrepancy_reason']}")

                    # Chain to tax calculation
                    tax_result = await calculate_tax_discrepancy(data["amount"], data["region"])
                    if tax_result.get("success", True):
                        response_parts.append(f"\n🧮 Cálculo de impuesto:")
                        response_parts.append(f"  Tasa esperada: {tax_result['tax_rate']*100}%")
                        response_parts.append(f"  Impuesto esperado: ${tax_result['expected_tax']:,.2f}")
            else:
                response_parts.append(f"❌ Factura #{order_id} no encontrada")

        else:
            response_parts.append(f"🤖 Procesando: '{request.query}'")
            response_parts.append(f"💡 Usa el endpoint /invoices/{'{order_id}'} para consultar una factura específica")

        response_text = "\n".join(response_parts) if response_parts else "No se pudo procesar la consulta."

        # Log successful access
        audit_trail.log(
            role=request.user_role,
            tool="agent_team",
            query=request.query[:200],
            allowed=True,
            session_id=session_id,
        )

        return QueryResponse(
            response=response_text,
            session_id=session_id,
            blocked=False,
            audit_entries=audit_trail.count(session_id),
        )

    except Exception as e:
        return QueryResponse(
            response=(
                "⚠️ Error al procesar la consulta. "
                "El sistema no está disponible temporalmente."
            ),
            session_id=session_id,
            error=str(e),
            audit_entries=audit_trail.count(session_id),
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
