from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace
from typing import Dict, List, Optional, Sequence

import numpy as np
import pandas as pd
from scipy.stats import ttest_1samp


@dataclass(frozen=True)
class BucketStatResult:
    bucket_label: str
    horizon: int
    n_events_raw: int
    n_events_dedup: int
    n_events_scored: int
    n_effective: int
    mean_event_return: float
    median_event_return: float
    hit_rate_event: float
    p10_event_return: float
    p25_event_return: float
    p75_event_return: float
    p90_event_return: float
    mean_cluster_return: float
    median_cluster_return: float
    hit_rate_cluster: float
    t_stat: float
    p_value: float
    p_fdr: Optional[float] = None


def build_symbol_date_index(
    feature_frames: Dict[str, pd.DataFrame],
) -> Dict[str, Dict[str, int]]:
    return {
        symbol: {
            str(date)[:10]: idx
            for idx, date in enumerate(
                frame.sort_values("date")["date"].astype(str).tolist()
            )
        }
        for symbol, frame in feature_frames.items()
    }


def deoverlap_symbol_events(
    events: Dict[str, List[str]],
    symbol_date_index: Dict[str, Dict[str, int]],
    horizon: int,
) -> Dict[str, List[str]]:
    """Apply same-symbol hard-window exclusion.

    This is intentionally the conservative version:
    keep the first event, then reject every later event whose date-index
    distance is `<= horizon`. The next event is only allowed after the full
    holding window has elapsed.
    """
    deduped: Dict[str, List[str]] = {}
    for symbol, event_dates in events.items():
        date_index = symbol_date_index.get(symbol)
        if not date_index:
            continue

        ordered_dates = sorted(
            {str(date)[:10] for date in event_dates if str(date)[:10] in date_index},
            key=lambda date: date_index[date],
        )
        kept: List[str] = []
        last_kept_idx: Optional[int] = None
        for date_str in ordered_dates:
            idx = date_index[date_str]
            if last_kept_idx is None or idx - last_kept_idx > horizon:
                kept.append(date_str)
                last_kept_idx = idx
        if kept:
            deduped[symbol] = kept
    return deduped


def summarize_bucket_stats(
    bucket_label: str,
    events: Dict[str, List[str]],
    return_matrices: Dict[int, pd.DataFrame],
    symbol_date_index: Dict[str, Dict[str, int]],
) -> List[BucketStatResult]:
    return [
        summarize_bucket_for_horizon(
            bucket_label=bucket_label,
            horizon=horizon,
            events=events,
            ret_df=ret_df,
            symbol_date_index=symbol_date_index,
        )
        for horizon, ret_df in sorted(return_matrices.items())
    ]


def summarize_bucket_for_horizon(
    bucket_label: str,
    horizon: int,
    events: Dict[str, List[str]],
    ret_df: pd.DataFrame,
    symbol_date_index: Dict[str, Dict[str, int]],
) -> BucketStatResult:
    n_events_raw = sum(len(values) for values in events.values())
    deduped = deoverlap_symbol_events(events, symbol_date_index, horizon)
    n_events_dedup = sum(len(values) for values in deduped.values())

    event_returns: List[float] = []
    date_bucket: Dict[str, List[float]] = defaultdict(list)
    n_events_scored = 0

    for symbol, event_dates in deduped.items():
        if symbol not in ret_df.columns:
            continue
        for date_str in event_dates:
            if date_str not in ret_df.index:
                continue
            value = ret_df.loc[date_str, symbol]
            if pd.notna(value):
                value = float(value)
                event_returns.append(value)
                date_bucket[date_str].append(value)
                n_events_scored += 1

    event_arr = np.array(event_returns, dtype=float)
    cluster_means = np.array(
        [np.mean(values) for values in date_bucket.values()],
        dtype=float,
    )

    if len(cluster_means) >= 2:
        t_stat, p_value = ttest_1samp(cluster_means, 0.0)
        t_stat = float(t_stat)
        p_value = float(p_value)
    else:
        t_stat = 0.0
        p_value = 1.0

    return BucketStatResult(
        bucket_label=bucket_label,
        horizon=horizon,
        n_events_raw=n_events_raw,
        n_events_dedup=n_events_dedup,
        n_events_scored=n_events_scored,
        n_effective=len(cluster_means),
        mean_event_return=float(np.mean(event_arr)) if len(event_arr) else 0.0,
        median_event_return=float(np.median(event_arr)) if len(event_arr) else 0.0,
        hit_rate_event=float(np.mean(event_arr > 0)) if len(event_arr) else 0.0,
        p10_event_return=_quantile(event_arr, 0.10),
        p25_event_return=_quantile(event_arr, 0.25),
        p75_event_return=_quantile(event_arr, 0.75),
        p90_event_return=_quantile(event_arr, 0.90),
        mean_cluster_return=float(np.mean(cluster_means)) if len(cluster_means) else 0.0,
        median_cluster_return=float(np.median(cluster_means)) if len(cluster_means) else 0.0,
        hit_rate_cluster=float(np.mean(cluster_means > 0)) if len(cluster_means) else 0.0,
        t_stat=t_stat,
        p_value=p_value,
    )


def apply_bh_fdr(results: Sequence[BucketStatResult]) -> List[BucketStatResult]:
    p_values = [result.p_value for result in results]
    corrected = _apply_bh_fdr_to_p_values(p_values)
    return [
        replace(result, p_fdr=p_fdr)
        for result, p_fdr in zip(results, corrected)
    ]


def _apply_bh_fdr_to_p_values(p_values: Sequence[float]) -> List[float]:
    if not p_values:
        return []
    n = len(p_values)
    indexed = sorted(enumerate(p_values), key=lambda item: item[1])
    adjusted = [1.0] * n
    running_min = 1.0
    for rank, (orig_idx, p_value) in enumerate(reversed(indexed), start=1):
        adjusted_p = min(1.0, p_value * n / (n - rank + 1))
        running_min = min(running_min, adjusted_p)
        adjusted[orig_idx] = running_min
    return adjusted


def _quantile(values: np.ndarray, q: float) -> float:
    if len(values) == 0:
        return 0.0
    return float(np.quantile(values, q))
