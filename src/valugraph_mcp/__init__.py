"""ValuGraph-MCP: Commercial Real Estate Underwriting and CMBS Risk Engine."""

from __future__ import annotations

__version__ = "0.1.0"

from valugraph_mcp.cmbs import CMBSRiskEngine
from valugraph_mcp.dcf import DCFEngine, calculate_irr
from valugraph_mcp.graph import TemporalCREGraph
from valugraph_mcp.server import create_mcp_server

__all__ = [
    "CMBSRiskEngine",
    "DCFEngine",
    "TemporalCREGraph",
    "__version__",
    "calculate_irr",
    "create_mcp_server",
]
