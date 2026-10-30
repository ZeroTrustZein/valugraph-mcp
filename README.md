# ValuGraph-MCP

[![CI](https://github.com/ZeroTrustZein/valugraph-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/ZeroTrustZein/valugraph-mcp/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/badge/coverage-97%25-brightgreen.svg)](https://github.com/ZeroTrustZein/valugraph-mcp)
[![Tests](https://img.shields.io/badge/tests-87%20passed-brightgreen.svg)](https://github.com/ZeroTrustZein/valugraph-mcp)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Types: PEP 561](https://img.shields.io/badge/typing-PEP%20561-blue.svg)](https://peps.python.org/pep-0561/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

**ValuGraph-MCP** is an autonomous commercial real estate (CRE) underwriting and CMBS risk engine featuring a temporal knowledge graph, automated cash-flow DCF stress-testing, and sequential-pay tranche waterfall analytics exposed via the Model Context Protocol (MCP).

---

## Documentation Index

- **[System Architecture & Mathematical Formulations](docs/ARCHITECTURE.md)**: Deep-dive into DCF formulas, hybrid Newton-Raphson/bisection IRR solver, CMBS waterfall loss allocation, logistic default hazard model, and graph schema.
- **[API Reference](docs/API_REFERENCE.md)**: Exhaustive programmatic reference covering all domain models, schemas, enums, utility functions, classes, and MCP tools.
- **[Practical Usage Guide](docs/USAGE_GUIDE.md)**: End-to-end recipes for connecting with OpenCode, Claude Desktop, and Cursor, running terminal CLI commands, executing Python scripts, and orchestrating autonomous agent workflows.

---

## Key Features

- **Multi-Scenario DCF Engine**: Automated 10-year discounted cash flow modeling across 4 scenarios (`Base`, `Bull`, `Bear`, and `Severe Stress`) with numerical IRR solving (Newton-Raphson with bisection fallback), debt service sizing, and exit valuations.
- **CMBS Tranche & Risk Engine**: Commercial Mortgage-Backed Securities pool analytics, weighted-average LTV / DSCR calculation, debt yields, and waterfall tranche credit loss modeling across tranches (AAA through Equity).
- **Autonomous Diagnosis Engine**: Rule-based quantitative diagnostic engine triaging property debt service coverage, leverage, liquidity, tenant concentration, and break-even occupancy into actionable underwriting decisions (`APPROVE`, `CONDITIONALLY_APPROVE`, `REJECT`).
- **Hybrid CRE Knowledge Graph**: Temporal graph structure tracking property parcels, ownership chains, tenant lease expirations, credit concentrations, and mortgage liens.
- **Model Context Protocol (MCP)**: Native FastMCP/MCPServer integration allowing LLM agents to orchestrate underwriting, stress-test CMBS pools, query graph neighbors, and inspect cash flows.
- **Rich Command Line Interface**: Terminal UI for instant property valuation, pool stress-testing, automated diagnostic triage, and running the MCP daemon.

---

## Architecture

```
                       ┌──────────────────────┐
                       │   LLM Agent / MCP    │
                       └──────────┬───────────┘
                                  │ stdio
                       ┌──────────▼───────────┐
                       │   ValuGraph MCP      │
                       │   Server Layer       │
                       └──────────┬───────────┘
           ┌──────────────────────┼──────────────────────┐
           ▼                      ▼                      ▼
┌──────────────────────┐ ┌──────────────────────┐ ┌──────────────────────┐
│ Temporal CRE Graph   │ │ Multi-Scenario DCF   │ │ CMBS Tranche Risk    │
│ Parcel/Owner/Tenant  │ │ IRR / NPV / Debt Cov │ │ Waterfall Loss Model │
└──────────────────────┘ └──────────┬───────────┘ └──────────┬───────────┘
                                    │                        │
                                    └──────────┬─────────────┘
                                               ▼
                                    ┌──────────────────────┐
                                    │   Diagnosis Engine   │
                                    │ Health / Risk Triage │
                                    └──────────────────────┘
```

---

## Quick Start

### Installation

```bash
git clone https://github.com/ZeroTrustZein/valugraph-mcp.git
cd valugraph-mcp
pip install -e ".[dev]"
```

### CLI Usage

```bash
# View engine status and subsystem capabilities
valugraph info

# Underwrite commercial property with 10-year DCF scenarios
valugraph underwrite --apn 042-108-01 --price 12500000 --revenue 1450000 --expenses 420000

# Run automated diagnostic health check on asset
valugraph diagnose --apn 042-108-01 --price 12500000 --noi 1030000 --loan 8125000 --occupancy 0.94

# Stress-test a CMBS loan pool under rate shocks
valugraph stress-test --balance 50000000 --shock-bps 150 --loss-severity 0.40

# Run pool diagnostic triage across tranches and delinquency
valugraph diagnose-pool --balance 50000000 --shock-bps 200 --loss-severity 0.45

# Start MCP server daemon on stdio
valugraph serve
```

---

## MCP Tool Directory

When running as an MCP server, ValuGraph exposes the following tools:

| Tool | Purpose | Primary Inputs |
|---|---|---|
| `underwrite_commercial_property` | 10-year DCF cash flow valuation across 4 scenarios | `apn`, `purchase_price`, `initial_revenue`, `initial_expenses`, `financing_ltv` |
| `stress_test_cmbs_pool` | Macro rate shock stress-testing and waterfall loss allocation | `deal_id`, `total_balance`, `rate_shock_bps`, `loss_severity` |
| `query_property_graph` | Knowledge graph search for ownership lineage, leases, and liens | `apn`, `depth` |
| `estimate_debt_capacity` | Sizing senior loan capacity under DSCR and LTV constraints | `net_operating_income`, `property_value`, `min_dscr`, `max_ltv` |
| `diagnose_property_risk` | Health score, red flag triage, and underwriting approval verdict | `apn`, `purchase_price`, `current_noi`, `loan_amount`, `occupancy_rate` |
| `diagnose_cmbs_pool` | Pool delinquency, tranche impairment, and pool health score | `deal_id`, `total_balance`, `rate_shock_bps`, `loss_severity` |

### MCP Client Integration

Add ValuGraph to your MCP client config (e.g., OpenCode, Claude Desktop, Cursor):

```json
{
  "mcpServers": {
    "valugraph": {
      "command": "python",
      "args": ["-m", "valugraph_mcp.cli", "serve"]
    }
  }
}
```

---

## Development & Verification

```bash
# Run test suite
pytest

# Run tests with coverage report
pytest --cov=valugraph_mcp --cov-report=term-missing

# Lint and format checks
ruff check .
ruff format --check .
```

---

## License

MIT License. Copyright (c) 2026 Zein Dergham.
