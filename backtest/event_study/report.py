from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence

import pandas as pd

from backtest.event_study.protocol import EventStudyConfig
from backtest.event_study.stats import BucketStatResult
from backtest.event_study.universe import EventUniverseAudit


def build_summary_frame(
    results_by_window: Mapping[str, Sequence[BucketStatResult]],
) -> pd.DataFrame:
    rows: List[dict] = []
    for window_label, results in results_by_window.items():
        for result in results:
            rows.append(
                {
                    "window": window_label,
                    "bucket": result.bucket_label,
                    "horizon": result.horizon,
                    "n_raw": result.n_events_raw,
                    "n_dedup": result.n_events_dedup,
                    "n_scored": result.n_events_scored,
                    "n_effective": result.n_effective,
                    "mean_event_return": result.mean_event_return,
                    "median_event_return": result.median_event_return,
                    "hit_rate_event": result.hit_rate_event,
                    "mean_cluster_return": result.mean_cluster_return,
                    "median_cluster_return": result.median_cluster_return,
                    "hit_rate_cluster": result.hit_rate_cluster,
                    "p_value": result.p_value,
                    "p_fdr": result.p_fdr,
                }
            )
    return pd.DataFrame(rows)


def merge_summary_frames(
    raw_summary_df: pd.DataFrame,
    excess_summary_df: pd.DataFrame,
) -> pd.DataFrame:
    join_keys = ["window", "bucket", "horizon"]
    raw = raw_summary_df.rename(
        columns={
            "n_raw": "raw_n_raw",
            "n_dedup": "raw_n_dedup",
            "n_scored": "raw_n_scored",
            "n_effective": "raw_n_effective",
            "mean_event_return": "raw_mean_event_return",
            "median_event_return": "raw_median_event_return",
            "hit_rate_event": "raw_hit_rate_event",
            "mean_cluster_return": "raw_mean_cluster_return",
            "median_cluster_return": "raw_median_cluster_return",
            "hit_rate_cluster": "raw_hit_rate_cluster",
            "p_value": "raw_p_value",
            "p_fdr": "raw_p_fdr",
        }
    )
    excess = excess_summary_df.rename(
        columns={
            "n_raw": "excess_n_raw",
            "n_dedup": "excess_n_dedup",
            "n_scored": "excess_n_scored",
            "n_effective": "excess_n_effective",
            "mean_event_return": "excess_mean_event_return",
            "median_event_return": "excess_median_event_return",
            "hit_rate_event": "excess_hit_rate_event",
            "mean_cluster_return": "excess_mean_cluster_return",
            "median_cluster_return": "excess_median_cluster_return",
            "hit_rate_cluster": "excess_hit_rate_cluster",
            "p_value": "excess_p_value",
            "p_fdr": "excess_p_fdr",
        }
    )
    return raw.merge(excess, on=join_keys, how="outer")


def build_markdown_report(
    config: EventStudyConfig,
    research_question: str,
    universe_audit: EventUniverseAudit,
    results_by_window: Mapping[str, Sequence[BucketStatResult]],
    notes: Optional[Sequence[str]] = None,
    failure_modes: Optional[Sequence[str]] = None,
    next_steps: Optional[Sequence[str]] = None,
) -> str:
    summary_frame = build_summary_frame(results_by_window)
    notes = list(notes or [])
    failure_modes = list(failure_modes or ["待补充"])
    next_steps = list(next_steps or ["待补充"])

    lines: List[str] = []
    lines.append(f"# {config.study_name} 事件研究报告")
    lines.append("")
    lines.append("## 摘要")
    lines.append("")
    lines.append(_build_summary_blurb(config, universe_audit, summary_frame))
    lines.append("")
    lines.append("## 研究问题")
    lines.append("")
    lines.append(research_question)
    lines.append("")
    lines.append("## 测试口径")
    lines.append("")
    lines.extend(_build_test_protocol_lines(config))
    lines.append("")
    lines.append("## 样本与股票池质量")
    lines.append("")
    lines.append("### 年度 Eligible Count")
    lines.append("")
    lines.append(_markdown_table(universe_audit.by_year))
    lines.append("")
    lines.append("### 审计摘要")
    lines.append("")
    lines.append(_markdown_table(pd.DataFrame([universe_audit.summary])))
    lines.append("")
    lines.append("## 主结果")
    lines.append("")
    for window_label in ["Full", "IS", "OOS"]:
        lines.append(f"### {window_label}")
        lines.append("")
        window_frame = summary_frame[summary_frame["window"] == window_label]
        if window_frame.empty:
            lines.append(f"`{window_label}` 样本不足或未输出。")
        else:
            lines.append(_markdown_table(window_frame))
        lines.append("")
    lines.append("## 分层结果")
    lines.append("")
    lines.append("第一阶段暂不输出额外分层；默认 bucket 维度直接体现在主结果表。")
    lines.append("")
    lines.append("## 失效条件")
    lines.append("")
    lines.extend(f"- {item}" for item in failure_modes)
    lines.append("")
    lines.append("## 结论与下一步")
    lines.append("")
    lines.extend(f"- {item}" for item in next_steps)
    if notes:
        lines.append("")
        lines.append("## 附录")
        lines.append("")
        lines.extend(f"- {item}" for item in notes)
    else:
        lines.append("")
        lines.append("## 附录")
        lines.append("")
        lines.append("- 无")
    lines.append("")
    return "\n".join(lines)


