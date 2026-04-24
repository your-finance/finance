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


class TestOptionPositions:
    def test_insert_and_get(self, store):
        store.upsert_company("QQQ", company_name="Invesco QQQ Trust")
        oid = store.insert_option_position(
            symbol="QQQ", expiration="2026-06-18", strike=580.0, side="PUT",
            quantity=10, avg_premium=23.605, open_date="2026-04-01",
        )
        assert oid > 0
        pos = store.get_open_option_positions()
        assert len(pos) == 1
        assert pos[0]["symbol"] == "QQQ"
        assert pos[0]["strike"] == 580.0
        assert pos[0]["quantity"] == 10
        assert pos[0]["status"] == "OPEN"

    def test_short_position(self, store):
        """Negative quantity = short."""
        store.upsert_company("QQQ", company_name="Invesco QQQ Trust")
        store.insert_option_position(
            symbol="QQQ", expiration="2026-09-18", strike=410.0, side="PUT",
            quantity=-10, avg_premium=4.78, open_date="2026-04-01",
        )
        pos = store.get_open_option_positions()
        assert pos[0]["quantity"] == -10

    def test_close_option(self, store):
        store.upsert_company("QQQ", company_name="Invesco QQQ Trust")
        oid = store.insert_option_position(
            symbol="QQQ", expiration="2026-04-17", strike=570.0, side="PUT",
            quantity=9, avg_premium=6.75, open_date="2026-04-01",
        )
        store.close_option_position(oid, close_date="2026-04-15")
        pos = store.get_open_option_positions()
        assert len(pos) == 0

    def test_get_by_symbol(self, store):
        store.upsert_company("QQQ", company_name="Invesco QQQ Trust")
        store.upsert_company("EWY", company_name="iShares MSCI South Korea ETF")
        store.insert_option_position(
            symbol="QQQ", expiration="2026-06-18", strike=580.0, side="PUT",
            quantity=10, avg_premium=23.605, open_date="2026-04-01",
        )
        store.insert_option_position(
            symbol="EWY", expiration="2026-07-17", strike=160.0, side="CALL",
            quantity=10, avg_premium=17.61, open_date="2026-04-01",
        )
        qqq = store.get_open_option_positions(symbol="QQQ")
        assert len(qqq) == 1
        assert qqq[0]["symbol"] == "QQQ"
        all_pos = store.get_open_option_positions()
        assert len(all_pos) == 2

    def test_strategy_tag(self, store):
        store.upsert_company("QQQ", company_name="Invesco QQQ Trust")
        store.insert_option_position(
            symbol="QQQ", expiration="2026-06-18", strike=580.0, side="PUT",
            quantity=10, avg_premium=23.605, open_date="2026-04-01",
            strategy_tag="tail_hedge",
        )
        pos = store.get_open_option_positions()
        assert pos[0]["strategy_tag"] == "tail_hedge"


