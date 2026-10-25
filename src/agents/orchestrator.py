"""Reconciliation orchestration for invoice queries.

Owns the query flow behind the /query endpoint: prompt validation, intent
routing, tool chaining and response synthesis, then audit logging. The API
layer delegates here so the transport never hosts the flow itself.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from src.security.prompt_validator import prompt_validator
from src.security.rbac import audit_trail
from src.tools.erp_tools import (
    calculate_tax_discrepancy,
    get_erp_data,
    list_pending_invoices,
)

ORDER_ID_PATTERN = re.compile(r"#?(\d{4})")


@dataclass
class QueryOutcome:
    """Outcome of a reconciliation query, before the API shapes the response."""

    response: str
    blocked: bool = False
    audit_entries: int = 0
    error: str | None = None


async def process_query(query: str, user_role: str, session_id: str) -> QueryOutcome:
    """Run the full reconciliation flow for a user query."""
    # 1. Prompt validation (injection + sensitive data)
    validation = prompt_validator.validate(query, user_role)
    if not validation.is_safe:
        audit_trail.log(
            role=user_role,
            tool="prompt_validation",
            query=query[:200],
            allowed=False,
            session_id=session_id,
            denial_reason=validation.reason,
        )
        return QueryOutcome(
            response=f"⛔ Consulta bloqueada: {validation.reason}",
            blocked=True,
            audit_entries=audit_trail.count(session_id),
        )

    # 2. Execute agent team
    try:
        # Determine which tools to call based on query
        query_lower = query.lower()
        response_parts: list[str] = []

        # Always try to find an order ID in the query
        order_match = ORDER_ID_PATTERN.search(query)

        if "pendiente" in query_lower or "pending" in query_lower:
            result = await list_pending_invoices()
            if result["success"]:
                invoices = result["data"]["invoices"]
                response_parts.append(f"📋 Facturas pendientes: {len(invoices)}")
                for inv in invoices:
                    response_parts.append(
                        f"  • #{inv['order_id']} — {inv['supplier']} — "
                        f"${inv['amount']:,.2f} — {inv['status']}"
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
                        response_parts.append("\n🧮 Cálculo de impuesto:")
                        response_parts.append(f"  Tasa esperada: {tax_result['tax_rate']*100}%")
                        response_parts.append(
                            f"  Impuesto esperado: ${tax_result['expected_tax']:,.2f}"
                        )
            else:
                response_parts.append(f"❌ Factura #{order_id} no encontrada")

        else:
            response_parts.append(f"🤖 Procesando: '{query}'")
            response_parts.append(
                "💡 Usa el endpoint /invoices/{order_id} "
                "para consultar una factura específica"
            )

        response_text = (
            "\n".join(response_parts) if response_parts else "No se pudo procesar la consulta."
        )

        # Log successful access
        audit_trail.log(
            role=user_role,
            tool="agent_team",
            query=query[:200],
            allowed=True,
            session_id=session_id,
        )

        return QueryOutcome(
            response=response_text,
            audit_entries=audit_trail.count(session_id),
        )

    except Exception as e:
        return QueryOutcome(
            response=(
                "⚠️ Error al procesar la consulta. "
                "El sistema no está disponible temporalmente."
            ),
            error=str(e),
            audit_entries=audit_trail.count(session_id),
        )
