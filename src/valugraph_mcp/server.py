"""Model Context Protocol (MCP) server for ValuGraph commercial real estate underwriting."""

from __future__ import annotations

from typing import Any

from mcp.server import MCPServer

from valugraph_mcp.cmbs import CMBSRiskEngine
from valugraph_mcp.dcf import DCFEngine
from valugraph_mcp.diagnosis import DiagnosisEngine
from valugraph_mcp.graph import TemporalCREGraph
from valugraph_mcp.types import (
    CMBSLoan,
    DCFInputs,
    OperatingStatement,
    PropertyParcel,
    PropertyType,
    StressTestConfig,
    Tenant,
)


def create_mcp_server(name: str = "valugraph-mcp") -> MCPServer:
    """Instantiate and configure the ValuGraph FastMCP/MCPServer instance with tools."""
    server = MCPServer(name)

    dcf_engine = DCFEngine()
    cmbs_engine = CMBSRiskEngine()
    diagnosis_engine = DiagnosisEngine()
    graph = TemporalCREGraph()

    # Pre-seed sample benchmark property into graph for instant testing
    sample_parcel = PropertyParcel(
        apn="APN-042-108-01",
        address="100 Wall Street, New York, NY 10005",
        property_type=PropertyType.OFFICE,
        gross_sqft=250000.0,
        rentable_sqft=240000.0,
        year_built=2014,
        purchase_price=85000000.0,
        current_noi=5800000.0,
        occupancy_rate=0.92,
    )
    graph.add_parcel(sample_parcel)
    graph.add_owner("OWN-770", "Empire Horizon REIT", entity_type="Public REIT")
    graph.link_ownership("OWN-770", sample_parcel.apn, "2018-05-15", 72000000.0)
    graph.add_tenant(
        Tenant(
            tenant_id="TEN-101",
            name="Apex Quant Strategies LLC",
            credit_rating="AA",
            leased_sqft=65000.0,
            annual_rent=1950000.0,
            lease_expiry="2032-12-31",
        ),
        sample_parcel.apn,
    )

    @server.tool()
    def underwrite_commercial_property(
        apn: str,
        purchase_price: float,
        initial_revenue: float,
        initial_expenses: float,
        hold_period_years: int = 10,
        exit_cap_rate: float = 0.065,
        discount_rate: float = 0.09,
        financing_ltv: float = 0.65,
        financing_interest_rate: float = 0.065,
    ) -> dict[str, Any]:
        """Run discounted cash flow (DCF) underwriting across Base, Bull, Bear, and Severe Stress scenarios."""
        inputs = DCFInputs(
            purchase_price=purchase_price,
            hold_period_years=hold_period_years,
            exit_cap_rate=exit_cap_rate,
            discount_rate=discount_rate,
            initial_revenue=initial_revenue,
            initial_expenses=initial_expenses,
            financing_ltv=financing_ltv,
            financing_interest_rate=financing_interest_rate,
        )

        parcel = PropertyParcel(
            apn=apn,
            address="Underwritten Asset",
            property_type=PropertyType.COMMERCIAL
            if hasattr(PropertyType, "COMMERCIAL")
            else PropertyType.OFFICE,
            gross_sqft=100000.0,
            rentable_sqft=95000.0,
            year_built=2020,
            purchase_price=purchase_price,
            current_noi=initial_revenue - initial_expenses,
            occupancy_rate=0.95,
        )

        report = dcf_engine.generate_underwriting_report(parcel, inputs)
        return {
            "apn": report.property_apn,
            "purchase_price": report.purchase_price,
            "recommended_loan": report.recommended_loan_amount,
            "average_dscr": report.average_dscr,
            "min_dscr": report.min_dscr,
            "scenarios": {
                "base": {
                    "irr": report.base_scenario.irr,
                    "npv": report.base_scenario.npv,
                    "equity_multiple": report.base_scenario.equity_multiple,
                    "exit_valuation": report.base_scenario.exit_valuation,
                },
                "bull": {
                    "irr": report.bull_scenario.irr,
                    "npv": report.bull_scenario.npv,
                    "equity_multiple": report.bull_scenario.equity_multiple,
                    "exit_valuation": report.bull_scenario.exit_valuation,
                },
                "bear": {
                    "irr": report.bear_scenario.irr,
                    "npv": report.bear_scenario.npv,
                    "equity_multiple": report.bear_scenario.equity_multiple,
                    "exit_valuation": report.bear_scenario.exit_valuation,
                },
                "severe_stress": {
                    "irr": report.severe_stress_scenario.irr,
                    "npv": report.severe_stress_scenario.npv,
                    "equity_multiple": report.severe_stress_scenario.equity_multiple,
                    "exit_valuation": report.severe_stress_scenario.exit_valuation,
                },
            },
            "conclusion": report.conclusion,
        }

    @server.tool()
    def stress_test_cmbs_pool(
        deal_id: str = "VALU-2026-C1",
        total_balance: float = 100000000.0,
        rate_shock_bps: float = 150.0,
        loss_severity: float = 0.40,
    ) -> dict[str, Any]:
        """Stress-test CMBS collateral pool under interest rate shocks and allocate waterfall tranche losses."""
        deal = cmbs_engine.build_synthetic_deal(deal_id=deal_id, total_balance=total_balance)
        pool_metrics = cmbs_engine.calculate_pool_summary(deal.collateral_loans)
        stress_results = cmbs_engine.evaluate_pool_stress(
            loans=deal.collateral_loans,
            loss_severity=loss_severity,
            rate_shock_bps=rate_shock_bps,
        )
        waterfall = cmbs_engine.allocate_waterfall_losses(
            tranches=deal.tranches,
            cumulative_pool_loss=stress_results["total_expected_loss"],
        )

        return {
            "deal_id": deal_id,
            "pool_metrics": pool_metrics,
            "stress_scenario": {
                "rate_shock_bps": rate_shock_bps,
                "loss_severity": loss_severity,
                "total_expected_loss": stress_results["total_expected_loss"],
                "pool_loss_pct": stress_results["pool_loss_pct"],
            },
            "tranche_allocations": waterfall,
        }

    @server.tool()
    def query_property_graph(apn: str, depth: int = 2) -> dict[str, Any]:
        """Query knowledge graph for title lineage, active tenant leases, and mortgage encumbrances."""
        subgraph = graph.get_neighborhood_subgraph(apn, depth=depth)
        lineage = graph.get_property_lineage(apn)
        tenants = graph.get_tenants(apn)
        encumbrances = graph.get_encumbrances(apn)

        return {
            "apn": apn,
            "lineage": lineage,
            "tenants": tenants,
            "encumbrances": encumbrances,
            "graph_summary": {
                "nodes_in_neighborhood": subgraph.get("node_count", 0),
                "edges_in_neighborhood": subgraph.get("edge_count", 0),
                "total_graph_nodes": graph.node_count,
                "total_graph_edges": graph.edge_count,
            },
        }

    @server.tool()
    def estimate_debt_capacity(
        net_operating_income: float,
        property_value: float,
        min_dscr: float = 1.25,
        max_ltv: float = 0.65,
        interest_rate: float = 0.065,
        amortization_years: int = 30,
    ) -> dict[str, Any]:
        """Size maximum senior debt capacity constrained by DSCR and LTV thresholds."""
        # 1. LTV constraint
        max_debt_ltv = property_value * max_ltv

        # 2. DSCR constraint
        max_annual_ds = net_operating_income / min_dscr if min_dscr > 0 else 0.0
        # Invert debt service formula: principal = annual_ds / [r*(1+r)^n / ((1+r)^n - 1)]
        r = interest_rate
        n = amortization_years
        if r > 0 and n > 0:
            annuity_factor = (r * ((1.0 + r) ** n)) / (((1.0 + r) ** n) - 1.0)
            max_debt_dscr = max_annual_ds / annuity_factor
        else:
            max_debt_dscr = max_annual_ds * n

        binding_constraint = "DSCR" if max_debt_dscr < max_debt_ltv else "LTV"
        recommended_debt = min(max_debt_dscr, max_debt_ltv)

        return {
            "property_value": property_value,
            "net_operating_income": net_operating_income,
            "max_debt_ltv_cap": round(max_debt_ltv, 2),
            "max_debt_dscr_cap": round(max_debt_dscr, 2),
            "binding_constraint": binding_constraint,
            "recommended_max_debt": round(recommended_debt, 2),
            "effective_ltv": round(
                recommended_debt / property_value if property_value > 0 else 0, 4
            ),
            "debt_yield": round(
                net_operating_income / recommended_debt if recommended_debt > 0 else 0, 4
            ),
        }

    @server.tool()
    def diagnose_property_risk(
        apn: str,
        purchase_price: float,
        current_noi: float,
        loan_amount: float | None = None,
        interest_rate: float = 0.065,
        occupancy_rate: float = 0.95,
        gross_potential_rent: float | None = None,
        operating_expenses: float | None = None,
    ) -> dict[str, Any]:
        """Diagnose property underwriting health, financial ratios, red flags, and loan approval."""
        parcel = PropertyParcel(
            apn=apn,
            address="Diagnostic Subject Asset",
            property_type=PropertyType.COMMERCIAL
            if hasattr(PropertyType, "COMMERCIAL")
            else PropertyType.OFFICE,
            gross_sqft=100000.0,
            rentable_sqft=95000.0,
            year_built=2020,
            purchase_price=purchase_price,
            current_noi=current_noi,
            occupancy_rate=occupancy_rate,
        )

        loan = None
        if loan_amount is not None and loan_amount > 0:
            ltv = round(loan_amount / purchase_price, 4) if purchase_price > 0 else 0.0
            annual_ds = DCFEngine.calculate_annual_debt_service(loan_amount, interest_rate, 30)
            dscr = round(current_noi / annual_ds, 4) if annual_ds > 0 else 2.0
            loan = CMBSLoan(
                loan_id=f"LN-{apn}",
                property_apn=apn,
                original_balance=loan_amount,
                current_balance=loan_amount,
                interest_rate=interest_rate,
                dscr=dscr,
                ltv=ltv,
                maturity_date="2036-12-31",
            )

        statement = None
        if gross_potential_rent is not None and operating_expenses is not None:
            statement = OperatingStatement(
                property_apn=apn,
                period_year=2026,
                gross_potential_rent=gross_potential_rent,
                vacancy_loss=gross_potential_rent * (1.0 - occupancy_rate),
                effective_gross_income=gross_potential_rent * occupancy_rate,
                total_operating_expenses=operating_expenses,
                net_operating_income=current_noi,
            )

        diag = diagnosis_engine.diagnose_property(
            parcel=parcel,
            loan=loan,
            statement=statement,
        )

        return {
            "apn": diag.property_apn,
            "health_score": diag.health_score,
            "overall_risk": diag.overall_risk.value,
            "underwriting_decision": diag.underwriting_decision,
            "metrics": {
                "cap_rate": diag.metrics.cap_rate,
                "debt_yield": diag.metrics.debt_yield,
                "loan_to_cost": diag.metrics.loan_to_cost,
                "break_even_occupancy": diag.metrics.break_even_occupancy,
            },
            "findings_count": len(diag.findings),
            "findings": [f.model_dump() for f in diag.findings],
            "strengths": diag.strengths,
            "red_flags": diag.red_flags,
        }

    @server.tool()
    def diagnose_cmbs_pool(
        deal_id: str = "VALU-2026-C1",
        total_balance: float = 100000000.0,
        rate_shock_bps: float = 150.0,
        loss_severity: float = 0.40,
    ) -> dict[str, Any]:
        """Run comprehensive risk diagnosis, delinquency checks, and health scoring on a CMBS collateral pool."""
        deal = cmbs_engine.build_synthetic_deal(deal_id=deal_id, total_balance=total_balance)
        stress_cfg = StressTestConfig(
            rate_shock_bps=rate_shock_bps,
            loss_severity=loss_severity,
        )
        pool_diag = diagnosis_engine.diagnose_cmbs_pool(deal=deal, stress_config=stress_cfg)

        return {
            "deal_id": pool_diag.deal_id,
            "pool_health_score": pool_diag.pool_health_score,
            "overall_risk": pool_diag.overall_risk.value,
            "summary": {
                "total_balance": pool_diag.summary.total_balance,
                "weighted_avg_dscr": pool_diag.summary.weighted_avg_dscr,
                "weighted_avg_ltv": pool_diag.summary.weighted_avg_ltv,
                "weighted_avg_coupon": pool_diag.summary.weighted_avg_coupon,
                "loan_count": pool_diag.summary.loan_count,
            },
            "delinquency_rate": pool_diag.delinquency_rate,
            "stressed_loss_pct": pool_diag.stressed_loss_pct,
            "impaired_tranches": pool_diag.impaired_tranches,
            "findings_count": len(pool_diag.findings),
            "findings": [f.model_dump() for f in pool_diag.findings],
        }

    return server
