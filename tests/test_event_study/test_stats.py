from __future__ import annotations

import pandas as pd

from backtest.event_study.stats import (
    apply_bh_fdr,
    build_symbol_date_index,
    deoverlap_symbol_events,
    summarize_bucket_for_horizon,
)


def test_deoverlap_symbol_events_uses_hard_window_exclusion() -> None:
    feature_frames = {
        "AAPL": pd.DataFrame(
            {
                "date": [f"2024-01-{day:02d}" for day in range(1, 6)],
            }
        )
    }
    index = build_symbol_date_index(feature_frames)
    events = {"AAPL": ["2024-01-01", "2024-01-02", "2024-01-05"]}

    deduped = deoverlap_symbol_events(events, index, horizon=2)

    assert deduped == {"AAPL": ["2024-01-01", "2024-01-05"]}


def test_summarize_bucket_for_horizon_clusters_same_day_events() -> None:
    feature_frames = {
        "AAPL": pd.DataFrame({"date": ["2024-01-02", "2024-01-03"]}),
        "MSFT": pd.DataFrame({"date": ["2024-01-02", "2024-01-03"]}),
    }
    index = build_symbol_date_index(feature_frames)
    events = {
        "AAPL": ["2024-01-02"],
        "MSFT": ["2024-01-02"],
    }
    ret_df = pd.DataFrame(
        {
            "AAPL": [0.10],
            "MSFT": [0.20],
        },
        index=["2024-01-02"],
    )

    result = summarize_bucket_for_horizon(
        bucket_label="rvol_up2_all",
        horizon=5,
        events=events,
        ret_df=ret_df,
        symbol_date_index=index,
    )

    assert result.n_events_raw == 2
    assert result.n_events_dedup == 2
    assert result.n_events_scored == 2
    assert result.n_effective == 1
    assert abs(result.mean_event_return - 0.15) < 1e-9
    assert abs(result.mean_cluster_return - 0.15) < 1e-9


def test_apply_bh_fdr_returns_monotone_adjusted_values() -> None:
    results = [
        summarize_bucket_for_horizon(
            bucket_label="b1",
            horizon=5,
            events={"AAPL": ["2024-01-02"]},
            ret_df=pd.DataFrame({"AAPL": [0.10]}, index=["2024-01-02"]),
            symbol_date_index=build_symbol_date_index(
                {"AAPL": pd.DataFrame({"date": ["2024-01-02", "2024-01-03"]})}
            ),
        ),
        summarize_bucket_for_horizon(
            bucket_label="b2",
            horizon=10,
            events={"AAPL": ["2024-01-02"], "MSFT": ["2024-01-02"]},
            ret_df=pd.DataFrame({"AAPL": [0.20], "MSFT": [0.20]}, index=["2024-01-02"]),
            symbol_date_index=build_symbol_date_index(
                {
                    "AAPL": pd.DataFrame({"date": ["2024-01-02", "2024-01-03"]}),
                    "MSFT": pd.DataFrame({"date": ["2024-01-02", "2024-01-03"]}),
                }
            ),
        ),
    ]

    adjusted = apply_bh_fdr(results)

    assert len(adjusted) == 2
    assert all(result.p_fdr is not None for result in adjusted)
    assert all(0.0 <= result.p_fdr <= 1.0 for result in adjusted)
