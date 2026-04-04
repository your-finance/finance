"""Tests for portfolio holdings manager (SQLite-backed)."""
import pytest
from terminal.company_store import CompanyStore


@pytest.fixture
def store(tmp_path):
    db_path = tmp_path / "test_company.db"
    s = CompanyStore(db_path=db_path)
    # Seed companies + OPRMS
    s.upsert_company("NVDA", company_name="NVIDIA", sector="Technology", industry="Semiconductors")
    s.upsert_company("AAPL", company_name="Apple", sector="Technology", industry="Consumer Electronics")
    s.save_oprms_rating("NVDA", dna="S", timing="A", timing_coeff=0.9)
    s.save_oprms_rating("AAPL", dna="A", timing="B", timing_coeff=0.5)
    yield s
    s.close()


@pytest.fixture
def manager(store):
    """Create a manager backed by the test store."""
    from portfolio.holdings.manager import PortfolioManager
    return PortfolioManager(store=store)


class TestLoadAndGet:
    def test_empty_portfolio(self, manager):
        positions = manager.load_holdings()
        assert positions == []

    def test_add_and_load(self, manager):
        manager.add_position("NVDA", shares=100, avg_cost=135.0, date="2026-04-01")
        positions = manager.load_holdings()
        assert len(positions) == 1
        p = positions[0]
        assert p.symbol == "NVDA"
        assert p.shares == 100
        assert p.cost_basis == 135.0
        assert p.company_name == "NVIDIA"
        assert p.sector == "Technology"
        assert p.dna_rating == "S"
        assert p.timing_rating == "A"
        assert p.status == "OPEN"

    def test_get_position(self, manager):
        manager.add_position("NVDA", shares=100, avg_cost=135.0, date="2026-04-01")
        p = manager.get_position("NVDA")
        assert p is not None
        assert p.symbol == "NVDA"

    def test_get_nonexistent(self, manager):
        assert manager.get_position("FAKE") is None


class TestClosePosition:
    def test_close_and_reopen(self, manager):
        manager.add_position("NVDA", shares=100, avg_cost=135.0, date="2026-04-01")
        manager.close_position("NVDA", sell_price=150.0, date="2026-04-05")
        assert manager.get_position("NVDA") is None

        # Reopen
        manager.add_position("NVDA", shares=50, avg_cost=160.0, date="2026-04-06")
        p = manager.get_position("NVDA")
        assert p.shares == 50

    def test_close_calculates_pnl(self, manager):
        manager.add_position("NVDA", shares=100, avg_cost=135.0, date="2026-04-01")
        manager.close_position("NVDA", sell_price=150.0, date="2026-04-05")
        # realized_pnl = (150 - 135) * 100 = 1500
        holdings = manager._store.get_all_open_holdings()
        assert len(holdings) == 0  # No open


class TestNAV:
    def test_total_nav(self, manager):
        manager.add_position("NVDA", shares=100, avg_cost=135.0, date="2026-04-01")
        manager._store.set_cash(500000.0)
        prices = {"NVDA": 150.0}
        nav = manager.get_total_nav(prices)
        # NAV = 100 * 150 + 500000 = 515000
        assert nav == pytest.approx(515000.0)

    def test_weights(self, manager):
        manager.add_position("NVDA", shares=100, avg_cost=135.0, date="2026-04-01")
        manager.add_position("AAPL", shares=200, avg_cost=200.0, date="2026-04-01")
        manager._store.set_cash(100000.0)
        prices = {"NVDA": 150.0, "AAPL": 210.0}
        positions = manager.refresh_prices(prices)
        # NVDA: 15000, AAPL: 42000, cash: 100000, NAV: 157000
        nvda = [p for p in positions if p.symbol == "NVDA"][0]
        assert nvda.current_weight == pytest.approx(15000 / 157000, rel=1e-3)

    def test_summary(self, manager):
        manager.add_position("NVDA", shares=100, avg_cost=135.0, date="2026-04-01")
        manager._store.set_cash(500000.0)
        prices = {"NVDA": 150.0}
        summary = manager.get_portfolio_summary(prices)
        assert summary["total_nav"] == pytest.approx(515000.0)
        assert summary["invested_pct"] == pytest.approx(15000 / 515000, rel=1e-3)
        assert summary["cash_pct"] == pytest.approx(500000 / 515000, rel=1e-3)
        assert summary["total_positions"] == 1


