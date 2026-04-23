from __future__ import annotations

import pytest

from backtest.event_study import (
    EventStudyConfig,
    EventStudyRunner,
    OverlapPolicy,
    ReportSplitConfig,
    ReturnConfig,
    UniverseConfig,
)
from backtest.event_study.studies import RVOLStudyAdapter


def test_event_study_config_defaults_match_frozen_protocol() -> None:
    config = EventStudyConfig(study_name="rvol_up2")

    assert config.event_type == "symbol_date"
    assert config.frequency == "daily"
    assert config.universe == UniverseConfig(
        universe_name="extended_true",
        market_cap_min_usd=10_000_000_000.0,
        audit_eligible_counts_by_year=True,
    )
    assert config.returns == ReturnConfig(
        entry="t_plus_1_open",
        exit="t_plus_h_close",
        horizons=(5, 10, 20, 60),
        benchmark_symbol="SPY",
        benchmark_same_semantics=True,
        drop_missing_exit=True,
        emit_raw_and_excess=True,
    )
    assert config.overlap == OverlapPolicy(
        same_symbol_mode="hard_window_exclusion",
        cluster_mode="by_event_date",
        fdr_family="per_window_return_type_all_horizon_bucket_pairs",
    )
    assert config.report_split == ReportSplitConfig(
        oos_start_date=None,
        emit_full_window=True,
        emit_is_window=True,
        emit_oos_window=True,
    )


def test_return_config_rejects_unsorted_or_duplicate_horizons() -> None:
    with pytest.raises(ValueError, match="sorted ascending"):
        ReturnConfig(horizons=(10, 5, 20))

    with pytest.raises(ValueError, match="duplicates"):
        ReturnConfig(horizons=(5, 10, 10, 60))


def test_event_study_config_validates_dates_and_oos_bounds() -> None:
    with pytest.raises(ValueError, match="study_start_date must be <= study_end_date"):
        EventStudyConfig(
            study_name="rvol_up2",
            study_start_date="2025-01-02",
            study_end_date="2025-01-01",
        )

    with pytest.raises(ValueError, match="oos_start_date must be <= study_end_date"):
        EventStudyConfig(
            study_name="rvol_up2",
            study_start_date="2024-01-01",
            study_end_date="2024-12-31",
            report_split=ReportSplitConfig(oos_start_date="2025-01-01"),
        )


def test_runner_shell_preserves_config_and_study_adapter() -> None:
    runner = EventStudyRunner(
        EventStudyConfig(study_name="rvol_up2"),
        study=RVOLStudyAdapter(),
    )

    adjusted = runner.with_study_window("2024-01-01", "2024-12-31")

    assert adjusted.config.study_name == "rvol_up2"
    assert adjusted.config.study_start_date == "2024-01-01"
    assert adjusted.config.study_end_date == "2024-12-31"
