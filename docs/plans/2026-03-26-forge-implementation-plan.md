# Forge — 接口级实现计划

> **依赖**: `docs/plans/2026-03-26-forge-strategy-optimizer.md` (v0.2)
> **目标**: 定义 runner.py / evaluator.py / campaign.lock.json 的函数签名、数据结构、字段，使得实现者可以机械性编码

---

## 1. campaign.lock.json — 实验配置锁

```jsonc
{
  // 元数据
  "campaign_id": "helen_v2_btc_001",
  "created_at": "2026-03-26T00:00:00Z",
  "strategy_name": "helen",
  "base_infra_sha": "663ed22",           // git SHA，evaluator/adapter 代码版本

  // 数据源
  "symbol": "BTCUSDT",
  "interval": "4h",
  "data_dir": "../data/crypto",           // 相对 forge/ 的路径
  "data_snapshot_hash": null,             // runner 首轮自动计算并填入

  // 时间窗口
  "warmup_start": "2017-08-17",
  "visible_windows": [
    {"name": "A", "start": "2019-01-01", "end": "2021-12-31"},
    {"name": "B", "start": "2020-01-01", "end": "2022-12-31"},
    {"name": "C", "start": "2021-01-01", "end": "2023-06-30"}
  ],
  "holdout_window": {"start": "2023-07-01", "end": "2026-03-26"},

  // 回测参数
  "transaction_cost_bps": 10.0,
  "rebalance_dead_zone_pct": 5.0,
  "days_per_year": 2190,                  // 365 × 6 (4H bars)

  // 门槛
  "gate_max_mdd": -0.55,                  // 每个 visible window 都必须 > 此值
  "gate_min_exposure": 0.20,              // 每个 visible window 都必须 > 此值

  // 棘轮
  "score_function": "min_excess_cagr",    // visible_score = min(window excess_cagr)

  // 停机规则
  "max_rounds": 50,
  "stale_stop_rounds": 20,               // 连续 N 轮无改进 → 停
  "structural_unlock_after_stale": 10,    // 参数面连续 N 轮无改进 → 解锁 Level 2
  "holdout_meltdown_threshold": -0.15,    // holdout excess_cagr 恶化超过此值 → 停

  // 参数面
  "parameter_surface_manifest": "manifests/helen_surface.yaml"
}
```

---

## 2. manifests/helen_surface.yaml — 参数面白名单

```yaml
# Helen v2.0 可调参数（Level 1 参数优化模式）
# agent 修改 candidate 时，Level 1 只允许改这些值

parameters:
  ema_period:
    type: int
    default: 144
    range: [50, 300]
    step: 10

  right_bear_slope_pct:
    type: float
    default: -0.03
    range: [-0.10, 0.0]
    step: 0.005

  right_neutral_slope_pct:
    type: float
    default: 0.0
    range: [-0.02, 0.05]
    step: 0.005

  right_trend_slope_pct:
    type: float
    default: 0.03
    range: [0.01, 0.20]
    step: 0.01

  pmarp_lookback:
    type: int
    default: 150
    range: [50, 300]
    step: 10

  bbwp_lookback:
    type: int
    default: 252
    range: [100, 500]
    step: 25

  rvol_window:
    type: int
    default: 20
    range: [10, 60]
    step: 5

  left_max_hold_bars:
    type: int
    default: 540
    range: [90, 1080]
    step: 90
```

---

## 3. evaluator.py — 评分裁判

### 3.1 公开接口

```python
"""
Forge evaluator — 不可改的评分裁判。

用法:
    python evaluator.py                        # 评估 candidate vs champion
    python evaluator.py --champion-only        # 只输出 champion baseline
    python evaluator.py --campaign lock.json   # 指定 campaign 文件
"""

import json
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class WindowResult:
    """单个时间窗口的回测结果"""
    name: str                # "A" / "B" / "C" / "holdout"
    start: str
    end: str
    cagr: float
    buyhold_cagr: float
    excess_cagr: float       # cagr - buyhold_cagr
    max_drawdown: float
    mean_exposure: float
    n_rebalances: int
    sharpe: float


@dataclass
class ForgeResult:
    """evaluator 的完整输出"""
    status: str              # "PASS" / "FAIL_GATE" / "FAIL_GUARD" / "ERROR"
    error_message: str       # 非空 when status=ERROR

    # Visible（agent 可见）
    visible_score: float     # min(window excess_cagr)
    visible_windows: List[WindowResult]

    # Holdout（agent 不可见，仅写入 private log）
    holdout: Optional[WindowResult]

    # 元数据
    strategy_hash: str       # candidate 文件的 SHA256
    data_hash: str           # 数据快照 hash
    infra_sha: str           # git SHA


def evaluate(
    campaign_path: Path,
    strategy_path: Path,
) -> ForgeResult:
    """
    核心评估函数。

    1. 加载 campaign.lock.json
    2. 加载数据（CryptoAdapter）
    3. 动态 import strategy_path 中的策略
    4. 对每个 visible window 跑回测
    5. 对 holdout window 跑回测
    6. 检查门槛
    7. 计算 visible_score
    8. 返回 ForgeResult
    """
    ...


def print_agent_result(result: ForgeResult, best_score: float) -> None:
    """
    打印 agent 可见的 stdout 输出。
    Holdout 字段打印 HIDDEN。
    """
    ...


def compute_data_hash(data_dir: Path, symbol: str, interval: str) -> str:
    """对数据文件计算 SHA256，用于 campaign.lock 的可复现性检查。"""
    ...
```

