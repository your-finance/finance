"""Tests for review generators — ensures option positions are included in reports."""
import pytest
from unittest.mock import patch
from terminal.company_store import CompanyStore
from portfolio.holdings.manager import PortfolioManager


@pytest.fixture
def store_stock_only(tmp_path):
    """Portfolio with stock only."""
    db = tmp_path / "test.db"
    s = CompanyStore(db_path=db)
    s.upsert_company("NVDA", company_name="NVIDIA", sector="Technology")
    s.save_oprms_rating("NVDA", dna="S", timing="A", timing_coeff=0.9)
    s.insert_holding("NVDA", shares=100, avg_cost=135.0, open_date="2026-04-01")
    s.set_cash(100000.0)
    yield s
    s.close()


@pytest.fixture
def store_option_only(tmp_path):
    """Portfolio with options only (no stock holdings)."""
    db = tmp_path / "test.db"
    s = CompanyStore(db_path=db)
    s.upsert_company("QQQ", company_name="QQQ")
    s.set_cash(100000.0)
    s.insert_option_position(
        symbol="QQQ", expiration="2026-06-18", strike=580.0, side="PUT",
        quantity=5, avg_premium=10.0, open_date="2026-04-01",
        strategy_tag="tail_hedge",
    )
    yield s
    s.close()


@pytest.fixture
def store_mixed(tmp_path):
    """Portfolio with stocks + options."""
    db = tmp_path / "test.db"
    s = CompanyStore(db_path=db)
    s.upsert_company("NVDA", company_name="NVIDIA", sector="Technology")
    s.save_oprms_rating("NVDA", dna="S", timing="A", timing_coeff=0.9)
    s.insert_holding("NVDA", shares=100, avg_cost=135.0, open_date="2026-04-01")
    s.upsert_company("QQQ", company_name="QQQ")
    s.insert_option_position(
        symbol="QQQ", expiration="2026-06-18", strike=580.0, side="PUT",
        quantity=5, avg_premium=10.0, open_date="2026-04-01",
    )
    s.set_cash(100000.0)
    yield s
    s.close()


def _patch_store(store):
    """Context manager to patch the singleton store."""
    from portfolio.holdings import manager as hm
    return patch.multiple(
        "terminal.company_store",
        get_store=lambda *a, **kw: store,
        _store=store,
    )


def _run_with_store(store, fn, **kwargs):
    """Run a review function with the test store injected."""
    from portfolio.holdings import manager as hm
    with patch("terminal.company_store.get_store", return_value=store):
        hm._default_mgr = None
        # Pass empty positions list to skip price refresh (which needs market.db)
        mgr = PortfolioManager(store=store)
        positions = mgr.load_holdings()
        # Set current_price = avg_cost for testing
        for p in positions:
            p.current_price = p.cost_basis
        return fn(positions=positions, **kwargs)


class TestWeeklySnapshot:
    def test_stock_only_includes_value(self, store_stock_only):
        from portfolio.benchmark.review import generate_weekly_snapshot
        report = _run_with_store(store_stock_only, generate_weekly_snapshot)
        assert "Weekly Snapshot" in report
        assert "No positions" not in report

    def test_option_only_not_empty(self, store_option_only):
        """Option-only book must NOT return 'No positions'."""
        from portfolio.benchmark.review import generate_weekly_snapshot
        report = _run_with_store(store_option_only, generate_weekly_snapshot)
        assert "No positions" not in report
        assert "Weekly Snapshot" in report

    def test_mixed_includes_options_in_total(self, store_mixed):
        from portfolio.benchmark.review import generate_weekly_snapshot
        report = _run_with_store(store_mixed, generate_weekly_snapshot)
        # Stock: 100*135=13500, Option: 5*10*100=5000, total=18500
        assert "options" in report.lower()
        assert "No positions" not in report


class TestMonthlyReview:
    def test_option_only_not_empty(self, store_option_only):
        from portfolio.benchmark.review import generate_monthly_review
        report = _run_with_store(store_option_only, generate_monthly_review)
        assert "No positions" not in report
        assert "Monthly Review" in report

    def test_mixed_includes_value(self, store_mixed):
        from portfolio.benchmark.review import generate_monthly_review
        report = _run_with_store(store_mixed, generate_monthly_review)
        assert "Monthly Review" in report
        assert "No positions" not in report


class TestQuarterlyReview:
    def test_option_only_not_empty(self, store_option_only):
        from portfolio.benchmark.review import generate_quarterly_review
        report = _run_with_store(store_option_only, generate_quarterly_review)
        assert "No positions" not in report
        assert "Quarterly Review" in report

    def test_mixed_includes_value(self, store_mixed):
        from portfolio.benchmark.review import generate_quarterly_review
        report = _run_with_store(store_mixed, generate_quarterly_review)
        assert "Quarterly Review" in report
        assert "No positions" not in report
