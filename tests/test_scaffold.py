"""Scaffolding and integration test suite for ValuGraph-MCP."""

from __future__ import annotations

import pytest
from click.testing import CliRunner

import valugraph_mcp
from valugraph_mcp import __version__, cli
from valugraph_mcp.cmbs import CMBSRiskEngine
from valugraph_mcp.dcf import DCFEngine, calculate_irr, calculate_npv
from valugraph_mcp.graph import TemporalCREGraph
from valugraph_mcp.server import create_mcp_server
from valugraph_mcp.types import (
    CMBSLoan,
    CMBSSecuritization,
    DCFInputs,
    PropertyParcel,
    ScenarioType,
    Tenant,
)


def test_package_metadata() -> None:
    """Verify package version and module availability."""
    assert __version__ == "0.1.0"
    assert valugraph_mcp.__version__ == "0.1.0"
    assert cli is not None


def test_cli_help(cli_runner: CliRunner) -> None:
    """Verify CLI root command help string."""
    result = cli_runner.invoke(cli.cli, ["--help"])
    assert result.exit_code == 0
    assert "ValuGraph-MCP" in result.output
    assert "info" in result.output
    assert "underwrite" in result.output
    assert "stress-test" in result.output
    assert "serve" in result.output


def test_cli_info(cli_runner: CliRunner) -> None:
    """Verify info subcommand displays subsystem status."""
    result = cli_runner.invoke(cli.cli, ["info"])
    assert result.exit_code == 0
    assert "ValuGraph-MCP" in result.output
    assert "v0.1.0" in result.output
    assert "Temporal CRE Graph" in result.output
    assert "Multi-Scenario DCF" in result.output
    assert "CMBS Tranche Waterfall" in result.output


def test_cli_underwrite(cli_runner: CliRunner) -> None:
    """Verify underwrite CLI command runs multi-scenario DCF."""
    result = cli_runner.invoke(
        cli.cli,
        [
            "underwrite",
            "--apn",
            "APN-TEST-1",
            "--price",
            "5000000",
            "--revenue",
            "600000",
            "--expenses",
            "200000",
        ],
    )
    assert result.exit_code == 0
    assert "ValuGraph DCF Underwriting: APN-TEST-1" in result.output
    assert "Base" in result.output
    assert "Bull" in result.output
    assert "Bear" in result.output
    assert "Severe Stress" in result.output


def test_cli_stress_test(cli_runner: CliRunner) -> None:
    """Verify stress-test CLI command calculates tranche allocations."""
    result = cli_runner.invoke(
        cli.cli,
        [
            "stress-test",
            "--balance",
            "50000000",
            "--shock-bps",
            "200",
            "--loss-severity",
            "0.45",
        ],
    )
    assert result.exit_code == 0
    assert "CMBS Subordination Waterfall" in result.output
    assert "Equity" in result.output
    assert "AAA" in result.output


def test_irr_and_npv_numerical_convergence() -> None:
    """Verify numerical IRR convergence and NPV consistency."""
    # Cash flows: -100 at t=0, +60 at t=1, +60 at t=2 -> r ~ 13.066%
    cfs = [-100.0, 60.0, 60.0]
    irr = calculate_irr(cfs)
    assert 0.12 <= irr <= 0.14

    # At the IRR, NPV should be effectively zero
    npv_at_irr = calculate_npv(irr, cfs)
    assert abs(npv_at_irr) < 1e-3


def test_dcf_scenarios(sample_dcf_inputs: DCFInputs) -> None:
    """Verify DCF engine scenario order: Bull > Base > Bear > Severe."""
    engine = DCFEngine()
    scenarios = engine.stress_test_multiscenario(sample_dcf_inputs)

    base = scenarios[ScenarioType.BASE]
    bull = scenarios[ScenarioType.BULL]
    bear = scenarios[ScenarioType.BEAR]
    severe = scenarios[ScenarioType.SEVERE_STRESS]

    assert bull.irr > base.irr
    assert base.irr > bear.irr
    assert bear.irr > severe.irr
    assert bull.equity_multiple > base.equity_multiple > bear.equity_multiple


