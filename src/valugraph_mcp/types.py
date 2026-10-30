"""Domain models, enums, data contracts, and validators for ValuGraph-MCP."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class PropertyType(str, Enum):
    """Commercial real estate property asset classes."""

    OFFICE = "office"
    MULTIFAMILY = "multifamily"
    INDUSTRIAL = "industrial"
    RETAIL = "retail"
    HOSPITALITY = "hospitality"
    MIXED_USE = "mixed_use"
    COMMERCIAL = "commercial"
    HEALTHCARE = "healthcare"
    DATA_CENTER = "data_center"
    SELF_STORAGE = "self_storage"
    SPECIALTY = "specialty"


class ScenarioType(str, Enum):
    """Underwriting scenario projections."""

    BASE = "base"
    BULL = "bull"
    BEAR = "bear"
    SEVERE_STRESS = "severe_stress"


class LeaseType(str, Enum):
    """Commercial lease structure contracts."""

    NNN = "nnn"
    MODIFIED_GROSS = "modified_gross"
    FULL_SERVICE = "full_service"
    GROSS = "gross"


class LoanStatus(str, Enum):
    """CMBS and commercial mortgage performance statuses."""

    CURRENT = "current"
    WATCHLIST = "watchlist"
    SPECIAL_SERVICING = "special_servicing"
    DELINQUENT_30 = "delinquent_30"
    DELINQUENT_60 = "delinquent_60"
    DELINQUENT_90_PLUS = "delinquent_90_plus"
    DEFAULT = "default"
    REO = "reo"


class TrancheRating(str, Enum):
    """Securitization credit ratings."""

    AAA = "AAA"
    AA = "AA"
    A = "A"
    BBB = "BBB"
    BB = "BB"
    B = "B"
    EQUITY = "Equity"


class RiskLevel(str, Enum):
    """Underwriting and credit risk classification tiers."""

    LOW = "low"
    MODERATE = "moderate"
    ELEVATED = "elevated"
    HIGH = "high"
    CRITICAL = "critical"


class RelationshipType(str, Enum):
    """Knowledge graph edge relation types."""

    OWNS = "OWNS"
    LEASES_FROM = "LEASES_FROM"
    ENCUMBERS = "ENCUMBERS"
    SERVICED_BY = "SERVICED_BY"
    GUARANTEES = "GUARANTEES"
    ADJACENT_TO = "ADJACENT_TO"


class DiagnosticCategory(str, Enum):
    """Classification of underwriting and risk diagnosis findings."""

    LEVERAGE = "leverage"
    COVERAGE = "coverage"
    LIQUIDITY = "liquidity"
    TENANT_CONCENTRATION = "tenant_concentration"
    LEASE_ROLLOVER = "lease_rollover"
    VALUATION = "valuation"
    OPERATIONAL = "operational"


# --- Domain Models ---


class PropertyParcel(BaseModel):
    """Commercial real estate parcel entity."""

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

    @field_validator("apn")
    @classmethod
    def validate_apn_field(cls, v: str) -> str:
        return validate_apn(v)

    @property
    def cap_rate(self) -> float:
        """In-place capitalization rate."""
        return calculate_cap_rate(self.current_noi, self.purchase_price)


class Tenant(BaseModel):
    """Commercial property tenant."""

    tenant_id: str = Field(..., description="Unique tenant identifier")
    name: str = Field(..., description="Tenant corporate name")
    credit_rating: str = Field(default="BBB", description="Tenant rating or unrated indicator")
    leased_sqft: float = Field(..., gt=0, description="Leased floor space in sqft")
    annual_rent: float = Field(..., gt=0, description="Annual base rent in USD")
    lease_expiry: str = Field(..., description="Lease expiration ISO date string")


class Lease(BaseModel):
    """Granular commercial lease contract."""

    lease_id: str = Field(..., description="Unique lease identifier")
    tenant_id: str = Field(..., description="Associated tenant ID")
    property_apn: str = Field(..., description="Associated property APN")
    suite: str = Field(default="", description="Suite or unit number")
    lease_type: LeaseType = Field(default=LeaseType.NNN, description="Lease structure")
    leased_sqft: float = Field(..., gt=0, description="Leased floor space in sqft")
    annual_base_rent: float = Field(..., gt=0, description="Annual base rent in USD")
    rent_per_sqft: float = Field(default=0.0, ge=0.0, description="Annual rent per square foot")
    start_date: str = Field(..., description="Lease commencement ISO date string")
    end_date: str = Field(..., description="Lease expiration ISO date string")
    escalation_rate: float = Field(
        default=0.03, ge=0.0, description="Annual rent escalation percentage"
    )
    renewal_options: int = Field(default=0, ge=0, description="Number of renewal options")

    def model_post_init(self, context: Any) -> None:
        if self.rent_per_sqft <= 0.0 and self.leased_sqft > 0:
            self.rent_per_sqft = round(self.annual_base_rent / self.leased_sqft, 2)


class RentRoll(BaseModel):
    """Commercial rent roll schedule."""

    property_apn: str = Field(..., description="Collateral property APN")
    as_of_date: str = Field(..., description="Snapshot as of ISO date")
    leases: list[Lease] = Field(default_factory=list, description="Active lease contracts")
    total_leased_sqft: float = Field(default=0.0, ge=0.0, description="Total occupied sqft")
    total_annual_rent: float = Field(
        default=0.0, ge=0.0, description="Total annual rent roll revenue"
    )
    occupancy_pct: float = Field(default=0.0, ge=0.0, le=1.0, description="Occupancy percentage")

    def model_post_init(self, context: Any) -> None:
        if self.leases:
            if self.total_leased_sqft <= 0.0:
                self.total_leased_sqft = sum(l.leased_sqft for l in self.leases)
            if self.total_annual_rent <= 0.0:
                self.total_annual_rent = sum(l.annual_base_rent for l in self.leases)


class OperatingStatement(BaseModel):
    """Operating statement line items for underwriting."""

    property_apn: str = Field(..., description="Collateral property APN")
    period_year: int = Field(..., ge=1900, le=2100, description="Operating period fiscal year")
    gross_potential_rent: float = Field(
        ..., gt=0, description="Gross potential rent (100% occupied)"
    )
    vacancy_loss: float = Field(default=0.0, ge=0.0, description="Economic vacancy and credit loss")
    effective_gross_income: float = Field(..., description="Effective gross revenue (EGI)")
    real_estate_taxes: float = Field(default=0.0, ge=0.0, description="Property taxes")
    insurance: float = Field(default=0.0, ge=0.0, description="Property insurance")
    utilities: float = Field(default=0.0, ge=0.0, description="Utilities expenses")
    repairs_maintenance: float = Field(default=0.0, ge=0.0, description="R&M expenses")
    management_fees: float = Field(default=0.0, ge=0.0, description="Property management fees")
    total_operating_expenses: float = Field(..., ge=0.0, description="Total operating expenses")
    net_operating_income: float = Field(..., description="Net operating income (NOI)")


class ValuationMetrics(BaseModel):
    """Key valuation metrics."""

    cap_rate: float = Field(..., ge=0.0, description="Capitalization rate")
    gross_rent_multiplier: float = Field(
        default=0.0, ge=0.0, description="Gross Rent Multiplier (GRM)"
    )
    debt_yield: float = Field(default=0.0, ge=0.0, description="Debt yield (NOI / Loan Amount)")
    loan_to_cost: float = Field(default=0.0, ge=0.0, le=2.0, description="Loan to Cost ratio")
    break_even_occupancy: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Break-even occupancy rate"
    )


class CMBSLoan(BaseModel):
    """CMBS mortgage loan contract and collateral debt metrics."""

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
    status: LoanStatus = Field(default=LoanStatus.CURRENT, description="Loan performance status")


class CMBSTranche(BaseModel):
    """Securitization tranche within CMBS capital structure."""

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
    """CMBS securitization issue and capital structure deal."""

    deal_id: str = Field(..., description="Deal identifier, e.g. COMM-2026-FL1")
    deal_name: str = Field(..., description="Full securitization issue name")
    total_issuance: float = Field(..., gt=0, description="Total initial deal issuance in USD")
    collateral_loans: list[CMBSLoan] = Field(
        default_factory=list, description="Underlying collateral pool"
    )
    tranches: list[CMBSTranche] = Field(
        default_factory=list, description="Capital structure tranches"
    )


class CMBSPoolSummary(BaseModel):
    """Aggregate portfolio summary for CMBS collateral loan pool."""

    total_balance: float = Field(..., ge=0.0, description="Total aggregate unpaid balance")
    weighted_avg_dscr: float = Field(..., ge=0.0, description="Weighted average DSCR")
    weighted_avg_ltv: float = Field(..., ge=0.0, description="Weighted average LTV")
    weighted_avg_coupon: float = Field(..., ge=0.0, description="Weighted average coupon rate")
    loan_count: int = Field(..., ge=0, description="Number of collateral loans")


class TrancheLossAllocation(BaseModel):
    """Result of waterfall loss distribution to a single tranche."""

    tranche_name: str = Field(..., description="Tranche name")
    attachment_point: float = Field(..., ge=0.0, le=1.0)
    detachment_point: float = Field(..., ge=0.0, le=1.0)
    initial_balance: float = Field(..., ge=0.0)
    allocated_loss: float = Field(..., ge=0.0)
    remaining_balance: float = Field(..., ge=0.0)
    impairment_pct: float = Field(..., ge=0.0, le=1.0)
    is_exhausted: bool = Field(default=False)


class CMBSSubordinationAnalysis(BaseModel):
    """CMBS waterfall loss stress-test output."""

    deal_id: str = Field(..., description="Securitization deal identifier")
    total_loss_simulated: float = Field(..., ge=0.0, description="Total simulated loss in USD")
    tranche_allocations: list[TrancheLossAllocation] = Field(
        default_factory=list, description="Tranche loss results"
    )
    equity_wiped_out: bool = Field(
        default=False, description="Whether first-loss equity is exhausted"
    )
    investment_grade_impaired: bool = Field(
        default=False, description="Whether BBB or higher tranches incurred losses"
    )


class StressTestConfig(BaseModel):
    """Stress test parameters for underwriting and CMBS analysis."""

    rate_shock_bps: float = Field(default=0.0, description="Interest rate shock in basis points")
    loss_severity: float = Field(
        default=0.40, ge=0.0, le=1.0, description="Loss Given Default severity"
    )
    vacancy_shock_pct: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Vacancy shock percentage"
    )
    cap_rate_expansion_bps: float = Field(
        default=0.0, ge=0.0, description="Cap rate expansion in bps"
    )


class DCFInputs(BaseModel):
    """Assumptions and drivers for 10-year discounted cash flow modeling."""

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
    """Annual DCF cash flow projection period."""

    year: int
    gross_revenue: float
    operating_expenses: float
    capex_reserve: float
    net_operating_income: float
    debt_service: float
    net_cash_flow: float


class ScenarioResult(BaseModel):
    """Outcome metrics for a single DCF scenario simulation."""

    scenario: ScenarioType
    npv: float
    irr: float
    equity_multiple: float
    exit_valuation: float
    terminal_noi: float
    cumulative_cash_flow: float
    annual_cash_flows: list[CashFlowYear]


class UnderwritingReport(BaseModel):
    """Comprehensive underwriting synthesis report."""

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


class DiagnosticFinding(BaseModel):
    """Specific diagnostic anomaly, vulnerability, or underwriting red flag."""

    category: DiagnosticCategory = Field(..., description="Risk category domain")
    severity: RiskLevel = Field(..., description="Severity classification")
    metric_name: str = Field(..., description="Underlying financial metric analyzed")
    metric_value: float = Field(..., description="Calculated metric value")
    threshold: float = Field(..., description="Underwriting threshold breached")
    summary: str = Field(..., description="Terse finding diagnosis")
    recommendation: str = Field(..., description="Mitigating action or loan covenant")


class PropertyDiagnosis(BaseModel):
    """Complete diagnostic health assessment of commercial real estate parcel."""

    property_apn: str = Field(..., description="Assessor Parcel Number")
    health_score: float = Field(..., ge=0.0, le=100.0, description="Overall health score (0-100)")
    overall_risk: RiskLevel = Field(..., description="Composite risk level")
    metrics: ValuationMetrics = Field(..., description="Key diagnostic ratios and metrics")
    findings: list[DiagnosticFinding] = Field(
        default_factory=list, description="All identified risk findings"
    )
    strengths: list[str] = Field(
        default_factory=list, description="Identified credit and operational strengths"
    )
    red_flags: list[str] = Field(default_factory=list, description="Critical warning items")
    underwriting_decision: str = Field(
        ..., description="Decision: APPROVE, CONDITIONALLY_APPROVE, REJECT"
    )


class PoolDiagnosis(BaseModel):
    """Diagnostic health assessment of CMBS collateral loan pool."""

    deal_id: str = Field(..., description="Securitization deal identifier")
    pool_health_score: float = Field(
        ..., ge=0.0, le=100.0, description="Overall pool health score (0-100)"
    )
    overall_risk: RiskLevel = Field(..., description="Composite risk level")
    summary: CMBSPoolSummary = Field(..., description="Aggregate collateral pool metrics")
    findings: list[DiagnosticFinding] = Field(
        default_factory=list, description="Identified pool risk findings"
    )
    stressed_loss_pct: float = Field(
        default=0.0, ge=0.0, description="Projected cumulative loss percentage"
    )
    impaired_tranches: list[str] = Field(
        default_factory=list, description="Tranches suffering principal loss"
    )
    delinquency_rate: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Fraction of non-current loan balance"
    )


class GraphNode(BaseModel):
    """Knowledge graph vertex representation."""

    node_id: str
    node_type: str
    attributes: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    """Knowledge graph edge representation."""

    source: str
    target: str
    relationship_type: str
    attributes: dict[str, Any] = Field(default_factory=dict)


class GraphQuery(BaseModel):
    """Neighborhood or lineage query specification."""

    entity_id: str = Field(..., description="Target node ID")
    depth: int = Field(default=1, ge=1, le=5, description="Search radius depth")
    relationship_types: list[str] | None = Field(
        default=None, description="Optional relationship filter"
    )


class GraphQueryResult(BaseModel):
    """Subgraph query result."""

    center_node_id: str
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    node_count: int = Field(default=0, ge=0)
    edge_count: int = Field(default=0, ge=0)


# --- Domain Helper Functions and Financial Formulas ---


def validate_apn(apn: str) -> str:
    """Validate and normalize Assessor Parcel Number format."""
    if not isinstance(apn, str):
        raise TypeError("APN must be a string")
    cleaned = apn.strip()
    if not cleaned:
        raise ValueError("APN cannot be empty")
    return cleaned


def calculate_cap_rate(noi: float, value: float) -> float:
    """Calculate capitalization rate = NOI / Value."""
    if value <= 0:
        raise ValueError("Property value must be greater than zero")
    return round(noi / value, 6)


def calculate_debt_yield(noi: float, loan_amount: float) -> float:
    """Calculate debt yield = NOI / Loan Amount."""
    if loan_amount <= 0:
        raise ValueError("Loan amount must be greater than zero")
    return round(noi / loan_amount, 6)


def calculate_dscr(noi: float, annual_debt_service: float) -> float:
    """Calculate Debt Service Coverage Ratio (DSCR) = NOI / Debt Service."""
    if annual_debt_service <= 0:
        raise ValueError("Annual debt service must be greater than zero")
    return round(noi / annual_debt_service, 4)


def calculate_ltv(loan_amount: float, property_value: float) -> float:
    """Calculate Loan-to-Value (LTV) ratio = Loan Amount / Property Value."""
    if property_value <= 0:
        raise ValueError("Property value must be greater than zero")
    return round(loan_amount / property_value, 4)


def calculate_break_even_occupancy(
    operating_expenses: float,
    debt_service: float,
    gross_potential_rent: float,
) -> float:
    """Calculate break-even occupancy rate = (OpEx + Debt Service) / Gross Potential Rent."""
    if gross_potential_rent <= 0:
        raise ValueError("Gross potential rent must be greater than zero")
    return round((operating_expenses + debt_service) / gross_potential_rent, 4)


def assess_risk_level(dscr: float, ltv: float, debt_yield: float) -> RiskLevel:
    """Evaluate CRE credit risk level based on DSCR, LTV, and Debt Yield."""
    if dscr < 1.0 or ltv > 0.85 or debt_yield < 0.07:
        return RiskLevel.CRITICAL
    if dscr < 1.15 or ltv > 0.75 or debt_yield < 0.08:
        return RiskLevel.HIGH
    if dscr < 1.25 or ltv > 0.70 or debt_yield < 0.09:
        return RiskLevel.ELEVATED
    if dscr < 1.40 or ltv > 0.65 or debt_yield < 0.10:
        return RiskLevel.MODERATE
    return RiskLevel.LOW


__all__ = [
    "CMBSLoan",
    "CMBSPoolSummary",
    "CMBSSecuritization",
    "CMBSSubordinationAnalysis",
    "CMBSTranche",
    "CashFlowYear",
    "DCFInputs",
    "DiagnosticCategory",
    "DiagnosticFinding",
    "GraphEdge",
    "GraphNode",
    "GraphQuery",
    "GraphQueryResult",
    "Lease",
    "LeaseType",
    "LoanStatus",
    "OperatingStatement",
    "PoolDiagnosis",
    "PropertyDiagnosis",
    "PropertyParcel",
    "PropertyType",
    "RelationshipType",
    "RentRoll",
    "RiskLevel",
    "ScenarioResult",
    "ScenarioType",
    "StressTestConfig",
    "Tenant",
    "TrancheLossAllocation",
    "TrancheRating",
    "UnderwritingReport",
    "ValuationMetrics",
    "assess_risk_level",
    "calculate_break_even_occupancy",
    "calculate_cap_rate",
    "calculate_debt_yield",
    "calculate_dscr",
    "calculate_ltv",
    "validate_apn",
]
