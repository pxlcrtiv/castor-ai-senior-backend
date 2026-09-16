"""FastAPI application for the Castor AI Reconciliation Agent.

Exposes the agent through REST endpoints with:
- Token streaming for improved UX
- Proper error handling for LLM/ERP failures
- CORS for Angular frontend integration
- Health checks for monitoring
"""

import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.agents.reconciler_agent import reconciliation_agent
from src.config.settings import settings


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    print("🚀 Starting Castor AI Reconciliation Agent...")
    print(f"   Model: {settings.openai_model}")
    print(f"   Port:  {settings.api_port}")
    yield
    print("👋 Shutting down...")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Castor AI — Reconciliation Agent",
    description="Sistema de agentes autónomos para conciliación fiscal ERP",
    version="0.1.0",
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

    query: str = Field(..., min_length=1, max_length=2000, description="Consulta en lenguaje natural")
    session_id: str | None = Field(default=None, description="ID de sesión para mantener contexto")
    user_role: str = Field(default="analyst", description="Rol: viewer, analyst, admin")


class QueryResponse(BaseModel):
    """Agent response."""

    response: str
    session_id: str
    blocked: bool = False
    tool_calls: list[dict] | None = None
    error: str | None = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    model: str
    version: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check for load balancers and monitoring."""
    return HealthResponse(
        status="healthy",
        model=settings.openai_model,
        version="0.1.0",
    )


@app.post("/query", response_model=QueryResponse)
async def query_agent(request: QueryRequest):
    """Process a natural language query through the reconciliation agent.

    Returns a complete response after the agent finishes reasoning.
    """
    session_id = request.session_id or str(uuid.uuid4())

    try:
        result = await reconciliation_agent.query(
            user_input=request.query,
            session_id=session_id,
            user_role=request.user_role,
        )
        return QueryResponse(
            response=result["response"],
            session_id=session_id,
            blocked=result.get("blocked", False),
            tool_calls=result.get("tool_calls"),
            error=result.get("error"),
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "agent_error",
                "message": "Error al procesar la consulta. "
                           "El sistema no está disponible temporalmente.",
                "details": str(e),
            },
        )


@app.post("/query/stream")
async def query_agent_stream(request: QueryRequest):
    """Stream agent response tokens for improved UX.

    Returns Server-Sent Events (SSE) with token-by-token output.
    """
    session_id = request.session_id or str(uuid.uuid4())

    async def event_stream() -> AsyncIterator[str]:
        try:
            async for token in reconciliation_agent.query_stream(
                user_input=request.query,
                session_id=session_id,
                user_role=request.user_role,
            ):
                yield f"data: {token}\n\n"
            yield f"data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {{\"error\": \"{str(e)}\"}}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
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


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
    )
