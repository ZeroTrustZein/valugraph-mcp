# ValuGraph-MCP: Architecture & Technical Deep-Dive

This document provides a comprehensive technical breakdown of the architecture, algorithmic formulations, mathematical models, and subsystem designs behind **`valugraph-mcp`** (Autonomous CRE Underwriting & CMBS Risk Engine).

---

## 1. System Overview & Engineering Philosophy

Commercial Real Estate (CRE) underwriting and structured debt analysis historically rely on manual spreadsheets, fragmented public filings, and opaque risk underwriting. ValuGraph-MCP formalizes these financial workflows into an autonomous, type-safe, and graph-integrated framework exposed via the Model Context Protocol (MCP).

### Core Design Principles
1. **Deterministic Financial Math**: Zero black-box assumptions. All internal rate of return (IRR) equations, debt sizing formulas, waterfall loss distributions, and capitalization rate math are deterministic and numerically validated.
2. **Hybrid Graph Modeling**: Real estate risk cannot be understood in isolation. The system couples multi-scenario discounted cash flow (DCF) models with a temporal knowledge graph that tracks ownership sponsors, tenant lease expirations, mortgage liens, and SEC EDGAR filings.
3. **Structured Subordination Risk**: CMBS securitizations are modeled as sequential-pay waterfalls. The engine calculates tranche attachment/detachment points, debt yields, and credit loss allocations under macroeconomic rate and vacancy shocks.
4. **Autonomous Diagnostic Triaging**: Beyond raw numbers, a rule-based quantitative diagnostic engine triages debt coverage, leverage, liquidity, tenant concentration, and break-even occupancy into actionable underwriting decisions (`APPROVE`, `CONDITIONALLY_APPROVE`, `REJECT`).
5. **Standard Model Context Protocol**: LLM agents (Claude Desktop, OpenCode, Cursor) interact via standardized JSON-RPC 2.0 tool endpoints over `stdio`.

---

## 2. High-Level Subsystem Architecture

```
                          ┌─────────────────────────────────────┐
                          │    LLM Agent / MCP Client           │
                          │ (OpenCode, Claude Desktop, Cursor)  │
                          └──────────────────┬──────────────────┘
                                             │ JSON-RPC 2.0 / stdio
                          ┌──────────────────▼──────────────────┐
                          │      ValuGraph MCP Server           │
                          │      (FastMCP / MCPServer)          │
                          └──────────────────┬──────────────────┘
                                             │
      ┌────────────────────────┬─────────────┴────────────┬────────────────────────┐
      ▼                        ▼                          ▼                        ▼
┌───────────────┐     ┌──────────────────┐     ┌─────────────────────┐   ┌───────────────────┐
│ Temporal CRE  │     │ Multi-Scenario   │     │ CMBS Tranche Risk   │   │ Autonomous        │
│ Graph Engine  │     │ DCF Engine       │     │ & Waterfall Engine  │   │ Diagnosis Engine  │
│ (NetworkX)    │     │ (Newton-Raphson) │     │ (Credit Losses)     │   │ (Health Scoring)  │
└───────┬───────┘     └────────┬─────────┘     └──────────┬──────────┘   └─────────┬─────────┘
        │                      │                          │                        │
        └──────────────────────┴─────────────┬────────────┴────────────────────────┘
                                             ▼
                               ┌───────────────────────────┐
                               │  Domain Types & Contracts │
                               │  (Pydantic V2 / Enums)    │
                               └───────────────────────────┘
```

---

## 3. Subsystem Deep-Dive

### 3.1 Domain Types & Contracts (`valugraph_mcp.types`)
Built on Pydantic v2 with runtime validation and domain-specific validators:
- **`PropertyParcel`**: Physical and financial parcel baseline (`apn`, `purchase_price`, `current_noi`, `gross_sqft`, `occupancy_rate`, `cap_rate`).
- **`Lease` & `RentRoll`**: Granular commercial tenant lease contracts (`NNN`, `Modified Gross`, `Full Service`) with escalation rates and area rollups.
- **`OperatingStatement`**: Granular income/expense line items (GPR, vacancy loss, EGI, real estate taxes, insurance, management fees, NOI).
- **`CMBSLoan` & `CMBSTranche`**: Mortgage debt and securitization capital stack structures (AAA through First-Loss Equity).
- **`DiagnosticFinding` & `PropertyDiagnosis`**: Structured triage findings, severity classifications, and underwriting verdicts.

