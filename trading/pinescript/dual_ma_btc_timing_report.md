# BTC 4H 双均线择时策略 — Forge 优化报告

> 2026-03-31 | Forge 策略锻造引擎 | BTCUSDT 4H

---

## 背景

使用 Forge 策略锻造引擎，对 BTC 4H 双均线择时策略进行自动优化。Forge 采用 visible/holdout 窗口隔离设计，优化 agent 只能看到 visible 窗口的评分，holdout 窗口完全隐藏，防止过拟合。

### 数据
- **标的**: BTCUSDT 币安永续合约
- **粒度**: 4H K线
- **总量**: 18,842 根 bar (2017-08 ~ 2026-03)

### 评估窗口

| 窗口 | 区间 | 用途 |
|------|------|------|
| A | 2019-01-01 ~ 2021-12-31 | Visible（牛市为主） |
| B | 2020-01-01 ~ 2022-12-31 | Visible（牛熊完整周期） |
| C | 2021-01-01 ~ 2023-06-30 | Visible（熊市为主） |
| Holdout | 2023-07-01 ~ 2026-03-26 | 隐藏（样本外验证） |

### 评分函数
`min_calmar` = 三个 visible 窗口中最差的 `excess_cagr / |max_drawdown|`

---

## 策略一：SMA 41/268

### 逻辑
- SMA(41) 上穿 SMA(268) → 全仓做多
- SMA(41) 下穿 SMA(268) → 清仓
- 纯二元开关，无连续仓位

### Forge 优化过程
- **种子**: fast=20, slow=50, score=-1.55
- **Campaign**: dual_ma_btc_001, 共 48 有效轮次（两次 session）
- **Champion 演进**: 20/50 → 50/150 → 60/240 → 42/240 → 42/270 → 40/270 → **41/268**
- 参数空间在 41/268 高度收敛（邻居 40/268=0.37, 42/268=0.38, 41/267=0.54, 41/269=0.43）
- Structural 尝试（EMA + 连续仓位）均不如纯 SMA

### 全样本表现（2019-01 ~ 2026-03）

| 指标 | Strategy | Buy & Hold |
|------|----------|-----------|
| 总收益 | 452x | 191x |
| CAGR | 69.4% | 50.4% |
| Max Drawdown | -51.8% | -77.0% |
| Sharpe | 1.32 | 0.82 |
| 换仓次数 | 75 | — |
| 平均仓位 | 53.4% | 100% |

### TradingView Pine v6

```pinescript
//@version=6
strategy("Dual SMA 41/268 | BTC 4H", overlay=true, default_qty_type=strategy.percent_of_equity, default_qty_value=100, initial_capital=10000, commission_type=strategy.commission.percent, commission_value=0.05, slippage=1)

// ─── Inputs ───
fastLen = input.int(41, "Fast SMA Period", minval=1)
slowLen = input.int(268, "Slow SMA Period", minval=1)

// ─── Indicators ───
fastMA = ta.sma(close, fastLen)
slowMA = ta.sma(close, slowLen)

// ─── Signals ───
goldenCross = ta.crossover(fastMA, slowMA)
deathCross  = ta.crossunder(fastMA, slowMA)

// ─── Strategy ───
if goldenCross
    strategy.entry("Long", strategy.long)

if deathCross
    strategy.close("Long")

// ─── Visuals ───
plot(fastMA, "Fast SMA", color=color.new(#2196F3, 0), linewidth=2)
plot(slowMA, "Slow SMA", color=color.new(#FF9800, 0), linewidth=2)

bgcolor(strategy.position_size > 0 ? color.new(#2196F3, 90) : na)

plotshape(goldenCross, "Golden Cross", shape.triangleup, location.belowbar, color.new(#4CAF50, 0), size=size.small)
plotshape(deathCross, "Death Cross", shape.triangledown, location.abovebar, color.new(#F44336, 0), size=size.small)

// ─── Alerts ───
alertcondition(goldenCross, "SMA Golden Cross", "SMA 41/268 Golden Cross - GO LONG")
alertcondition(deathCross, "SMA Death Cross", "SMA 41/268 Death Cross - EXIT")
```

---

## 策略二：EMA 33/140 + Regime Filter