### 3.2 策略接口 Contract

`strategies/helen_candidate.py` 必须暴露以下接口供 evaluator import：

```python
"""
策略文件必须实现的接口。
evaluator 会动态 import 并调用这些函数。
"""

from dataclasses import dataclass
from typing import List
import pandas as pd


@dataclass
class StrategyConfig:
    """策略可调参数，对应 surface.yaml 的白名单。"""
    ema_period: int = 144
    right_bear_slope_pct: float = -0.03
    right_neutral_slope_pct: float = 0.0
    right_trend_slope_pct: float = 0.03
    pmarp_lookback: int = 150
    bbwp_lookback: int = 252
    rvol_window: int = 20
    left_max_hold_bars: int = 540
    # ... agent 可以加新字段


def evaluate_bar(
    snapshot_4h: dict,
    snapshot_1d: dict,
    state: dict,
    config: StrategyConfig,
) -> tuple[float, dict, list[str]]:
    """
    评估单根 4H bar。

    Args:
        snapshot_4h: 指标快照 {"close": float, "ema_slope_pct": float, "pmarp": {...}, "bbwp": {...}, "rvol": {...}}
        snapshot_1d: 同上，日线级别
        state: 可变状态 dict（由 evaluator 跨 bar 传递）
        config: 策略配置

    Returns:
        (target_position_pct, updated_state, reasons)
        target_position_pct: 0.0 ~ 100.0
        updated_state: 更新后的状态 dict
        reasons: 触发原因列表
    """
    ...


def get_default_config() -> StrategyConfig:
    """返回默认配置。"""
    ...


def get_initial_state() -> dict:
    """返回初始状态。"""
    ...
```

### 3.3 评估流程伪代码

```python
def evaluate(campaign_path, strategy_path):
    campaign = load_campaign(campaign_path)
    strategy = dynamic_import(strategy_path)  # importlib

    # 数据加载
    adapter_4h = CryptoAdapter(symbols=[campaign.symbol], interval="4h")
    adapter_1d = CryptoAdapter(symbols=[campaign.symbol], interval="1d")
    df_4h = adapter_4h.load_all()[campaign.symbol]
    df_1d = adapter_1d.load_all()[campaign.symbol]

    # 预计算指标（全量，一次性）
    config = strategy.get_default_config()
    prepared_4h = prepare_indicator_frame(df_4h, config)
    prepared_1d = prepare_indicator_frame(df_1d, config)

    # 遍历所有 4H bar，生成 target_positions
    state = strategy.get_initial_state()
    all_targets = []        # len == len(prepared_4h)
    all_timestamps = []

    for i in range(len(prepared_4h)):
        snap_4h = snapshot_from_row(prepared_4h, i)
        snap_1d = get_aligned_daily_snapshot(prepared_1d, prepared_4h, i)
        target, state, reasons = strategy.evaluate_bar(snap_4h, snap_1d, state, config)
        all_targets.append(target / 100.0)
        all_timestamps.append(snap_4h["timestamp"])

    # 对每个窗口切片并跑回测
    visible_results = []
    for window in campaign.visible_windows:
        result = run_window_backtest(
            prepared_4h, all_targets, all_timestamps,
            window, campaign
        )
        visible_results.append(result)

    holdout_result = run_window_backtest(
        prepared_4h, all_targets, all_timestamps,
        campaign.holdout_window, campaign
    )

    # 门槛检查（每个 visible window）
    for wr in visible_results:
        if wr.max_drawdown < campaign.gate_max_mdd:
            return ForgeResult(status="FAIL_GATE", ...)
        if wr.mean_exposure < campaign.gate_min_exposure:
            return ForgeResult(status="FAIL_GATE", ...)

    # 计算 visible_score
    visible_score = min(wr.excess_cagr for wr in visible_results)

    return ForgeResult(
        status="PASS",
        visible_score=visible_score,
        visible_windows=visible_results,
        holdout=holdout_result,
        strategy_hash=hash_file(strategy_path),
        data_hash=compute_data_hash(...),
        infra_sha=get_git_sha(),
    )
```

