from __future__ import annotations

import pandas as pd

from backtest.event_study.returns import (
    build_t1open_excess_return_matrices,
    build_t1open_return_matrices,
)


def _price_frame(rows: list[tuple[str, float, float]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["date", "open", "close"])


def test_build_t1open_return_matrices_uses_fixed_event_semantics() -> None:
    price_dict = {
        "AAPL": _price_frame(
            [
                ("2024-01-01", 90.0, 95.0),
                ("2024-01-02", 100.0, 101.0),
                ("2024-01-03", 105.0, 110.0),
            ]
        )
    }

    matrices = build_t1open_return_matrices(
        price_dict=price_dict,
        computation_dates=["2024-01-01"],
        horizons=[2],
    )

    assert abs(matrices[2].loc["2024-01-01", "AAPL"] - 0.10) < 1e-9


def test_build_t1open_excess_return_matrices_uses_same_benchmark_timing() -> None:
    price_dict = {
        "AAPL": _price_frame(
            [
                ("2024-01-01", 90.0, 95.0),
                ("2024-01-02", 100.0, 101.0),
                ("2024-01-03", 105.0, 110.0),
            ]
        )
    }
    benchmark_df = _price_frame(
        [
            ("2024-01-01", 180.0, 190.0),
            ("2024-01-02", 200.0, 201.0),
            ("2024-01-03", 205.0, 210.0),
        ]
    )

    matrices = build_t1open_excess_return_matrices(
        price_dict=price_dict,
        benchmark_df=benchmark_df,
        computation_dates=["2024-01-01"],
        horizons=[2],
    )

    # AAPL: 100 -> 110 = +10%
    # SPY: 200 -> 210 = +5%
    assert abs(matrices[2].loc["2024-01-01", "AAPL"] - 0.05) < 1e-9