### 逻辑
- EMA(33) 上穿 EMA(140) **且** slow EMA 60 bar 斜率 > 0 → 全仓做多
- EMA(33) 下穿 EMA(140) → 清仓（无条件退出）
- Regime filter 的作用：过滤熊市中 slow EMA 仍在下行时的假金叉（反弹陷阱）

### Forge 优化过程
- **种子**: fast=30, slow=150, score=0.565
- **Campaign**: dual_ema_btc_001, 20 轮
- **Champion 演进**: 30/150 → 33/140 → 33/140 + regime filter (structural)
- R15 structural 突破：agent 自主发明了 slow EMA slope regime filter，score 从 0.592 → 0.633
- 参数微调（R16-R20）均未超越 structural champion

### 全样本表现（2019-01 ~ 2026-03）

| 指标 | Strategy | Buy & Hold |
|------|----------|-----------|
| 总收益 | 350x | 191x |
| CAGR | 64.3% | 50.4% |
| Max Drawdown | -43.3% | -77.0% |
| Sharpe | 1.56 | 0.82 |
| 换仓次数 | 91 | — |
| 平均仓位 | 49.5% | 100% |

### TradingView Pine v6

```pinescript
//@version=6
strategy("Dual EMA 33/140 + Regime | BTC 4H", overlay=true, default_qty_type=strategy.percent_of_equity, default_qty_value=100, initial_capital=10000, commission_type=strategy.commission.percent, commission_value=0.05, slippage=1)

// ─── Inputs ───
fastLen   = input.int(33, "Fast EMA Period", minval=1)
slowLen   = input.int(140, "Slow EMA Period", minval=1)
slopeLen  = input.int(60, "Regime Slope Lookback", minval=1, tooltip="Slow EMA must be rising over this many bars to allow entry")

// ─── Indicators ───
fastEMA = ta.ema(close, fastLen)
slowEMA = ta.ema(close, slowLen)

// Regime: slow EMA slope over N bars
slowSlope = slowEMA - slowEMA[slopeLen]
regimeOK  = slowSlope > 0

// ─── Signals ───
bullCross = ta.crossover(fastEMA, slowEMA)
bearCross = ta.crossunder(fastEMA, slowEMA)

// Entry: golden cross + regime bullish
// Also enter if already above and regime just turned bullish (re-entry after regime block)
aboveSlow    = fastEMA > slowEMA
regimeFlip   = regimeOK and not regimeOK[1]
entrySignal  = bullCross and regimeOK
reentrySignal = aboveSlow and regimeFlip and strategy.position_size == 0

// Exit: death cross (unconditional)
exitSignal = bearCross

// ─── Strategy ───
if entrySignal or reentrySignal
    strategy.entry("Long", strategy.long)

if exitSignal
    strategy.close("Long")

// ─── Visuals ───
plot(fastEMA, "Fast EMA", color=color.new(#E91E63, 0), linewidth=2)
plot(slowEMA, "Slow EMA", color=color.new(#FF9800, 0), linewidth=2)

// Regime background
bgcolor(strategy.position_size > 0 ? color.new(#E91E63, 90) : na)
bgcolor(not regimeOK and fastEMA > slowEMA ? color.new(#FF9800, 93) : na) // golden cross but regime blocked

plotshape(entrySignal, "Entry", shape.triangleup, location.belowbar, color.new(#4CAF50, 0), size=size.small)
plotshape(reentrySignal, "Re-entry", shape.triangleup, location.belowbar, color.new(#8BC34A, 0), size=size.tiny)
plotshape(exitSignal, "Exit", shape.triangledown, location.abovebar, color.new(#F44336, 0), size=size.small)

// Regime indicator
plotshape(regimeOK and not regimeOK[1], "Regime ON", shape.diamond, location.bottom, color.new(#4CAF50, 30), size=size.tiny)
plotshape(not regimeOK and regimeOK[1], "Regime OFF", shape.diamond, location.bottom, color.new(#F44336, 30), size=size.tiny)

// ─── Alerts ───
alertcondition(entrySignal, "EMA Entry", "EMA 33/140 Golden Cross + Regime Bullish - GO LONG")
alertcondition(reentrySignal, "EMA Re-entry", "EMA 33/140 Regime Flip Bullish - RE-ENTER LONG")
alertcondition(exitSignal, "EMA Exit", "EMA 33/140 Death Cross - EXIT")
alertcondition(not regimeOK and fastEMA > slowEMA, "Regime Block", "Golden cross but regime bearish - ENTRY BLOCKED")
```