class TestExecuteTrade:
    def test_buy_new_position(self, manager):
        manager._store.set_cash(500000.0)
        result = manager.execute_trade("NVDA", "BUY", shares=100, price=135.0, date="2026-04-01")
        assert result["action"] == "BUY"
        assert result["new_shares"] == 100
        assert result["new_avg_cost"] == 135.0
        p = manager.get_position("NVDA")
        assert p.shares == 100
        assert manager._store.get_cash_balance() == pytest.approx(500000 - 100 * 135)

    def test_add_to_existing(self, manager):
        manager._store.set_cash(500000.0)
        manager.execute_trade("NVDA", "BUY", shares=100, price=135.0, date="2026-04-01")
        manager.execute_trade("NVDA", "ADD", shares=50, price=140.0, date="2026-04-03")
        p = manager.get_position("NVDA")
        assert p.shares == 150
        # avg_cost = (100*135 + 50*140) / 150 = 136.67
        assert p.cost_basis == pytest.approx((100 * 135 + 50 * 140) / 150, rel=1e-2)
        assert manager._store.get_cash_balance() == pytest.approx(500000 - 100 * 135 - 50 * 140)

    def test_trim(self, manager):
        manager._store.set_cash(500000.0)
        manager.execute_trade("NVDA", "BUY", shares=100, price=135.0, date="2026-04-01")
        manager.execute_trade("NVDA", "TRIM", shares=30, price=150.0, date="2026-04-05")
        p = manager.get_position("NVDA")
        assert p.shares == 70
        assert manager._store.get_cash_balance() == pytest.approx(500000 - 100 * 135 + 30 * 150)

    def test_sell_all_closes_position(self, manager):
        manager._store.set_cash(500000.0)
        manager.execute_trade("NVDA", "BUY", shares=100, price=135.0, date="2026-04-01")
        result = manager.execute_trade("NVDA", "SELL", shares=100, price=150.0, date="2026-04-05")
        assert result["closed"] is True
        assert result["realized_pnl"] == pytest.approx(1500.0)
        assert manager.get_position("NVDA") is None
        assert manager._store.get_cash_balance() == pytest.approx(500000 - 13500 + 15000)

    def test_atomic_rollback(self, manager):
        """If cash goes negative, entire trade should rollback."""
        manager._store.set_cash(1000.0)  # Not enough for 100 @ 135
        with pytest.raises(ValueError, match="Insufficient cash"):
            manager.execute_trade("NVDA", "BUY", shares=100, price=135.0, date="2026-04-01")
        # Nothing changed
        assert manager.get_position("NVDA") is None
        assert manager._store.get_cash_balance() == pytest.approx(1000.0)

    def test_trim_then_sell_cumulative_pnl(self, manager):
        """BUY 100@100 -> TRIM 40@120 -> SELL 60@130: cumulative = 800 + 1800 = 2600."""
        manager._store.set_cash(500000.0)
        manager.execute_trade("NVDA", "BUY", shares=100, price=100.0, date="2026-04-01")

        # TRIM 40 @ 120: this_leg = (120-100)*40 = 800
        trim_result = manager.execute_trade("NVDA", "TRIM", shares=40, price=120.0, date="2026-04-05")
        assert trim_result["this_leg_pnl"] == pytest.approx(800.0)
        assert trim_result["realized_pnl"] == pytest.approx(800.0)  # cumulative so far
        assert trim_result["closed"] is False

        # SELL remaining 60 @ 130: this_leg = (130-100)*60 = 1800, cumulative = 800+1800 = 2600
        sell_result = manager.execute_trade("NVDA", "SELL", shares=60, price=130.0, date="2026-04-10")
        assert sell_result["this_leg_pnl"] == pytest.approx(1800.0)
        assert sell_result["realized_pnl"] == pytest.approx(2600.0)  # total across all legs
        assert sell_result["closed"] is True

    def test_buy_rejects_existing_open(self, manager):
        """BUY should reject if position already open — use ADD instead."""
        manager._store.set_cash(500000.0)
        manager.execute_trade("NVDA", "BUY", shares=100, price=135.0, date="2026-04-01")
        with pytest.raises(ValueError, match="already open"):
            manager.execute_trade("NVDA", "BUY", shares=50, price=140.0, date="2026-04-02")

    def test_transactions_logged(self, manager):
        manager._store.set_cash(500000.0)
        manager.execute_trade("NVDA", "BUY", shares=100, price=135.0, date="2026-04-01")
        manager.execute_trade("NVDA", "ADD", shares=50, price=140.0, date="2026-04-03")
        txns = manager._store.get_transactions("NVDA")
        assert len(txns) == 2
        assert txns[0]["action"] == "BUY"
        assert txns[1]["action"] == "ADD"
