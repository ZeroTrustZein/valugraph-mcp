"""Domain models, enums, and data contracts for ValuGraph-MCP."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class PropertyType(str, Enum):
    OFFICE = "office"
    MULTIFAMILY = "multifamily"
    INDUSTRIAL = "industrial"
    RETAIL = "retail"
    HOSPITALITY = "hospitality"
    MIXED_USE = "mixed_use"


class ScenarioType(str, Enum):
    BASE = "base"
    BULL = "bull"
    BEAR = "bear"
    SEVERE_STRESS = "severe_stress"


class PropertyParcel(BaseModel):
    apn: str = Field(..., description="Assessor Parcel Number or unique property ID")
    address: str = Field(..., description="Full physical property address")
    property_type: PropertyType = Field(default=PropertyType.OFFICE, description="Asset class")
    gross_sqft: float = Field(..., gt=0, description="Gross building area in sqft")
    rentable_sqft: float = Field(..., gt=0, description="Net rentable area in sqft")
    year_built: int = Field(..., ge=1800, le=2100, description="Construction year")
    purchase_price: float = Field(..., gt=0, description="Acquisition or market price in USD")
    current_noi: float = Field(..., description="Current in-place Net Operating Income")
    occupancy_rate: float = Field(
        default=0.95, ge=0.0, le=1.0, description="Current occupancy rate"
    )


class Tenant(BaseModel):
    tenant_id: str = Field(..., description="Unique tenant identifier")
    name: str = Field(..., description="Tenant corporate name")
    credit_rating: str = Field(default="BBB", description="Tenant rating or unrated indicator")
    leased_sqft: float = Field(..., gt=0, description="Leased floor space in sqft")
    annual_rent: float = Field(..., gt=0, description="Annual base rent in USD")
    lease_expiry: str = Field(..., description="Lease expiration ISO date string")


class CMBSLoan(BaseModel):
    loan_id: str = Field(..., description="CMBS mortgage loan ID")
    property_apn: str = Field(..., description="Collateral property APN")
    original_balance: float = Field(..., gt=0, description="Original note amount")
    current_balance: float = Field(..., gt=0, description="Current unpaid principal balance")
    interest_rate: float = Field(..., gt=0, description="Note rate (e.g. 0.065 for 6.5%)")
    term_months: int = Field(default=120, gt=0, description="Loan term in months")
    amortization_months: int = Field(
        default=360, ge=0, description="Amortization period in months (0 for IO)"
    )
    maturity_date: str = Field(..., description="Maturity ISO date string")
    dscr: float = Field(
        default=1.25, ge=0.0, description="Underwritten Debt Service Coverage Ratio"
    )
    ltv: float = Field(default=0.65, ge=0.0, le=1.5, description="Loan to Value ratio")
    is_interest_only: bool = Field(
        default=False, description="Whether loan is currently interest-only"
    )


class CMBSTranche(BaseModel):
    tranche_name: str = Field(..., description="Tranche name (e.g. AAA, AA, A, BBB, BB, B, Equity)")
    attachment_point: float = Field(
        ..., ge=0.0, le=1.0, description="Lower loss attachment threshold"
    )
    detachment_point: float = Field(
        ..., ge=0.0, le=1.0, description="Upper loss exhaustion threshold"
    )
    coupon_rate: float = Field(..., gt=0, description="Annual coupon spread or rate")
    initial_balance: float = Field(..., gt=0, description="Starting tranche principal balance")
    current_balance: float = Field(..., ge=0, description="Remaining principal balance")
    accumulated_loss: float = Field(default=0.0, ge=0, description="Total credit losses allocated")


class CMBSSecuritization(BaseModel):
    deal_id: str = Field(..., description="Deal identifier, e.g. COMM-2026-FL1")
    deal_name: str = Field(..., description="Full securitization issue name")
    total_issuance: float = Field(..., gt=0, description="Total initial deal issuance in USD")
    collateral_loans: list[CMBSLoan] = Field(
        default_factory=list, description="Underlying collateral pool"
    )
    tranches: list[CMBSTranche] = Field(
        default_factory=list, description="Capital structure tranches"
    )


class DCFInputs(BaseModel):
    purchase_price: float = Field(..., gt=0, description="Initial acquisition cost")
    hold_period_years: int = Field(default=10, ge=1, le=30, description="Investment horizon")
    exit_cap_rate: float = Field(default=0.065, gt=0, description="Terminal capitalization rate")
    discount_rate: float = Field(default=0.09, gt=0, description="Discount rate / hurdle rate")
    initial_revenue: float = Field(..., gt=0, description="Year 1 gross revenue")
    initial_expenses: float = Field(..., ge=0, description="Year 1 operating expenses")
    revenue_growth_rate: float = Field(default=0.03, description="Annual revenue growth assumption")
    expense_growth_rate: float = Field(
        default=0.025, description="Annual expense escalation assumption"
    )
    capex_reserve_pct: float = Field(
        default=0.03, ge=0, description="CapEx reserve as % of revenue"
    )
    financing_ltv: float = Field(
        default=0.65, ge=0, le=1.0, description="Loan-to-Value for acquisition debt"
    )
    financing_interest_rate: float = Field(default=0.065, gt=0, description="Debt interest rate")
    debt_term_years: int = Field(default=30, ge=1, description="Amortization horizon in years")


class CashFlowYear(BaseModel):
    year: int
    gross_revenue: float
    operating_expenses: float
    capex_reserve: float
    net_operating_income: float
    debt_service: float
    net_cash_flow: float


class ScenarioResult(BaseModel):
    scenario: ScenarioType
    npv: float
    irr: float
    equity_multiple: float
    exit_valuation: float
    terminal_noi: float
    cumulative_cash_flow: float
    annual_cash_flows: list[CashFlowYear]


class UnderwritingReport(BaseModel):
    property_apn: str
    valuation_date: str
    purchase_price: float
    recommended_loan_amount: float
    base_scenario: ScenarioResult
    bull_scenario: ScenarioResult
    bear_scenario: ScenarioResult
    severe_stress_scenario: ScenarioResult
    average_dscr: float
    min_dscr: float
    conclusion: str


class GraphNode(BaseModel):
    node_id: str
    node_type: str
    attributes: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    source: str
    target: str
    relationship_type: str
    attributes: dict[str, Any] = Field(default_factory=dict)
