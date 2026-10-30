"""Comprehensive async integration tests for all Model Context Protocol (MCP) server tools."""

from __future__ import annotations

import json

import pytest

from valugraph_mcp.server import create_mcp_server


@pytest.mark.asyncio
class TestServerToolsDeep:
    """Tests executing each registered MCP tool and asserting structure and math."""

    async def test_underwrite_commercial_property_tool(self) -> None:
        """Verify underwrite_commercial_property tool executes multi-scenario DCF."""
        server = create_mcp_server("test-mcp")
        result = await server.call_tool(
            "underwrite_commercial_property",
            {
                "apn": "APN-MCP-UNDERWRITE",
                "purchase_price": 25000000.0,
                "initial_revenue": 3200000.0,
                "initial_expenses": 950000.0,
                "hold_period_years": 7,
                "exit_cap_rate": 0.065,
                "discount_rate": 0.09,
                "financing_ltv": 0.65,
                "financing_interest_rate": 0.065,
            },
        )
        assert result is not None
        assert not result.is_error
        data = json.loads(result.content[0].text)
        assert data["apn"] == "APN-MCP-UNDERWRITE"
        assert data["purchase_price"] == 25000000.0
        assert data["recommended_loan"] > 0
        assert data["average_dscr"] > 0
        assert "base" in data["scenarios"]
        assert "bull" in data["scenarios"]
        assert "bear" in data["scenarios"]
        assert "severe_stress" in data["scenarios"]
        assert data["scenarios"]["bull"]["irr"] > data["scenarios"]["bear"]["irr"]

    async def test_stress_test_cmbs_pool_tool(self) -> None:
        """Verify stress_test_cmbs_pool tool calculates rate shocks and waterfall tranche losses."""
        server = create_mcp_server("test-mcp")
        result = await server.call_tool(
            "stress_test_cmbs_pool",
            {
                "deal_id": "DEAL-MCP-2026",
                "total_balance": 150000000.0,
                "rate_shock_bps": 200.0,
                "loss_severity": 0.45,
            },
        )
        assert result is not None
        assert not result.is_error
        data = json.loads(result.content[0].text)
        assert data["deal_id"] == "DEAL-MCP-2026"
        assert "pool_metrics" in data
        assert "stress_scenario" in data
        assert data["stress_scenario"]["total_expected_loss"] > 0
        assert len(data["tranche_allocations"]) == 5

    async def test_query_property_graph_tool(self) -> None:
        """Verify query_property_graph tool retrieves seeded lineage, leases, and encumbrances."""
        server = create_mcp_server("test-mcp")
        result = await server.call_tool(
            "query_property_graph",
            {
                "apn": "APN-042-108-01",  # Pre-seeded sample parcel in create_mcp_server
                "depth": 2,
            },
        )
        assert result is not None
        assert not result.is_error
        data = json.loads(result.content[0].text)
        assert data["apn"] == "APN-042-108-01"
        assert len(data["lineage"]) >= 1
        assert len(data["tenants"]) >= 1
        assert data["graph_summary"]["nodes_in_neighborhood"] >= 1
        assert data["graph_summary"]["total_graph_nodes"] >= 3

        # Non-existent parcel should return safely with empty collections
        result_unknown = await server.call_tool(
            "query_property_graph",
            {
                "apn": "NON-EXISTENT-APN",
                "depth": 1,
            },
        )
        assert not result_unknown.is_error
        data_unknown = json.loads(result_unknown.content[0].text)
        assert data_unknown["lineage"] == []
        assert data_unknown["tenants"] == []
        assert data_unknown["graph_summary"]["nodes_in_neighborhood"] == 0

    async def test_estimate_debt_capacity_tool_dscr_and_ltv_binding(self) -> None:
        """Verify estimate_debt_capacity correctly identifies DSCR vs LTV binding constraints."""
        server = create_mcp_server("test-mcp")

        # 1. Low NOI relative to property value -> DSCR is the binding constraint
        res_dscr = await server.call_tool(
            "estimate_debt_capacity",
            {
                "net_operating_income": 400000.0,
                "property_value": 20000000.0,
                "min_dscr": 1.25,
                "max_ltv": 0.70,
                "interest_rate": 0.065,
                "amortization_years": 30,
            },
        )
        assert not res_dscr.is_error
        data_dscr = json.loads(res_dscr.content[0].text)
        assert data_dscr["binding_constraint"] == "DSCR"
        assert data_dscr["recommended_max_debt"] == data_dscr["max_debt_dscr_cap"]

        # 2. High NOI relative to property value -> LTV is the binding constraint
        res_ltv = await server.call_tool(
            "estimate_debt_capacity",
            {
                "net_operating_income": 2500000.0,
                "property_value": 20000000.0,
                "min_dscr": 1.25,
                "max_ltv": 0.65,
                "interest_rate": 0.065,
                "amortization_years": 30,
            },
        )
        assert not res_ltv.is_error
        data_ltv = json.loads(res_ltv.content[0].text)
        assert data_ltv["binding_constraint"] == "LTV"
        assert data_ltv["recommended_max_debt"] == data_ltv["max_debt_ltv_cap"]

        # 3. Zero interest rate branch
        res_zero = await server.call_tool(
            "estimate_debt_capacity",
            {
                "net_operating_income": 1000000.0,
                "property_value": 15000000.0,
                "interest_rate": 0.0,
                "amortization_years": 25,
            },
        )
        assert not res_zero.is_error
        data_zero = json.loads(res_zero.content[0].text)
        assert data_zero["recommended_max_debt"] > 0
