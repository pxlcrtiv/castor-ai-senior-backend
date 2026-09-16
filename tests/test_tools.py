"""Tests for ERP tools — the agent's data layer.

Seams under test:
1. get_erp_data(order_id) → dict with invoice details
2. calculate_tax_discrepancy(amount, region) → dict with tax calculation
3. list_pending_invoices() → dict with pending invoices
"""

import asyncio
import pytest

from src.tools.erp_tools import get_erp_data, calculate_tax_discrepancy, list_pending_invoices


# ---------------------------------------------------------------------------
# get_erp_data — SQL lookup simulation
# ---------------------------------------------------------------------------

class TestGetErpData:

    @pytest.mark.asyncio
    async def test_existing_order_returns_success(self):
        result = await get_erp_data("4402")
        assert result["success"] is True
        assert result["data"]["order_id"] == "4402"

    @pytest.mark.asyncio
    async def test_existing_order_has_required_fields(self):
        result = await get_erp_data("4402")
        data = result["data"]
        required = {"order_id", "supplier", "amount", "tax", "region", "status"}
        assert required.issubset(data.keys())

    @pytest.mark.asyncio
    async def test_order_with_discrepancy_flags_it(self):
        result = await get_erp_data("4402")
        assert result["data"]["discrepancy"] > 0
        assert "discrepancy_reason" in result["data"]

    @pytest.mark.asyncio
    async def test_clean_order_has_zero_discrepancy(self):
        result = await get_erp_data("4403")
        assert result["data"]["discrepancy"] == 0

    @pytest.mark.asyncio
    async def test_nonexistent_order_returns_failure(self):
        result = await get_erp_data("9999")
        assert result["success"] is False
        assert "not found" in result["error"].lower()


# ---------------------------------------------------------------------------
# calculate_tax_discrepancy — business logic
# ---------------------------------------------------------------------------

class TestTaxCalculation:

    @pytest.mark.asyncio
    async def test_cdmx_standard_rate(self):
        result = await calculate_tax_discrepancy(10000.0, "CDMX")
        assert result["success"] is True
        assert result["tax_rate"] == 0.16
        assert result["expected_tax"] == 1600.0

    @pytest.mark.asyncio
    async def test_oaxaca_reduced_rate(self):
        result = await calculate_tax_discrepancy(10000.0, "Oaxaca")
        assert result["success"] is True
        assert result["tax_rate"] == 0.08
        assert result["expected_tax"] == 800.0

    @pytest.mark.asyncio
    async def test_unknown_region_defaults_to_16_percent(self):
        result = await calculate_tax_discrepancy(5000.0, "Unknown")
        assert result["tax_rate"] == 0.16

    @pytest.mark.asyncio
    async def test_zero_amount(self):
        result = await calculate_tax_discrepancy(0.0, "CDMX")
        assert result["expected_tax"] == 0.0

    @pytest.mark.asyncio
    async def test_formula_includes_rate_and_amount(self):
        result = await calculate_tax_discrepancy(1000.0, "Jalisco")
        assert "formula" in result
        assert "1000" in result["formula"]


# ---------------------------------------------------------------------------
# list_pending_invoices — bulk query
# ---------------------------------------------------------------------------

class TestPendingInvoices:

    @pytest.mark.asyncio
    async def test_returns_only_non_approved(self):
        result = await list_pending_invoices()
        assert result["success"] is True
        statuses = {inv["status"] for inv in result["invoices"]}
        assert "approved" not in statuses

    @pytest.mark.asyncio
    async def test_count_matches_list(self):
        result = await list_pending_invoices()
        assert result["count"] == len(result["invoices"])

    @pytest.mark.asyncio
    async def test_includes_discrepancy_orders(self):
        result = await list_pending_invoices()
        order_ids = [inv["order_id"] for inv in result["invoices"]]
        assert "4402" in order_ids  # pending_review
        assert "4404" in order_ids  # flagged