---

## 4. runner.py — 控制面

### 4.1 公开接口

```python
"""
Forge runner — 控制面。负责循环、mutation guard、晋级、日志、停机。

用法:
    python runner.py --rounds 50 --strategy helen
    python runner.py --rounds 50 --strategy helen --campaign campaign.lock.json
"""

import argparse
import json
import subprocess
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class RoundResult:
    """单轮实验结果"""
    round_num: int
    hypothesis: str
    status: str                    # PASS / FAIL_GATE / FAIL_GUARD / ERROR
    visible_score: float
    best_visible_score: float
    accepted: bool
    strategy_hash: str
    # visible window details
    window_results: list           # List[WindowResult]
    # holdout（仅写入 private log）
    holdout_excess_cagr: Optional[float]
    holdout_mdd: Optional[float]


def run_campaign(
    strategy_name: str = "helen",
    campaign_path: Optional[Path] = None,
    max_rounds: int = 50,
) -> None:
    """
    主循环入口。

    每轮：
    1. 复制 champion → candidate
    2. 调用 claude -p（传入 forge.md + champion + public log）
    3. Mutation guard 检查
    4. 调用 evaluator
    5. 比较 visible_score
    6. Promote 或 discard
    7. 写日志
    8. 检查停机规则
    """
    ...


def _copy_champion_to_candidate(strategy_name: str) -> None:
    """复制 champion → candidate，给 agent 一个干净的起点。"""
    ...


def _invoke_agent(
    forge_md: str,
    champion_code: str,
    public_log_tail: str,
    best_score: float,
    current_level: str,           # "parameter" / "structural"
) -> str:
    """
    调用 claude -p，返回 agent 的输出。
    Agent 应修改 candidate 文件并在头部写入 hypothesis。
    """
    ...


def _mutation_guard(
    strategy_name: str,
    campaign: dict,
    current_level: str,
) -> tuple[bool, str]:
    """
    检查 candidate 的修改是否合规。

    检查项:
    - candidate 文件是否可 import（语法正确）
    - candidate 是否实现了必要接口（evaluate_bar, get_default_config, get_initial_state）
    - 如果 Level 1（参数模式），检查是否只修改了 surface.yaml 白名单中的参数值
    - 没有修改 runner.py / evaluator.py / campaign.lock.json / private log

    Returns:
        (passed: bool, reason: str)
    """
    ...


def _extract_hypothesis(candidate_path: Path) -> str:
    """从 candidate 文件头部提取 hypothesis 注释。"""
    ...


def _write_public_log(round_result: RoundResult, log_path: Path) -> None:
    """追加一行到 experiments_public.tsv（不含 holdout）。"""
    ...


def _write_private_log(
    round_result: RoundResult,
    campaign: dict,
    log_path: Path,
) -> None:
    """追加一行到 experiments_private.jsonl（含 holdout + hashes）。"""
    ...


def _promote_candidate(strategy_name: str) -> None:
    """candidate → champion（文件覆盖）。"""
    ...


def _discard_candidate(strategy_name: str) -> None:
    """删除 candidate 文件。"""
    ...


def _check_stop_rules(
    campaign: dict,
    round_num: int,
    stale_count: int,
    champion_holdout_baseline: float,
    current_holdout: float,
) -> tuple[bool, str]:
    """
    检查是否应停机。

    规则:
    - round_num >= max_rounds → 停
    - stale_count >= stale_stop_rounds → 停
    - current_holdout < champion_holdout_baseline + holdout_meltdown_threshold → 停

    Returns:
        (should_stop: bool, reason: str)
    """
    ...


def _determine_level(
    campaign: dict,
    stale_count: int,
) -> str:
    """
    判断当前应使用 Level 1（参数面）还是 Level 2（结构进化）。

    如果 stale_count >= structural_unlock_after_stale → "structural"
    否则 → "parameter"
    """
    ...
```

### 4.2 主循环伪代码

