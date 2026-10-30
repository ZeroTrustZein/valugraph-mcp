"""Unit and integration test suite for the Stage 3 Diagnosis Engine."""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from valugraph_mcp.cli import cli
from valugraph_mcp.dcf import DCFEngine
from valugraph_mcp.diagnosis import DiagnosisEngine
from valugraph_mcp.server import create_mcp_server
from valugraph_mcp.types import (
    CMBSLoan,
    CMBSSecuritization,
    CMBSTranche,
    DCFInputs,
    DiagnosticCategory,
    Lease,
    LeaseType,
    LoanStatus,
    OperatingStatement,
    PropertyParcel,
    PropertyType,
    RentRoll,
    RiskLevel,
    StressTestConfig,
)


@pytest.fixture
def diagnosis_engine() -> DiagnosisEngine:
    return DiagnosisEngine()


@pytest.fixture
def prime_parcel() -> PropertyParcel:
    """Class A low-risk commercial office parcel."""
    return PropertyParcel(
        apn="APN-001-PRIME",
        address="500 Park Avenue, New York, NY",
        property_type=PropertyType.OFFICE,
        gross_sqft=150000.0,
        rentable_sqft=145000.0,
        year_built=2021,
        purchase_price=50000000.0,
        current_noi=4000000.0,
        occupancy_rate=0.98,
    )


@pytest.fixture
def distressed_parcel() -> PropertyParcel:
    """Severely stressed commercial parcel with thin NOI."""
    return PropertyParcel(
        apn="APN-999-STRESS",
        address="10 Rust Belt Way, Detroit, MI",
        property_type=PropertyType.RETAIL,
        gross_sqft=80000.0,
        rentable_sqft=75000.0,
        year_built=1978,
        purchase_price=10000000.0,
        current_noi=300000.0,
        occupancy_rate=0.60,
    )


