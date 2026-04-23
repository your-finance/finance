from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from scipy.stats import ttest_1samp

from src.indicators.pmarp import calculate_pmarp
from src.indicators.rvol import calculate_rvol_series


@dataclass(frozen=True)
class RVOLSignalStatsConfig:
    study_start_date: str = "2021-07-01"
    rvol_lookback: int = 150
    rvol_threshold: float = 2.0
    pmarp_ema_period: int = 20
    pmarp_lookback: int = 150
    flat_move_threshold: float = 0.01
    pmarp_low_cutoff: float = 20.0
    pmarp_high_cutoff: float = 80.0


@dataclass(frozen=True)
class RVOLSignalStatResult:
    signal_label: str
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


def build_rvol_feature_frames(
    price_dict: Dict[str, pd.DataFrame],
    config: RVOLSignalStatsConfig,
) -> Dict[str, pd.DataFrame]:
    frames: Dict[str, pd.DataFrame] = {}

    for symbol, raw in price_dict.items():
        frame = _build_symbol_feature_frame(raw, config)
        if not frame.empty:
            frames[symbol] = frame
    return frames


def build_rvol_signal_buckets(
    feature_frames: Dict[str, pd.DataFrame],
    config: RVOLSignalStatsConfig,
) -> Dict[str, Dict[str, List[str]]]:
    buckets: Dict[str, Dict[str, List[str]]] = defaultdict(dict)

    def add_event(bucket: str, symbol: str, date_str: str) -> None:
        buckets.setdefault(bucket, {}).setdefault(symbol, []).append(date_str)

    for symbol, frame in feature_frames.items():
        ordered = frame.sort_values("date").reset_index(drop=True)
        for _, row in ordered.iterrows():
            date_str = str(row["date"])
            if date_str < config.study_start_date:
                continue
            if not bool(row.get("rvol_up2", False)):
                continue

            add_event("rvol_up2_all", symbol, date_str)

            move_bucket = row.get("move_bucket")
            if move_bucket in {"sign_neg", "sign_flat", "sign_pos"}:
                add_event(f"rvol_up2_{move_bucket}", symbol, date_str)

            pmarp_bucket = row.get("pmarp_bucket")
            if pmarp_bucket in {"pmarp_low", "pmarp_mid", "pmarp_high"}:
                add_event(f"rvol_up2_{pmarp_bucket}", symbol, date_str)

            combined = _combined_bucket(move_bucket, pmarp_bucket)
            if combined is not None:
                add_event(f"rvol_up2_{combined}", symbol, date_str)

    return dict(buckets)


