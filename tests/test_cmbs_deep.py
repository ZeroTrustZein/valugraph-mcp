"""Comprehensive unit and edge-case tests for CMBS risk engine and waterfall losses."""

from __future__ import annotations

import pytest

from valugraph_mcp.cmbs import CMBSRiskEngine
from valugraph_mcp.types import CMBSTranche


class TestCMBSRiskEngineDeep:
    """Tests for edge cases in CMBS pool summary, synthetic deal creation, and waterfall losses."""

    def test_pool_summary_empty_loans(self) -> None:
        """Verify calculate_pool_summary handles empty loan list safely."""
        engine = CMBSRiskEngine()
        summary = engine.calculate_pool_summary([])
        assert summary["total_balance"] == 0.0
        assert summary["loan_count"] == 0
        assert summary["weighted_avg_dscr"] == 0.0
        assert summary["weighted_avg_ltv"] == 0.0
        assert summary["weighted_avg_coupon"] == 0.0

    def test_pool_summary_zero_total_balance(self) -> None:
        """Verify calculate_pool_summary handles loans with zero balance via duck typing."""
        engine = CMBSRiskEngine()
        from types import SimpleNamespace

        mock_loan = SimpleNamespace(
            current_balance=0.0,
            interest_rate=0.06,
            dscr=1.25,
            ltv=0.60,
        )
        summary = engine.calculate_pool_summary([mock_loan])  # type: ignore[list-item]
        assert summary["total_balance"] == 0.0
        assert summary["loan_count"] == 1
        assert summary["weighted_avg_dscr"] == 0.0

    def test_waterfall_zero_loss(self) -> None:
        """Verify allocate_waterfall_losses with zero cumulative loss."""
        engine = CMBSRiskEngine()
        tranches = [
            CMBSTranche(
                tranche_name="AAA",
                attachment_point=0.30,
                detachment_point=1.00,
                coupon_rate=0.05,
                initial_balance=70000000.0,
                current_balance=70000000.0,
            ),
            CMBSTranche(
                tranche_name="BBB",
                attachment_point=0.10,
                detachment_point=0.30,
                coupon_rate=0.07,
                initial_balance=20000000.0,
                current_balance=20000000.0,
            ),
            CMBSTranche(
                tranche_name="Equity",
                attachment_point=0.00,
                detachment_point=0.10,
                coupon_rate=0.12,
                initial_balance=10000000.0,
                current_balance=10000000.0,
            ),
        ]
        allocations = engine.allocate_waterfall_losses(tranches, cumulative_pool_loss=0.0)
        for a in allocations:
            assert a["allocated_loss"] == 0.0
            assert a["remaining_balance"] == a["initial_balance"]
            assert a["impairment_pct"] == 0.0
            assert a["is_exhausted"] is False

    def test_waterfall_partial_and_multi_tranche_loss(self) -> None:
        """Verify losses sequentially wipe Equity, then partially impair BBB."""
        engine = CMBSRiskEngine()
        tranches = [
            CMBSTranche(
                tranche_name="AAA",
                attachment_point=0.30,
                detachment_point=1.00,
                coupon_rate=0.05,
                initial_balance=70000000.0,
                current_balance=70000000.0,
            ),
            CMBSTranche(
                tranche_name="BBB",
                attachment_point=0.10,
                detachment_point=0.30,
                coupon_rate=0.07,
                initial_balance=20000000.0,
                current_balance=20000000.0,
            ),
            CMBSTranche(
                tranche_name="Equity",
                attachment_point=0.00,
                detachment_point=0.10,
                coupon_rate=0.12,
                initial_balance=10000000.0,
                current_balance=10000000.0,
            ),
        ]
        # Cumulative loss of $15,000,000 -> wipes Equity ($10M) + takes $5M of BBB ($20M)
        allocations = engine.allocate_waterfall_losses(tranches, cumulative_pool_loss=15000000.0)

        equity = next(a for a in allocations if a["tranche_name"] == "Equity")
        assert equity["allocated_loss"] == 10000000.0
        assert equity["remaining_balance"] == 0.0
        assert equity["impairment_pct"] == 1.0
        assert equity["is_exhausted"] is True

        bbb = next(a for a in allocations if a["tranche_name"] == "BBB")
        assert bbb["allocated_loss"] == 5000000.0
        assert bbb["remaining_balance"] == 15000000.0
        assert bbb["impairment_pct"] == 0.25
        assert bbb["is_exhausted"] is False

        aaa = next(a for a in allocations if a["tranche_name"] == "AAA")
        assert aaa["allocated_loss"] == 0.0
        assert aaa["remaining_balance"] == 70000000.0
        assert aaa["impairment_pct"] == 0.0
        assert aaa["is_exhausted"] is False

    def test_waterfall_catastrophic_loss_exceeding_pool_balance(self) -> None:
        """Verify loss exceeding entire structure balance caps at total pool balance."""
        engine = CMBSRiskEngine()
        tranches = [
            CMBSTranche(
                tranche_name="AAA",
                attachment_point=0.30,
                detachment_point=1.00,
                coupon_rate=0.05,
                initial_balance=70000000.0,
                current_balance=70000000.0,
            ),
            CMBSTranche(
                tranche_name="Equity",
                attachment_point=0.00,
                detachment_point=0.30,
                coupon_rate=0.12,
                initial_balance=30000000.0,
                current_balance=30000000.0,
            ),
        ]
        # Total pool is $100M, loss is $150M
        allocations = engine.allocate_waterfall_losses(tranches, cumulative_pool_loss=150000000.0)
        total_allocated = sum(a["allocated_loss"] for a in allocations)
        assert total_allocated == 100000000.0
        for a in allocations:
            assert a["remaining_balance"] == 0.0
            assert a["impairment_pct"] == 1.0
            assert a["is_exhausted"] is True
            assert a["impairment_pct"] == 1.0

    def test_build_synthetic_deal_proportions(self) -> None:
        """Verify synthetic deal creates balanced tranches and collateral loans."""
        engine = CMBSRiskEngine()
        deal = engine.build_synthetic_deal(deal_id="CUSTOM-POOL-1", total_balance=200000000.0)
        assert deal.deal_id == "CUSTOM-POOL-1"
        assert deal.total_issuance == 200000000.0

        tranche_sum = sum(t.initial_balance for t in deal.tranches)
        assert tranche_sum == pytest.approx(200000000.0)

        loan_sum = sum(l.current_balance for l in deal.collateral_loans)
        assert loan_sum == pytest.approx(200000000.0)
