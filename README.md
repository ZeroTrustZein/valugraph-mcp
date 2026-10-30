# ValuGraph-MCP

[![CI](https://github.com/ZeroTrustZein/valugraph-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/ZeroTrustZein/valugraph-mcp/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

**ValuGraph-MCP** is an autonomous multi-agent commercial real estate (CRE) underwriting and CMBS risk engine featuring a hybrid graph-vector RAG pipeline, automated cash-flow DCF stress-testing, and live financial data ingestion exposed via the Model Context Protocol (MCP).

## Key Features

- **Multi-Scenario DCF Engine**: Automated 10-year discounted cash flow modeling (Base, Bull, Bear, and Severe Stress) with numerical IRR solving (Newton-Raphson with bisection fallback), debt service sizing, and exit valuations.
- **CMBS Tranche & Risk Engine**: Commercial Mortgage-Backed Securities pool analytics, weighted-average LTV / DSCR calculation, debt yields, and waterfall tranche credit loss modeling across tranches (AAA through Equity).
- **Autonomous Diagnosis Engine**: Rule-based quantitative diagnostic engine triaging property debt service coverage, leverage, liquidity, tenant concentration, and break-even occupancy into actionable underwriting decisions (`APPROVE`, `CONDITIONALLY_APPROVE`, `REJECT`).
- **Hybrid CRE Knowledge Graph**: Temporal graph structure tracking property parcels, ownership chains, tenant lease expirations, credit concentrations, and mortgage liens.
- **Model Context Protocol (MCP)**: Native FastMCP/MCPServer integration allowing LLM agents to orchestrate underwriting, stress-test CMBS pools, query graph neighbors, and inspect cash flows.
- **Command Line Interface**: Rich terminal UI for instant property valuation, pool stress-testing, automated diagnostic triage, and running the MCP daemon.

## Architecture

```
                       ┌──────────────────────┐
                       │   LLM Agent / MCP    │
                       └──────────┬───────────┘
                                  │ stdio / SSE
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

# Underwrite commercial property with DCF scenarios
valugraph underwrite --apn 042-108-01 --price 12500000 --revenue 1450000 --expenses 420000

# Run automated diagnostic health check on asset
valugraph diagnose --apn 042-108-01 --price 12500000 --noi 1030000 --loan 8125000 --occupancy 0.94

# Stress-test a CMBS loan pool
valugraph stress-test --balance 50000000 --shock-bps 150 --loss-severity 0.40

# Run pool diagnostic triage across tranches and delinquency
valugraph diagnose-pool --balance 50000000 --shock-bps 200 --loss-severity 0.45

# Start MCP server daemon
valugraph serve
```

## MCP Integration

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

## License

MIT License. Copyright (c) 2026 Zein Dergham.
