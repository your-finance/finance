"""
择时研究聚合器

对全池 + 指数跑择时回测，汇总统计结果。
"""

import logging
import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from backtest.timing.engine import TimingResult, run_timing_backtest
from backtest.timing.signals import SIGNAL_REGISTRY

logger = logging.getLogger(__name__)

# VIX 信号需要 aux_data (^VIX 价格序列)
_VIX_SIGNALS = {"VIX_MA", "VIX_Spike", "VIX_Percentile", "VIX_RSI",
                "VIX_Spike_Hold", "VIX_Spike_Revert"}


@dataclass
class TimingStudyConfig:
    """择时研究配置"""
    signal_name: str
    signal_params: dict = field(default_factory=dict)
    symbols: Optional[List[str]] = None     # None = 全池
    include_indices: List[str] = field(default_factory=lambda: ["QQQ", "SPY"])
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    min_trades: int = 2                     # 最少交易次数过滤


@dataclass
class AggregateResult:
    """聚合结果"""
    signal_name: str
    signal_params: dict
    n_stocks: int
    mean_excess_cagr: float
    std_excess_cagr: float
    t_stat: float
    p_value: float
    hit_rate: float                     # % 跑赢 buy-and-hold
    mean_sharpe_diff: float
    mean_time_in_market: float
    mean_n_trades: float
    per_stock_results: List[TimingResult]
    index_results: List[TimingResult]


def run_timing_study(config: TimingStudyConfig, adapter) -> AggregateResult:
    """
    执行择时研究

    1. adapter.load_all()
    2. 对每只股票：生成信号 -> run_timing_backtest -> TimingResult
    3. 对指数：同上
    4. 聚合统计

    Args:
        config: 择时研究配置
        adapter: USStocksAdapter (需有 load_all, _load_prices)

    Returns:
        AggregateResult
    """
    # 获取信号函数和参数
    if config.signal_name not in SIGNAL_REGISTRY:
        raise ValueError(
            "Unknown signal: %s. Available: %s"
            % (config.signal_name, list(SIGNAL_REGISTRY.keys()))
        )

    signal_fn, default_params = SIGNAL_REGISTRY[config.signal_name]
    params = {**default_params, **config.signal_params}

    # 加载 VIX aux_data (仅对 VIX 信号)
    aux_data = None
    if config.signal_name in _VIX_SIGNALS:
        aux_data = adapter._load_prices("^VIX")
        if aux_data is None or len(aux_data) < 70:
            logger.error("^VIX data unavailable or too short for %s", config.signal_name)
            return _aggregate(config, params, [], [])

    # 加载数据
    price_cache = adapter.load_all()

    # 确定股票列表
    if config.symbols:
        symbols = [s for s in config.symbols if s in price_cache]
    else:
        symbols = list(price_cache.keys())

    logger.info(
        "择时研究: signal=%s, params=%s, stocks=%d, indices=%s",
        config.signal_name, params, len(symbols), config.include_indices,
    )

    # 构建运行参数 (VIX 信号注入 aux_data)
    run_params = dict(params)
    if aux_data is not None:
        run_params["aux_data"] = aux_data

    # 跑全池
    per_stock_results = []
    for sym in symbols:
        result = _run_single(
            sym, config.signal_name, price_cache[sym],
            signal_fn, run_params, config.start_date, config.end_date,
        )
        if result is not None and result.n_trades >= config.min_trades:
            per_stock_results.append(result)

    logger.info(
        "池内结果: %d / %d (过滤 n_trades < %d)",
        len(per_stock_results), len(symbols), config.min_trades,
    )

    # 跑指数
    index_results = []
    for idx_sym in config.include_indices:
        idx_df = adapter._load_prices(idx_sym)
        if idx_df is not None and len(idx_df) >= 70:
            result = _run_single(
                idx_sym, config.signal_name, idx_df,
                signal_fn, run_params, config.start_date, config.end_date,
            )
            if result is not None:
                index_results.append(result)

    # 聚合统计 (用原始 params，不含 DataFrame)
    return _aggregate(config, params, per_stock_results, index_results)


def _run_single(
    symbol: str,
    signal_name: str,
    price_df,
    signal_fn,
    params: dict,
    start_date: Optional[str],
    end_date: Optional[str],
) -> Optional[TimingResult]:
    """对单只股票跑择时回测"""
    import pandas as pd

    df = price_df.copy()

    # 日期过滤
    if start_date:
        df = df[df["date"].astype(str) >= start_date]
    if end_date:
        df = df[df["date"].astype(str) <= end_date]

    df = df.reset_index(drop=True)

    if len(df) < 70:
        return None

    try:
        signals = signal_fn(df, **params)
        return run_timing_backtest(symbol, signal_name, df, signals)
    except Exception as e:
        logger.warning("%s: 回测失败: %s", symbol, e)
        return None


def _aggregate(
    config: TimingStudyConfig,
    params: dict,
    per_stock_results: List[TimingResult],
    index_results: List[TimingResult],
) -> AggregateResult:
    """聚合所有个股结果"""
    n = len(per_stock_results)

    if n == 0:
        return AggregateResult(
            signal_name=config.signal_name,
            signal_params=params,
            n_stocks=0,
            mean_excess_cagr=0.0,
            std_excess_cagr=0.0,
            t_stat=0.0,
            p_value=1.0,
            hit_rate=0.0,
            mean_sharpe_diff=0.0,
            mean_time_in_market=0.0,
            mean_n_trades=0.0,
            per_stock_results=[],
            index_results=index_results,
        )

    excess_cagrs = [r.excess_cagr for r in per_stock_results]
    sharpe_diffs = [r.sharpe_diff for r in per_stock_results]
    time_in_markets = [r.time_in_market for r in per_stock_results]
    n_trades_list = [r.n_trades for r in per_stock_results]

    mean_excess = sum(excess_cagrs) / n
    std_excess = (
        math.sqrt(sum((x - mean_excess) ** 2 for x in excess_cagrs) / (n - 1))
        if n > 1 else 0.0
    )

    # t-test: H0: mean_excess_cagr = 0
    if std_excess > 1e-10 and n > 1:
        t_stat = mean_excess / (std_excess / math.sqrt(n))
        # 近似 p-value (两尾, 用正态近似对大 n)
        p_value = _approx_p_value(t_stat, n - 1)
    else:
        t_stat = 0.0
        p_value = 1.0

    hit_rate = sum(1 for x in excess_cagrs if x > 0) / n

    return AggregateResult(
        signal_name=config.signal_name,
        signal_params=params,
        n_stocks=n,
        mean_excess_cagr=round(mean_excess, 6),
        std_excess_cagr=round(std_excess, 6),
        t_stat=round(t_stat, 4),
        p_value=round(p_value, 6),
        hit_rate=round(hit_rate, 4),
        mean_sharpe_diff=round(sum(sharpe_diffs) / n, 4),
        mean_time_in_market=round(sum(time_in_markets) / n, 4),
        mean_n_trades=round(sum(n_trades_list) / n, 1),
        per_stock_results=per_stock_results,
        index_results=index_results,
    )


def _approx_p_value(t: float, df: int) -> float:
    """
    t-distribution 的双尾 p-value

    使用 scipy.stats.t 精确计算。
    """
    from scipy.stats import t as t_dist

    return float(t_dist.sf(abs(t), df) * 2)