class TestPropertyDiagnosis:
    """Tests for individual asset underwriting diagnosis."""

    def test_prime_property_diagnosis(
        self, diagnosis_engine: DiagnosisEngine, prime_parcel: PropertyParcel
    ) -> None:
        """Verify prime commercial parcel achieves APPROVE decision and high health score."""
        loan = CMBSLoan(
            loan_id="LN-PRIME",
            property_apn=prime_parcel.apn,
            original_balance=25000000.0,
            current_balance=25000000.0,
            interest_rate=0.055,
            term_months=120,
            amortization_months=360,
            maturity_date="2036-01-01",
            dscr=2.35,
            ltv=0.50,
            status=LoanStatus.CURRENT,
        )

        diag = diagnosis_engine.diagnose_property(prime_parcel, loan=loan)

        assert diag.property_apn == prime_parcel.apn
        assert diag.health_score >= 85.0
        assert diag.overall_risk in (RiskLevel.LOW, RiskLevel.MODERATE)
        assert diag.underwriting_decision == "APPROVE"
        assert len(diag.red_flags) == 0
        assert len(diag.strengths) >= 2

    def test_distressed_property_diagnosis(
        self, diagnosis_engine: DiagnosisEngine, distressed_parcel: PropertyParcel
    ) -> None:
        """Verify distressed asset triggers CRITICAL flags and REJECT decision."""
        loan = CMBSLoan(
            loan_id="LN-DISTRESSED",
            property_apn=distressed_parcel.apn,
            original_balance=9000000.0,
            current_balance=8500000.0,
            interest_rate=0.08,
            term_months=60,
            amortization_months=300,
            maturity_date="2027-01-01",
            dscr=0.45,  # Insolvent debt coverage
            ltv=0.85,  # Over-leveraged
            status=LoanStatus.WATCHLIST,
        )

        diag = diagnosis_engine.diagnose_property(distressed_parcel, loan=loan)

        assert diag.property_apn == distressed_parcel.apn
        assert diag.health_score <= 40.0
        assert diag.overall_risk == RiskLevel.CRITICAL
        assert diag.underwriting_decision == "REJECT"
        assert len(diag.red_flags) >= 2

        categories = {f.category for f in diag.findings}
        assert DiagnosticCategory.COVERAGE in categories
        assert DiagnosticCategory.LEVERAGE in categories

    def test_tenant_concentration_diagnostics(
        self, diagnosis_engine: DiagnosisEngine, prime_parcel: PropertyParcel
    ) -> None:
        """Verify high single-tenant concentration triggers finding and score deduction."""
        rent_roll = RentRoll(
            property_apn=prime_parcel.apn,
            as_of_date="2026-10-01",
            leases=[
                Lease(
                    lease_id="L-1",
                    tenant_id="TENANT-WHALE",
                    property_apn=prime_parcel.apn,
                    leased_sqft=100000.0,
                    annual_base_rent=3000000.0,
                    start_date="2020-01-01",
                    end_date="2030-01-01",
                    lease_type=LeaseType.NNN,
                ),
                Lease(
                    lease_id="L-2",
                    tenant_id="TENANT-SMALL",
                    property_apn=prime_parcel.apn,
                    leased_sqft=45000.0,
                    annual_base_rent=1000000.0,
                    start_date="2022-01-01",
                    end_date="2027-01-01",
                    lease_type=LeaseType.NNN,
                ),
            ],
        )

        diag = diagnosis_engine.diagnose_property(prime_parcel, rent_roll=rent_roll)

        conc_findings = [
            f for f in diag.findings if f.category == DiagnosticCategory.TENANT_CONCENTRATION
        ]
        assert len(conc_findings) == 1
        assert conc_findings[0].severity == RiskLevel.HIGH
        assert conc_findings[0].metric_value == 0.75  # 3M / 4M = 75%

    def test_operating_statement_diagnostics(
        self, diagnosis_engine: DiagnosisEngine, prime_parcel: PropertyParcel
    ) -> None:
        """Verify elevated OpEx ratio triggers diagnostic operational finding."""
        statement = OperatingStatement(
            property_apn=prime_parcel.apn,
            period_year=2025,
            gross_potential_rent=8000000.0,
            vacancy_loss=200000.0,
            effective_gross_income=7800000.0,
            total_operating_expenses=4800000.0,  # 61.5% OpEx ratio
            net_operating_income=3000000.0,
        )

        diag = diagnosis_engine.diagnose_property(prime_parcel, statement=statement)
        opex_findings = [
            f
            for f in diag.findings
            if f.category == DiagnosticCategory.OPERATIONAL and f.metric_name == "OpEx Ratio"
        ]
        assert len(opex_findings) == 1
        assert opex_findings[0].metric_value > 0.55