---

## 样本外对比（Holdout: 2023-07 ~ 2026-03）

| 指标 | SMA 41/268 | EMA 33/140+Regime | 胜负 |
|------|-----------|-------------------|------|
| Total Return | +164.1% | +153.2% | SMA |
| CAGR | +42.6% | +40.5% | SMA |
| Excess CAGR | **+6.4%** | +4.2% | SMA |
| Max Drawdown | -34.4% | **-29.4%** | EMA |
| Sharpe | 1.24 | 1.24 | 平局 |
| Exposure | 55.3% | 50.6% | — |
| Rebalances | 28 | 38 | SMA |

### 结论

**Sharpe 完全一致（1.24）**，两种策略是同一个 trade-off 的不同表达：

- **SMA 41/268**: 更长周期 → 更少换仓 → 牛市多赚 2% → 但回撤多扛 5%
- **EMA 33/140 + Regime**: 更短周期 + regime filter → 回撤控制更好 → 但牛市少赚一点

样本外 excess CAGR 衰减明显（SMA: 42% → 6.4%, EMA: 25% → 4.2%），符合预期。两者的核心价值都在回撤控制（vs B&H -50%），而非绝对收益。

---

## 风险提示

1. **Sharp peak 风险**: SMA 41/268 是一个尖锐的参数峰值（邻居得分骤降），暗示参数敏感度高，实盘可能不如回测稳定
2. **Regime filter 自由度**: EMA 策略引入了额外的 slope lookback 参数（60 bar），增加了过拟合风险
3. **交易成本假设**: 回测使用 10bps 单边成本，实盘滑点可能更高
4. **数据粒度**: 4H bar 的信号延迟最多 4 小时，极端行情下可能错过最佳出场点
5. **单标的**: 仅在 BTCUSDT 上验证，未在其他加密资产上测试泛化性

---

## 跨资产验证：QQQ（美股纳指 ETF）

在 QQQ 日线上测试同样的策略逻辑，验证是否具有跨资产泛化能力。

### QQQ 回测结果（2019-01 ~ 2026-03，日线）

| 策略 | CAGR | Excess | MDD | Sharpe | 换仓 |
|------|------|--------|-----|--------|------|
| **B&H QQQ** | **20.2%** | — | -35.1% | **0.89** | — |
| SMA 41/268 | 15.9% | -4.2% | -28.6% | 0.82 | 5 |
| EMA 33/140+Regime | 15.0% | -5.2% | -28.6% | 0.85 | 7 |
| SMA 50/200 (经典) | 16.8% | -3.4% | -28.6% | 0.86 | 7 |

### 结论

**双均线择时在 QQQ 上全面跑输 B&H**。原因：

1. **波动率不足**: BTC 年化波动率 ~80%，QQQ ~20%。趋势跟踪策略需要大幅趋势来覆盖 whipsaw 成本
2. **长牛结构**: 2019-2025 QQQ 是超级牛市，空仓期间错过的涨幅 > 躲开的跌幅
3. **回撤改善有限**: QQQ B&H MDD 仅 -35%（vs BTC -77%），均线能躲掉的跌幅本身不大

**这两个策略是 crypto 专用的，不适合美股大盘。**

---

## 文件清单

| 文件 | 说明 |
|------|------|
| `dual_sma_41_268.pine` | SMA 策略 TradingView Pine v6 |
| `dual_ema_33_140_regime.pine` | EMA+Regime 策略 TradingView Pine v6 |
| `dual_ma_btc_timing_report.md` | 本文档 |

### 相关资源
- Forge 设计文档: `docs/plans/2026-03-26-forge-strategy-optimizer.md`
- Forge 实现计划: `docs/plans/2026-03-26-forge-implementation-plan.md`
- Campaign 日志: `forge/logs/dual_ma_btc_001/`, `forge/logs/dual_ema_btc_001/`
- 净值曲线: `reports/forge_dual_ma_champion_41_268.png`, `reports/forge_ema_champion_33_140_regime.png`
