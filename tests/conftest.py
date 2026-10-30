"""Pytest fixtures for ValuGraph-MCP."""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from valugraph_mcp.cmbs import CMBSRiskEngine
from valugraph_mcp.types import (
    CMBSSecuritization,
    DCFInputs,
    PropertyParcel,
    PropertyType,
    Tenant,
)


@pytest.fixture
def cli_runner() -> CliRunner:
    """CLI test runner fixture."""
    return CliRunner()


@pytest.fixture
def sample_parcel() -> PropertyParcel:
    """Fixture providing a standard commercial office parcel."""
    return PropertyParcel(
        apn="APN-042-108-01",
        address="100 Wall Street, New York, NY 10005",
        property_type=PropertyType.OFFICE,
        gross_sqft=250000.0,
        rentable_sqft=240000.0,
        year_built=2014,
        purchase_price=85000000.0,
        current_noi=5800000.0,
        occupancy_rate=0.92,
    )


@pytest.fixture
def sample_dcf_inputs() -> DCFInputs:
    """Fixture providing standard DCF underwriting assumptions."""
    return DCFInputs(
        purchase_price=10000000.0,
        hold_period_years=10,
        exit_cap_rate=0.065,
        discount_rate=0.09,
        initial_revenue=1200000.0,
        initial_expenses=350000.0,
        revenue_growth_rate=0.03,
        expense_growth_rate=0.025,
        financing_ltv=0.65,
        financing_interest_rate=0.065,
        debt_term_years=30,
    )


@pytest.fixture
def sample_tenant() -> Tenant:
    """Fixture providing a prime commercial tenant."""
    return Tenant(
        tenant_id="TEN-101",
        name="Apex Quant Strategies LLC",
        credit_rating="AA",
        leased_sqft=65000.0,
        annual_rent=1950000.0,
        lease_expiry="2032-12-31",
    )


@pytest.fixture
def sample_cmbs_deal() -> CMBSSecuritization:
    """Fixture providing a synthetic benchmark CMBS securitization deal."""
    engine = CMBSRiskEngine()
    return engine.build_synthetic_deal(total_balance=100000000.0)