### 3.2 Multi-Scenario DCF Engine (`valugraph_mcp.dcf`)
Performs 10-year discounted cash flow projections across four core scenarios:
1. **Base Case**: In-place contractual growth ($g_{rev} = 3.0\%$, $g_{exp} = 2.5\%$, terminal cap rate unchanged).
2. **Bull Case**: Accelerated rent growth ($1.5\times$ growth multiplier, $0.9\times$ expense multiplier, 50 bps cap rate compression).
3. **Bear Case**: Stagnant rent and inflationary expenses ($0.5\times$ growth multiplier, $1.3\times$ expense multiplier, 75 bps cap rate expansion).
4. **Severe Stress**: Downturn stress ($0.0\times$ growth multiplier, $1.6\times$ expense multiplier, 150 bps cap rate expansion).

#### Mathematical Formulations
- **Net Present Value (NPV)**:
  $$\text{NPV}(r) = \sum_{t=0}^{N} \frac{CF_t}{(1 + r)^t}$$
- **Internal Rate of Return (IRR)**:
  Solved via hybrid **Newton-Raphson** iteration:
  $$r_{k+1} = r_k - \frac{\text{NPV}(r_k)}{\text{NPV}'(r_k)}$$
  Where the first derivative is:
  $$\text{NPV}'(r) = - \sum_{t=1}^{N} \frac{t \cdot CF_t}{(1 + r)^{t+1}}$$
  If the derivative vanishes ($|\text{NPV}'(r)| < 10^{-12}$) or fails to converge, the engine seamlessly activates a bounded **bisection search fallback** across $[-0.90, 5.0]$.
- **Constant Annual Debt Service**:
  $$\text{ADS} = P \cdot \frac{r(1 + r)^n}{(1 + r)^n - 1}$$
- **Unamortized Loan Balance**:
  $$B_t = P \cdot \frac{(1 + r)^n - (1 + r)^t}{(1 + r)^n - 1}$$

### 3.3 CMBS Risk & Tranche Waterfall Engine (`valugraph_mcp.cmbs`)
Models commercial mortgage-backed securities pools and evaluates tranche impairment:
- **Pool Weighted Averages**: Balance-weighted DSCR, LTV, and coupon metrics:
  $$\overline{\text{DSCR}} = \frac{\sum (DSCR_i \cdot Balance_i)}{\sum Balance_i}$$
- **Default Probability Modeling**:
  Empirical logistic hazard formulation linking leverage (LTV) and coverage (DSCR) to conditional default probability:
  $$z = 2.5 \cdot (\text{LTV} - 0.70) - 3.2 \cdot (\text{DSCR} - 1.20)$$
  $$P(\text{Default}) = \frac{1}{1 + e^{-z}}$$
- **Sequential-Pay Waterfall Loss Allocation**:
  Losses are absorbed strictly bottom-up by attachment point:
  $$\text{Equity} \to \text{B} \to \text{BBB} \to \text{A} \to \text{AA} \to \text{AAA}$$
  For each tranche $k$ with initial balance $B_k$, allocated loss $L_k$ is:
  $$L_k = \min(\text{Remaining Unallocated Loss}, B_k)$$
  $$\text{Remaining Balance}_k = B_k - L_k$$

### 3.4 Autonomous Diagnosis Engine (`valugraph_mcp.diagnosis`)
Evaluates credit risk and operational health by computing a deterministic 0–100 health score with penalties:
- **Baseline**: 100.0 points.
- **Coverage Penalties**:
  - $\text{DSCR} < 1.0$: Critical default risk ($-35$ pts, `CRITICAL`, triggers auto-`REJECT`).
  - $1.0 \le \text{DSCR} < 1.20$: Elevated refinancing risk ($-18$ pts, `HIGH`).
  - $1.20 \le \text{DSCR} < 1.35$: Moderate coverage ($-7$ pts, `MODERATE`).
- **Leverage Penalties**:
  - $\text{LTV} > 80\%$: Excessive leverage ($-25$ pts, `HIGH`).
  - $70\% < \text{LTV} \le 80\%$: Elevated leverage ($-12$ pts, `MODERATE`).
- **Debt Yield Penalties**:
  - $\text{Debt Yield} < 7.0\%$: Inadequate lender yield ($-15$ pts, `HIGH`).
  - $7.0\% \le \text{Debt Yield} < 8.5\%$: Marginal yield ($-8$ pts, `MODERATE`).
- **Occupancy & Concentration Penalties**:
  - Break-even occupancy $> 85\%$: Vulnerable operating margin ($-10$ pts).
  - Single tenant concentration $> 40\%$ rentable area: Concentration risk ($-12$ pts).
  - Imminent lease rollover within 2 years $> 30\%$: Re-leasing risk ($-10$ pts).
- **Underwriting Decision Rule**:
  - Health Score $\ge 80$ and zero critical/high findings $\implies$ **`APPROVE`**
  - Health Score $\ge 60$ and zero critical findings $\implies$ **`CONDITIONALLY_APPROVE`**
  - Health Score $< 60$ or any critical finding $\implies$ **`REJECT`**

### 3.5 Temporal CRE Knowledge Graph (`valugraph_mcp.graph`)
Implements an in-memory multidirected property graph (`networkx.MultiDiGraph`) capturing commercial real estate relationships:
- **Nodes**: `Property` (APN), `Entity` (Sponsor / Owner / REIT), `Tenant` (Corporate Name, Rating), `Loan` (Lien, Note Balance), `Filing` (SEC EDGAR Form 8-K / 10-K).
- **Edges**:
  - `OWNS`: Chronological title history with acquisition date and price.
  - `LEASES_FROM`: Tenant lease terms, rented sqft, and annual rent.
  - `ENCUMBERS`: Mortgage loan security deeds and trust agreements.
  - `MENTIONED_IN`: SEC EDGAR regulatory and financial filing linkages.
- **Traversal & Lineage**: Fast $k$-hop neighborhood queries (`get_neighborhood_subgraph`), full chronological chain-of-title reconstruction (`get_property_lineage`), and encumbrance tracking (`get_encumbrances`).

---

## 4. MCP Server & Tool Protocol Interface

The server (`valugraph_mcp.server.create_mcp_server`) exposes five core tools:

| MCP Tool Name | Primary Purpose | Key Parameters |
|---|---|---|
| `underwrite_commercial_property` | 10-year multi-scenario DCF valuation & debt sizing | `apn`, `purchase_price`, `initial_revenue`, `initial_expenses`, `financing_ltv` |
| `stress_test_cmbs_pool` | Macro interest rate and vacancy shock waterfall loss allocation | `deal_id`, `total_balance`, `rate_shock_bps`, `loss_severity` |
| `query_property_graph` | Subgraph neighborhood, title lineage, tenants, and liens | `apn`, `depth` |
| `estimate_debt_capacity` | Maximum senior loan sizing constrained by DSCR and LTV caps | `net_operating_income`, `property_value`, `min_dscr`, `max_ltv` |
| `diagnose_property_risk` | Health score, red flag triage, and underwriting approval verdict | `apn`, `purchase_price`, `current_noi`, `loan_amount`, `occupancy_rate` |
| `diagnose_cmbs_pool` | Pool delinquency, tranche impairment, and pool health score | `deal_id`, `total_balance`, `rate_shock_bps`, `loss_severity` |

---

## 5. Security & Determinism Guarantees

- **No Network Egress for Core Math**: All DCF, IRR, and CMBS loss allocations run entirely locally with zero external network overhead or token-cost dependencies.
- **Type Safety**: Strictly validated with Pydantic v2 domain schemas and PEP 561 compliance (`py.typed`).
- **Memory Footprint**: In-memory NetworkX directed graph structure ensures $O(V + E)$ space complexity, suitable for low-overhead embedded execution.
