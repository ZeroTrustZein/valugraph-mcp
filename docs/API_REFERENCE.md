# ValuGraph-MCP: API Reference

Complete programmatic reference for all modules, classes, models, schemas, and utility functions in **`valugraph_mcp`**.

---

## Table of Contents
1. [Domain Types & Models (`valugraph_mcp.types`)](#1-domain-types--models)
2. [Discounted Cash Flow Engine (`valugraph_mcp.dcf`)](#2-discounted-cash-flow-engine)
3. [CMBS Risk & Waterfall Engine (`valugraph_mcp.cmbs`)](#3-cmbs-risk--waterfall-engine)
4. [Autonomous Diagnosis Engine (`valugraph_mcp.diagnosis`)](#4-autonomous-diagnosis-engine)
5. [Temporal CRE Knowledge Graph (`valugraph_mcp.graph`)](#5-temporal-cre-knowledge-graph)
6. [MCP Server & Tool Definitions (`valugraph_mcp.server`)](#6-mcp-server--tool-definitions)
7. [Command-Line Interface (`valugraph_mcp.cli`)](#7-command-line-interface)

---

## 1. Domain Types & Models

**Module**: `valugraph_mcp.types`

### 1.1 Enumerations

#### `PropertyType`
Asset class categorization for commercial real estate properties:
- `OFFICE = "office"`
- `MULTIFAMILY = "multifamily"`
- `INDUSTRIAL = "industrial"`
- `RETAIL = "retail"`
- `HOSPITALITY = "hospitality"`
- `MIXED_USE = "mixed_use"`
- `COMMERCIAL = "commercial"`
- `HEALTHCARE = "healthcare"`
- `DATA_CENTER = "data_center"`
- `SELF_STORAGE = "self_storage"`
- `SPECIALTY = "specialty"`

#### `ScenarioType`
Underwriting scenario projections:
- `BASE = "base"`: Standard contractual growth assumptions.
- `BULL = "bull"`: Accelerated rental growth and cap rate compression.
- `BEAR = "bear"`: Stagnant rent, inflationary expenses, and cap rate expansion.
- `SEVERE_STRESS = "severe_stress"`: Severe market downturn and elevated vacancy.

#### `LeaseType`
Commercial lease structure contracts:
- `NNN = "nnn"`: Triple net lease (tenant covers taxes, insurance, maintenance).
- `MODIFIED_GROSS = "modified_gross"`: Shared operating expenses.
- `FULL_SERVICE = "full_service"`: Landlord pays all expenses included in base rent.
- `GROSS = "gross"`: Standard gross lease.

#### `LoanStatus`
CMBS and commercial mortgage performance statuses:
- `CURRENT = "current"`
- `WATCHLIST = "watchlist"`
- `SPECIAL_SERVICING = "special_servicing"`
- `DELINQUENT_30 = "delinquent_30"`
- `DELINQUENT_60 = "delinquent_60"`
- `DELINQUENT_90_PLUS = "delinquent_90_plus"`
- `DEFAULT = "default"`
- `REO = "reo"` (Real Estate Owned / Foreclosed)

#### `TrancheRating`
Securitization credit ratings:
- `AAA`, `AA`, `A`, `BBB`, `BB`, `B`, `EQUITY`

#### `RiskLevel`
Underwriting risk classification tiers:
- `LOW = "low"`
- `MODERATE = "moderate"`
- `ELEVATED = "elevated"`
- `HIGH = "high"`
- `CRITICAL = "critical"`

#### `DiagnosticCategory`
Classification of underwriting and risk diagnosis findings:
- `LEVERAGE`: Loan-to-value, debt sizing, and subordination.
- `COVERAGE`: DSCR and debt service buffers.
- `LIQUIDITY`: Cash flow, reserves, and debt yields.
- `TENANT_CONCENTRATION`: Major tenant lease exposure.
- `LEASE_ROLLOVER`: Expirations within near-term horizon.
- `VALUATION`: Cap rates and pricing multiples.
- `OPERATIONAL`: Expense ratios and break-even occupancy.

---

### 1.2 Domain Models

#### `PropertyParcel`
Represents a physical commercial real estate property asset.
```python
class PropertyParcel(BaseModel):
    apn: str  # Unique Assessor Parcel Number
    address: str  # Physical street address
    property_type: PropertyType  # Commercial asset class
    gross_sqft: float  # Gross building area (> 0)
    rentable_sqft: float  # Net rentable floor area (> 0)
    year_built: int  # Construction year (1800 - 2100)
    purchase_price: float  # Acquisition or appraised value in USD (> 0)
    current_noi: float  # In-place Net Operating Income
    occupancy_rate: float = 0.95  # In-place occupancy (0.0 to 1.0)
```
- **Properties**: `cap_rate` $\to$ Returns `current_noi / purchase_price`.

#### `Tenant`
Represents an occupying corporate tenant.
```python
class Tenant(BaseModel):
    tenant_id: str
    name: str
    credit_rating: str = "BBB"
    leased_sqft: float  # Floor area in sqft (> 0)
    annual_rent: float  # Annual base rent in USD (> 0)
    lease_expiry: str  # ISO date string (YYYY-MM-DD)
```

#### `Lease`
Granular commercial lease contract terms.
```python
class Lease(BaseModel):
    lease_id: str
    tenant_id: str
    property_apn: str
    suite: str = ""
    lease_type: LeaseType = LeaseType.NNN
    leased_sqft: float
    annual_base_rent: float
    rent_per_sqft: float = 0.0  # Auto-calculated if omitted
    start_date: str
    end_date: str
    escalation_rate: float = 0.03
    renewal_options: int = 0
```

#### `RentRoll`
Portfolio of active tenant leases for a property parcel.
```python
class RentRoll(BaseModel):
    property_apn: str
    as_of_date: str
    leases: list[Lease] = []
    total_leased_sqft: float = 0.0  # Auto-aggregated if leases present
    total_annual_rent: float = 0.0  # Auto-aggregated if leases present
    occupancy_pct: float = 0.0
```

#### `OperatingStatement`
Financial line items for underwriting revenue and expenses.
```python
class OperatingStatement(BaseModel):
    property_apn: str
    period_year: int
    gross_potential_rent: float
    vacancy_loss: float = 0.0
    effective_gross_income: float
    real_estate_taxes: float = 0.0
    insurance: float = 0.0
    utilities: float = 0.0
    repairs_maintenance: float = 0.0
    management_fees: float = 0.0
    total_operating_expenses: float
    net_operating_income: float
```

#### `CMBSLoan`
Commercial mortgage note metrics and collateral debt parameters.
```python
class CMBSLoan(BaseModel):
    loan_id: str
    property_apn: str
    original_balance: float
    current_balance: float
    interest_rate: float
    term_months: int = 120
    amortization_months: int = 360  # 0 for Interest-Only
    maturity_date: str
    dscr: float = 1.25
    ltv: float = 0.65
    is_interest_only: bool = False
    status: LoanStatus = LoanStatus.CURRENT
```

#### `CMBSTranche`
Single securitization tranche in a CMBS capital structure.
```python
class CMBSTranche(BaseModel):
    tranche_name: str
    attachment_point: float  # Lower loss threshold (e.g. 0.10)
    detachment_point: float  # Upper loss threshold (e.g. 0.18)
    coupon_rate: float
    initial_balance: float
    current_balance: float
    accumulated_loss: float = 0.0
```

#### `DCFInputs`
Assumptions and macroeconomic drivers for 10-year cash flow modeling.
```python
class DCFInputs(BaseModel):
    purchase_price: float
    hold_period_years: int = 10
    exit_cap_rate: float = 0.065
    discount_rate: float = 0.09
    initial_revenue: float
    initial_expenses: float
    revenue_growth_rate: float = 0.03
    expense_growth_rate: float = 0.025
    capex_reserve_pct: float = 0.03
    financing_ltv: float = 0.65
    financing_interest_rate: float = 0.065
    debt_term_years: int = 30
```

---

### 1.3 Financial Helper Functions

- `calculate_cap_rate(noi: float, value: float) -> float`: Calculates capitalization rate $\frac{\text{NOI}}{\text{Value}}$.
- `calculate_debt_yield(noi: float, loan_amount: float) -> float`: Calculates debt yield $\frac{\text{NOI}}{\text{Loan Amount}}$.
- `calculate_dscr(noi: float, annual_debt_service: float) -> float`: Calculates Debt Service Coverage Ratio $\frac{\text{NOI}}{\text{Debt Service}}$.
- `calculate_ltv(loan_amount: float, property_value: float) -> float`: Calculates Loan-to-Value ratio.
- `calculate_break_even_occupancy(operating_expenses: float, debt_service: float, gross_potential_rent: float) -> float`: Computes required occupancy to cover OpEx and debt payments.

---

## 2. Discounted Cash Flow Engine

**Module**: `valugraph_mcp.dcf`

### `calculate_npv(rate: float, cash_flows: list[float]) -> float`
Computes net present value of periodic cash flows at a given discount rate.

### `calculate_irr(cash_flows: list[float], guess: float = 0.10, max_iter: int = 1000, tol: float = 1e-7) -> float`
Solves for Internal Rate of Return using Newton-Raphson with an analytical first-derivative and automatic bisection search fallback over $[-0.90, 5.0]$.

### `class DCFEngine`
The primary multi-scenario discounted cash flow modeler.

#### Methods:
- `calculate_annual_debt_service(principal: float, interest_rate: float, amortization_years: int) -> float`: Calculates constant annual mortgage payment using the standard annuity formula.
- `calculate_remaining_debt_balance(principal: float, interest_rate: float, amortization_years: int, elapsed_years: int) -> float`: Computes unamortized loan balance at year $t$.
- `run_projection(inputs: DCFInputs, scenario: ScenarioType = ScenarioType.BASE, growth_multiplier: float = 1.0, expense_multiplier: float = 1.0, cap_rate_adjustment: float = 0.0) -> ScenarioResult`: Simulates annual revenues, operating expenses, CapEx reserves, debt service, terminal exit valuation, NPV, IRR, and equity multiple for a given scenario.
- `generate_underwriting_report(parcel: PropertyParcel, inputs: DCFInputs) -> UnderwritingReport`: Runs all 4 scenarios (Base, Bull, Bear, Severe Stress), solves debt capacity sizing, evaluates minimum DSCR, and synthesizes an underwriting verdict.

---

## 3. CMBS Risk & Waterfall Engine

**Module**: `valugraph_mcp.cmbs`

### `class CMBSRiskEngine`
Quantitative risk modeler for commercial mortgage-backed securities pools and securitization tranches.

#### Methods:
- `calculate_pool_summary(loans: list[CMBSLoan]) -> dict[str, float]`: Computes balance-weighted DSCR, LTV, coupon rate, and total pool balance.
- `estimate_loan_default_prob(dscr: float, ltv: float) -> float`: Empirical logistic hazard model estimating loan-level conditional default probability:
  $$z = 2.5 \cdot (\text{LTV} - 0.70) - 3.2 \cdot (\text{DSCR} - 1.20), \quad P = \frac{1}{1 + e^{-z}}$$
- `evaluate_pool_stress(loans: list[CMBSLoan], loss_severity: float = 0.40, rate_shock_bps: float = 0.0) -> dict[str, Any]`: Evaluates pool default probability under interest rate shocks and calculates aggregate expected loss.
- `allocate_waterfall_losses(tranches: list[CMBSTranche], cumulative_pool_loss: float) -> list[dict[str, Any]]`: Distributes cumulative pool dollar losses sequentially bottom-up through the subordination structure (Equity $\to$ B $\to$ BBB $\to$ A $\to$ AA $\to$ AAA).
- `build_synthetic_deal(deal_id: str, deal_name: str, total_balance: float) -> CMBSSecuritization`: Constructs a standard benchmark multi-borrower CMBS conduit deal structure.

---

## 4. Autonomous Diagnosis Engine

**Module**: `valugraph_mcp.diagnosis`

### `class DiagnosisEngine`
Rule-based underwriting engine that scores properties and loan pools.

#### Methods:
- `diagnose_property(parcel: PropertyParcel, loan: CMBSLoan | None = None, rent_roll: RentRoll | None = None, statement: OperatingStatement | None = None) -> PropertyDiagnosis`:
  Computes a 0–100 health score, evaluates DSCR, LTV, debt yield, break-even occupancy, tenant concentration, and near-term lease rollover, and outputs an underwriting decision (`APPROVE`, `CONDITIONALLY_APPROVE`, `REJECT`).
- `diagnose_cmbs_pool(deal: CMBSSecuritization, stress_config: StressTestConfig | None = None) -> PoolDiagnosis`:
  Assesses CMBS collateral pool health, delinquency rate, weighted leverage, stressed loss, and affected tranches.
- `diagnose_underwriting_report(report: UnderwritingReport) -> PropertyDiagnosis`:
  Converts a 4-scenario DCF underwriting report into diagnostic health findings.

---

## 5. Temporal CRE Knowledge Graph

**Module**: `valugraph_mcp.graph`

### `class TemporalCREGraph`
NetworkX-backed property graph representing commercial real estate entities, ownership chains, tenant leases, and mortgage encumbrances.

#### Methods:
- `add_parcel(parcel: PropertyParcel) -> None`: Adds a property vertex.
- `add_owner(owner_id: str, name: str, entity_type: str = "LLC") -> None`: Adds a property sponsor or REIT entity node.
- `link_ownership(owner_id: str, apn: str, acquisition_date: str, purchase_price: float) -> None`: Creates an `OWNS` edge with transaction date and consideration.
- `add_tenant(tenant: Tenant, apn: str) -> None`: Creates a tenant node and connects it via a `LEASES_FROM` edge.
- `add_loan(loan: CMBSLoan) -> None`: Creates a loan node and connects it via an `ENCUMBERS` edge.
- `add_sec_filing(filing_id: str, filing_type: str, filed_date: str, entity_id: str, summary: str = "") -> None`: Links an SEC EDGAR filing to a sponsor entity.
- `get_property_lineage(apn: str) -> list[dict[str, Any]]`: Returns the chronological chain-of-title for a parcel.
- `get_tenants(apn: str) -> list[dict[str, Any]]`: Returns all active tenant leases associated with a parcel.
- `get_encumbrances(apn: str) -> list[dict[str, Any]]`: Returns all active mortgage liens encumbering a parcel.
- `get_neighborhood_subgraph(node_id: str, depth: int = 1) -> dict[str, Any]`: Traverses $k$-hop neighbors and returns subgraphs formatted for LLM consumption.

---

## 6. MCP Server & Tool Definitions

**Module**: `valugraph_mcp.server`

### `create_mcp_server(name: str = "valugraph-mcp") -> MCPServer`
Initializes the FastMCP / MCPServer instance and registers the six underwriting tools:

1. `underwrite_commercial_property`: DCF cash flow scenarios, IRR, and debt capacity sizing.
2. `stress_test_cmbs_pool`: Interest rate shock and waterfall tranche loss modeling.
3. `query_property_graph`: Knowledge graph neighbor search, title history, tenants, and liens.
4. `estimate_debt_capacity`: Loan sizing under dual DSCR and LTV binding constraints.
5. `diagnose_property_risk`: Health score, red flags, and loan approval triage.
6. `diagnose_cmbs_pool`: Collateral pool risk, delinquency check, and tranche impairment.

---

## 7. Command-Line Interface

**Module**: `valugraph_mcp.cli`

- `valugraph info`: Displays subsystem statuses and version information.
- `valugraph underwrite`: Evaluates DCF cash flows and returns rich tables for Base/Bull/Bear/Stress scenarios.
- `valugraph stress-test`: Runs rate-shock simulations against a synthetic or custom CMBS pool and displays waterfall loss distribution.
- `valugraph diagnose`: Evaluates property metrics against risk thresholds and renders health score, decision, strengths, and red flags.
- `valugraph diagnose-pool`: Analyzes CMBS pool delinquency and credit loss metrics.
- `valugraph serve`: Launches the FastMCP server on stdio transport for agent integration.
