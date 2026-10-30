"""Command Line Interface for ValuGraph-MCP."""

from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table

import valugraph_mcp
from valugraph_mcp.cmbs import CMBSRiskEngine
from valugraph_mcp.dcf import DCFEngine
from valugraph_mcp.server import create_mcp_server
from valugraph_mcp.types import DCFInputs, PropertyParcel, PropertyType

console = Console()


@click.group()
@click.version_option(version=valugraph_mcp.__version__, prog_name="valugraph-mcp")
def cli() -> None:
    """ValuGraph-MCP: Commercial Real Estate Underwriting & CMBS Risk Engine."""


@cli.command("info")
def info_cmd() -> None:
    """Display engine subsystems, version, and architecture info."""
    table = Table(title=f"ValuGraph-MCP Engine v{valugraph_mcp.__version__}")
    table.add_column("Subsystem", style="cyan", no_wrap=True)
    table.add_column("Status", style="green")
    table.add_column("Description", style="white")

    table.add_row(
        "Temporal CRE Graph",
        "ONLINE",
        "NetworkX knowledge graph mapping parcels, sponsors, leases, and liens",
    )
    table.add_row(
        "Multi-Scenario DCF",
        "ONLINE",
        "10-yr cash flow modeling (Base/Bull/Bear/Severe) with Newton-Raphson IRR",
    )
    table.add_row(
        "CMBS Tranche Waterfall",
        "ONLINE",
        "Securitization subordination risk and default loss allocation",
    )
    table.add_row(
        "Model Context Protocol",
        "ONLINE",
        "FastMCP/MCPServer tools for LLM agent integration",
    )

    console.print(table)


@cli.command("underwrite")
@click.option("--apn", required=True, help="Property Assessor Parcel Number")
@click.option("--price", required=True, type=float, help="Acquisition price in USD")
@click.option("--revenue", required=True, type=float, help="Year 1 Gross Revenue in USD")
@click.option("--expenses", required=True, type=float, help="Year 1 Operating Expenses in USD")
@click.option("--hold", default=10, type=int, help="Hold period in years (default: 10)")
@click.option("--ltv", default=0.65, type=float, help="Acquisition loan LTV (default: 0.65)")
@click.option("--rate", default=0.065, type=float, help="Debt interest rate (default: 0.065)")
def underwrite_cmd(
    apn: str,
    price: float,
    revenue: float,
    expenses: float,
    hold: int,
    ltv: float,
    rate: float,
) -> None:
    """Run full multi-scenario DCF underwriting on a commercial property."""
    inputs = DCFInputs(
        purchase_price=price,
        hold_period_years=hold,
        initial_revenue=revenue,
        initial_expenses=expenses,
        financing_ltv=ltv,
        financing_interest_rate=rate,
    )

    parcel = PropertyParcel(
        apn=apn,
        address=f"Asset-{apn}",
        property_type=PropertyType.OFFICE,
        gross_sqft=100000.0,
        rentable_sqft=95000.0,
        year_built=2021,
        purchase_price=price,
        current_noi=revenue - expenses,
        occupancy_rate=0.95,
    )

    engine = DCFEngine()
    report = engine.generate_underwriting_report(parcel, inputs)

    table = Table(title=f"ValuGraph DCF Underwriting: {apn}")
    table.add_column("Scenario", style="cyan")
    table.add_column("IRR", style="magenta")
    table.add_column("NPV ($)", style="green")
    table.add_column("Equity Multiple", style="yellow")
    table.add_column("Terminal Value ($)", style="white")

    for sc_name, sc in [
        ("Base", report.base_scenario),
        ("Bull", report.bull_scenario),
        ("Bear", report.bear_scenario),
        ("Severe Stress", report.severe_stress_scenario),
    ]:
        table.add_row(
            sc_name,
            f"{sc.irr * 100:.2f}%",
            f"${sc.npv:,.0f}",
            f"{sc.equity_multiple:.2f}x",
            f"${sc.exit_valuation:,.0f}",
        )

    console.print(table)
    console.print(
        f"[bold green]Recommended Max Debt:[/bold green] ${report.recommended_loan_amount:,.0f}"
    )
    console.print(
        f"[bold cyan]Average DSCR:[/bold cyan] {report.average_dscr:.2f}x (Min: {report.min_dscr:.2f}x)"
    )
    console.print(f"[italic]{report.conclusion}[/italic]")


@cli.command("stress-test")
@click.option("--balance", default=100000000.0, type=float, help="Total CMBS pool issuance")
@click.option("--shock-bps", default=150.0, type=float, help="Interest rate shock in basis points")
@click.option("--loss-severity", default=0.40, type=float, help="Severity percentage on default")
def stress_test_cmd(balance: float, shock_bps: float, loss_severity: float) -> None:
    """Stress-test benchmark CMBS conduit deal tranches and show waterfall loss allocation."""
    engine = CMBSRiskEngine()
    deal = engine.build_synthetic_deal(total_balance=balance)
    stress = engine.evaluate_pool_stress(
        loans=deal.collateral_loans,
        loss_severity=loss_severity,
        rate_shock_bps=shock_bps,
    )
    allocations = engine.allocate_waterfall_losses(
        tranches=deal.tranches,
        cumulative_pool_loss=stress["total_expected_loss"],
    )

    table = Table(title=f"CMBS Subordination Waterfall ({deal.deal_id})")
    table.add_column("Tranche", style="cyan")
    table.add_column("Attach-Detach", style="white")
    table.add_column("Initial Bal ($)", style="green")
    table.add_column("Loss Allocated ($)", style="red")
    table.add_column("Remaining Bal ($)", style="yellow")
    table.add_column("Impairment", style="magenta")

    for a in allocations:
        table.add_row(
            a["tranche_name"],
            f"{a['attachment_point'] * 100:.0f}% - {a['detachment_point'] * 100:.0f}%",
            f"${a['initial_balance']:,.0f}",
            f"${a['allocated_loss']:,.0f}",
            f"${a['remaining_balance']:,.0f}",
            f"{a['impairment_pct'] * 100:.1f}%",
        )

    console.print(table)
    console.print(
        f"[bold]Total Pool Expected Loss:[/bold] ${stress['total_expected_loss']:,.0f} ({stress['pool_loss_pct'] * 100:.2f}%)"
    )


@cli.command("serve")
def serve_cmd() -> None:
    """Start ValuGraph FastMCP server on stdio transport."""
    server = create_mcp_server()
    server.run()


if __name__ == "__main__":
    cli()