def filter_events_by_date(
    events: Dict[str, List[str]],
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Dict[str, List[str]]:
    filtered: Dict[str, List[str]] = {}
    for symbol, dates in events.items():
        kept = [
            d for d in dates
            if (start_date is None or d >= start_date)
            and (end_date is None or d <= end_date)
        ]
        if kept:
            filtered[symbol] = kept
    return filtered


def build_symbol_date_index(
    feature_frames: Dict[str, pd.DataFrame],
) -> Dict[str, Dict[str, int]]:
    return {
        symbol: {
            str(date): idx
            for idx, date in enumerate(
                frame.sort_values("date")["date"].astype(str).tolist()
            )
        }
        for symbol, frame in feature_frames.items()
    }


def run_bucket_event_stats(
    signal_label: str,
    events: Dict[str, List[str]],
    return_matrices: Dict[int, pd.DataFrame],
    symbol_date_index: Dict[str, Dict[str, int]],
) -> List[RVOLSignalStatResult]:
    results: List[RVOLSignalStatResult] = []
    for horizon, ret_df in sorted(return_matrices.items()):
        results.append(
            _study_for_horizon(
                signal_label=signal_label,
                horizon=horizon,
                events=events,
                ret_df=ret_df,
                symbol_date_index=symbol_date_index,
            )
        )
    return results


def _study_for_horizon(
    signal_label: str,
    horizon: int,
    events: Dict[str, List[str]],
    ret_df: pd.DataFrame,
    symbol_date_index: Dict[str, Dict[str, int]],
) -> RVOLSignalStatResult:
    n_events_raw = sum(len(dates) for dates in events.values())
    deduped_events = _deoverlap_events(events, symbol_date_index, horizon)

    n_events_dedup = sum(len(dates) for dates in deduped_events.values())
    n_events_scored = 0
    event_returns: List[float] = []
    date_bucket: Dict[str, List[float]] = defaultdict(list)

    for symbol, event_dates in deduped_events.items():
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

    return RVOLSignalStatResult(
        signal_label=signal_label,
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


def _build_symbol_feature_frame(
    df: pd.DataFrame,
    config: RVOLSignalStatsConfig,
) -> pd.DataFrame:
    ordered = df.sort_values("date").reset_index(drop=True).copy()
    if ordered.empty:
        return ordered

    ordered["date"] = ordered["date"].astype(str).str[:10]
    close = ordered["close"].astype(float)
    volume = ordered["volume"].astype(float)

    rvol = calculate_rvol_series(volume, lookback=config.rvol_lookback)
    pmarp = calculate_pmarp(
        close,
        ema_period=config.pmarp_ema_period,
        lookback=config.pmarp_lookback,
    )
    daily_return = close.pct_change()

    ordered["rvol"] = rvol
    ordered["pmarp"] = pmarp
    ordered["daily_return"] = daily_return
    ordered["rvol_up2"] = (
        (rvol.shift(1) <= config.rvol_threshold)
        & (rvol > config.rvol_threshold)
    ).fillna(False)
    ordered["move_bucket"] = daily_return.apply(
        lambda value: _move_bucket(value, config.flat_move_threshold)
    )
    ordered["pmarp_bucket"] = pmarp.apply(
        lambda value: _pmarp_bucket(
            value,
            low_cutoff=config.pmarp_low_cutoff,
            high_cutoff=config.pmarp_high_cutoff,
        )
    )

    return ordered


def _deoverlap_events(
    events: Dict[str, List[str]],
    symbol_date_index: Dict[str, Dict[str, int]],
    horizon: int,
) -> Dict[str, List[str]]:
    deduped: Dict[str, List[str]] = {}

    for symbol, event_dates in events.items():
        date_index = symbol_date_index.get(symbol)
        if not date_index:
            continue

        ordered_dates = sorted(
            {date for date in event_dates if date in date_index},
            key=lambda date: date_index[date],
        )
        kept: List[str] = []
        last_kept_idx: Optional[int] = None

        for date in ordered_dates:
            idx = date_index[date]
            if last_kept_idx is None or idx - last_kept_idx > horizon:
                kept.append(date)
                last_kept_idx = idx

        if kept:
            deduped[symbol] = kept

    return deduped


def _move_bucket(value: float, flat_threshold: float) -> Optional[str]:
    if pd.isna(value):
        return None
    if value < -flat_threshold:
        return "sign_neg"
    if value > flat_threshold:
        return "sign_pos"
    return "sign_flat"


def _pmarp_bucket(
    value: float,
    low_cutoff: float,
    high_cutoff: float,
) -> Optional[str]:
    if pd.isna(value):
        return None
    if value < low_cutoff:
        return "pmarp_low"
    if value > high_cutoff:
        return "pmarp_high"
    return "pmarp_mid"


def _combined_bucket(
    move_bucket: Optional[str],
    pmarp_bucket: Optional[str],
) -> Optional[str]:
    mapping = {
        ("sign_neg", "pmarp_low"): "panic_proxy",
        ("sign_flat", "pmarp_mid"): "base_proxy",
        ("sign_pos", "pmarp_high"): "churn_proxy",
    }
    return mapping.get((move_bucket, pmarp_bucket))


def _quantile(values: np.ndarray, q: float) -> float:
    if len(values) == 0:
        return 0.0
    return float(np.quantile(values, q))
