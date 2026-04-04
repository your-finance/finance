"""Tests for portfolio tables in CompanyStore."""
import pytest
from terminal.company_store import CompanyStore


@pytest.fixture
def store(tmp_path):
    db_path = tmp_path / "test_company.db"
    s = CompanyStore(db_path=db_path)
    # Seed a company for FK
    s.upsert_company("NVDA", company_name="NVIDIA", sector="Technology")
    yield s
    s.close()


class TestHoldings:
    def test_insert_and_get(self, store):
        pid = store.insert_holding("NVDA", shares=100, avg_cost=135.0, open_date="2026-04-01")
        assert pid > 0
        h = store.get_open_holding("NVDA")
        assert h is not None
        assert h["shares"] == 100
        assert h["avg_cost"] == 135.0
        assert h["status"] == "OPEN"

    def test_no_duplicate_open(self, store):
        store.insert_holding("NVDA", shares=100, avg_cost=135.0, open_date="2026-04-01")
        with pytest.raises(Exception):  # UNIQUE constraint
            store.insert_holding("NVDA", shares=50, avg_cost=140.0, open_date="2026-04-02")

    def test_close_and_reopen(self, store):
        pid1 = store.insert_holding("NVDA", shares=100, avg_cost=135.0, open_date="2026-04-01")
        store.close_holding(pid1, close_date="2026-04-05", realized_pnl=500.0)

        # Closed — no open holding
        assert store.get_open_holding("NVDA") is None

        # Can open new position for same symbol
        pid2 = store.insert_holding("NVDA", shares=50, avg_cost=150.0, open_date="2026-04-06")
        assert pid2 != pid1
        assert store.get_open_holding("NVDA") is not None

    def test_update_holding(self, store):
        pid = store.insert_holding("NVDA", shares=100, avg_cost=135.0, open_date="2026-04-01")
        store.update_holding(pid, shares=200, avg_cost=137.5)
        h = store.get_open_holding("NVDA")
        assert h["shares"] == 200
        assert h["avg_cost"] == 137.5

    def test_get_all_open(self, store):
        store.upsert_company("AAPL", company_name="Apple", sector="Technology")
        store.insert_holding("NVDA", shares=100, avg_cost=135.0, open_date="2026-04-01")
        store.insert_holding("AAPL", shares=50, avg_cost=200.0, open_date="2026-04-01")
        holdings = store.get_all_open_holdings()
        assert len(holdings) == 2


class TestTransactions:
    def test_insert_and_query(self, store):
        pid = store.insert_holding("NVDA", shares=100, avg_cost=135.0, open_date="2026-04-01")
        store.insert_transaction(pid, "NVDA", "BUY", shares=100, price=135.0, date="2026-04-01")
        txns = store.get_transactions("NVDA")
        assert len(txns) == 1
        assert txns[0]["action"] == "BUY"
        assert txns[0]["position_id"] == pid

    def test_multiple_transactions(self, store):
        pid = store.insert_holding("NVDA", shares=100, avg_cost=135.0, open_date="2026-04-01")
        store.insert_transaction(pid, "NVDA", "BUY", shares=100, price=135.0, date="2026-04-01")
        store.insert_transaction(pid, "NVDA", "ADD", shares=50, price=140.0, date="2026-04-03")
        txns = store.get_transactions("NVDA")
        assert len(txns) == 2


class TestPortfolioCash:
    def test_set_initial(self, store):
        store.set_cash(500000.0, notes="Initial deposit")
        assert store.get_cash_balance() == 500000.0

    def test_adjust_cash(self, store):
        store.set_cash(500000.0)
        store.adjust_cash(-13500.0, action="WITHDRAW", notes="Buy NVDA 100@135")
        assert store.get_cash_balance() == pytest.approx(486500.0)

    def test_no_cash_returns_zero(self, store):
        assert store.get_cash_balance() == 0.0

    def test_audit_trail(self, store):
        store.set_cash(100000.0)
        store.adjust_cash(-5000.0, action="WITHDRAW")
        store.adjust_cash(3000.0, action="DEPOSIT")
        entries = store.get_cash_history()
        assert len(entries) == 3
        assert entries[-1]["balance_after"] == pytest.approx(98000.0)


class TestKillConditionsMigration:
    def test_save_reads_from_sqlite(self, store):
        """company_db facade should read from SQLite after migration."""
        from unittest.mock import patch
        import terminal.company_db as cdb

        # Seed company
        store.upsert_company("AAPL", company_name="Apple")

        # Save via CompanyStore (SQLite)
        store.save_kill_conditions("AAPL", [
            {"description": "Revenue < $90B", "source_lens": "fundamental"},
        ])

        # company_db.get_kill_conditions should return SQLite data
        with patch.object(cdb, "_get_store", return_value=store):
            conditions = cdb.get_kill_conditions("AAPL")
            assert len(conditions) >= 1
            assert any("Revenue" in c.get("description", "") for c in conditions)

    def test_save_via_facade_roundtrip(self, store, tmp_path):
        """save via company_db facade writes to SQLite and reads back."""
        from unittest.mock import patch
        import terminal.company_db as cdb

        store.upsert_company("MSFT", company_name="Microsoft")

        with patch.object(cdb, "_get_store", return_value=store), \
             patch.object(cdb, "_COMPANIES_DIR", tmp_path):
            cdb.save_kill_conditions("MSFT", [
                {"description": "Azure growth < 20%", "metric": "cloud"},
            ])
            conditions = cdb.get_kill_conditions("MSFT")
            assert len(conditions) >= 1
            assert any("Azure" in c.get("description", "") for c in conditions)


class TestCheckpoint:
    def test_checkpoint_company_db(self, store):
        """checkpoint should not raise."""
        store.checkpoint()  # No error = pass
