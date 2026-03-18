#!/usr/bin/env python3
"""
VIX Spike 优化参数扫描

对 VIX_Spike_Hold 和 VIX_Spike_Revert 做参数扫描，
与原始 VIX_Spike 对比。
"""

import logging
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

from backtest.adapters.us_stocks import USStocksAdapter
from backtest.timing.runner import TimingStudyConfig, run_timing_study

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)


def main():
    adapter = USStocksAdapter()

    configs = []

    # 基线: 原始 VIX_Spike
    configs.append(("VIX_Spike (baseline)", "VIX_Spike",
                     {"buy_threshold": 30, "sell_threshold": 20}))

    # VIX_Spike_Hold: hold_days 扫描
    for hold in [5, 10, 20, 40, 60]:
        configs.append(
            ("VIX_Spike_Hold (hold=%d)" % hold, "VIX_Spike_Hold",
             {"buy_threshold": 30, "hold_days": hold})
        )

    # VIX_Spike_Revert: exit_drop_pct 扫描
    for pct in [20, 30, 40, 50]:
        configs.append(
            ("VIX_Spike_Revert (drop=%d%%)" % pct, "VIX_Spike_Revert",
             {"buy_threshold": 30, "exit_drop_pct": pct})
        )

    # 额外: 降低买入门槛
    for thresh in [25, 28]:
        configs.append(
            ("VIX_Spike_Hold (th=%d,hold=20)" % thresh, "VIX_Spike_Hold",
             {"buy_threshold": thresh, "hold_days": 20})
        )

    print("")
    print("=" * 100)
    print("  VIX Spike Optimization Sweep")
    print("=" * 100)
    print("")
    print("%-38s %8s %8s %8s %8s %8s %8s %6s" % (
        "Strategy", "ExCAGR", "t-stat", "p-value", "HitRate",
        "InMkt%", "Trades", "QQQ_Ex",
    ))
    print("-" * 100)

    for label, signal_name, params in configs:
        config = TimingStudyConfig(
            signal_name=signal_name,
            signal_params=params,
            include_indices=["QQQ", "SPY"],
        )

        result = run_timing_study(config, adapter)

        # QQQ excess
        qqq_ex = 0.0
        for ir in result.index_results:
            if ir.symbol == "QQQ":
                qqq_ex = ir.excess_cagr
                break

        sig = ""
        if result.p_value < 0.001:
            sig = "***"
        elif result.p_value < 0.01:
            sig = "**"
        elif result.p_value < 0.05:
            sig = "*"

        print("%-38s %+7.2f%% %8.2f %7.4f%s %7.1f%% %7.1f%% %6.1f %+6.2f%%" % (
            label,
            result.mean_excess_cagr * 100,
            result.t_stat,
            result.p_value,
            sig,
            result.hit_rate * 100,
            result.mean_time_in_market * 100,
            result.mean_n_trades,
            qqq_ex * 100,
        ))

    print("-" * 100)
    print("")


if __name__ == "__main__":
    main()