def write_report_artifacts(
    output_dir: str | Path,
    summary_df: pd.DataFrame,
    event_level_df: pd.DataFrame,
    universe_audit: EventUniverseAudit,
    report_markdown: str,
) -> Dict[str, str]:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)

    summary_path = target / "summary.csv"
    event_level_path = target / "event_level.csv"
    universe_audit_path = target / "universe_audit.csv"
    report_path = target / "report.md"

    summary_df.to_csv(summary_path, index=False)
    event_level_df.to_csv(event_level_path, index=False)
    universe_audit.to_frame().to_csv(universe_audit_path, index=False)
    report_path.write_text(report_markdown, encoding="utf-8")

    return {
        "summary.csv": str(summary_path),
        "event_level.csv": str(event_level_path),
        "universe_audit.csv": str(universe_audit_path),
        "report.md": str(report_path),
    }


def build_markdown_report_from_summary(
    config: EventStudyConfig,
    research_question: str,
    universe_audit: EventUniverseAudit,
    summary_df: pd.DataFrame,
    notes: Optional[Sequence[str]] = None,
    failure_modes: Optional[Sequence[str]] = None,
    next_steps: Optional[Sequence[str]] = None,
) -> str:
    notes = list(notes or [])
    failure_modes = list(failure_modes or ["待补充"])
    next_steps = list(next_steps or ["待补充"])

    lines: List[str] = []
    lines.append(f"# {config.study_name} 事件研究报告")
    lines.append("")
    lines.append("## 摘要")
    lines.append("")
    lines.append(_build_summary_blurb_from_merged(config, universe_audit, summary_df))
    lines.append("")
    lines.append("## 研究问题")
    lines.append("")
    lines.append(research_question)
    lines.append("")
    lines.append("## 测试口径")
    lines.append("")
    lines.extend(_build_test_protocol_lines(config))
    lines.append("")
    lines.append("## 样本与股票池质量")
    lines.append("")
    lines.append("### 年度 Eligible Count")
    lines.append("")
    lines.append(_markdown_table(universe_audit.by_year))
    lines.append("")
    lines.append("### 审计摘要")
    lines.append("")
    lines.append(_markdown_table(pd.DataFrame([universe_audit.summary])))
    lines.append("")
    lines.append("## 主结果")
    lines.append("")
    for window_label in ["Full", "IS", "OOS"]:
        lines.append(f"### {window_label}")
        lines.append("")
        window_frame = summary_df[summary_df["window"] == window_label]
        if window_frame.empty:
            lines.append(f"`{window_label}` 样本不足或未输出。")
        else:
            lines.append(_markdown_table(window_frame))
        lines.append("")
    lines.append("## 分层结果")
    lines.append("")
    lines.append("第一阶段暂不输出额外分层；默认 bucket 维度直接体现在主结果表。")
    lines.append("")
    lines.append("## 失效条件")
    lines.append("")
    lines.extend(f"- {item}" for item in failure_modes)
    lines.append("")
    lines.append("## 结论与下一步")
    lines.append("")
    lines.extend(f"- {item}" for item in next_steps)
    lines.append("")
    lines.append("## 附录")
    lines.append("")
    if notes:
        lines.extend(f"- {item}" for item in notes)
    else:
        lines.append("- 无")
    lines.append("")
    return "\n".join(lines)


