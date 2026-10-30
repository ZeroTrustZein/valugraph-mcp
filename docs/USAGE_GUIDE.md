# ValuGraph-MCP: Practical Usage Guide

This guide provides practical recipes, configuration templates, CLI commands, and programmatic Python walkthroughs for integrating, configuring, and operating **`valugraph-mcp`** across underwriting pipelines, quantitative debt analysis, and LLM agent workflows.

---

## Table of Contents
1. [Recipe 1: Connecting with MCP Clients (OpenCode, Claude Desktop, Cursor)](#recipe-1-connecting-with-mcp-clients-opencode-claude-desktop-cursor)
2. [Recipe 2: Property Valuation & Multi-Scenario DCF Modeling](#recipe-2-property-valuation--multi-scenario-dcf-modeling)
3. [Recipe 3: CMBS Securitization Stress-Testing & Waterfall Losses](#recipe-3-cmbs-securitization-stress-testing--waterfall-losses)
4. [Recipe 4: Automated Property Diagnostic Triage & Health Scoring](#recipe-4-automated-property-diagnostic-triage--health-scoring)
5. [Recipe 5: CMBS Collateral Pool Risk & Delinquency Diagnostics](#recipe-5-cmbs-collateral-pool-risk--delinquency-diagnostics)
6. [Recipe 6: Building & Querying the Temporal CRE Knowledge Graph](#recipe-6-building--querying-the-temporal-cre-knowledge-graph)
7. [Recipe 7: Sizing Maximum Senior Debt Under DSCR & LTV Constraints](#recipe-7-sizing-maximum-senior-debt-under-dscr--ltv-constraints)
8. [Recipe 8: Orchestrating an Autonomous LLM Underwriter](#recipe-8-orchestrating-an-autonomous-llm-underwriter)

---

## Recipe 1: Connecting with MCP Clients (OpenCode, Claude Desktop, Cursor)

ValuGraph-MCP exposes native JSON-RPC 2.0 tools over `stdio`.

### OpenCode Configuration
Add to your global `~/.config/opencode/opencode.json` or workspace `.opencode/mcp.json`:

```json
{
  "mcp": {
    "valugraph": {
      "command": "python",
      "args": ["-m", "valugraph_mcp.cli", "serve"]
    }
  }
}
```

### Claude Desktop Configuration
Add to `%APPDATA%\Claude\claude_desktop_config.json` (Windows) or `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS):

```json
{
  "mcpServers": {
    "valugraph": {
      "command": "valugraph",
      "args": ["serve"]
    }
  }
}
```

### Cursor Configuration
In Cursor Settings $\to$ MCP:
- **Name**: `valugraph`
- **Type**: `command`
- **Command**: `valugraph serve`

---

## Recipe 2: Property Valuation & Multi-Scenario DCF Modeling

### Via Terminal CLI
Run 10-year multi-scenario DCF underwriting directly from your terminal:

```bash
valugraph underwrite \
  --apn "APN-042-108-01" \
  --price 12500000 \
  --revenue 1450000 \
  --expenses 420000 \
  --hold 10 \
  --ltv 0.65 \
  --rate 0.065
```

Output:
```
                       ValuGraph DCF Underwriting: APN-042-108-01
┏━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━┓
┃ Scenario      ┃ IRR    ┃ NPV ($)     ┃ Equity Multiple ┃ Terminal Value ($) ┃
┡━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━┩
│ Base          │ 14.12% │ $1,842,501  │ 2.41x           │ $18,450,210        │
│ Bull          │ 19.85% │ $3,450,119  │ 3.12x           │ $22,100,500        │
│ Bear          │ 8.42%  │ -$125,400   │ 1.62x           │ $14,200,000        │
│ Severe Stress │ 3.15%  │ -$1,150,000 │ 1.18x           │ $11,800,000        │
└───────────────┴────────┴─────────────┴─────────────────┴────────────────────┘
Recommended Max Debt: $8,125,000
Average DSCR: 1.48x (Min: 1.32x)
Solid cash-flow profile under Base and Bull scenarios; robust debt coverage.
```

### Via Python API
```python
from valugraph_mcp.dcf import DCFEngine
from valugraph_mcp.types import DCFInputs, PropertyParcel, PropertyType

parcel = PropertyParcel(
    apn="APN-042-108-01",
    address="452 Innovation Blvd, Austin, TX",
    property_type=PropertyType.OFFICE,
    gross_sqft=85000,
    rentable_sqft=80000,
    year_built=2021,
    purchase_price=12500000.0,
    current_noi=1030000.0,
)

inputs = DCFInputs(
    purchase_price=12500000.0,
    hold_period_years=10,
    initial_revenue=1450000.0,
    initial_expenses=420000.0,
    financing_ltv=0.65,
    financing_interest_rate=0.065,
)

engine = DCFEngine()
report = engine.generate_underwriting_report(parcel, inputs)

print(f"Base IRR: {report.base_scenario.irr * 100:.2f}%")
print(f"Base NPV: ${report.base_scenario.npv:,.2f}")
print(f"Verdict: {report.conclusion}")
```

---

## Recipe 3: CMBS Securitization Stress-Testing & Waterfall Losses

Simulate an interest rate shock and evaluate which tranches absorb losses.

### Via Terminal CLI
```bash
valugraph stress-test \
  --balance 50000000 \
  --shock-bps 200 \
  --loss-severity 0.45
```

Output:
```
                   CMBS Subordination Waterfall (VALU-2026-C1)
┏━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┓
┃ Tranche ┃ Attach-Detach ┃ Initial Bal ($)┃ Loss Allocated ($┃ Remaining Bal ($) ┃ Impairment ┃
┡━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━┩
│ Equity  │ 0% - 5%       │ $2,500,000     │ $2,500,000       │ $0                │ 100.0%     │
│ B       │ 5% - 10%      │ $2,500,000     │ $1,840,250       │ $659,750          │ 73.6%      │
│ BBB     │ 10% - 18%     │ $4,000,000     │ $0               │ $4,000,000        │ 0.0%       │
│ A       │ 18% - 28%     │ $5,000,000     │ $0               │ $5,000,000        │ 0.0%       │
│ AAA     │ 28% - 100%    │ $36,000,000    │ $0               │ $36,000,000       │ 0.0%       │
└━━━━━━━━━┴━━━━━━━━━━━━━━━┴━━━━━━━━━━━━━━━━┴━━━━━━━━━━━━━━━━━━┴━━━━━━━━━━━━━━━━━━━┴━━━━━━━━━━━━┘
Total Pool Expected Loss: $4,340,250 (8.68%)
```

---

## Recipe 4: Automated Property Diagnostic Triage & Health Scoring

Run the quantitative diagnosis engine to identify red flags, coverage deficits, and underwriting decisions.

### Via Terminal CLI
```bash
valugraph diagnose \
  --apn "APN-042-108-01" \
  --price 12500000 \
  --noi 1030000 \
  --loan 8125000 \
  --occupancy 0.94 \
  --gpr 1450000 \
  --opex 420000
```

Output:
```
                 ValuGraph Property Diagnosis: APN-042-108-01
┏━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Metric               ┃ Value      ┃ Status / Benchmark                         ┃
┡━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Health Score         │ 85.0/100   │ Risk: LOW                                  │
│ Decision             │ APPROVE    │ Underwriting Verdict                       │
│ Cap Rate             │ 8.24%      │ NOI / Value                                │
│ Debt Yield           │ 12.68%     │ Target >= 8.0%                             │
│ Senior LTV           │ 65.0%      │ Target <= 75.0%                            │
│ Break-even Occupancy │ 69.8%      │ Current: 94.0%                             │
└──────────────────────┴────────────┴────────────────────────────────────────────┘
Strengths:
  • Strong debt service coverage (DSCR >= 1.35x)
  • Robust debt yield (Debt Yield >= 10.0%)
  • Healthy in-place occupancy (>= 90%)
  • Comfortable break-even occupancy margin (< 75%)
```

---

## Recipe 5: CMBS Collateral Pool Risk & Delinquency Diagnostics

Triage an entire CMBS securitization pool across delinquency, rate shocks, and tranche health:

```bash
valugraph diagnose-pool \
  --balance 100000000 \
  --shock-bps 150 \
  --loss-severity 0.40
```

Output:
```
                ValuGraph CMBS Pool Diagnosis: VALU-2026-C1
┏━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Metric           ┃ Value      ┃ Status / Benchmark                     ┃
┡━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ Health Score     │ 88.0/100   │ Risk: LOW                              │
│ Weighted DSCR    │ 1.37x      │ Target >= 1.25x                        │
│ Weighted LTV     │ 62.1%      │ Target <= 70.0%                        │
│ Delinquency Rate │ 0.0%       │ Target <= 2.0%                         │
│ Stressed Loss    │ 2.45%      │ Expected pool loss                     │
│ Impaired Tranches│ Equity     │ Tranches suffering principal loss      │
└──────────────────┴────────────┴────────────────────────────────────────┘
```

---

## Recipe 6: Building & Querying the Temporal CRE Knowledge Graph

Track property ownership, tenant roll, liens, and corporate entity lineage:

```python
from valugraph_mcp.graph import TemporalCREGraph
from valugraph_mcp.types import CMBSLoan, PropertyParcel, PropertyType, Tenant

graph = TemporalCREGraph()

# 1. Register Property Parcel
parcel = PropertyParcel(
    apn="APN-TEX-501",
    address="100 Congress Ave, Austin, TX",
    property_type=PropertyType.OFFICE,
    gross_sqft=200000,
    rentable_sqft=190000,
    year_built=2018,
    purchase_price=45000000.0,
    current_noi=3200000.0,
)
graph.add_parcel(parcel)

# 2. Add Sponsors and Chain of Title
graph.add_owner("OWN-001", "Lone Star Real Estate Partners", entity_type="Fund LP")
graph.link_ownership("OWN-001", parcel.apn, "2019-03-01", 38000000.0)

# 3. Add Leases
graph.add_tenant(
    Tenant(
        tenant_id="TEN-101",
        name="Silicon Cloud Inc",
        credit_rating="A",
        leased_sqft=50000,
        annual_rent=1750000.0,
        lease_expiry="2031-12-31",
    ),
    parcel.apn,
)

# 4. Add Senior Mortgage Lien
graph.add_loan(
    CMBSLoan(
        loan_id="LN-TEX-1",
        property_apn=parcel.apn,
        original_balance=27000000.0,
        current_balance=26200000.0,
        interest_rate=0.061,
        maturity_date="2034-03-01",
        dscr=1.42,
        ltv=0.58,
    )
)

# 5. Query Lineage and Neighbors
print("Chain of Title:", graph.get_property_lineage(parcel.apn))
print("Tenants:", graph.get_tenants(parcel.apn))
print("Liens:", graph.get_encumbrances(parcel.apn))
```

---

## Recipe 7: Sizing Maximum Senior Debt Under DSCR & LTV Constraints

Programmatically determine the maximum debt a property can support without violating lender covenants:

```python
from valugraph_mcp.server import create_mcp_server

server = create_mcp_server()

# Size debt for a $20M property generating $1.6M NOI
# Constraints: Min DSCR 1.25x, Max LTV 65%, 6.5% interest rate, 30-year amort
capacity = server._tools["estimate_debt_capacity"](
    net_operating_income=1600000.0,
    property_value=20000000.0,
    min_dscr=1.25,
    max_ltv=0.65,
    interest_rate=0.065,
    amortization_years=30,
)

print(f"Binding Constraint: {capacity['binding_constraint']}")
print(f"Recommended Debt: ${capacity['recommended_max_debt']:,.2f}")
print(f"Effective LTV: {capacity['effective_ltv'] * 100:.1f}%")
print(f"Debt Yield: {capacity['debt_yield'] * 100:.2f}%")
```

---

## Recipe 8: Orchestrating an Autonomous LLM Underwriter

When connected to an LLM agent (e.g., via OpenCode or Claude Desktop), the agent can execute multi-step underwriting autonomously:

**Sample User Prompt**:
> "Underwrite the commercial office building at APN 042-108-01 valued at $12,500,000. It has $1.45M gross revenue and $420k expenses. Run DCF, size maximum senior debt at 1.25x DSCR / 65% LTV, diagnose property credit health, and give me a loan committee recommendation."

**Agent Autonomous Execution**:
1. Agent calls `underwrite_commercial_property` $\to$ gets 10-year DCF cash flows across Base, Bull, Bear, and Severe Stress.
2. Agent calls `estimate_debt_capacity` $\to$ solves for max loan amount constrained by DSCR and LTV caps.
3. Agent calls `diagnose_property_risk` $\to$ runs the quantitative diagnosis engine, receiving a health score (e.g. `85/100`), strengths, and red flags.
4. Agent synthesizes a complete investment committee memorandum with exact numbers, sensitivities, and loan covenants.
