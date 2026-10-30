"""Comprehensive unit and edge-case tests for the DCF engine and financial mathematics."""

from __future__ import annotations

from valugraph_mcp.dcf import (
    DCFEngine,
    calculate_irr,
    calculate_npv,
)
from valugraph_mcp.types import DCFInputs, PropertyParcel, PropertyType, ScenarioType


class TestFinancialMath:
    """Tests for core financial math formulas and numerical solvers."""

    def test_irr_empty_or_single_cf(self) -> None:
        """Verify IRR returns 0.0 when cash flows are empty or single-element."""
        assert calculate_irr([]) == 0.0
        assert calculate_irr([-100.0]) == 0.0

    def test_irr_no_sign_change(self) -> None:
        """Verify IRR returns 0.0 when all cash flows are positive or all negative."""
        assert calculate_irr([100.0, 50.0, 20.0]) == 0.0
        assert calculate_irr([-100.0, -50.0, -20.0]) == 0.0

    def test_irr_bisection_fallback_on_zero_derivative(self) -> None:
        """Verify bisection fallback is engaged when derivative vanishes or divergence occurs."""
        # Carefully crafted sequence where initial derivative triggers Newton-Raphson break or bisection
        cfs = [-1000.0, 0.0, 0.0, 0.0, 2000.0]
        irr = calculate_irr(cfs, guess=0.0)
        assert irr > 0.0
        # NPV at calculated IRR should be near 0
        npv = calculate_npv(irr, cfs)
        assert abs(npv) < 1.0

    def test_irr_severe_negative_rate_clamp(self) -> None:
        """Verify IRR handles near -100% boundary conditions."""
        cfs = [-1000.0, 1.0, 1.0]
        irr = calculate_irr(cfs, guess=-0.999)
        assert isinstance(irr, float)

    def test_npv_zero_and_negative_rates(self) -> None:
        """Verify NPV calculation with 0% discount rate and negative rates."""
        cfs = [-100.0, 50.0, 60.0]
        # At r=0, NPV is simply the sum of cash flows: -100 + 50 + 60 = 10
        assert calculate_npv(0.0, cfs) == 10.0
        assert calculate_npv(-0.1, cfs) > 10.0


class TestDCFEngineEdgeCases:
    """Tests for debt service, remaining debt, and underwriting report edge cases."""

    def test_debt_service_zero_or_negative_inputs(self) -> None:
        """Verify annual debt service handles zero/negative principal, rate, or amort."""
        assert DCFEngine.calculate_annual_debt_service(0.0, 0.065, 30) == 0.0
        assert DCFEngine.calculate_annual_debt_service(-500000.0, 0.065, 30) == 0.0
        assert DCFEngine.calculate_annual_debt_service(1000000.0, 0.065, 0) == 0.0
        assert DCFEngine.calculate_annual_debt_service(1000000.0, 0.065, -10) == 0.0

        # Zero interest rate loan (straight principal amortization)
        zero_rate_ds = DCFEngine.calculate_annual_debt_service(1200000.0, 0.0, 30)
        assert zero_rate_ds == 40000.0

    def test_remaining_debt_balance_edge_cases(self) -> None:
        """Verify remaining debt balance for zero principal, zero rate, and full maturity."""
        assert DCFEngine.calculate_remaining_debt_balance(0.0, 0.065, 30, 5) == 0.0
        assert DCFEngine.calculate_remaining_debt_balance(1000000.0, 0.065, 30, 30) == 0.0
        assert DCFEngine.calculate_remaining_debt_balance(1000000.0, 0.065, 30, 35) == 0.0

        # Zero interest rate remaining balance
        rem = DCFEngine.calculate_remaining_debt_balance(1000000.0, 0.0, 20, 5)
        assert rem == 750000.0  # 1,000,000 * (1 - 5/20)

    def test_underwriting_report_low_dscr_loan_constraint(self) -> None:
        """Verify that when min_dscr < 1.20, recommended loan amount is curtailed."""
        engine = DCFEngine()
        parcel = PropertyParcel(
            apn="APN-TIGHT-DSCR",
            address="10 Low Cover St",
            property_type=PropertyType.OFFICE,
            gross_sqft=50000.0,
            rentable_sqft=48000.0,
            year_built=2015,
            purchase_price=10000000.0,
            current_noi=550000.0,
            occupancy_rate=0.90,
        )

        # High LTV with tight NOI -> low DSCR below 1.20
        inputs = DCFInputs(
            purchase_price=10000000.0,
            hold_period_years=5,
            exit_cap_rate=0.07,
            discount_rate=0.09,
            initial_revenue=900000.0,
            initial_expenses=450000.0,  # initial NOI = 450,000
            financing_ltv=0.75,  # $7.5M debt at 7% -> DS ~ $598,771 -> DSCR < 1.0
            financing_interest_rate=0.07,
            debt_term_years=30,
        )

        report = engine.generate_underwriting_report(parcel, inputs)
        assert report.min_dscr < 1.20
        # Recommended loan should be strictly less than unconstrained purchase_price * financing_ltv ($7.5M)
        assert report.recommended_loan_amount < 10000000.0 * 0.75

    def test_multiscenario_hold_period_variations(self) -> None:
        """Verify projections across 3-year and 15-year holding periods."""
        engine = DCFEngine()
        inputs = DCFInputs(
            purchase_price=8000000.0,
            hold_period_years=3,
            exit_cap_rate=0.06,
            discount_rate=0.08,
            initial_revenue=1000000.0,
            initial_expenses=300000.0,
        )
        scenarios = engine.stress_test_multiscenario(inputs)
        assert len(scenarios) == 4
        assert len(scenarios[ScenarioType.BASE].annual_cash_flows) == 3
        assert scenarios[ScenarioType.BASE].irr > 0.0
