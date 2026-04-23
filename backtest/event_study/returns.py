from __future__ import annotations

from typing import Dict, List

import numpy as np
import pandas as pd


def build_t1open_return_matrices(
    price_dict: Dict[str, pd.DataFrame],
    computation_dates: List[str],
    horizons: List[int],
) -> Dict[int, pd.DataFrame]:
    """Build raw event returns with fixed event-study semantics.

    Signal on T
    Entry on T+1 open
    Exit on T+H close

    The matrix index remains the event date T.
    """
    normalized_price_dict = {
        symbol: _normalize_price_frame(df)
        for symbol, df in price_dict.items()
    }
    date_index_maps: Dict[str, Dict[str, int]] = {}
    sorted_dates_map: Dict[str, List[str]] = {}
    open_maps: Dict[str, Dict[str, float]] = {}
    close_maps: Dict[str, Dict[str, float]] = {}

    for symbol, df in normalized_price_dict.items():
        dates = df["date"].tolist()
        opens = df["open"].astype(float).tolist()
        closes = df["close"].astype(float).tolist()
        date_index_maps[symbol] = {d: i for i, d in enumerate(dates)}
        sorted_dates_map[symbol] = dates
        open_maps[symbol] = dict(zip(dates, opens))
        close_maps[symbol] = dict(zip(dates, closes))

    symbols = sorted(normalized_price_dict.keys())
    result: Dict[int, pd.DataFrame] = {}
    event_dates = [str(value)[:10] for value in computation_dates]
    for horizon in horizons:
        matrix_data: Dict[str, List[float]] = {sym: [] for sym in symbols}
        for comp_date in event_dates:
            for sym in symbols:
                ret = _t1open_close_forward_return(
                    comp_date=comp_date,
                    horizon=horizon,
                    date_index_map=date_index_maps[sym],
                    sorted_dates=sorted_dates_map[sym],
                    open_map=open_maps[sym],
                    close_map=close_maps[sym],
                )
                matrix_data[sym].append(ret)
        df = pd.DataFrame(matrix_data, index=event_dates)
        df.index.name = "date"
        result[horizon] = df
    return result


def build_t1open_excess_return_matrices(
    price_dict: Dict[str, pd.DataFrame],
    benchmark_df: pd.DataFrame,
    computation_dates: List[str],
    horizons: List[int],
) -> Dict[int, pd.DataFrame]:
    """Build stock excess returns using the same T+1-open/T+H-close semantics.

    If the benchmark cannot produce the matching exit price for an event, that
    event date is dropped for every symbol in the matrix (all values -> NaN).
    """
    stock_raw = build_t1open_return_matrices(price_dict, computation_dates, horizons)
    bench_raw = build_t1open_return_matrices(
        {"__BENCH__": benchmark_df},
        computation_dates,
        horizons,
    )

    result: Dict[int, pd.DataFrame] = {}
    for horizon in horizons:
        ret_df = stock_raw[horizon].copy()
        bench_series = bench_raw[horizon]["__BENCH__"]
        for date_str in ret_df.index:
            bench_ret = bench_series.get(date_str, np.nan)
            if pd.isna(bench_ret):
                ret_df.loc[date_str] = np.nan
            else:
                ret_df.loc[date_str] = ret_df.loc[date_str] - bench_ret
        result[horizon] = ret_df
    return result


def _normalize_price_frame(df: pd.DataFrame) -> pd.DataFrame:
    normalized = df.copy()
    normalized["date"] = normalized["date"].astype(str).str[:10]
    return normalized.sort_values("date").reset_index(drop=True)


def _t1open_close_forward_return(
    comp_date: str,
    horizon: int,
    date_index_map: Dict[str, int],
    sorted_dates: List[str],
    open_map: Dict[str, float],
    close_map: Dict[str, float],
) -> float:
    start_idx = date_index_map.get(comp_date)
    if start_idx is None:
        return np.nan

    entry_idx = start_idx + 1
    exit_idx = start_idx + horizon
    if entry_idx >= len(sorted_dates) or exit_idx >= len(sorted_dates):
        return np.nan

    entry_date = sorted_dates[entry_idx]
    exit_date = sorted_dates[exit_idx]
    entry_price = open_map.get(entry_date)
    exit_price = close_map.get(exit_date)
    if entry_price is None or exit_price is None or entry_price <= 0:
        return np.nan

    return exit_price / entry_price - 1.0
