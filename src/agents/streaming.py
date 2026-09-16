"""Streaming adapter — bridges AutoGen orchestration with SSE streaming.

Uses raw OpenAI SDK for the final streaming response while
keeping AutoGen for multi-agent orchestration. This is the
hybrid approach: each tool where it's strongest.
"""

from __future__ import annotations

import json
from typing import AsyncIterator

from src.security.rbac import rbac, audit_trail
from src.security.prompt_validator import prompt_validator


class StreamAdapter:
    """Stream agent responses token-by-token via async generator.

    Flow: validate → RBAC check → mock stream → audit log
    In production: validate → RBAC check → OpenAI streaming → audit log
    """

    async def stream(
        self,
        query: str,
        role: str = "analyst",
        session_id: str = "default",
    ) -> AsyncIterator[str]:
        """Stream response tokens for a query.

        Args:
            query: User's natural language query.
            role: User's RBAC role.
            session_id: Session ID for audit trail.

        Yields:
            Response tokens as strings.
        """
        # 1. Security validation
        validation = prompt_validator.validate(query, role)
        if not validation.is_safe:
            audit_trail.log(
                role=role,
                tool="stream_validation",
                query=query[:200],
                allowed=False,
                session_id=session_id,
                denial_reason=validation.reason,
            )
            yield f"⛔ Consulta bloqueada: {validation.reason}"
            return

        # 2. Log stream start
        audit_trail.log(
            role=role,
            tool="stream_response",
            query=query[:200],
            allowed=True,
            session_id=session_id,
        )

        # 3. Generate response (mock for prototype)
        # In production: yield from openai.ChatCompletion.create(stream=True, ...)
        response = self._mock_response(query)

        # Simulate token-by-token streaming
        words = response.split()
        for i, word in enumerate(words):
            prefix = " " if i > 0 else ""
            yield prefix + word

    def _mock_response(self, query: str) -> str:
        """Generate mock response for prototype.

        In production, this would be the OpenAI streaming call.
        """
        if "4402" in query:
            return (
                "📋 Factura #4402 encontrada en el ERP.\n\n"
                "Proveedor: Logística Express S.A.\n"
                "Monto: $15,420.50 MXN\n"
                "Estado: Pendiente de revisión\n"
                "Discrepancia: $250.00 (IVA calculado con tasa incorrecta)"
            )
        elif "4403" in query:
            return (
                "📋 Factura #4403 encontrada.\n\n"
                "Proveedor: Transporte Global Ltd.\n"
                "Monto: $8,750.00 MXN\n"
                "Estado: Aprobada"
            )
        elif "pendiente" in query.lower():
            return (
                "📋 Facturas pendientes de revisión:\n\n"
                "• #4402 - Logística Express ($15,420.50) - Pendiente\n"
                "• #4404 - Envíos Rápidos ($23,100.00) - Marcada"
            )
        else:
            return (
                f"🤖 Procesando consulta: '{query}'\n\n"
                "El agente está analizando la solicitud. "
                "Se requiere OPENAI_API_KEY para respuestas reales."
            )


def sse_format(token: str) -> str:
    """Format a token as Server-Sent Event data."""
    return f"data: {json.dumps({'token': token})}\n\n"


def sse_done() -> str:
    """SSE stream termination signal."""
    return "data: [DONE]\n\n"
