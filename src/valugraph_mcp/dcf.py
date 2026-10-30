"""Discounted Cash Flow (DCF) and quantitative underwriting engine."""

from __future__ import annotations

from valugraph_mcp.types import (
    CashFlowYear,
    DCFInputs,
    PropertyParcel,
    ScenarioResult,
    ScenarioType,
    UnderwritingReport,
)


def calculate_npv(rate: float, cash_flows: list[float]) -> float:
    """Calculate Net Present Value given discount rate and periodic cash flows."""
    total = 0.0
    for t, cf in enumerate(cash_flows):
        total += cf / ((1.0 + rate) ** t)
    return total


def calculate_irr(
    cash_flows: list[float],
    guess: float = 0.10,
    max_iter: int = 1000,
    tol: float = 1e-7,
) -> float:
    """Calculate Internal Rate of Return (IRR) using Newton-Raphson with bisection fallback."""
    if not cash_flows or len(cash_flows) < 2:
        return 0.0

    # Quick check for sign change
    has_pos = any(cf > 0 for cf in cash_flows)
    has_neg = any(cf < 0 for cf in cash_flows)
    if not (has_pos and has_neg):
        return 0.0

    # 1. Newton-Raphson
    r = guess
    for _ in range(max_iter):
        if r <= -0.99:
            r = -0.95

        npv = 0.0
        d_npv = 0.0
        for t, cf in enumerate(cash_flows):
            denom = (1.0 + r) ** t
            npv += cf / denom
            if t > 0:
                d_npv -= (t * cf) / ((1.0 + r) ** (t + 1))

        if abs(npv) < tol:
            return round(r, 6)

        if abs(d_npv) < 1e-12:
            break

        delta = npv / d_npv
        r_new = r - delta

        if abs(r_new - r) < tol:
            return round(r_new, 6)
        r = r_new

    # 2. Bisection fallback across [-0.90, 5.0]
    low, high = -0.90, 5.0
    f_low = calculate_npv(low, cash_flows)
    f_high = calculate_npv(high, cash_flows)

    if f_low * f_high > 0:
        # Search wider or return guess
        return round(guess, 6)

    for _ in range(max_iter):
        mid = (low + high) / 2.0
        f_mid = calculate_npv(mid, cash_flows)
        if abs(f_mid) < tol or (high - low) / 2.0 < tol:
            return round(mid, 6)
        if f_low * f_mid < 0:
            high = mid
            f_high = f_mid
        else:
            low = mid
            f_low = f_mid

    return round((low + high) / 2.0, 6)


