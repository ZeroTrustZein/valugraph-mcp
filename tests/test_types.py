"""Unit tests for ValuGraph-MCP domain types, enums, data contracts, and helper functions."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from valugraph_mcp.types import (
    CashFlowYear,
    CMBSLoan,
    CMBSPoolSummary,
    CMBSSecuritization,
    CMBSSubordinationAnalysis,
    CMBSTranche,
    DCFInputs,
    GraphEdge,
    GraphNode,
    GraphQuery,
    GraphQueryResult,
    Lease,
    LeaseType,
    LoanStatus,
    OperatingStatement,
    PropertyParcel,
    PropertyType,
    RelationshipType,
    RentRoll,
    RiskLevel,
    ScenarioResult,
    ScenarioType,
    StressTestConfig,
    Tenant,
    TrancheLossAllocation,
    TrancheRating,
    UnderwritingReport,
    ValuationMetrics,
    assess_risk_level,
    calculate_break_even_occupancy,
    calculate_cap_rate,
    calculate_debt_yield,
    calculate_dscr,
    calculate_ltv,
    validate_apn,
)


class TestEnums:
    """Test domain enumerations, string inheritance, and membership."""

    def test_property_type_enum(self) -> None:
        assert PropertyType.OFFICE == "office"
        assert PropertyType.MULTIFAMILY == "multifamily"
        assert PropertyType.INDUSTRIAL == "industrial"
        assert PropertyType.RETAIL == "retail"
        assert PropertyType.HOSPITALITY == "hospitality"
        assert PropertyType.MIXED_USE == "mixed_use"
        assert PropertyType.COMMERCIAL == "commercial"
        assert PropertyType.HEALTHCARE == "healthcare"
        assert PropertyType.DATA_CENTER == "data_center"
        assert PropertyType.SELF_STORAGE == "self_storage"
        assert PropertyType.SPECIALTY == "specialty"
        assert issubclass(PropertyType, str)

    def test_scenario_type_enum(self) -> None:
        assert ScenarioType.BASE == "base"
        assert ScenarioType.BULL == "bull"
        assert ScenarioType.BEAR == "bear"
        assert ScenarioType.SEVERE_STRESS == "severe_stress"
        assert issubclass(ScenarioType, str)

    def test_lease_type_enum(self) -> None:
        assert LeaseType.NNN == "nnn"
        assert LeaseType.MODIFIED_GROSS == "modified_gross"
        assert LeaseType.FULL_SERVICE == "full_service"
        assert LeaseType.GROSS == "gross"
        assert issubclass(LeaseType, str)

    def test_loan_status_enum(self) -> None:
        assert LoanStatus.CURRENT == "current"
        assert LoanStatus.WATCHLIST == "watchlist"
        assert LoanStatus.SPECIAL_SERVICING == "special_servicing"
        assert LoanStatus.DELINQUENT_30 == "delinquent_30"
        assert LoanStatus.DELINQUENT_60 == "delinquent_60"
        assert LoanStatus.DELINQUENT_90_PLUS == "delinquent_90_plus"
        assert LoanStatus.DEFAULT == "default"
        assert LoanStatus.REO == "reo"
        assert issubclass(LoanStatus, str)

    def test_tranche_rating_enum(self) -> None:
        assert TrancheRating.AAA == "AAA"
        assert TrancheRating.AA == "AA"
        assert TrancheRating.A == "A"
        assert TrancheRating.BBB == "BBB"
        assert TrancheRating.BB == "BB"
        assert TrancheRating.B == "B"
        assert TrancheRating.EQUITY == "Equity"
        assert issubclass(TrancheRating, str)

    def test_risk_level_enum(self) -> None:
        assert RiskLevel.LOW == "low"
        assert RiskLevel.MODERATE == "moderate"
        assert RiskLevel.ELEVATED == "elevated"
        assert RiskLevel.HIGH == "high"
        assert RiskLevel.CRITICAL == "critical"
        assert issubclass(RiskLevel, str)

    def test_relationship_type_enum(self) -> None:
        assert RelationshipType.OWNS == "OWNS"
        assert RelationshipType.LEASES_FROM == "LEASES_FROM"
        assert RelationshipType.ENCUMBERS == "ENCUMBERS"
        assert RelationshipType.SERVICED_BY == "SERVICED_BY"
        assert RelationshipType.GUARANTEES == "GUARANTEES"
        assert RelationshipType.ADJACENT_TO == "ADJACENT_TO"
        assert issubclass(RelationshipType, str)


class TestHelperFunctions:
    """Test domain mathematical calculations and input sanitization helpers."""

    def test_validate_apn_valid(self) -> None:
        assert validate_apn("042-108-01") == "042-108-01"
        assert validate_apn("  APN-999-X  ") == "APN-999-X"

    def test_validate_apn_invalid_type(self) -> None:
        with pytest.raises(TypeError, match="APN must be a string"):
            validate_apn(12345)  # type: ignore[arg-type]

    def test_validate_apn_empty(self) -> None:
        with pytest.raises(ValueError, match="APN cannot be empty"):
            validate_apn("   ")

    def test_calculate_cap_rate_valid(self) -> None:
        # $600,000 NOI on $10,000,000 value = 6.0%
        cap = calculate_cap_rate(600000.0, 10000000.0)
        assert cap == 0.06

    def test_calculate_cap_rate_zero_or_negative_value(self) -> None:
        with pytest.raises(ValueError, match="Property value must be greater than zero"):
            calculate_cap_rate(500000.0, 0.0)
        with pytest.raises(ValueError, match="Property value must be greater than zero"):
            calculate_cap_rate(500000.0, -1000.0)

    def test_calculate_debt_yield_valid(self) -> None:
        # $650,000 NOI on $6,500,000 loan = 10.0%
        dy = calculate_debt_yield(650000.0, 6500000.0)
        assert dy == 0.10

    def test_calculate_debt_yield_invalid(self) -> None:
        with pytest.raises(ValueError, match="Loan amount must be greater than zero"):
            calculate_debt_yield(650000.0, 0.0)

    def test_calculate_dscr_valid(self) -> None:
        # $1,250,000 NOI / $1,000,000 debt service = 1.25x
        dscr = calculate_dscr(1250000.0, 1000000.0)
        assert dscr == 1.25

    def test_calculate_dscr_invalid(self) -> None:
        with pytest.raises(ValueError, match="Annual debt service must be greater than zero"):
            calculate_dscr(100000.0, 0.0)

    def test_calculate_ltv_valid(self) -> None:
        # $6,500,000 loan / $10,000,000 value = 65.0%
        ltv = calculate_ltv(6500000.0, 10000000.0)
        assert ltv == 0.65

    def test_calculate_ltv_invalid(self) -> None:
        with pytest.raises(ValueError, match="Property value must be greater than zero"):
            calculate_ltv(500000.0, 0.0)

    def test_calculate_break_even_occupancy_valid(self) -> None:
        # ($300k opex + $500k debt service) / $1M potential rent = 80.0%
        be = calculate_break_even_occupancy(300000.0, 500000.0, 1000000.0)
        assert be == 0.80

    def test_calculate_break_even_occupancy_invalid(self) -> None:
        with pytest.raises(ValueError, match="Gross potential rent must be greater than zero"):
            calculate_break_even_occupancy(100.0, 100.0, 0.0)

    def test_assess_risk_level_tiers(self) -> None:
        # Critical
        assert assess_risk_level(dscr=0.90, ltv=0.70, debt_yield=0.08) == RiskLevel.CRITICAL
        assert assess_risk_level(dscr=1.30, ltv=0.88, debt_yield=0.08) == RiskLevel.CRITICAL
        assert assess_risk_level(dscr=1.30, ltv=0.65, debt_yield=0.06) == RiskLevel.CRITICAL

        # High
        assert assess_risk_level(dscr=1.10, ltv=0.72, debt_yield=0.085) == RiskLevel.HIGH

        # Elevated
        assert assess_risk_level(dscr=1.20, ltv=0.68, debt_yield=0.088) == RiskLevel.ELEVATED

        # Moderate
        assert assess_risk_level(dscr=1.35, ltv=0.64, debt_yield=0.095) == RiskLevel.MODERATE

        # Low
        assert assess_risk_level(dscr=1.60, ltv=0.55, debt_yield=0.12) == RiskLevel.LOW


class TestDomainModels:
    """Test domain model instantiation, default fields, validation rules, and methods."""

    def test_property_parcel_valid(self) -> None:
        parcel = PropertyParcel(
            apn="042-108-01",
            address="500 Market St, San Francisco, CA",
            property_type=PropertyType.COMMERCIAL,
            gross_sqft=120000.0,
            rentable_sqft=110000.0,
            year_built=2015,
            purchase_price=50000000.0,
            current_noi=3250000.0,
            occupancy_rate=0.94,
        )
        assert parcel.apn == "042-108-01"
        assert parcel.property_type == PropertyType.COMMERCIAL
        assert parcel.cap_rate == 0.065

    def test_property_parcel_validation_errors(self) -> None:
        # APN empty
        with pytest.raises(ValidationError):
            PropertyParcel(
                apn="",
                address="Test",
                gross_sqft=1000.0,
                rentable_sqft=900.0,
                year_built=2000,
                purchase_price=100000.0,
                current_noi=10000.0,
            )

        # Negative gross_sqft
        with pytest.raises(ValidationError):
            PropertyParcel(
                apn="APN-1",
                address="Test",
                gross_sqft=-10.0,
                rentable_sqft=900.0,
                year_built=2000,
                purchase_price=100000.0,
                current_noi=10000.0,
            )

        # Year built out of bounds
        with pytest.raises(ValidationError):
            PropertyParcel(
                apn="APN-1",
                address="Test",
                gross_sqft=1000.0,
                rentable_sqft=900.0,
                year_built=1750,
                purchase_price=100000.0,
                current_noi=10000.0,
            )

        # Occupancy rate > 1.0
        with pytest.raises(ValidationError):
            PropertyParcel(
                apn="APN-1",
                address="Test",
                gross_sqft=1000.0,
                rentable_sqft=900.0,
                year_built=2000,
                purchase_price=100000.0,
                current_noi=10000.0,
                occupancy_rate=1.5,
            )

    def test_lease_and_rent_roll(self) -> None:
        lease1 = Lease(
            lease_id="L-1",
            tenant_id="T-1",
            property_apn="042-108-01",
            suite="100",
            lease_type=LeaseType.NNN,
            leased_sqft=10000.0,
            annual_base_rent=400000.0,
            start_date="2024-01-01",
            end_date="2034-01-01",
        )
        assert lease1.rent_per_sqft == 40.0
        assert lease1.escalation_rate == 0.03

        lease2 = Lease(
            lease_id="L-2",
            tenant_id="T-2",
            property_apn="042-108-01",
            suite="200",
            lease_type=LeaseType.FULL_SERVICE,
            leased_sqft=15000.0,
            annual_base_rent=750000.0,
            rent_per_sqft=50.0,
            start_date="2023-06-01",
            end_date="2033-05-31",
        )
        assert lease2.rent_per_sqft == 50.0

        rent_roll = RentRoll(
            property_apn="042-108-01",
            as_of_date="2026-10-31",
            leases=[lease1, lease2],
            occupancy_pct=0.92,
        )
        assert rent_roll.total_leased_sqft == 25000.0
        assert rent_roll.total_annual_rent == 1150000.0
        assert rent_roll.occupancy_pct == 0.92

    def test_operating_statement(self) -> None:
        stmt = OperatingStatement(
            property_apn="APN-001",
            period_year=2026,
            gross_potential_rent=2000000.0,
            vacancy_loss=100000.0,
            effective_gross_income=1900000.0,
            real_estate_taxes=250000.0,
            insurance=60000.0,
            utilities=90000.0,
            repairs_maintenance=70000.0,
            management_fees=80000.0,
            total_operating_expenses=550000.0,
            net_operating_income=1350000.0,
        )
        assert stmt.net_operating_income == 1350000.0
        assert stmt.period_year == 2026

    def test_valuation_metrics(self) -> None:
        metrics = ValuationMetrics(
            cap_rate=0.065,
            gross_rent_multiplier=8.5,
            debt_yield=0.105,
            loan_to_cost=0.62,
            break_even_occupancy=0.74,
        )
        assert metrics.cap_rate == 0.065
        assert metrics.break_even_occupancy == 0.74

    def test_cmbs_loan_and_status(self) -> None:
        loan = CMBSLoan(
            loan_id="LN-100",
            property_apn="042-108-01",
            original_balance=25000000.0,
            current_balance=24000000.0,
            interest_rate=0.0625,
            maturity_date="2035-10-01",
            status=LoanStatus.WATCHLIST,
        )
        assert loan.status == LoanStatus.WATCHLIST
        assert loan.is_interest_only is False
        assert loan.dscr == 1.25

    def test_cmbs_tranche_and_subordination(self) -> None:
        tranche = CMBSTranche(
            tranche_name="BBB",
            attachment_point=0.10,
            detachment_point=0.18,
            coupon_rate=0.075,
            initial_balance=8000000.0,
            current_balance=8000000.0,
        )
        assert tranche.tranche_name == "BBB"
        assert tranche.accumulated_loss == 0.0

        loss_alloc = TrancheLossAllocation(
            tranche_name="Equity",
            attachment_point=0.0,
            detachment_point=0.05,
            initial_balance=5000000.0,
            allocated_loss=5000000.0,
            remaining_balance=0.0,
            impairment_pct=1.0,
            is_exhausted=True,
        )
        assert loss_alloc.is_exhausted is True

        analysis = CMBSSubordinationAnalysis(
            deal_id="COMM-2026-FL1",
            total_loss_simulated=7500000.0,
            tranche_allocations=[loss_alloc],
            equity_wiped_out=True,
            investment_grade_impaired=False,
        )
        assert analysis.equity_wiped_out is True
        assert analysis.investment_grade_impaired is False

    def test_cmbs_pool_summary(self) -> None:
        summary = CMBSPoolSummary(
            total_balance=150000000.0,
            weighted_avg_dscr=1.42,
            weighted_avg_ltv=0.61,
            weighted_avg_coupon=0.068,
            loan_count=12,
        )
        assert summary.loan_count == 12
        assert summary.weighted_avg_dscr == 1.42

    def test_stress_test_config(self) -> None:
        config = StressTestConfig(rate_shock_bps=150.0, loss_severity=0.45)
        assert config.rate_shock_bps == 150.0
        assert config.loss_severity == 0.45
        assert config.vacancy_shock_pct == 0.0

    def test_tenant_model(self) -> None:
        tenant = Tenant(
            tenant_id="TEN-501",
            name="Google LLC",
            credit_rating="AA+",
            leased_sqft=50000.0,
            annual_rent=4500000.0,
            lease_expiry="2035-12-31",
        )
        assert tenant.tenant_id == "TEN-501"
        assert tenant.credit_rating == "AA+"
        assert tenant.leased_sqft == 50000.0

    def test_cmbs_securitization_model(self) -> None:
        loan = CMBSLoan(
            loan_id="LN-1",
            property_apn="APN-1",
            original_balance=10000000.0,
            current_balance=9500000.0,
            interest_rate=0.06,
            maturity_date="2034-01-01",
        )
        tranche = CMBSTranche(
            tranche_name="AAA",
            attachment_point=0.30,
            detachment_point=1.00,
            coupon_rate=0.055,
            initial_balance=7000000.0,
            current_balance=7000000.0,
        )
        deal = CMBSSecuritization(
            deal_id="DEAL-2026-1",
            deal_name="CRE Conduit Series 2026-1",
            total_issuance=10000000.0,
            collateral_loans=[loan],
            tranches=[tranche],
        )
        assert deal.deal_id == "DEAL-2026-1"
        assert len(deal.collateral_loans) == 1
        assert len(deal.tranches) == 1

    def test_dcf_reporting_models(self) -> None:
        cf_yr = CashFlowYear(
            year=1,
            gross_revenue=1000000.0,
            operating_expenses=300000.0,
            capex_reserve=30000.0,
            net_operating_income=670000.0,
            debt_service=400000.0,
            net_cash_flow=270000.0,
        )
        assert cf_yr.net_cash_flow == 270000.0

        scenario_res = ScenarioResult(
            scenario=ScenarioType.BASE,
            npv=1250000.0,
            irr=0.142,
            equity_multiple=1.85,
            exit_valuation=12000000.0,
            terminal_noi=750000.0,
            cumulative_cash_flow=3500000.0,
            annual_cash_flows=[cf_yr],
        )
        assert scenario_res.scenario == ScenarioType.BASE
        assert scenario_res.irr == 0.142

        report = UnderwritingReport(
            property_apn="APN-001",
            valuation_date="2026-10-31",
            purchase_price=10000000.0,
            recommended_loan_amount=6500000.0,
            base_scenario=scenario_res,
            bull_scenario=scenario_res,
            bear_scenario=scenario_res,
            severe_stress_scenario=scenario_res,
            average_dscr=1.45,
            min_dscr=1.28,
            conclusion="Asset qualifies for CMBS financing",
        )
        assert report.recommended_loan_amount == 6500000.0
        assert report.average_dscr == 1.45

    def test_graph_query_models(self) -> None:
        node = GraphNode(node_id="APN-1", node_type="property", attributes={"city": "NYC"})
        edge = GraphEdge(
            source="OWN-1",
            target="APN-1",
            relationship_type=RelationshipType.OWNS,
            attributes={"year": 2024},
        )
        assert node.node_id == "APN-1"
        assert edge.relationship_type == RelationshipType.OWNS

        query = GraphQuery(entity_id="APN-1", depth=2, relationship_types=["OWNS", "LEASES_FROM"])
        assert query.depth == 2

        result = GraphQueryResult(
            center_node_id="APN-1",
            nodes=[node],
            edges=[edge],
            node_count=1,
            edge_count=1,
        )
        assert result.node_count == 1
        assert len(result.edges) == 1

        with pytest.raises(ValidationError):
            GraphQuery(entity_id="APN-1", depth=10)  # depth > 5


class TestSerializationAndFidelity:
    """Test model serialization, JSON output, and lossless round-trip validation."""

    def test_property_parcel_json_roundtrip(self) -> None:
        original = PropertyParcel(
            apn="042-108-01",
            address="100 Wall Street",
            property_type=PropertyType.OFFICE,
            gross_sqft=250000.0,
            rentable_sqft=240000.0,
            year_built=2014,
            purchase_price=85000000.0,
            current_noi=5800000.0,
            occupancy_rate=0.92,
        )
        dumped = original.model_dump()
        assert dumped["apn"] == "042-108-01"
        assert dumped["property_type"] == "office"

        json_str = original.model_dump_json()
        raw = json.loads(json_str)
        assert raw["property_type"] == "office"

        restored = PropertyParcel.model_validate_json(json_str)
        assert restored.apn == original.apn
        assert restored.property_type == original.property_type
        assert restored.purchase_price == original.purchase_price

    def test_dcf_inputs_json_roundtrip(self) -> None:
        inputs = DCFInputs(
            purchase_price=15000000.0,
            hold_period_years=7,
            exit_cap_rate=0.0675,
            discount_rate=0.085,
            initial_revenue=1600000.0,
            initial_expenses=450000.0,
        )
        json_str = inputs.model_dump_json()
        restored = DCFInputs.model_validate_json(json_str)
        assert restored.purchase_price == 15000000.0
        assert restored.hold_period_years == 7
        assert restored.exit_cap_rate == 0.0675