```python
def run_campaign(strategy_name, campaign_path, max_rounds):
    campaign = load_campaign(campaign_path)
    forge_md = load_forge_md()

    # 初始化：评估 champion 作为 baseline
    champion_result = evaluate_champion(campaign, strategy_name)
    best_score = champion_result.visible_score
    champion_holdout_baseline = champion_result.holdout.excess_cagr

    stale_count = 0

    for round_num in range(1, max_rounds + 1):
        level = _determine_level(campaign, stale_count)

        # 1. 复制 champion → candidate
        _copy_champion_to_candidate(strategy_name)

        # 2. 调用 agent
        public_log_tail = read_last_n_lines(public_log, 20)
        champion_code = read_file(champion_path)
        _invoke_agent(forge_md, champion_code, public_log_tail, best_score, level)

        # 3. Mutation guard
        passed, reason = _mutation_guard(strategy_name, campaign, level)
        if not passed:
            round_result = RoundResult(status="FAIL_GUARD", ...)
            _write_public_log(round_result, ...)
            _write_private_log(round_result, ...)
            _discard_candidate(strategy_name)
            stale_count += 1
            continue

        # 4. 评估 candidate
        candidate_result = evaluate(campaign_path, candidate_path)

        # 5. 比较
        accepted = (
            candidate_result.status == "PASS"
            and candidate_result.visible_score > best_score
        )

        # 6. Promote 或 discard
        if accepted:
            _promote_candidate(strategy_name)
            best_score = candidate_result.visible_score
            stale_count = 0
        else:
            _discard_candidate(strategy_name)
            stale_count += 1

        # 7. 日志
        round_result = build_round_result(round_num, candidate_result, accepted)
        _write_public_log(round_result, ...)
        _write_private_log(round_result, ...)

        # 8. 停机检查
        should_stop, stop_reason = _check_stop_rules(
            campaign, round_num, stale_count,
            champion_holdout_baseline,
            candidate_result.holdout.excess_cagr if candidate_result.holdout else None,
        )
        if should_stop:
            print(f"FORGE STOPPED: {stop_reason}")
            break

    print_summary(best_score, round_num, public_log)
```

---

## 5. 实现顺序 Checklist

### Phase 1: 骨架 + 数据管道（可验证：champion 能跑通评估）

- [ ] 创建 `forge/` 目录结构
- [ ] 编写 `campaign.lock.json`（Helen BTC 配置）
- [ ] 编写 `manifests/helen_surface.yaml`
- [ ] 从 `src/timing/dual_engine.py` 提取 `strategies/helen_champion.py`
  - 重构为 `evaluate_bar()` / `get_default_config()` / `get_initial_state()` 接口
- [ ] 编写 `evaluator.py` 核心
  - 动态 import 策略
  - 预计算指标（全量一次性，非逐 bar）
  - 多窗口回测 + holdout 回测
  - 门槛检查 + visible_score 计算
  - stdout 输出格式
- [ ] 验证：`python evaluator.py --champion-only` 输出 Helen v2.0 baseline

### Phase 2: runner 控制面（可验证：手动 1 轮循环跑通）

- [ ] 编写 `runner.py`
  - champion → candidate 复制
  - claude -p 调用
  - mutation guard（import 检查 + 接口检查）
  - promote / discard
  - public + private 日志
- [ ] 编写 `forge.md`（agent 指令）
- [ ] 验证：`python runner.py --rounds 1` 手动跑通 1 轮

### Phase 3: 停机规则 + Level 2 解锁（可验证：3-5 轮自动循环）

- [ ] 实现停机规则（max_rounds / stale / holdout meltdown）
- [ ] 实现 Level 1 → Level 2 升级逻辑
- [ ] 实现参数面 mutation guard（Level 1 只允许改白名单参数）
- [ ] 验证：`python runner.py --rounds 5` 自动跑 5 轮

### Phase 4: 端到端验证（可验证：跑 20-50 轮，检查 holdout）

- [ ] 跑 20 轮，检查 experiments_public.tsv 的 visible_score 趋势
- [ ] 检查 experiments_private.jsonl 的 holdout 是否恶化
- [ ] 对比 champion 和原始 Helen v2.0 的 holdout 表现
- [ ] 编写 `README.md`

---

## 6. 测试策略

| 层级 | 测试什么 | 方法 |
|------|---------|------|
| evaluator | 窗口切片正确性 | 对比 `run_dual_engine_backtest --start-date` 的结果 |
| evaluator | 门槛判定 | 构造一个超过 MDD 门槛的策略，断言 FAIL_GATE |
| evaluator | visible_score 计算 | 手算 min(3 窗口 excess_cagr) 对比 |
| runner | mutation guard | 构造一个改了 evaluator.py 的 diff，断言 FAIL_GUARD |
| runner | promote/discard | 跑 2 轮，1 接受 1 拒绝，检查文件状态 |
| runner | 停机 | 设 stale_stop_rounds=3，跑到自动停 |
| E2E | holdout 不泄漏 | 检查 public log 无 holdout 值，private log 有 |

---

## 变更记录

| 版本 | 日期 | 内容 |
|------|------|------|
| v0.1 | 2026-03-26 | 接口级实现计划，覆盖 campaign.lock / evaluator / runner / strategy contract / 实现顺序 |