class TestCMBSPoolDiagnosis:
    """Tests for securitized loan pool diagnosis."""

    @pytest.fixture
    def sample_securitization(self) -> CMBSSecuritization:
        loans = [
            CMBSLoan(
                loan_id="LN-1",
                property_apn="APN-1",
                original_balance=25000000.0,
                current_balance=24000000.0,
                interest_rate=0.060,
                dscr=1.45,
                ltv=0.60,
                maturity_date="2031-01-01",
                status=LoanStatus.CURRENT,
            ),
            CMBSLoan(
                loan_id="LN-2",
                property_apn="APN-2",
                original_balance=25000000.0,
                current_balance=24000000.0,
                interest_rate=0.065,
                dscr=1.30,
                ltv=0.65,
                maturity_date="2031-01-01",
                status=LoanStatus.CURRENT,
            ),
            CMBSLoan(
                loan_id="LN-3",
                property_apn="APN-3",
                original_balance=25000000.0,
                current_balance=24000000.0,
                interest_rate=0.070,
                dscr=1.12,
                ltv=0.74,
                maturity_date="2028-06-01",
                status=LoanStatus.WATCHLIST,
            ),
            CMBSLoan(
                loan_id="LN-4",
                property_apn="APN-4",
                original_balance=25000000.0,
                current_balance=24000000.0,
                interest_rate=0.075,
                dscr=0.85,
                ltv=0.82,
                maturity_date="2027-01-01",
                status=LoanStatus.SPECIAL_SERVICING,
            ),
        ]
        tranches = [
            CMBSTranche(
                tranche_name="AAA",
                attachment_point=0.30,
                detachment_point=1.00,
                coupon_rate=0.050,
                initial_balance=67200000.0,
                current_balance=67200000.0,
            ),
            CMBSTranche(
                tranche_name="BBB",
                attachment_point=0.15,
                detachment_point=0.30,
                coupon_rate=0.065,
                initial_balance=14400000.0,
                current_balance=14400000.0,
            ),
            CMBSTranche(
                tranche_name="Equity",
                attachment_point=0.00,
                detachment_point=0.15,
                coupon_rate=0.110,
                initial_balance=14400000.0,
                current_balance=14400000.0,
            ),
        ]
        return CMBSSecuritization(
            deal_id="COMM-2026-TEST",
            deal_name="Commercial Mortgage Trust 2026-TEST",
            total_issuance=96000000.0,
            collateral_loans=loans,
            tranches=tranches,
        )

    def test_cmbs_pool_diagnosis_healthy_and_stress(
        self, diagnosis_engine: DiagnosisEngine, sample_securitization: CMBSSecuritization
    ) -> None:
        """Verify CMBS pool diagnosis computes delinquency, tranche impairment, and health score."""
        stress_cfg = StressTestConfig(rate_shock_bps=200.0, loss_severity=0.50)
        pool_diag = diagnosis_engine.diagnose_cmbs_pool(sample_securitization, stress_cfg)

        assert pool_diag.deal_id == "COMM-2026-TEST"
        assert pool_diag.summary.loan_count == 4
        assert pool_diag.delinquency_rate == 0.50  # 2 out of 4 loans in watchlist/special_servicing
        assert len(pool_diag.impaired_tranches) >= 1
        assert "Equity" in pool_diag.impaired_tranches
        assert pool_diag.overall_risk in (RiskLevel.HIGH, RiskLevel.CRITICAL)


class TestUnderwritingReportDiagnosis:
    """Tests for DCF underwriting report diagnosis."""

    def test_diagnose_underwriting_report(
        self,
        diagnosis_engine: DiagnosisEngine,
        prime_parcel: PropertyParcel,
    ) -> None:
        """Verify DCF report diagnosis flags downside risks and validates viability."""
        inputs = DCFInputs(
            purchase_price=50000000.0,
            initial_revenue=6000000.0,
            initial_expenses=2000000.0,
            hold_period_years=10,
        )
        dcf_engine = DCFEngine()
        report = dcf_engine.generate_underwriting_report(prime_parcel, inputs)

        diag = diagnosis_engine.diagnose_underwriting_report(report)

        assert diag["property_apn"] == prime_parcel.apn
        assert diag["is_viable"] is True
        assert diag["verdict"] in ("RECOMMENDED", "CAUTION")
        assert len(diag["strengths"]) >= 1


class TestDiagnosisIntegration:
    """Tests for CLI diagnose subcommand and MCP server tool."""

    def test_cli_diagnose_command(self) -> None:
        """Verify CLI diagnose command executes and outputs formatted table."""
        runner = CliRunner()
        result = runner.invoke(
            cli,
            [
                "diagnose",
                "--apn",
                "APN-CLI-TEST",
                "--price",
                "20000000",
                "--noi",
                "1500000",
                "--loan",
                "12000000",
                "--rate",
                "0.06",
            ],
        )
        assert result.exit_code == 0
        assert "ValuGraph Property Diagnosis: APN-CLI-TEST" in result.output
        assert "Health Score" in result.output
        assert "Decision" in result.output
        assert "Debt Yield" in result.output

    @pytest.mark.asyncio
    async def test_mcp_server_diagnose_tool(self) -> None:
        """Verify MCP server tool 'diagnose_property_risk' evaluates property correctly."""
        server = create_mcp_server("test-server")
        tools = await server.list_tools()
        assert "diagnose_property_risk" in [t.name for t in tools]

        res = await server.call_tool(
            "diagnose_property_risk",
            {
                "apn": "APN-MCP-TEST",
                "purchase_price": 30000000.0,
                "current_noi": 2400000.0,
                "loan_amount": 18000000.0,
            },
        )
        assert res is not None
        assert not res.is_error
        assert len(res.content) > 0
