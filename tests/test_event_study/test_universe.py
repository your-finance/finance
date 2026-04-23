from __future__ import annotations

import sqlite3
from pathlib import Path

from backtest.event_study.protocol import UniverseConfig
from backtest.event_study.universe import EventUniverseGate


def _create_market_db(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE historical_market_cap (
                symbol TEXT NOT NULL,
                date TEXT NOT NULL,
                market_cap REAL NOT NULL,
                PRIMARY KEY (symbol, date)
            )
            """
        )
        conn.executemany(
            "INSERT INTO historical_market_cap(symbol, date, market_cap) VALUES (?, ?, ?)",
            [
                ("AAPL", "2024-01-02", 9_000_000_000.0),
                ("AAPL", "2024-01-05", 12_000_000_000.0),
                ("MSFT", "2024-01-02", 20_000_000_000.0),
                ("MSFT", "2024-01-05", 25_000_000_000.0),
            ],
        )
        conn.commit()


def test_build_eligibility_matrix_uses_asof_market_cap_gate(tmp_path: Path) -> None:
    market_db = tmp_path / "market.db"
    _create_market_db(market_db)

    gate = EventUniverseGate(
        config=UniverseConfig(universe_name="extended_true", market_cap_min_usd=10_000_000_000.0),
        market_db_path=market_db,
        candidate_symbols=["AAPL", "MSFT", "NVDA"],
    )

    eligibility = gate.build_eligibility_matrix(["2024-01-03", "2024-01-06"])

    assert list(eligibility.index) == ["2024-01-03", "2024-01-06"]
    assert bool(eligibility.loc["2024-01-03", "AAPL"]) is False
    assert bool(eligibility.loc["2024-01-06", "AAPL"]) is True
    assert bool(eligibility.loc["2024-01-03", "MSFT"]) is True
    assert bool(eligibility.loc["2024-01-06", "NVDA"]) is False


def test_build_universe_audit_emits_yearly_eligible_counts(tmp_path: Path) -> None:
    market_db = tmp_path / "market.db"
    _create_market_db(market_db)

    gate = EventUniverseGate(
        config=UniverseConfig(universe_name="extended_true", market_cap_min_usd=10_000_000_000.0),
        market_db_path=market_db,
        candidate_symbols=["AAPL", "MSFT"],
    )

    eligibility = gate.build_eligibility_matrix(
        ["2024-01-03", "2024-01-06", "2025-01-07"]
    )
    audit = gate.build_universe_audit(
        eligibility,
        loaded_symbol_count=2,
        json_universe_count=3,
    )

    assert set(audit.by_year["year"]) == {"2024", "2025"}
    year_2024 = audit.by_year[audit.by_year["year"] == "2024"].iloc[0]
    assert int(year_2024["eligible_count_min"]) == 1
    assert int(year_2024["eligible_count_max"]) == 2
    assert "historical_market_cap_min_date" in audit.summary
    assert audit.summary["loaded_symbol_count"] == 2
    assert audit.summary["json_universe_count"] == 3

    audit_frame = audit.to_frame()
    assert set(audit_frame["audit_type"]) == {"by_date", "by_year", "summary"}