def test_underwriting_report(
    sample_parcel: PropertyParcel,
    sample_dcf_inputs: DCFInputs,
) -> None:
    """Verify underwriting synthesis and debt sizing."""
    engine = DCFEngine()
    report = engine.generate_underwriting_report(sample_parcel, sample_dcf_inputs)

    assert report.property_apn == sample_parcel.apn
    assert report.recommended_loan_amount > 0
    assert report.average_dscr > 1.0
    assert "qualifies" in report.conclusion.lower()


def test_cmbs_risk_engine(sample_cmbs_deal: CMBSSecuritization) -> None:
    """Verify CMBS pool metrics, stress calculations, and waterfall losses."""
    engine = CMBSRiskEngine()

    pool_summary = engine.calculate_pool_summary(sample_cmbs_deal.collateral_loans)
    assert pool_summary["loan_count"] == 4
    assert pool_summary["total_balance"] == 100000000.0
    assert pool_summary["weighted_avg_dscr"] > 1.0

    # Stress test
    stress = engine.evaluate_pool_stress(
        loans=sample_cmbs_deal.collateral_loans,
        loss_severity=0.40,
        rate_shock_bps=150.0,
    )
    assert stress["total_expected_loss"] > 0
    assert stress["pool_loss_pct"] < 1.0

    # Waterfall
    allocations = engine.allocate_waterfall_losses(
        tranches=sample_cmbs_deal.tranches,
        cumulative_pool_loss=stress["total_expected_loss"],
    )
    assert len(allocations) == 5

    # Equity tranche should take losses first
    equity_tranche = next(a for a in allocations if a["tranche_name"] == "Equity")
    assert equity_tranche["allocated_loss"] > 0


def test_temporal_graph_operations(
    sample_parcel: PropertyParcel,
    sample_tenant: Tenant,
) -> None:
    """Verify graph creation, node relations, and neighborhood query."""
    graph = TemporalCREGraph()
    assert graph.node_count == 0
    assert graph.edge_count == 0

    graph.add_parcel(sample_parcel)
    assert graph.node_count == 1

    graph.add_owner("OWN-1", "Blackstone CRE Fund", "Private Equity")
    graph.link_ownership("OWN-1", sample_parcel.apn, "2021-03-01", 80000000.0)
    assert graph.node_count == 2
    assert graph.edge_count == 1

    graph.add_tenant(sample_tenant, sample_parcel.apn)
    assert graph.node_count == 3
    assert graph.edge_count == 2

    loan = CMBSLoan(
        loan_id="LN-901",
        property_apn=sample_parcel.apn,
        original_balance=50000000.0,
        current_balance=48000000.0,
        interest_rate=0.065,
        maturity_date="2031-03-01",
        dscr=1.35,
        ltv=0.60,
    )
    graph.add_loan(loan)
    assert graph.node_count == 4
    assert graph.edge_count == 3

    # Queries
    lineage = graph.get_property_lineage(sample_parcel.apn)
    assert len(lineage) == 1
    assert lineage[0]["owner_name"] == "Blackstone CRE Fund"

    tenants = graph.get_tenants(sample_parcel.apn)
    assert len(tenants) == 1
    assert tenants[0]["name"] == sample_tenant.name

    encumbrances = graph.get_encumbrances(sample_parcel.apn)
    assert len(encumbrances) == 1
    assert encumbrances[0]["loan_id"] == "LN-901"

    subgraph = graph.get_neighborhood_subgraph(sample_parcel.apn, depth=2)
    assert subgraph["node_count"] == 4
    assert subgraph["edge_count"] == 3


@pytest.mark.asyncio
async def test_mcp_server_tools_registered() -> None:
    """Verify MCP server factory creates server with registered tools."""
    server = create_mcp_server("test-valugraph")
    tools = await server.list_tools()
    tool_names = [t.name for t in tools]

    assert "underwrite_commercial_property" in tool_names
    assert "stress_test_cmbs_pool" in tool_names
    assert "query_property_graph" in tool_names
    assert "estimate_debt_capacity" in tool_names
    assert "diagnose_property_risk" in tool_names
