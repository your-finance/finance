from __future__ import annotations

import pandas as pd

from backtest.event_study.returns import build_t1open_return_matrices
from backtest.event_study.stats import build_symbol_date_index, summarize_bucket_stats
from backtest.event_study.studies import RVOLStudyAdapter, RVOLStudyParams


def _frame(rows: list[tuple[str, float, float, float]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["date", "open", "close", "volume"])


def test_rvol_study_detects_threshold_cross_event() -> None:
    adapter = RVOLStudyAdapter(
        RVOLStudyParams(rvol_lookback=3, rvol_threshold=1.0)
    )
    price_dict = {
        "AAPL": _frame(
            [
                ("2024-01-01", 10, 10, 10),
                ("2024-01-02", 10, 11, 11),
                ("2024-01-03", 11, 10, 9),
                ("2024-01-04", 10, 10, 10),
                ("2024-01-05", 10, 10, 30),
                ("2024-01-08", 10, 11, 12),
                ("2024-01-09", 11, 12, 11),
            ]
        )
    }

    feature_frames = adapter.build_feature_frames(price_dict)
    bucket_events = adapter.detect_events(feature_frames)

    assert bucket_events["rvol_up2_all"]["AAPL"] == ["2024-01-05"]


def test_rvol_study_runs_through_returns_and_stats() -> None:
    adapter = RVOLStudyAdapter(
        RVOLStudyParams(rvol_lookback=3, rvol_threshold=1.0)
    )
    price_dict = {
        "AAPL": _frame(
            [
                ("2024-01-01", 10, 10, 10),
                ("2024-01-02", 10, 11, 11),
                ("2024-01-03", 11, 10, 9),
                ("2024-01-04", 10, 10, 10),
                ("2024-01-05", 10, 10, 30),
                ("2024-01-08", 10, 11, 12),
                ("2024-01-09", 11, 12, 11),
            ]
        )
    }

    feature_frames = adapter.build_feature_frames(price_dict)
    bucket_events = adapter.detect_events(feature_frames)
    symbol_date_index = build_symbol_date_index(feature_frames)
    return_matrices = build_t1open_return_matrices(
        price_dict=price_dict,
        computation_dates=feature_frames["AAPL"]["date"].astype(str).tolist(),
        horizons=[2],
    )

    results = summarize_bucket_stats(
        bucket_label="rvol_up2_all",
        events=bucket_events["rvol_up2_all"],
        return_matrices=return_matrices,
        symbol_date_index=symbol_date_index,
    )

    assert len(results) == 1
    result = results[0]
    assert result.n_events_raw == 1
    assert result.n_events_dedup == 1
    assert result.n_events_scored == 1
    assert result.n_effective == 1
    assert result.mean_event_return > 0
