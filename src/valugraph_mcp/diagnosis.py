"""Autonomous Diagnosis Engine for commercial real estate underwriting and CMBS risk."""

from __future__ import annotations

from typing import Any

from valugraph_mcp.cmbs import CMBSRiskEngine
from valugraph_mcp.dcf import DCFEngine
from valugraph_mcp.types import (
    CMBSLoan,
    CMBSPoolSummary,
    CMBSSecuritization,
    DiagnosticCategory,
    DiagnosticFinding,
    LoanStatus,
    OperatingStatement,
    PoolDiagnosis,
    PropertyDiagnosis,
    PropertyParcel,
    RentRoll,
    RiskLevel,
    StressTestConfig,
    UnderwritingReport,
    ValuationMetrics,
    calculate_break_even_occupancy,
    calculate_debt_yield,
    calculate_dscr,
)


class DiagnosisEngine:
    """Quantitative diagnosis engine assessing CRE asset viability, debt safety, and CMBS risk."""

    def __init__(self) -> None:
        self.cmbs_engine = CMBSRiskEngine()

    def diagnose_property(
        self,
        parcel: PropertyParcel,
        loan: CMBSLoan | None = None,
        rent_roll: RentRoll | None = None,
        statement: OperatingStatement | None = None,
    ) -> PropertyDiagnosis:
        """Run deep diagnostic health check on commercial property parcel."""
        cap_rate = parcel.cap_rate

        if loan is not None:
            ltv = loan.ltv
            dscr = loan.dscr
            loan_balance = loan.current_balance
            if loan.is_interest_only:
                annual_debt_service = loan_balance * loan.interest_rate
            else:
                amort_years = max(1, loan.amortization_months // 12)
                annual_debt_service = DCFEngine.calculate_annual_debt_service(
                    loan_balance, loan.interest_rate, amort_years
                )
        else:
            ltv = 0.65
            loan_balance = parcel.purchase_price * 0.65
            annual_debt_service = DCFEngine.calculate_annual_debt_service(loan_balance, 0.065, 30)
            dscr = (
                calculate_dscr(parcel.current_noi, annual_debt_service)
                if annual_debt_service > 0
                else 2.0
            )

        debt_yield = calculate_debt_yield(parcel.current_noi, loan_balance)

        if statement is not None:
            total_opex = statement.total_operating_expenses
            gpr = statement.gross_potential_rent
        else:
            total_opex = max(1.0, parcel.purchase_price * 0.03)
            gpr = max(total_opex + annual_debt_service + 1.0, parcel.current_noi + total_opex)

        break_even_occ = calculate_break_even_occupancy(total_opex, annual_debt_service, gpr)
        grm = round(parcel.purchase_price / gpr, 2) if gpr > 0 else 0.0

        metrics = ValuationMetrics(
            cap_rate=cap_rate,
            gross_rent_multiplier=grm,
            debt_yield=debt_yield,
            loan_to_cost=ltv,
            break_even_occupancy=break_even_occ,
        )

        findings: list[DiagnosticFinding] = []
        strengths: list[str] = []
        red_flags: list[str] = []
        deductions = 0.0

        # 1. Debt Service Coverage Ratio (DSCR)
        if dscr < 1.0:
            findings.append(
                DiagnosticFinding(
                    category=DiagnosticCategory.COVERAGE,
                    severity=RiskLevel.CRITICAL,
                    metric_name="DSCR",
                    metric_value=dscr,
                    threshold=1.0,
                    summary="Negative cash flow coverage; unable to service senior debt",
                    recommendation="Mandate equity paydown or cash sweep to avoid imminent default",
                )
            )
            red_flags.append(f"Insolvent debt coverage ({dscr:.2f}x < 1.00x)")
            deductions += 35.0
        elif dscr < 1.15:
            findings.append(
                DiagnosticFinding(
                    category=DiagnosticCategory.COVERAGE,
                    severity=RiskLevel.HIGH,
                    metric_name="DSCR",
                    metric_value=dscr,
                    threshold=1.15,
                    summary="Tight debt coverage; highly vulnerable to minor NOI shocks",
                    recommendation="Require 6-month upfront debt service reserve escrow",
                )
            )
            red_flags.append(f"Tight debt coverage cushion ({dscr:.2f}x < 1.15x)")
            deductions += 25.0
        elif dscr < 1.25:
            findings.append(
                DiagnosticFinding(
                    category=DiagnosticCategory.COVERAGE,
                    severity=RiskLevel.ELEVATED,
                    metric_name="DSCR",
                    metric_value=dscr,
                    threshold=1.25,
                    summary="DSCR below standard institutional 1.25x underwriting benchmark",
                    recommendation="Monitor quarterly operating statements and lease rollover",
                )
            )
            deductions += 15.0
        elif dscr >= 1.40:
            strengths.append(f"Strong debt service coverage cushion ({dscr:.2f}x)")

        # 2. Loan to Value (LTV)
        if ltv > 0.80:
            findings.append(
                DiagnosticFinding(
                    category=DiagnosticCategory.LEVERAGE,
                    severity=RiskLevel.CRITICAL,
                    metric_name="LTV",
                    metric_value=ltv,
                    threshold=0.80,
                    summary="Over-leveraged capital structure; high default risk under cap rate expansion",
                    recommendation="Require sponsor cash equity infusion to reduce LTV below 75%",
                )
            )
            red_flags.append(f"Excessive senior leverage ({ltv * 100:.1f}% > 80%)")
            deductions += 30.0
        elif ltv > 0.75:
            findings.append(
                DiagnosticFinding(
                    category=DiagnosticCategory.LEVERAGE,
                    severity=RiskLevel.HIGH,
                    metric_name="LTV",
                    metric_value=ltv,
                    threshold=0.75,
                    summary="High loan-to-value ratio exceeds standard 75% underwriting ceiling",
                    recommendation="Require warm-body carve-out guarantees or mezzanine structure",
                )
            )
            red_flags.append(f"Elevated senior leverage ({ltv * 100:.1f}% > 75%)")
            deductions += 20.0
        elif ltv > 0.70:
            findings.append(
                DiagnosticFinding(
                    category=DiagnosticCategory.LEVERAGE,
                    severity=RiskLevel.ELEVATED,
                    metric_name="LTV",
                    metric_value=ltv,
                    threshold=0.70,
                    summary="Moderate-to-high leverage",
                    recommendation="Implement springing cash management triggers",
                )
            )
            deductions += 10.0
        elif ltv <= 0.60:
            strengths.append(f"Conservative senior leverage ({ltv * 100:.1f}% <= 60%)")

        # 3. Debt Yield
        if debt_yield < 0.07:
            findings.append(
                DiagnosticFinding(
                    category=DiagnosticCategory.LIQUIDITY,
                    severity=RiskLevel.CRITICAL,
                    metric_name="Debt Yield",
                    metric_value=debt_yield,
                    threshold=0.07,
                    summary="Sub-7.0% debt yield indicates insufficient collateral earning power",
                    recommendation="Downsize maximum permitted senior debt proceeds",
                )
            )
            red_flags.append(f"Sub-7% debt yield ({debt_yield * 100:.2f}%)")
            deductions += 25.0
        elif debt_yield < 0.08:
            findings.append(
                DiagnosticFinding(
                    category=DiagnosticCategory.LIQUIDITY,
                    severity=RiskLevel.HIGH,
                    metric_name="Debt Yield",
                    metric_value=debt_yield,
                    threshold=0.08,
                    summary="Debt yield below 8.0% institutional underwriting hurdle",
                    recommendation="Require ongoing quarterly debt yield covenants",
                )
            )
            deductions += 15.0
        elif debt_yield < 0.09:
            findings.append(
                DiagnosticFinding(
                    category=DiagnosticCategory.LIQUIDITY,
                    severity=RiskLevel.ELEVATED,
                    metric_name="Debt Yield",
                    metric_value=debt_yield,
                    threshold=0.09,
                    summary="Tight debt yield cushion (8.0% - 9.0%)",
                    recommendation="Cap additional subordinate debt incurrence",
                )
            )
            deductions += 8.0
        elif debt_yield >= 0.10:
            strengths.append(f"Healthy double-digit debt yield ({debt_yield * 100:.2f}%)")

        # 4. Occupancy and Break-even
        if break_even_occ > parcel.occupancy_rate:
            findings.append(
                DiagnosticFinding(
                    category=DiagnosticCategory.OPERATIONAL,
                    severity=RiskLevel.CRITICAL,
                    metric_name="Break-even Occupancy",
                    metric_value=break_even_occ,
                    threshold=parcel.occupancy_rate,
                    summary="Break-even occupancy exceeds current in-place physical occupancy",
                    recommendation="Mandate operational expense audit and sponsor cash replenishment",
                )
            )
            red_flags.append(
                f"Break-even occupancy ({break_even_occ * 100:.1f}%) exceeds current ({parcel.occupancy_rate * 100:.1f}%)"
            )
            deductions += 25.0
        elif break_even_occ > 0.85:
            findings.append(
                DiagnosticFinding(
                    category=DiagnosticCategory.OPERATIONAL,
                    severity=RiskLevel.ELEVATED,
                    metric_name="Break-even Occupancy",
                    metric_value=break_even_occ,
                    threshold=0.85,
                    summary="High break-even occupancy leaves narrow buffer for tenant loss",
                    recommendation="Require lease renewal contingency reserves",
                )
            )
            deductions += 10.0

        if parcel.occupancy_rate >= 0.95:
            strengths.append(f"High collateral occupancy ({parcel.occupancy_rate * 100:.1f}%)")

        # 5. Rent Roll & Tenant Concentration
        if rent_roll is not None and rent_roll.leases:
            total_rent = sum(l.annual_base_rent for l in rent_roll.leases)
            if total_rent > 0:
                tenant_rents: dict[str, float] = {}
                for lease in rent_roll.leases:
                    tenant_rents[lease.tenant_id] = (
                        tenant_rents.get(lease.tenant_id, 0.0) + lease.annual_base_rent
                    )
                max_tenant_share = max(tenant_rents.values()) / total_rent
                if max_tenant_share > 0.40:
                    findings.append(
                        DiagnosticFinding(
                            category=DiagnosticCategory.TENANT_CONCENTRATION,
                            severity=RiskLevel.HIGH,
                            metric_name="Tenant Concentration",
                            metric_value=round(max_tenant_share, 4),
                            threshold=0.40,
                            summary="Single tenant generates over 40% of property rental cash flows",
                            recommendation="Require tenant lease extension or letter of credit escrow",
                        )
                    )
                    red_flags.append(
                        f"Single tenant concentration exceeds 40% ({max_tenant_share * 100:.1f}%)"
                    )
                    deductions += 15.0
                elif max_tenant_share > 0.25:
                    findings.append(
                        DiagnosticFinding(
                            category=DiagnosticCategory.TENANT_CONCENTRATION,
                            severity=RiskLevel.ELEVATED,
                            metric_name="Tenant Concentration",
                            metric_value=round(max_tenant_share, 4),
                            threshold=0.25,
                            summary="Single tenant generates over 25% of property rental cash flows",
                            recommendation="Track tenant credit ratings and lease rollovers quarterly",
                        )
                    )
                    deductions += 8.0

        # 6. Operating Statement Expense Ratio
        if statement is not None and statement.effective_gross_income > 0:
            opex_ratio = statement.total_operating_expenses / statement.effective_gross_income
            if opex_ratio > 0.55:
                findings.append(
                    DiagnosticFinding(
                        category=DiagnosticCategory.OPERATIONAL,
                        severity=RiskLevel.ELEVATED,
                        metric_name="OpEx Ratio",
                        metric_value=round(opex_ratio, 4),
                        threshold=0.55,
                        summary="Elevated operating expense ratio (>55% of EGI)",
                        recommendation="Re-negotiate vendor and third-party property management contracts",
                    )
                )
                deductions += 10.0
            elif opex_ratio < 0.35:
                strengths.append(
                    f"Lean operating expense profile ({opex_ratio * 100:.1f}% OpEx ratio)"
                )

        health_score = round(max(0.0, min(100.0, 100.0 - deductions)), 1)

        # Composite risk level
        if any(f.severity == RiskLevel.CRITICAL for f in findings):
            overall_risk = RiskLevel.CRITICAL
        elif any(f.severity == RiskLevel.HIGH for f in findings):
            overall_risk = RiskLevel.HIGH
        elif any(f.severity == RiskLevel.ELEVATED for f in findings):
            overall_risk = RiskLevel.ELEVATED
        elif health_score < 75.0:
            overall_risk = RiskLevel.MODERATE
        else:
            overall_risk = RiskLevel.LOW

        # Underwriting decision
        if overall_risk in (RiskLevel.CRITICAL, RiskLevel.HIGH) or health_score < 50.0:
            underwriting_decision = "REJECT"
        elif overall_risk == RiskLevel.ELEVATED or health_score < 75.0:
            underwriting_decision = "CONDITIONALLY_APPROVE"
        else:
            underwriting_decision = "APPROVE"

        return PropertyDiagnosis(
            property_apn=parcel.apn,
            health_score=health_score,
            overall_risk=overall_risk,
            metrics=metrics,
            findings=findings,
            strengths=strengths,
            red_flags=red_flags,
            underwriting_decision=underwriting_decision,
        )

    def diagnose_cmbs_pool(
        self,
        deal: CMBSSecuritization,
        stress_config: StressTestConfig | None = None,
    ) -> PoolDiagnosis:
        """Run stress diagnosis on CMBS collateral pool and identify tranche vulnerabilities."""
        config = stress_config or StressTestConfig()
        pool_metrics_dict = self.cmbs_engine.calculate_pool_summary(deal.collateral_loans)

        summary = CMBSPoolSummary(
            total_balance=pool_metrics_dict["total_balance"],
            weighted_avg_dscr=pool_metrics_dict["weighted_avg_dscr"],
            weighted_avg_ltv=pool_metrics_dict["weighted_avg_ltv"],
            weighted_avg_coupon=pool_metrics_dict["weighted_avg_coupon"],
            loan_count=pool_metrics_dict["loan_count"],
        )

        stress_results = self.cmbs_engine.evaluate_pool_stress(
            loans=deal.collateral_loans,
            loss_severity=config.loss_severity,
            rate_shock_bps=config.rate_shock_bps,
        )

        waterfall = self.cmbs_engine.allocate_waterfall_losses(
            tranches=deal.tranches,
            cumulative_pool_loss=stress_results["total_expected_loss"],
        )

        # Delinquency triage
        non_current_statuses = {
            LoanStatus.WATCHLIST,
            LoanStatus.SPECIAL_SERVICING,
            LoanStatus.DELINQUENT_30,
            LoanStatus.DELINQUENT_60,
            LoanStatus.DELINQUENT_90_PLUS,
            LoanStatus.DEFAULT,
            LoanStatus.REO,
        }
        total_balance = summary.total_balance
        non_current_balance = sum(
            l.current_balance for l in deal.collateral_loans if l.status in non_current_statuses
        )
        delinquency_rate = (
            round(non_current_balance / total_balance, 4) if total_balance > 0 else 0.0
        )

        impaired_tranches = [
            t["tranche_name"] for t in waterfall if t.get("allocated_loss", 0.0) > 0.0
        ]

        findings: list[DiagnosticFinding] = []
        deductions = 0.0

        # DSCR
        if summary.weighted_avg_dscr < 1.10:
            findings.append(
                DiagnosticFinding(
                    category=DiagnosticCategory.COVERAGE,
                    severity=RiskLevel.CRITICAL,
                    metric_name="Weighted Average DSCR",
                    metric_value=summary.weighted_avg_dscr,
                    threshold=1.10,
                    summary="Collateral pool weighted DSCR is critically depressed (<1.10x)",
                    recommendation="Increase credit enhancement and subordination buffers",
                )
            )
            deductions += 35.0
        elif summary.weighted_avg_dscr < 1.25:
            findings.append(
                DiagnosticFinding(
                    category=DiagnosticCategory.COVERAGE,
                    severity=RiskLevel.HIGH,
                    metric_name="Weighted Average DSCR",
                    metric_value=summary.weighted_avg_dscr,
                    threshold=1.25,
                    summary="Collateral pool weighted DSCR is below institutional target (<1.25x)",
                    recommendation="Require structural cash trap triggers across underlying loans",
                )
            )
            deductions += 20.0

        # LTV
        if summary.weighted_avg_ltv > 0.75:
            findings.append(
                DiagnosticFinding(
                    category=DiagnosticCategory.LEVERAGE,
                    severity=RiskLevel.HIGH,
                    metric_name="Weighted Average LTV",
                    metric_value=summary.weighted_avg_ltv,
                    threshold=0.75,
                    summary="Collateral pool average LTV exceeds 75% risk threshold",
                    recommendation="Size higher first-loss equity piece",
                )
            )
            deductions += 25.0
        elif summary.weighted_avg_ltv > 0.70:
            findings.append(
                DiagnosticFinding(
                    category=DiagnosticCategory.LEVERAGE,
                    severity=RiskLevel.ELEVATED,
                    metric_name="Weighted Average LTV",
                    metric_value=summary.weighted_avg_ltv,
                    threshold=0.70,
                    summary="Collateral pool average LTV is elevated (>70%)",
                    recommendation="Monitor high-LTV concentration by property type",
                )
            )
            deductions += 15.0

        # Delinquency rate
        if delinquency_rate > 0.10:
            findings.append(
                DiagnosticFinding(
                    category=DiagnosticCategory.OPERATIONAL,
                    severity=RiskLevel.CRITICAL,
                    metric_name="Delinquency Rate",
                    metric_value=delinquency_rate,
                    threshold=0.10,
                    summary="Pool delinquency and distressed loan rate exceeds 10%",
                    recommendation="Accelerate special servicer transfers and workout resolutions",
                )
            )
            deductions += 35.0
        elif delinquency_rate > 0.05:
            findings.append(
                DiagnosticFinding(
                    category=DiagnosticCategory.OPERATIONAL,
                    severity=RiskLevel.HIGH,
                    metric_name="Delinquency Rate",
                    metric_value=delinquency_rate,
                    threshold=0.05,
                    summary="Pool delinquency rate exceeds 5%",
                    recommendation="Audit watchlist loans for impending lease expirations",
                )
            )
            deductions += 20.0
        elif delinquency_rate > 0.02:
            findings.append(
                DiagnosticFinding(
                    category=DiagnosticCategory.OPERATIONAL,
                    severity=RiskLevel.ELEVATED,
                    metric_name="Delinquency Rate",
                    metric_value=delinquency_rate,
                    threshold=0.02,
                    summary="Minor delinquency activity present in pool (>2%)",
                    recommendation="Review watchlist monthly",
                )
            )
            deductions += 10.0

        # Investment Grade impairment
        ig_set = {"AAA", "AA", "A", "BBB"}
        ig_impaired = [t for t in impaired_tranches if t in ig_set]
        if ig_impaired:
            findings.append(
                DiagnosticFinding(
                    category=DiagnosticCategory.VALUATION,
                    severity=RiskLevel.CRITICAL,
                    metric_name="Investment Grade Losses",
                    metric_value=float(len(ig_impaired)),
                    threshold=0.0,
                    summary=f"Severe credit stress impairs investment-grade tranches: {', '.join(ig_impaired)}",
                    recommendation="Restructure subordination waterfall or increase excess spread",
                )
            )
            deductions += 35.0

        pool_health_score = round(max(0.0, min(100.0, 100.0 - deductions)), 1)

        if any(f.severity == RiskLevel.CRITICAL for f in findings):
            overall_risk = RiskLevel.CRITICAL
        elif any(f.severity == RiskLevel.HIGH for f in findings):
            overall_risk = RiskLevel.HIGH
        elif any(f.severity == RiskLevel.ELEVATED for f in findings):
            overall_risk = RiskLevel.ELEVATED
        elif pool_health_score < 75.0:
            overall_risk = RiskLevel.MODERATE
        else:
            overall_risk = RiskLevel.LOW

        return PoolDiagnosis(
            deal_id=deal.deal_id,
            pool_health_score=pool_health_score,
            overall_risk=overall_risk,
            summary=summary,
            findings=findings,
            stressed_loss_pct=stress_results["pool_loss_pct"],
            impaired_tranches=impaired_tranches,
            delinquency_rate=delinquency_rate,
        )

    @staticmethod
    def diagnose_underwriting_report(report: UnderwritingReport) -> dict[str, Any]:
        """Diagnose multi-scenario DCF report for downside resilience and risk flags."""
        red_flags: list[str] = []
        strengths: list[str] = []

        if report.severe_stress_scenario.irr < 0.0:
            red_flags.append(
                f"Negative IRR under severe stress ({report.severe_stress_scenario.irr * 100:.2f}%)"
            )
        if report.bear_scenario.irr < 0.05:
            red_flags.append(
                f"Sub-5% return in bear scenario ({report.bear_scenario.irr * 100:.2f}%)"
            )
        if report.min_dscr < 1.0:
            red_flags.append(f"Minimum DSCR drops below break-even ({report.min_dscr:.2f}x)")

        if report.base_scenario.irr >= 0.12:
            strengths.append(
                f"Strong base return profile ({report.base_scenario.irr * 100:.2f}% IRR)"
            )
        if report.average_dscr >= 1.35:
            strengths.append(f"Comfortable average debt coverage ({report.average_dscr:.2f}x)")

        is_viable = len(red_flags) == 0 and report.base_scenario.irr > 0.08
        verdict = (
            "RECOMMENDED"
            if is_viable and report.average_dscr >= 1.25
            else ("CAUTION" if len(red_flags) <= 1 else "REJECTED")
        )

        return {
            "property_apn": report.property_apn,
            "verdict": verdict,
            "is_viable": is_viable,
            "base_irr": report.base_scenario.irr,
            "severe_stress_irr": report.severe_stress_scenario.irr,
            "average_dscr": report.average_dscr,
            "min_dscr": report.min_dscr,
            "strengths": strengths,
            "red_flags": red_flags,
        }