class DCFEngine:
    """Multi-scenario discounted cash flow underwriter and financial modeler."""

    def __init__(self, default_discount_rate: float = 0.09) -> None:
        self.default_discount_rate = default_discount_rate

    @staticmethod
    def calculate_annual_debt_service(
        principal: float,
        interest_rate: float,
        amortization_years: int,
    ) -> float:
        """Calculate constant annual debt service payment."""
        if principal <= 0 or amortization_years <= 0:
            return 0.0
        if interest_rate <= 0:
            return principal / amortization_years

        r = interest_rate
        n = amortization_years
        return principal * (r * ((1.0 + r) ** n)) / (((1.0 + r) ** n) - 1.0)

    @staticmethod
    def calculate_remaining_debt_balance(
        principal: float,
        interest_rate: float,
        amortization_years: int,
        elapsed_years: int,
    ) -> float:
        """Compute unamortized loan balance at year t."""
        if principal <= 0:
            return 0.0
        if elapsed_years >= amortization_years:
            return 0.0
        if interest_rate <= 0:
            return principal * (1.0 - elapsed_years / amortization_years)

        r = interest_rate
        n = amortization_years
        t = elapsed_years
        factor_n = (1.0 + r) ** n
        factor_t = (1.0 + r) ** t
        balance = principal * (factor_n - factor_t) / (factor_n - 1.0)
        return max(0.0, balance)

    def run_projection(
        self,
        inputs: DCFInputs,
        scenario: ScenarioType = ScenarioType.BASE,
        growth_multiplier: float = 1.0,
        expense_multiplier: float = 1.0,
        cap_rate_adjustment: float = 0.0,
    ) -> ScenarioResult:
        """Run single DCF scenario cash-flow projection and return investor metrics."""
        debt_principal = inputs.purchase_price * inputs.financing_ltv
        equity_invested = inputs.purchase_price - debt_principal
        annual_debt_service = self.calculate_annual_debt_service(
            principal=debt_principal,
            interest_rate=inputs.financing_interest_rate,
            amortization_years=inputs.debt_term_years,
        )

        annual_cash_flows: list[CashFlowYear] = []
        equity_cf_stream = [-equity_invested]

        effective_rev_growth = inputs.revenue_growth_rate * growth_multiplier
        effective_exp_growth = inputs.expense_growth_rate * expense_multiplier

        last_noi = 0.0

        for year in range(1, inputs.hold_period_years + 1):
            rev = inputs.initial_revenue * ((1.0 + effective_rev_growth) ** (year - 1))
            exp = inputs.initial_expenses * ((1.0 + effective_exp_growth) ** (year - 1))
            capex = rev * inputs.capex_reserve_pct
            noi = rev - exp - capex
            last_noi = noi

            net_cf = noi - annual_debt_service
            annual_cash_flows.append(
                CashFlowYear(
                    year=year,
                    gross_revenue=round(rev, 2),
                    operating_expenses=round(exp, 2),
                    capex_reserve=round(capex, 2),
                    net_operating_income=round(noi, 2),
                    debt_service=round(annual_debt_service, 2),
                    net_cash_flow=round(net_cf, 2),
                )
            )

            if year < inputs.hold_period_years:
                equity_cf_stream.append(net_cf)

        # Terminal valuation at exit
        terminal_cap = max(0.02, inputs.exit_cap_rate + cap_rate_adjustment)
        forward_noi = last_noi * (1.0 + effective_rev_growth)
        exit_valuation = forward_noi / terminal_cap

        remaining_debt = self.calculate_remaining_debt_balance(
            principal=debt_principal,
            interest_rate=inputs.financing_interest_rate,
            amortization_years=inputs.debt_term_years,
            elapsed_years=inputs.hold_period_years,
        )
        net_terminal_equity = exit_valuation - remaining_debt
        final_year_equity_cf = (
            annual_cash_flows[-1].net_cash_flow + net_terminal_equity
            if annual_cash_flows
            else net_terminal_equity
        )
        equity_cf_stream.append(final_year_equity_cf)

        # Metrics
        npv = calculate_npv(inputs.discount_rate, equity_cf_stream)
        irr = calculate_irr(equity_cf_stream)
        positives = sum(cf for cf in equity_cf_stream if cf > 0)
        equity_multiple = positives / equity_invested if equity_invested > 0 else 0.0
        cumulative_cf = sum(equity_cf_stream)

        return ScenarioResult(
            scenario=scenario,
            npv=round(npv, 2),
            irr=round(irr, 4),
            equity_multiple=round(equity_multiple, 3),
            exit_valuation=round(exit_valuation, 2),
            terminal_noi=round(last_noi, 2),
            cumulative_cash_flow=round(cumulative_cf, 2),
            annual_cash_flows=annual_cash_flows,
        )

    def stress_test_multiscenario(self, inputs: DCFInputs) -> dict[ScenarioType, ScenarioResult]:
        """Generate full suite of underwriting scenarios (Base, Bull, Bear, Severe Stress)."""
        scenarios = {
            ScenarioType.BASE: self.run_projection(
                inputs=inputs,
                scenario=ScenarioType.BASE,
                growth_multiplier=1.0,
                expense_multiplier=1.0,
                cap_rate_adjustment=0.0,
            ),
            ScenarioType.BULL: self.run_projection(
                inputs=inputs,
                scenario=ScenarioType.BULL,
                growth_multiplier=1.25,
                expense_multiplier=0.90,
                cap_rate_adjustment=-0.005,
            ),
            ScenarioType.BEAR: self.run_projection(
                inputs=inputs,
                scenario=ScenarioType.BEAR,
                growth_multiplier=0.50,
                expense_multiplier=1.25,
                cap_rate_adjustment=0.0075,
            ),
            ScenarioType.SEVERE_STRESS: self.run_projection(
                inputs=inputs,
                scenario=ScenarioType.SEVERE_STRESS,
                growth_multiplier=0.10,
                expense_multiplier=1.45,
                cap_rate_adjustment=0.015,
            ),
        }
        return scenarios

    def generate_underwriting_report(
        self,
        property_parcel: PropertyParcel,
        inputs: DCFInputs,
    ) -> UnderwritingReport:
        """Synthesize comprehensive underwriting memo and risk metrics."""
        scenarios = self.stress_test_multiscenario(inputs)
        base = scenarios[ScenarioType.BASE]
        bull = scenarios[ScenarioType.BULL]
        bear = scenarios[ScenarioType.BEAR]
        severe = scenarios[ScenarioType.SEVERE_STRESS]

        dscrs: list[float] = []
        for cf in base.annual_cash_flows:
            if cf.debt_service > 0:
                dscrs.append(cf.net_operating_income / cf.debt_service)

        avg_dscr = sum(dscrs) / len(dscrs) if dscrs else 0.0
        min_dscr = min(dscrs) if dscrs else 0.0

        recommended_loan = inputs.purchase_price * inputs.financing_ltv
        if min_dscr < 1.20 and avg_dscr > 0:
            # Constrain by debt coverage
            recommended_loan *= min_dscr / 1.25

        conclusion = (
            f"Asset {property_parcel.apn} qualifies with Base IRR {base.irr * 100:.1f}%, "
            f"min DSCR {min_dscr:.2f}x, and equity multiple {base.equity_multiple:.2f}x. "
            f"Under severe stress, IRR settles at {severe.irr * 100:.1f}%."
        )

        return UnderwritingReport(
            property_apn=property_parcel.apn,
            valuation_date="2026-10-31",
            purchase_price=inputs.purchase_price,
            recommended_loan_amount=round(recommended_loan, 2),
            base_scenario=base,
            bull_scenario=bull,
            bear_scenario=bear,
            severe_stress_scenario=severe,
            average_dscr=round(avg_dscr, 2),
            min_dscr=round(min_dscr, 2),
            conclusion=conclusion,
        )
