"""Comprehensive unit and edge-case tests for the Temporal CRE Knowledge Graph."""

from __future__ import annotations

from valugraph_mcp.graph import TemporalCREGraph
from valugraph_mcp.types import CMBSLoan, PropertyParcel, Tenant


class TestTemporalGraphDeep:
    """Tests for graph mutations, lineage queries, SEC filings, and subgraph extraction."""

    def test_non_existent_parcel_queries(self) -> None:
        """Verify queries on non-existent parcel gracefully return empty results."""
        graph = TemporalCREGraph()
        assert graph.get_property_lineage("UNKNOWN-APN") == []
        assert graph.get_tenants("UNKNOWN-APN") == []
        assert graph.get_encumbrances("UNKNOWN-APN") == []
        subgraph = graph.get_neighborhood_subgraph("UNKNOWN-APN")
        assert subgraph["nodes"] == []
        assert subgraph["edges"] == []
        assert subgraph["node_count"] == 0
        assert subgraph["edge_count"] == 0

    def test_sec_edgar_filing_attachment(self, sample_parcel: PropertyParcel) -> None:
        """Verify SEC 10-K filing node addition and relationship edge citation."""
        graph = TemporalCREGraph()
        graph.add_parcel(sample_parcel)

        filing_id = "SEC-0001018724-26-000001"
        graph.add_sec_filing(
            filing_id=filing_id,
            cik="0001018724",
            form="10-K",
            filing_date="2026-02-15",
            target_id=sample_parcel.apn,
            summary="Annual CRE lease portfolio disclosure",
        )

        assert graph.node_count == 2
        assert graph.edge_count == 1
        node_data = graph.g.nodes[filing_id]
        assert node_data["node_type"] == "sec_filing"
        assert node_data["cik"] == "0001018724"
        assert node_data["form"] == "10-K"

    def test_chronological_ownership_transfers(self, sample_parcel: PropertyParcel) -> None:
        """Verify get_property_lineage returns transfers sorted chronologically."""
        graph = TemporalCREGraph()
        graph.add_parcel(sample_parcel)

        graph.add_owner("OWN-A", "Early Pioneer LLC", "LLC")
        graph.link_ownership("OWN-A", sample_parcel.apn, "2015-06-01", 30000000.0)

        graph.add_owner("OWN-C", "Current Capital Group", "REIT")
        graph.link_ownership("OWN-C", sample_parcel.apn, "2024-01-15", 85000000.0)

        graph.add_owner("OWN-B", "Midway Partners", "LP")
        graph.link_ownership("OWN-B", sample_parcel.apn, "2019-11-20", 52000000.0)

        lineage = graph.get_property_lineage(sample_parcel.apn)
        assert len(lineage) == 3
        dates = [entry["acquisition_date"] for entry in lineage]
        assert dates == ["2015-06-01", "2019-11-20", "2024-01-15"]
        assert lineage[0]["owner_name"] == "Early Pioneer LLC"
        assert lineage[2]["owner_name"] == "Current Capital Group"

    def test_multi_tenant_and_multi_encumbrance_aggregation(
        self, sample_parcel: PropertyParcel
    ) -> None:
        """Verify multiple active leases and senior/mezzanine loans are tracked."""
        graph = TemporalCREGraph()
        graph.add_parcel(sample_parcel)

        t1 = Tenant(
            tenant_id="TEN-1",
            name="Alpha Corp",
            credit_rating="AA",
            leased_sqft=50000.0,
            annual_rent=1500000.0,
            lease_expiry="2030-12-31",
        )
        t2 = Tenant(
            tenant_id="TEN-2",
            name="Beta Logistics",
            credit_rating="BBB",
            leased_sqft=30000.0,
            annual_rent=800000.0,
            lease_expiry="2028-06-30",
        )
        graph.add_tenant(t1, sample_parcel.apn)
        graph.add_tenant(t2, sample_parcel.apn)

        l1 = CMBSLoan(
            loan_id="LN-SR-1",
            property_apn=sample_parcel.apn,
            original_balance=40000000.0,
            current_balance=38000000.0,
            interest_rate=0.06,
            maturity_date="2032-01-01",
            dscr=1.45,
            ltv=0.45,
        )
        l2 = CMBSLoan(
            loan_id="LN-MEZZ-1",
            property_apn=sample_parcel.apn,
            original_balance=10000000.0,
            current_balance=10000000.0,
            interest_rate=0.09,
            maturity_date="2032-01-01",
            dscr=1.15,
            ltv=0.57,
        )
        graph.add_loan(l1)
        graph.add_loan(l2)

        tenants = graph.get_tenants(sample_parcel.apn)
        assert len(tenants) == 2
        tenant_names = {t["name"] for t in tenants}
        assert "Alpha Corp" in tenant_names
        assert "Beta Logistics" in tenant_names

        encumbrances = graph.get_encumbrances(sample_parcel.apn)
        assert len(encumbrances) == 2
        loan_ids = {e["loan_id"] for e in encumbrances}
        assert "LN-SR-1" in loan_ids
        assert "LN-MEZZ-1" in loan_ids

        # Neighborhood subgraph ego query
        subgraph = graph.get_neighborhood_subgraph(sample_parcel.apn, depth=1)
        assert subgraph["node_count"] == 5  # 1 parcel + 2 tenants + 2 loans
        assert subgraph["edge_count"] == 4
