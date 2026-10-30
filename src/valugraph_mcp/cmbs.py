"""CMBS risk, credit analytics, and waterfall tranche loss engine."""

from __future__ import annotations

import math
from typing import Any

from valugraph_mcp.types import (
    CMBSLoan,
    CMBSSecuritization,
    CMBSTranche,
)


class CMBSRiskEngine:
    """Quantitative risk engine for CMBS loan pools and securitization tranches."""

    def __init__(self) -> None:
        pass

    @staticmethod
    def calculate_pool_summary(loans: list[CMBSLoan]) -> dict[str, float]:
        """Compute pool-level weighted credit metrics."""
        if not loans:
            return {
                "total_balance": 0.0,
                "weighted_avg_dscr": 0.0,
                "weighted_avg_ltv": 0.0,
                "weighted_avg_coupon": 0.0,
                "loan_count": 0,
            }

        total_balance = sum(l.current_balance for l in loans)
        if total_balance <= 0:
            return {
                "total_balance": 0.0,
                "weighted_avg_dscr": 0.0,
                "weighted_avg_ltv": 0.0,
                "weighted_avg_coupon": 0.0,
                "loan_count": len(loans),
            }

        wa_dscr = sum(l.dscr * l.current_balance for l in loans) / total_balance
        wa_ltv = sum(l.ltv * l.current_balance for l in loans) / total_balance
        wa_coupon = sum(l.interest_rate * l.current_balance for l in loans) / total_balance

        return {
            "total_balance": round(total_balance, 2),
            "weighted_avg_dscr": round(wa_dscr, 3),
            "weighted_avg_ltv": round(wa_ltv, 3),
            "weighted_avg_coupon": round(wa_coupon, 4),
            "loan_count": len(loans),
        }

    @staticmethod
    def estimate_loan_default_prob(dscr: float, ltv: float) -> float:
        """Estimate empirical conditional default probability given DSCR and LTV."""
        # Logistic hazard model based on commercial real estate historical loss distributions
        z = 2.5 * (ltv - 0.70) - 3.2 * (dscr - 1.20)
        prob = 1.0 / (1.0 + math.exp(-z))
        return min(0.99, max(0.005, prob))

    def evaluate_pool_stress(
        self,
        loans: list[CMBSLoan],
        loss_severity: float = 0.40,
        rate_shock_bps: float = 0.0,
    ) -> dict[str, Any]:
        """Stress-test pool under rate shocks and evaluate cumulative pool expected loss."""
        total_balance = sum(l.current_balance for l in loans)
        total_expected_loss = 0.0
        loan_details = []

        rate_shock_decimal = rate_shock_bps / 10000.0

        for loan in loans:
            shocked_rate = loan.interest_rate + rate_shock_decimal
            # Shocked DSCR drops if interest rate rises
            dscr_ratio = loan.interest_rate / shocked_rate if shocked_rate > 0 else 1.0
            shocked_dscr = max(0.2, loan.dscr * dscr_ratio)

            pd = self.estimate_loan_default_prob(shocked_dscr, loan.ltv)
            expected_loss = loan.current_balance * pd * loss_severity
            total_expected_loss += expected_loss

            loan_details.append(
                {
                    "loan_id": loan.loan_id,
                    "apn": loan.property_apn,
                    "balance": loan.current_balance,
                    "original_dscr": loan.dscr,
                    "shocked_dscr": round(shocked_dscr, 3),
                    "default_prob": round(pd, 4),
                    "expected_loss": round(expected_loss, 2),
                }
            )

        pool_loss_pct = total_expected_loss / total_balance if total_balance > 0 else 0.0

        return {
            "total_balance": round(total_balance, 2),
            "total_expected_loss": round(total_expected_loss, 2),
            "pool_loss_pct": round(pool_loss_pct, 4),
            "loss_severity_assumed": loss_severity,
            "rate_shock_bps": rate_shock_bps,
            "loans": loan_details,
        }

    @staticmethod
    def allocate_waterfall_losses(
        tranches: list[CMBSTranche],
        cumulative_pool_loss: float,
    ) -> list[dict[str, Any]]:
        """Distribute dollar losses through CMBS capital structure subordination waterfall."""
        # Order by attachment point ascending (Equity / lowest credit rank first)
        sorted_tranches = sorted(tranches, key=lambda t: t.attachment_point)
        results = []
        unallocated_loss = max(0.0, cumulative_pool_loss)

        for tranche in sorted_tranches:
            tranche_cap = tranche.initial_balance
            allocated = min(unallocated_loss, tranche_cap)
            remaining_bal = max(0.0, tranche_cap - allocated)
            impairment_pct = allocated / tranche_cap if tranche_cap > 0 else 0.0
            unallocated_loss -= allocated

            results.append(
                {
                    "tranche_name": tranche.tranche_name,
                    "attachment_point": tranche.attachment_point,
                    "detachment_point": tranche.detachment_point,
                    "initial_balance": tranche.initial_balance,
                    "allocated_loss": round(allocated, 2),
                    "remaining_balance": round(remaining_bal, 2),
                    "impairment_pct": round(impairment_pct, 4),
                    "is_exhausted": remaining_bal <= 0.01,
                }
            )

        return results

    def build_synthetic_deal(
        self,
        deal_id: str = "VALU-2026-C1",
        deal_name: str = "ValuGraph CRE Conduit 2026-C1",
        total_balance: float = 100000000.0,
    ) -> CMBSSecuritization:
        """Construct standard benchmark CMBS conduit deal structure with typical tranches."""
        tranches = [
            CMBSTranche(
                tranche_name="Equity",
                attachment_point=0.00,
                detachment_point=0.05,
                coupon_rate=0.14,
                initial_balance=total_balance * 0.05,
                current_balance=total_balance * 0.05,
            ),
            CMBSTranche(
                tranche_name="B",
                attachment_point=0.05,
                detachment_point=0.10,
                coupon_rate=0.095,
                initial_balance=total_balance * 0.05,
                current_balance=total_balance * 0.05,
            ),
            CMBSTranche(
                tranche_name="BBB",
                attachment_point=0.10,
                detachment_point=0.18,
                coupon_rate=0.075,
                initial_balance=total_balance * 0.08,
                current_balance=total_balance * 0.08,
            ),
            CMBSTranche(
                tranche_name="A",
                attachment_point=0.18,
                detachment_point=0.28,
                coupon_rate=0.065,
                initial_balance=total_balance * 0.10,
                current_balance=total_balance * 0.10,
            ),
            CMBSTranche(
                tranche_name="AAA",
                attachment_point=0.28,
                detachment_point=1.00,
                coupon_rate=0.055,
                initial_balance=total_balance * 0.72,
                current_balance=total_balance * 0.72,
            ),
        ]

        # Standard 4-loan portfolio
        loans = [
            CMBSLoan(
                loan_id="LN-001",
                property_apn="APN-OFFICE-401",
                original_balance=total_balance * 0.35,
                current_balance=total_balance * 0.35,
                interest_rate=0.062,
                term_months=120,
                amortization_months=360,
                maturity_date="2036-10-31",
                dscr=1.35,
                ltv=0.62,
            ),
            CMBSLoan(
                loan_id="LN-002",
                property_apn="APN-MF-202",
                original_balance=total_balance * 0.30,
                current_balance=total_balance * 0.30,
                interest_rate=0.058,
                term_months=120,
                amortization_months=360,
                maturity_date="2036-08-31",
                dscr=1.45,
                ltv=0.58,
            ),
            CMBSLoan(
                loan_id="LN-003",
                property_apn="APN-IND-103",
                original_balance=total_balance * 0.20,
                current_balance=total_balance * 0.20,
                interest_rate=0.060,
                term_months=120,
                amortization_months=360,
                maturity_date="2036-05-31",
                dscr=1.40,
                ltv=0.60,
            ),
            CMBSLoan(
                loan_id="LN-004",
                property_apn="APN-RET-804",
                original_balance=total_balance * 0.15,
                current_balance=total_balance * 0.15,
                interest_rate=0.068,
                term_months=120,
                amortization_months=360,
                maturity_date="2036-01-31",
                dscr=1.18,
                ltv=0.72,
            ),
        ]

        return CMBSSecuritization(
            deal_id=deal_id,
            deal_name=deal_name,
            total_issuance=total_balance,
            collateral_loans=loans,
            tranches=tranches,
        )