def _build_summary_blurb(
    config: EventStudyConfig,
    universe_audit: EventUniverseAudit,
    summary_frame: pd.DataFrame,
) -> str:
    if summary_frame.empty:
        return (
            f"本次研究测试 `{config.study_name}`，但当前没有可展示的事件统计结果。"
        )

    top_row = summary_frame.sort_values(
        ["window", "p_fdr", "mean_cluster_return"],
        ascending=[True, True, False],
        na_position="last",
    ).iloc[0]
    eligible_median = universe_audit.summary.get("eligible_count_median")
    return (
        f"本次研究测试 `{config.study_name}`，默认股票池为 "
        f"`{config.universe.universe_name}` 且历史市值门槛为 "
        f"`{config.universe.market_cap_min_usd:,.0f}`。"
        f" 当前最强结果来自 `{top_row['window']}` / `{top_row['bucket']}` / "
        f"`{int(top_row['horizon'])}d`，"
        f"聚类均值收益 `{top_row['mean_cluster_return']:.4f}`，"
        f"`p_fdr={_format_optional_float(top_row['p_fdr'])}`。"
        f" 样本审计显示日度 eligible count 中位数为 `{eligible_median}`。"
    )


def _build_summary_blurb_from_merged(
    config: EventStudyConfig,
    universe_audit: EventUniverseAudit,
    summary_df: pd.DataFrame,
) -> str:
    if summary_df.empty:
        return f"本次研究测试 `{config.study_name}`，但当前没有可展示的事件统计结果。"

    sortable = summary_df.copy()
    sortable["_rank_p"] = sortable["excess_p_fdr"].fillna(1.0)
    sortable["_rank_ret"] = sortable["excess_mean_cluster_return"].fillna(-999.0)
    top_row = sortable.sort_values(
        ["window", "_rank_p", "_rank_ret"],
        ascending=[True, True, False],
    ).iloc[0]
    eligible_median = universe_audit.summary.get("eligible_count_median")
    return (
        f"本次研究测试 `{config.study_name}`，默认股票池为 "
        f"`{config.universe.universe_name}` 且历史市值门槛为 "
        f"`{config.universe.market_cap_min_usd:,.0f}`。"
        f" 当前最强结果来自 `{top_row['window']}` / `{top_row['bucket']}` / "
        f"`{int(top_row['horizon'])}d`，"
        f"原始聚类均值收益 `{top_row['raw_mean_cluster_return']:.4f}`，"
        f"超额聚类均值收益 `{top_row['excess_mean_cluster_return']:.4f}`，"
        f"`excess_p_fdr={_format_optional_float(top_row['excess_p_fdr'])}`。"
        f" 样本审计显示日度 eligible count 中位数为 `{eligible_median}`。"
    )


def _build_test_protocol_lines(config: EventStudyConfig) -> List[str]:
    return [
        f"- 频率: `{config.frequency}`",
        f"- 事件类型: `{config.event_type}`",
        f"- 股票池: `{config.universe.universe_name}`",
        f"- 历史市值门槛: `{config.universe.market_cap_min_usd:,.0f}`",
        f"- 收益口径: `{config.returns.entry}` -> `{config.returns.exit}`",
        f"- Horizons: `{', '.join(str(h) for h in config.returns.horizons)}`",
        f"- 基准: `{config.returns.benchmark_symbol}`",
        f"- Excess 口径与股票完全同语义: `{config.returns.benchmark_same_semantics}`",
        f"- 缺失 `T+H close` 时直接 drop: `{config.returns.drop_missing_exit}`",
        f"- 同股去重: `{config.overlap.same_symbol_mode}`",
        f"- 日期聚类: `{config.overlap.cluster_mode}`",
        f"- FDR 家族: `{config.overlap.fdr_family}`",
        f"- OOS 起点: `{config.report_split.oos_start_date or '未设置'}`",
    ]


def _markdown_table(df: pd.DataFrame) -> str:
    if df.empty:
        return "_空_"
    headers = [str(col) for col in df.columns]
    rows = []
    for _, row in df.iterrows():
        rows.append([_format_cell(row[col]) for col in df.columns])

    header_line = "| " + " | ".join(headers) + " |"
    sep_line = "| " + " | ".join("---" for _ in headers) + " |"
    body = ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join([header_line, sep_line, *body])


def _format_cell(value: object) -> str:
    if pd.isna(value):
        return ""
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def _format_optional_float(value: object) -> str:
    if value is None or pd.isna(value):
        return "NA"
    return f"{float(value):.4f}"
