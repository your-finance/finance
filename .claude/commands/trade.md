---
name: trade
description: 录入交易 — 解析意图、展示确认、原子写入
user-invocable: true
---

## /trade — 交易录入

解析用户交易意图并执行原子写入。

### 流程

1. **解析意图**：从用户输入提取 action (BUY/SELL/ADD/TRIM) + ticker + shares + price
   - 示例: `/trade NVDA BUY 100@135`, `/trade NVDA SELL 50@150`
   - 如果信息不完整，追问缺失字段

2. **查询当前状态**：
   ```python
   from portfolio.holdings.manager import PortfolioManager
   from terminal.company_store import get_store
   store = get_store()
   mgr = PortfolioManager(store=store)
   position = mgr.get_position(symbol)
   cash = store.get_cash_balance()
   oprms = store.get_current_oprms(symbol)
   ```

3. **展示确认摘要**（必须等 Boss 确认才能执行）：
   - 当前持仓 / 无持仓
   - 交易后均价、股数、仓位占比 (基于 total_NAV)
   - OPRMS DNA 上限 vs 交易后仓位
   - 现金变化
   - 格式示例：
   ```
   📝 交易确认
   NVDA BUY 100 @ $135.00
   
   当前: 600 shares @ $176.09 (DNA=S, Timing=A)
   交易后: 700 shares, 均价 $170.22
   仓位: 7.1% → 8.3% (DNA上限 25%)
   现金: $750,000 → $736,500
   
   确认执行？
   ```

4. **Boss 确认后执行**：
   ```python
   result = mgr.execute_trade(symbol, action, shares, price, date)
   ```

5. **交易后自动检查**（不需要 Boss 确认，直接展示）：
   - [ ] 交易后仓位是否超过 DNA 上限？ → 警告
   - [ ] 交易后行业集中度是否超标（>40%）？ → 警告
   - [ ] 该股票有没有 OPRMS 评���？ → 没有则提醒先做分析

6. **Auto-push**：
   交易 `execute_trade()` 返回成功后，执行：
   ```python
   store.checkpoint()
   ```
   ```bash
   ./sync_to_cloud.sh --push
   ```
   push 失败只 warning，不影响已提交的本地交易。

### 期权交易

如果用户说"买/卖期权"，使用 `store.insert_option_position()` 而非 `execute_trade()`：
```python
store.insert_option_position(
    symbol=symbol, expiration=expiry, strike=strike,
    side="CALL"/"PUT", quantity=qty, avg_premium=premium,
    open_date=date, strategy_tag=tag
)
```

### 注意事项

- 所有交易必须等 Boss 确认，禁止自动执行
- 日期默认今天，除非 Boss 指定
- SELL/TRIM 时检查持仓够不够
- 港股 ticker 带 .HK 后缀
