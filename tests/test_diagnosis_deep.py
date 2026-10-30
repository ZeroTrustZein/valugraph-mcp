"""Comprehensive diagnostic branches and scoring tests for properties and CMBS pools."""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from valugraph_mcp.cli import cli
from valugraph_mcp.diagnosis import DiagnosisEngine
from valugraph_mcp.types import (
    CMBSLoan,
    CMBSSecuritization,
    CMBSTranche,
    Lease,
    LeaseType,
    LoanStatus,
    OperatingStatement,
    PropertyParcel,
    PropertyType,
    RentRoll,
    RiskLevel,
    ScenarioResult,
    ScenarioType,
    StressTestConfig,
    UnderwritingReport,
)


class TestDiagnosisEngineDeep:
    """Tests covering all threshold tiers and edge cases across DiagnosisEngine."""

    def test_property_interest_only_loan_and_intermediate_tiers(self) -> None:
        """Verify interest-only loan, dscr 1.15-1.25, ltv 0.70-0.75, debt yield 0.085-0.095."""
        engine = DiagnosisEngine()
        parcel = PropertyParcel(
            apn="APN-MID-TIER",
            address="456 Neutral Blvd",
            property_type=PropertyType.COMMERCIAL,
            gross_sqft=100000.0,
            rentable_sqft=90000.0,
            year_built=2018,
            purchase_price=20000000.0,
            current_noi=1200000.0,  # Cap rate = 6.0%
            occupancy_rate=0.88,  # Medium occupancy warning
        )
        # Interest-only loan: loan = 14.4M (LTV = 72%), rate = 7.5% -> IO debt service = 1,080,000
        # DSCR = 1.2M / 1.08M = 1.111 (hits 1.0 <= dscr < 1.15 High tier)
        # LTV = 0.72 (hits 0.70 < ltv <= 0.75 Medium tier)
        # Debt yield = 1.2M / 14.4M = 0.0833 (hits 0.08 <= dy < 0.09 Elevated tier)
        loan = CMBSLoan(
            loan_id="LN-IO-1",
            property_apn=parcel.apn,
            original_balance=14400000.0,
            current_balance=14400000.0,
            interest_rate=0.075,
            maturity_date="2031-10-31",
            dscr=1.20,
            ltv=0.72,
            is_interest_only=True,
        )

        statement = OperatingStatement(
            statement_id="STMT-MID",
            property_apn=parcel.apn,
            period_year=2026,
            gross_potential_rent=2500000.0,
            effective_gross_income=2200000.0,
            total_operating_expenses=1100000.0,  # expense ratio = 50%
            net_operating_income=1100000.0,
        )

        diag = engine.diagnose_property(parcel=parcel, loan=loan, statement=statement)
        assert diag.health_score > 0
        categories = {f.category.value for f in diag.findings}
        assert "coverage" in categories
        assert "leverage" in categories
        assert "liquidity" in categories
        assert "operational" in categories
        assert diag.overall_risk == RiskLevel.ELEVATED

    def test_property_warning_and_high_risk_tiers(self) -> None:
        """Verify dscr 1.0-1.15, ltv 0.75-0.85, debt yield 0.07-0.08, and tenant concentration > 0.25."""
        engine = DiagnosisEngine()
        parcel = PropertyParcel(
            apn="APN-HIGH-RISK",
            address="789 Tight St",
            property_type=PropertyType.OFFICE,
            gross_sqft=100000.0,
            rentable_sqft=90000.0,
            year_built=2010,
            purchase_price=20000000.0,
            current_noi=1150000.0,
            occupancy_rate=0.82,  # High occupancy warning (0.75 <= occ < 0.85)
        )
        # Loan = 15.4M (LTV = 77% -> High risk tier 0.75 < LTV <= 0.80)
        # Debt yield = 1.15M / 15.4M = 0.0746 (High risk tier 0.07 <= dy < 0.08)
        loan = CMBSLoan(
            loan_id="LN-HIGH-1",
            property_apn=parcel.apn,
            original_balance=15400000.0,
            current_balance=15400000.0,
            interest_rate=0.07,
            maturity_date="2031-10-31",
            dscr=1.12,  # High risk tier 1.0 <= dscr < 1.15
            ltv=0.77,
            amortization_months=360,
        )

        rent_roll = RentRoll(
            property_apn=parcel.apn,
            as_of_date="2026-10-31",
            leases=[
                Lease(
                    lease_id="L-1",
                    tenant_id="T-1",
                    property_apn=parcel.apn,
                    suite="100",
                    leased_sqft=30000.0,
                    annual_base_rent=350000.0,  # 35% of total 1,000,000 -> hits 0.25 < share <= 0.40
                    start_date="2020-01-01",
                    end_date="2030-01-01",
                    lease_type=LeaseType.NNN,
                ),
                Lease(
                    lease_id="L-2",
                    tenant_id="T-2",
                    property_apn=parcel.apn,
                    suite="200",
                    leased_sqft=25000.0,
                    annual_base_rent=250000.0,
                    start_date="2020-01-01",
                    end_date="2030-01-01",
                    lease_type=LeaseType.FULL_SERVICE,
                ),
                Lease(
                    lease_id="L-3",
                    tenant_id="T-3",
                    property_apn=parcel.apn,
                    suite="300",
                    leased_sqft=35000.0,
                    annual_base_rent=400000.0,
                    start_date="2020-01-01",
                    end_date="2030-01-01",
                    lease_type=LeaseType.MODIFIED_GROSS,
                ),
            ],
        )

        diag = engine.diagnose_property(parcel=parcel, loan=loan, rent_roll=rent_roll)
        severities = {f.severity for f in diag.findings}
        assert RiskLevel.HIGH in severities
        assert RiskLevel.ELEVATED in severities
        assert diag.health_score < 75.0

    def test_cmbs_pool_diagnosis_all_loss_and_rating_tiers(self) -> None:
        """Verify pool DSCR 1.15-1.25, LTV 0.70-0.75, delinquency tiers (2-5% and 5-10%), and IG impairment."""
        engine = DiagnosisEngine()

        # 40 loans total: 2 delinquent = 5% delinquency, 1 = 2.5% delinquency
        loans = []
        for i in range(40):
            status = LoanStatus.DELINQUENT_30 if i == 0 else LoanStatus.CURRENT
            loans.append(
                CMBSLoan(
                    loan_id=f"LN-{i}",
                    property_apn=f"APN-{i}",
                    original_balance=2500000.0,
                    current_balance=2500000.0,
                    interest_rate=0.065,
                    maturity_date="2031-01-01",
                    dscr=1.20,  # WA DSCR = 1.20 (hits 1.15 <= dscr < 1.25)
                    ltv=0.72,  # WA LTV = 0.72 (hits 0.70 < ltv <= 0.75)
                    status=status,
                )
            )

        tranches = [
            CMBSTranche(
                tranche_name="AAA",
                attachment_point=0.30,
                detachment_point=1.00,
                coupon_rate=0.05,
                initial_balance=70000000.0,
                current_balance=70000000.0,
            ),
            CMBSTranche(
                tranche_name="BBB",
                attachment_point=0.10,
                detachment_point=0.30,
                coupon_rate=0.075,
                initial_balance=20000000.0,
                current_balance=20000000.0,
            ),
            CMBSTranche(
                tranche_name="Equity",
                attachment_point=0.00,
                detachment_point=0.10,
                coupon_rate=0.12,
                initial_balance=10000000.0,
                current_balance=10000000.0,
            ),
        ]
        deal = CMBSSecuritization(
            deal_id="TEST-TIERS-2026",
            deal_name="Tiers Trust",
            total_issuance=100000000.0,
            collateral_loans=loans,
            tranches=tranches,
        )

        # 1. 1 out of 40 delinquent = 2.5% delinquency (hits 0.02 < rate <= 0.05 tier)
        cfg_mild = StressTestConfig(rate_shock_bps=50.0, loss_severity=0.10)
        diag_mild = engine.diagnose_cmbs_pool(deal, cfg_mild)
        assert any(f.metric_name == "Weighted Average DSCR" for f in diag_mild.findings)
        assert any(f.metric_name == "Weighted Average LTV" for f in diag_mild.findings)
        assert any(f.metric_name == "Delinquency Rate" for f in diag_mild.findings)

        # 2. Add 2 more delinquencies -> 3 out of 40 = 7.5% (hits 0.05 < rate <= 0.10 tier)
        loans[1].status = LoanStatus.SPECIAL_SERVICING
        loans[2].status = LoanStatus.DELINQUENT_60
        diag_moderate = engine.diagnose_cmbs_pool(deal, cfg_mild)
        assert any(
            f.severity == RiskLevel.HIGH and f.metric_name == "Delinquency Rate"
            for f in diag_moderate.findings
        )

        # 3. Severe shock impairing Investment Grade (BBB/AAA)
        cfg_severe = StressTestConfig(rate_shock_bps=400.0, loss_severity=0.80)
        diag_severe = engine.diagnose_cmbs_pool(deal, cfg_severe)
        assert any("investment-grade" in f.summary.lower() for f in diag_severe.findings)
        assert diag_severe.overall_risk == RiskLevel.CRITICAL

    def test_underwriting_report_diagnosis_downside_and_negative_irr(self) -> None:
        """Verify red flags in underwriting report diagnosis for negative IRR, bear < 5%, min DSCR < 1."""
        engine = DiagnosisEngine()

        def make_dummy_scenario(
            scenario_type: ScenarioType, irr: float, equity_mult: float = 1.2
        ) -> ScenarioResult:
            return ScenarioResult(
                scenario=scenario_type,
                irr=irr,
                npv=100000.0,
                equity_multiple=equity_mult,
                exit_valuation=10000000.0,
                terminal_noi=650000.0,
                cumulative_cash_flow=2000000.0,
                annual_cash_flows=[],
            )

        report = UnderwritingReport(
            property_apn="APN-UNDERWRITE-DOWN",
            valuation_date="2026-10-31",
            purchase_price=10000000.0,
            recommended_loan_amount=6000000.0,
            base_scenario=make_dummy_scenario(ScenarioType.BASE, 0.06),  # low base IRR
            bull_scenario=make_dummy_scenario(ScenarioType.BULL, 0.10),
            bear_scenario=make_dummy_scenario(
                ScenarioType.BEAR, 0.02
            ),  # < 0.05 (triggers bear warning)
            severe_stress_scenario=make_dummy_scenario(ScenarioType.SEVERE_STRESS, -0.04),  # < 0.0
            average_dscr=1.10,
            min_dscr=0.85,  # < 1.0 (triggers min dscr warning)
            conclusion="Asset has high downside risk",
        )

        diag = engine.diagnose_underwriting_report(report)
        assert diag["is_viable"] is False
        assert diag["verdict"] == "REJECTED"
        assert len(diag["red_flags"]) >= 3
        assert any("Negative IRR" in rf for rf in diag["red_flags"])
        assert any("Sub-5% return" in rf for rf in diag["red_flags"])
        assert any("Minimum DSCR drops" in rf for rf in diag["red_flags"])

    def test_cli_diagnose_command_red_flags_rendering(self) -> None:
        """Verify CLI diagnose outputs red flags when present."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "diagnose",
                "--apn",
                "APN-RED-FLAGS",
                "--price",
                "50000000",
                "--noi",
                "500000",
                "--loan",
                "45000000",
                "--rate",
                "0.08",
            ],
        )
        assert result.exit_code == 0
        assert "Red Flags:" in result.output
        assert "Insolvent debt coverage" in result.output

    def test_cli_serve_command_mocked(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify CLI serve command constructs server and invokes run()."""
        called = {"ran": False}

        class MockServer:
            def run(self) -> None:
                called["ran"] = True

        monkeypatch.setattr("valugraph_mcp.cli.create_mcp_server", lambda: MockServer())

        runner = CliRunner()
        result = runner.invoke(cli, ["serve"])
        assert result.exit_code == 0
        assert called["ran"] is True
