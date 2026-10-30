"""Command Line Interface for ValuGraph-MCP."""

from __future__ import annotations

import click
from rich.console import Console
from rich.table import Table

import valugraph_mcp
from valugraph_mcp.cmbs import CMBSRiskEngine
from valugraph_mcp.dcf import DCFEngine
from valugraph_mcp.diagnosis import DiagnosisEngine
from valugraph_mcp.server import create_mcp_server
from valugraph_mcp.types import (
    CMBSLoan,
    DCFInputs,
    OperatingStatement,
    PropertyParcel,
    PropertyType,
    StressTestConfig,
)

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
        "Diagnosis Engine",
        "ONLINE",
        "Autonomous diagnostic scoring, red flag triage, and underwriting decisioning",
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


@cli.command("diagnose")
@click.option("--apn", required=True, help="Property Assessor Parcel Number")
@click.option("--price", required=True, type=float, help="Property purchase price in USD")
@click.option("--noi", required=True, type=float, help="Current Net Operating Income in USD")
@click.option("--loan", default=None, type=float, help="Existing loan amount in USD")
@click.option("--rate", default=0.065, type=float, help="Debt interest rate (default: 0.065)")
@click.option("--occupancy", default=0.95, type=float, help="Occupancy rate (default: 0.95)")
@click.option("--gpr", default=None, type=float, help="Gross Potential Rent in USD")
@click.option("--opex", default=None, type=float, help="Operating Expenses in USD")
def diagnose_cmd(
    apn: str,
    price: float,
    noi: float,
    loan: float | None,
    rate: float,
    occupancy: float,
    gpr: float | None,
    opex: float | None,
) -> None:
    """Run comprehensive risk diagnosis and health scoring on a CRE property."""
    parcel = PropertyParcel(
        apn=apn,
        address=f"Asset-{apn}",
        property_type=PropertyType.COMMERCIAL
        if hasattr(PropertyType, "COMMERCIAL")
        else PropertyType.OFFICE,
        gross_sqft=100000.0,
        rentable_sqft=95000.0,
        year_built=2020,
        purchase_price=price,
        current_noi=noi,
        occupancy_rate=occupancy,
    )

    loan_obj = None
    if loan is not None and loan > 0:
        ltv = round(loan / price, 4) if price > 0 else 0.0
        annual_ds = DCFEngine.calculate_annual_debt_service(loan, rate, 30)
        dscr = round(noi / annual_ds, 4) if annual_ds > 0 else 2.0
        loan_obj = CMBSLoan(
            loan_id=f"LN-{apn}",
            property_apn=apn,
            original_balance=loan,
            current_balance=loan,
            interest_rate=rate,
            dscr=dscr,
            ltv=ltv,
            maturity_date="2036-12-31",
        )

    statement = None
    if gpr is not None and opex is not None:
        statement = OperatingStatement(
            property_apn=apn,
            period_year=2026,
            gross_potential_rent=gpr,
            vacancy_loss=round(gpr * (1.0 - occupancy), 2),
            effective_gross_income=round(gpr * occupancy, 2),
            total_operating_expenses=opex,
            net_operating_income=noi,
        )

    engine = DiagnosisEngine()
    diag = engine.diagnose_property(parcel=parcel, loan=loan_obj, statement=statement)

    table = Table(title=f"ValuGraph Property Diagnosis: {apn}")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="yellow")
    table.add_column("Status / Benchmark", style="white")

    table.add_row(
        "Health Score", f"{diag.health_score}/100", f"Risk: {diag.overall_risk.value.upper()}"
    )
    table.add_row("Decision", diag.underwriting_decision, "Underwriting Verdict")
    table.add_row("Cap Rate", f"{diag.metrics.cap_rate * 100:.2f}%", "NOI / Value")
    table.add_row("Debt Yield", f"{diag.metrics.debt_yield * 100:.2f}%", "Target >= 8.0%")
    table.add_row("Senior LTV", f"{diag.metrics.loan_to_cost * 100:.1f}%", "Target <= 75.0%")
    table.add_row(
        "Break-even Occupancy",
        f"{diag.metrics.break_even_occupancy * 100:.1f}%",
        f"Current: {occupancy * 100:.1f}%",
    )

    console.print(table)

    if diag.red_flags:
        console.print("[bold red]Red Flags:[/bold red]")
        for rf in diag.red_flags:
            console.print(f"  • {rf}")

    if diag.strengths:
        console.print("[bold green]Strengths:[/bold green]")
        for s in diag.strengths:
            console.print(f"  • {s}")


@cli.command("diagnose-pool")
@click.option("--balance", default=100000000.0, type=float, help="Total CMBS pool issuance")
@click.option("--shock-bps", default=150.0, type=float, help="Interest rate shock in basis points")
@click.option("--loss-severity", default=0.40, type=float, help="Severity percentage on default")
def diagnose_pool_cmd(balance: float, shock_bps: float, loss_severity: float) -> None:
    """Run comprehensive risk diagnosis and health scoring on a CMBS pool."""
    cmbs_engine = CMBSRiskEngine()
    deal = cmbs_engine.build_synthetic_deal(total_balance=balance)
    stress_cfg = StressTestConfig(rate_shock_bps=shock_bps, loss_severity=loss_severity)
    engine = DiagnosisEngine()
    pool_diag = engine.diagnose_cmbs_pool(deal=deal, stress_config=stress_cfg)

    table = Table(title=f"ValuGraph CMBS Pool Diagnosis: {pool_diag.deal_id}")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="yellow")
    table.add_column("Status / Benchmark", style="white")

    table.add_row(
        "Health Score",
        f"{pool_diag.pool_health_score}/100",
        f"Risk: {pool_diag.overall_risk.value.upper()}",
    )
    table.add_row(
        "Weighted DSCR",
        f"{pool_diag.summary.weighted_avg_dscr:.2f}x",
        "Target >= 1.25x",
    )
    table.add_row(
        "Weighted LTV",
        f"{pool_diag.summary.weighted_avg_ltv * 100:.1f}%",
        "Target <= 70.0%",
    )
    table.add_row(
        "Delinquency Rate",
        f"{pool_diag.delinquency_rate * 100:.1f}%",
        "Target <= 2.0%",
    )
    table.add_row(
        "Stressed Loss",
        f"{pool_diag.stressed_loss_pct * 100:.2f}%",
        "Expected pool loss",
    )
    table.add_row(
        "Impaired Tranches",
        ", ".join(pool_diag.impaired_tranches) if pool_diag.impaired_tranches else "None",
        "Tranches suffering principal loss",
    )

    console.print(table)

    if pool_diag.findings:
        console.print("[bold red]Diagnostic Findings:[/bold red]")
        for f in pool_diag.findings:
            console.print(f"  • [{f.severity.value.upper()}] {f.metric_name}: {f.summary}")
            console.print(f"    Action: {f.recommendation}")


@cli.command("serve")
def serve_cmd() -> None:
    """Start ValuGraph FastMCP server on stdio transport."""
    server = create_mcp_server()
    server.run()


if __name__ == "__main__":
    cli()