class TestOptionLifecycleSchema:
    def test_get_open_option_position_exact_contract(self, store):
        store.upsert_company("QQQ", company_name="Invesco QQQ Trust")
        store.insert_option_position(
            symbol="QQQ", expiration="2026-09-18", strike=410.0, side="PUT",
            quantity=-10, avg_premium=4.78, open_date="2026-04-01",
            strategy_tag="tail_hedge",
        )
        pos = store.get_open_option_position(
            symbol="QQQ", expiration="2026-09-18", strike=410.0,
            side="PUT", strategy_tag="tail_hedge",
        )
        assert pos is not None
        assert pos["quantity"] == -10
        assert pos["avg_premium"] == 4.78

    def test_get_open_option_position_no_match_returns_none(self, store):
        store.upsert_company("QQQ", company_name="Invesco QQQ Trust")
        store.insert_option_position(
            symbol="QQQ", expiration="2026-09-18", strike=410.0, side="PUT",
            quantity=-10, avg_premium=4.78, open_date="2026-04-01",
        )
        # different strike
        assert store.get_open_option_position(
            symbol="QQQ", expiration="2026-09-18", strike=420.0, side="PUT",
        ) is None

    def test_get_open_option_position_distinguishes_strategy_tag(self, store):
        store.upsert_company("QQQ", company_name="Invesco QQQ Trust")
        store.insert_option_position(
            symbol="QQQ", expiration="2026-09-18", strike=410.0, side="PUT",
            quantity=-10, avg_premium=4.78, open_date="2026-04-01",
            strategy_tag="tail_hedge",
        )
        # Empty tag should NOT match the tagged leg
        assert store.get_open_option_position(
            symbol="QQQ", expiration="2026-09-18", strike=410.0, side="PUT",
            strategy_tag="",
        ) is None

    def test_insert_and_list_option_transactions(self, store):
        store.upsert_company("QQQ", company_name="Invesco QQQ Trust")
        oid = store.insert_option_position(
            symbol="QQQ", expiration="2026-09-18", strike=410.0, side="PUT",
            quantity=-10, avg_premium=4.78, open_date="2026-04-01",
        )
        store.insert_option_transaction(
            option_position_id=oid, symbol="QQQ", expiration="2026-09-18",
            strike=410.0, side="PUT", action="STO", quantity=10,
            premium=4.78, date="2026-04-01",
        )
        store.insert_option_transaction(
            option_position_id=oid, symbol="QQQ", expiration="2026-09-18",
            strike=410.0, side="PUT", action="BTC", quantity=10,
            premium=2.10, date="2026-04-15",
        )
        txns = store.get_option_transactions(symbol="QQQ")
        assert len(txns) == 2
        # ordered by id (insert order)
        assert txns[0]["action"] == "STO"
        assert txns[1]["action"] == "BTC"
        assert txns[0]["option_position_id"] == oid

    def test_get_option_transactions_filter_by_position_id(self, store):
        store.upsert_company("QQQ", company_name="Invesco QQQ Trust")
        store.upsert_company("EWY", company_name="iShares MSCI South Korea ETF")
        oid_a = store.insert_option_position(
            symbol="QQQ", expiration="2026-09-18", strike=410.0, side="PUT",
            quantity=-10, avg_premium=4.78, open_date="2026-04-01",
        )
        oid_b = store.insert_option_position(
            symbol="EWY", expiration="2026-07-17", strike=160.0, side="CALL",
            quantity=10, avg_premium=17.61, open_date="2026-04-01",
        )
        store.insert_option_transaction(
            option_position_id=oid_a, symbol="QQQ", expiration="2026-09-18",
            strike=410.0, side="PUT", action="STO", quantity=10,
            premium=4.78, date="2026-04-01",
        )
        store.insert_option_transaction(
            option_position_id=oid_b, symbol="EWY", expiration="2026-07-17",
            strike=160.0, side="CALL", action="BTO", quantity=10,
            premium=17.61, date="2026-04-01",
        )
        only_a = store.get_option_transactions(option_position_id=oid_a)
        assert len(only_a) == 1
        assert only_a[0]["symbol"] == "QQQ"

    def test_option_position_realized_pnl_defaults_zero(self, store):
        store.upsert_company("QQQ", company_name="Invesco QQQ Trust")
        store.insert_option_position(
            symbol="QQQ", expiration="2026-09-18", strike=410.0, side="PUT",
            quantity=-10, avg_premium=4.78, open_date="2026-04-01",
        )
        pos = store.get_open_option_positions()
        assert pos[0]["realized_pnl"] == 0

    def test_reject_duplicate_open_option_contract_same_strategy(self, store):
        store.upsert_company("QQQ", company_name="Invesco QQQ Trust")
        store.insert_option_position(
            symbol="QQQ", expiration="2026-09-18", strike=410.0, side="PUT",
            quantity=-10, avg_premium=4.78, open_date="2026-04-01",
            strategy_tag="tail_hedge",
        )
        with pytest.raises(Exception):  # UNIQUE partial index
            store.insert_option_position(
                symbol="QQQ", expiration="2026-09-18", strike=410.0, side="PUT",
                quantity=-5, avg_premium=5.0, open_date="2026-04-02",
                strategy_tag="tail_hedge",
            )

    def test_allow_duplicate_open_with_different_strategy_tag(self, store):
        store.upsert_company("QQQ", company_name="Invesco QQQ Trust")
        store.insert_option_position(
            symbol="QQQ", expiration="2026-09-18", strike=410.0, side="PUT",
            quantity=-10, avg_premium=4.78, open_date="2026-04-01",
            strategy_tag="tail_hedge",
        )
        # Different strategy tag → should be allowed (new identity)
        store.insert_option_position(
            symbol="QQQ", expiration="2026-09-18", strike=410.0, side="PUT",
            quantity=-5, avg_premium=5.0, open_date="2026-04-02",
            strategy_tag="theta_carry",
        )
        all_pos = store.get_open_option_positions(symbol="QQQ")
        assert len(all_pos) == 2


class TestCheckpoint:
    def test_checkpoint_company_db(self, store):
        """checkpoint should not raise."""
        store.checkpoint()  # No error = pass
