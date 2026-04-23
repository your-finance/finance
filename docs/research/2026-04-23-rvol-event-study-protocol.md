# RVOL Event Study Protocol

## Scope

- 只覆盖 `股票-日期事件`
- 只覆盖 `RVOL upcross`
- 频率固定为 `日频`
- 第一阶段不包含 `PMARP / BBWP / breadth`

## Frozen Defaults

- 股票池: `extended_true`
- 历史市值门槛: `$10B`
- 事件收益口径: `T+1 open -> T+H close`
- 基准: `SPY`
- Excess 口径: `SPY` 也用同样的 `T+1 open -> T+H close`
- 缺失 `T+H close`: 直接 drop，不做 forward-fill
- Horizons: `5 / 10 / 20 / 60`

## Independence Rules

- 同一只股票在持有窗内重复触发: `hard_window_exclusion`
- 同一天多个股票一起触发: 按日期聚类后做统计检验
- FDR 家族: 每个 `(window, return_type)` 组合内的全部 `(horizon, bucket)` 一起做 BH-FDR

## OOS Rule

- `IS/OOS` 只表示报告层时间切片
- 默认输出 `Full / IS / OOS`
- 若 `OOS` 样本不足，只允许写“样本不足”，不允许装作验证通过

## Fixed Artifacts

- `summary.csv`
- `event_level.csv`
- `universe_audit.csv`
- `report.md`

## Current Entry Point

- CLI: [scripts/run_event_study.py](/Users/owen/CC%20workspace/Finance/.worktrees/event-study-standardization/scripts/run_event_study.py)
- 当前唯一 study: `rvol_up2`

## Next Step

- 第二阶段把 `PMARP / BBWP` 并入同一协议
- `breadth` 先作为市场过滤器加入，不单独定义市场事件
