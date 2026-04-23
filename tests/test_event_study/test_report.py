from __future__ import annotations

from pathlib import Path

import pandas as pd

from backtest.event_study.protocol import EventStudyConfig, ReportSplitConfig
from backtest.event_study.report import (
    build_markdown_report,
    build_summary_frame,
    write_report_artifacts,
)
from backtest.event_study.stats import BucketStatResult
from backtest.event_study.universe import EventUniverseAudit


def _result(
    *,
    window_bucket: str,
    horizon: int,
    p_fdr: float | None,
) -> BucketStatResult:
    return BucketStatResult(
        bucket_label=window_bucket,
        horizon=horizon,
        n_events_raw=10,
        n_events_dedup=8,
        n_events_scored=8,
        n_effective=4,
        mean_event_return=0.12,
        median_event_return=0.10,
        hit_rate_event=0.75,
        p10_event_return=-0.02,
        p25_event_return=0.01,
        p75_event_return=0.20,
        p90_event_return=0.30,
        mean_cluster_return=0.08,
        median_cluster_return=0.07,
        hit_rate_cluster=0.75,
        t_stat=2.1,
        p_value=0.04,
        p_fdr=p_fdr,
    )


def _audit() -> EventUniverseAudit:
    by_date = pd.DataFrame(
        {
            "date": ["2024-01-02", "2024-01-03", "2025-01-02"],
            "year": ["2024", "2024", "2025"],
            "candidate_count": [3, 3, 3],
            "eligible_count": [2, 2, 3],
        }
    )
    by_year = pd.DataFrame(
        {
            "year": ["2024", "2025"],
            "n_dates": [2, 1],
            "first_date": ["2024-01-02", "2025-01-02"],
            "last_date": ["2024-01-03", "2025-01-02"],
            "candidate_count": [3, 3],
            "eligible_count_min": [2, 3],
            "eligible_count_median": [2.0, 3.0],
            "eligible_count_max": [2, 3],
            "eligible_count_mean": [2.0, 3.0],
        }
    )
    summary = {
        "candidate_count": 3,
        "eligible_count_median": 2.0,
        "historical_market_cap_min_date": "2021-04-13",
        "historical_market_cap_max_date": "2026-04-10",
    }
    return EventUniverseAudit(by_date=by_date, by_year=by_year, summary=summary)


def test_build_markdown_report_contains_fixed_sections() -> None:
    config = EventStudyConfig(
        study_name="rvol_up2",
        report_split=ReportSplitConfig(oos_start_date="2024-09-01"),
    )
    report = build_markdown_report(
        config=config,
        research_question="RVOL 上穿 2 是否在之后产生稳定超额收益？",
        universe_audit=_audit(),
        results_by_window={
            "Full": [_result(window_bucket="rvol_up2_all", horizon=20, p_fdr=0.03)],
            "IS": [_result(window_bucket="rvol_up2_all", horizon=20, p_fdr=0.04)],
            "OOS": [],
        },
        failure_modes=["OOS 样本过少时不解读显著性"],
        next_steps=["若 OOS 保持同方向，再并入 PMARP/BBWP"],
    )

    assert "## 摘要" in report
    assert "## 研究问题" in report
    assert "## 测试口径" in report
    assert "## 样本与股票池质量" in report
    assert "## 主结果" in report
    assert "### Full" in report
    assert "### IS" in report
    assert "### OOS" in report
    assert "`OOS` 样本不足或未输出。" in report
    assert "## 失效条件" in report
    assert "## 结论与下一步" in report
    assert "## 附录" in report


def test_write_report_artifacts_writes_fixed_outputs(tmp_path) -> None:
    summary_df = build_summary_frame(
        {"Full": [_result(window_bucket="rvol_up2_all", horizon=20, p_fdr=0.03)]}
    )
    event_level_df = pd.DataFrame(
        [{"symbol": "AAPL", "date": "2024-01-02", "bucket": "rvol_up2_all"}]
    )
    paths = write_report_artifacts(
        output_dir=tmp_path,
        summary_df=summary_df,
        event_level_df=event_level_df,
        universe_audit=_audit(),
        report_markdown="# Demo",
    )

    assert set(paths.keys()) == {
        "summary.csv",
        "event_level.csv",
        "universe_audit.csv",
        "report.md",
    }
    for path in paths.values():
        assert (tmp_path / Path(path).name).exists()
