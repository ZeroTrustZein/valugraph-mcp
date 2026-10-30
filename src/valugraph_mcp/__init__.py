"""ValuGraph-MCP: Commercial Real Estate Underwriting and CMBS Risk Engine."""

from __future__ import annotations

__version__ = "0.1.0"

from valugraph_mcp.cmbs import CMBSRiskEngine
from valugraph_mcp.dcf import DCFEngine, calculate_irr
from valugraph_mcp.graph import TemporalCREGraph
from valugraph_mcp.server import create_mcp_server
from valugraph_mcp.types import (
    CMBSLoan,
    CMBSPoolSummary,
    CMBSSecuritization,
    CMBSTranche,
    DCFInputs,
    Lease,
    LeaseType,
    LoanStatus,
    OperatingStatement,
    PropertyParcel,
    PropertyType,
    RentRoll,
    RiskLevel,
    ScenarioResult,
    ScenarioType,
    Tenant,
    UnderwritingReport,
    ValuationMetrics,
)

__all__ = [
    "CMBSLoan",
    "CMBSPoolSummary",
    "CMBSRiskEngine",
    "CMBSSecuritization",
    "CMBSTranche",
    "DCFEngine",
    "DCFInputs",
    "Lease",
    "LeaseType",
    "LoanStatus",
    "OperatingStatement",
    "PropertyParcel",
    "PropertyType",
    "RentRoll",
    "RiskLevel",
    "ScenarioResult",
    "ScenarioType",
    "TemporalCREGraph",
    "Tenant",
    "UnderwritingReport",
    "ValuationMetrics",
    "__version__",
    "calculate_irr",
    "create_mcp_server",
]
