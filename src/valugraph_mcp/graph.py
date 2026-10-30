"""Temporal CRE Knowledge Graph modeling parcels, ownership, debt liens, and tenants."""

from __future__ import annotations

from typing import Any

import networkx as nx

from valugraph_mcp.types import (
    CMBSLoan,
    PropertyParcel,
    Tenant,
)


class TemporalCREGraph:
    """NetworkX-backed knowledge graph for commercial real estate underwriting."""

    def __init__(self) -> None:
        self.g = nx.MultiDiGraph()

    @property
    def node_count(self) -> int:
        return self.g.number_of_nodes()

    @property
    def edge_count(self) -> int:
        return self.g.number_of_edges()

    def add_parcel(self, parcel: PropertyParcel) -> None:
        """Add commercial property parcel node to knowledge graph."""
        self.g.add_node(
            parcel.apn,
            node_type="property",
            address=parcel.address,
            property_type=parcel.property_type.value,
            gross_sqft=parcel.gross_sqft,
            rentable_sqft=parcel.rentable_sqft,
            year_built=parcel.year_built,
            purchase_price=parcel.purchase_price,
            current_noi=parcel.current_noi,
            occupancy_rate=parcel.occupancy_rate,
        )

    def add_owner(self, owner_id: str, name: str, entity_type: str = "LLC") -> None:
        """Add property sponsor or holding company node."""
        self.g.add_node(
            owner_id,
            node_type="entity",
            name=name,
            entity_type=entity_type,
        )

    def link_ownership(
        self,
        owner_id: str,
        apn: str,
        acquisition_date: str,
        purchase_price: float,
    ) -> None:
        """Link an owner to a property via OWNS edge."""
        self.g.add_edge(
            owner_id,
            apn,
            key=f"owns_{acquisition_date}",
            relationship_type="OWNS",
            acquisition_date=acquisition_date,
            purchase_price=purchase_price,
        )

    def add_tenant(self, tenant: Tenant, apn: str) -> None:
        """Add tenant node and connect to property via LEASES_FROM edge."""
        self.g.add_node(
            tenant.tenant_id,
            node_type="tenant",
            name=tenant.name,
            credit_rating=tenant.credit_rating,
            leased_sqft=tenant.leased_sqft,
            annual_rent=tenant.annual_rent,
            lease_expiry=tenant.lease_expiry,
        )
        self.g.add_edge(
            tenant.tenant_id,
            apn,
            key=f"leases_{tenant.tenant_id}",
            relationship_type="LEASES_FROM",
            leased_sqft=tenant.leased_sqft,
            annual_rent=tenant.annual_rent,
            lease_expiry=tenant.lease_expiry,
        )

    def add_loan(self, loan: CMBSLoan) -> None:
        """Add CMBS mortgage loan node and link to property as ENCUMBERS."""
        self.g.add_node(
            loan.loan_id,
            node_type="loan",
            original_balance=loan.original_balance,
            current_balance=loan.current_balance,
            interest_rate=loan.interest_rate,
            dscr=loan.dscr,
            ltv=loan.ltv,
            maturity_date=loan.maturity_date,
        )
        self.g.add_edge(
            loan.loan_id,
            loan.property_apn,
            key=f"encumbers_{loan.loan_id}",
            relationship_type="ENCUMBERS",
            balance=loan.current_balance,
            interest_rate=loan.interest_rate,
        )

    def add_sec_filing(
        self,
        filing_id: str,
        cik: str,
        form: str,
        filing_date: str,
        target_id: str,
        summary: str,
    ) -> None:
        """Add SEC Edgar filing node and attach citation to target entity or parcel."""
        self.g.add_node(
            filing_id,
            node_type="sec_filing",
            cik=cik,
            form=form,
            filing_date=filing_date,
            summary=summary,
        )
        self.g.add_edge(
            filing_id,
            target_id,
            key=f"cites_{filing_id}",
            relationship_type="CITES",
            filing_date=filing_date,
        )

    def get_property_lineage(self, apn: str) -> list[dict[str, Any]]:
        """Retrieve chronological chain of title and ownership transfers."""
        lineage = []
        if not self.g.has_node(apn):
            return lineage

        for u, v, data in self.g.in_edges(apn, data=True):
            if data.get("relationship_type") == "OWNS":
                owner_data = self.g.nodes.get(u, {})
                lineage.append(
                    {
                        "owner_id": u,
                        "owner_name": owner_data.get("name", u),
                        "entity_type": owner_data.get("entity_type", "Unknown"),
                        "acquisition_date": data.get("acquisition_date"),
                        "purchase_price": data.get("purchase_price"),
                    }
                )
        return sorted(lineage, key=lambda x: str(x.get("acquisition_date") or ""))

    def get_tenants(self, apn: str) -> list[dict[str, Any]]:
        """Retrieve tenant roster and lease terms for property."""
        tenants = []
        if not self.g.has_node(apn):
            return tenants

        for u, v, data in self.g.in_edges(apn, data=True):
            if data.get("relationship_type") == "LEASES_FROM":
                t_node = self.g.nodes.get(u, {})
                tenants.append(
                    {
                        "tenant_id": u,
                        "name": t_node.get("name", u),
                        "credit_rating": t_node.get("credit_rating", "Unrated"),
                        "leased_sqft": data.get("leased_sqft", 0),
                        "annual_rent": data.get("annual_rent", 0),
                        "lease_expiry": data.get("lease_expiry", ""),
                    }
                )
        return tenants

    def get_encumbrances(self, apn: str) -> list[dict[str, Any]]:
        """Retrieve active mortgages and debt encumbrances on property."""
        encumbrances = []
        if not self.g.has_node(apn):
            return encumbrances

        for u, v, data in self.g.in_edges(apn, data=True):
            if data.get("relationship_type") == "ENCUMBERS":
                loan_node = self.g.nodes.get(u, {})
                encumbrances.append(
                    {
                        "loan_id": u,
                        "balance": loan_node.get("current_balance", 0),
                        "interest_rate": loan_node.get("interest_rate", 0),
                        "dscr": loan_node.get("dscr", 0),
                        "ltv": loan_node.get("ltv", 0),
                        "maturity_date": loan_node.get("maturity_date", ""),
                    }
                )
        return encumbrances

    def get_neighborhood_subgraph(self, apn: str, depth: int = 2) -> dict[str, Any]:
        """Extract ego-graph centered at parcel up to depth hops."""
        if not self.g.has_node(apn):
            return {"nodes": [], "edges": []}

        sub_nodes = nx.single_source_shortest_path_length(
            self.g.to_undirected(as_view=True), apn, cutoff=depth
        )
        nodes_list = []
        for n in sub_nodes:
            attrs = dict(self.g.nodes[n])
            attrs["id"] = n
            nodes_list.append(attrs)

        edges_list = []
        subgraph = self.g.subgraph(sub_nodes.keys())
        for u, v, key, data in subgraph.edges(keys=True, data=True):
            edges_list.append(
                {
                    "source": u,
                    "target": v,
                    "key": key,
                    "relationship_type": data.get("relationship_type", "RELATED"),
                    **{k: val for k, val in data.items() if k != "relationship_type"},
                }
            )

        return {
            "root_apn": apn,
            "depth": depth,
            "node_count": len(nodes_list),
            "edge_count": len(edges_list),
            "nodes": nodes_list,
            "edges": edges_list,
        }
