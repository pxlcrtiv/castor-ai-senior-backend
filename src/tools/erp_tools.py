"""Mock ERP tools for the agent.

These simulate queries to SQL Server and business logic
for invoice reconciliation.
"""

import asyncio
from typing import Any


# Simulated ERP database
_MOCK_ERP_DATA: dict[str, dict[str, Any]] = {
    "4402": {
        "order_id": "4402",
        "supplier": "Logística Express S.A.",
        "amount": 15420.50,
        "tax": 2775.69,
        "region": "CDMX",
        "status": "pending_review",
        " discrepancy": 250.00,
        "discrepancy_reason": "IVA calculado con tasa incorrecta (16% vs 11%)",
        "date": "2024-09-15",
        "items": [
            {"description": "Flete internacional", "amount": 12000.00},
            {"description": "Seguro de carga", "amount": 1500.00},
            {"description": "Manejo aduanal", "amount": 1920.50},
        ],
    },
    "4403": {
        "order_id": "4403",
        "supplier": "Transporte Global Ltd.",
        "amount": 8750.00,
        "tax": 1575.00,
        "region": "Jalisco",
        "status": "approved",
        "discrepancy": 0.0,
        "date": "2024-09-18",
    },
    "4404": {
        "order_id": "4404",
        "supplier": "Envíos Rápidos S.A.",
        "amount": 23100.00,
        "tax": 4158.00,
        "region": "Nuevo León",
        "status": "flagged",
        "discrepancy": 1200.00,
        "discrepancy_reason": "Monto excede umbral de aprobación automática",
        "date": "2024-10-02",
    },
}


async def get_erp_data(order_id: str) -> dict[str, Any]:
    """Simulate a SQL Server query for ERP invoice data.

    Args:
        order_id: The order/invoice ID to look up.

    Returns:
        Dictionary with invoice details or error.
    """
    # Simulate network latency
    await asyncio.sleep(0.1)

    if order_id in _MOCK_ERP_DATA:
        return {
            "success": True,
            "data": _MOCK_ERP_DATA[order_id],
        }

    return {
        "success": False,
        "error": f"Order #{order_id} not found in ERP system",
    }


async def calculate_tax_discrepancy(amount: float, region: str) -> dict[str, Any]:
    """Calculate expected tax and identify discrepancies.

    Args:
        amount: Base amount of the invoice.
        region: Mexican state/region for tax rate lookup.

    Returns:
        Dictionary with tax calculation and discrepancy info.
    """
    await asyncio.sleep(0.05)

    # Tax rates by region (simplified)
    tax_rates = {
        "CDMX": 0.16,
        "Jalisco": 0.16,
        "Nuevo León": 0.16,
        "Oaxaca": 0.08,  # Frontera sur
    }

    rate = tax_rates.get(region, 0.16)
    expected_tax = round(amount * rate, 2)

    return {
        "success": True,
        "region": region,
        "tax_rate": rate,
        "base_amount": amount,
        "expected_tax": expected_tax,
        "formula": f"{amount} × {rate} = {expected_tax}",
    }


async def list_pending_invoices() -> dict[str, Any]:
    """List all invoices pending review in the ERP.

    Returns:
        Dictionary with list of pending invoices.
    """
    await asyncio.sleep(0.1)

    pending = [
        v for v in _MOCK_ERP_DATA.values() if v["status"] in ("pending_review", "flagged")
    ]

    return {
        "success": True,
        "count": len(pending),
        "invoices": pending,
    }
