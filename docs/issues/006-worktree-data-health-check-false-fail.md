# 006: Fresh worktree 缺少忽略数据，数据脚本末尾 health_check 假失败

**日期**: 2026-03-25
**严重程度**: 中（功能本身成功，但端到端验证可能被误判为失败）
**根因**: git worktree 不会带上被 `.gitignore` 排除的数据文件和 `.env`，但 `update_data.py` 末尾会无条件跑全量 `health_check()`

---

## 发生了什么

在新的 worktree 中验证 `scripts/update_data.py --social-sentiment --symbols NVDA,AAPL`：

- 市场级采集成功
  - `market reddit/trending: 20 rows`
  - `market reddit/trending/sectors: 11 rows`
  - `market x/trending: 20 rows`
  - `market x/trending/sectors: 11 rows`
- 个股级采集也成功
  - `NVDA`: Reddit + X 各 7 天
  - `AAPL`: Reddit + X 各 7 天

但脚本最终仍以 `exit code 1` 结束，因为 worktree 里没有完整的数据底座：

- `data/pool/universe.json` 不存在
- `data/company.db` 不存在
- `profiles.json` 不存在
- `.env` 也不会自动出现在新 worktree

结果是：**目标功能已经写入成功，但最后的全量 health check 把这次验证打成 FAIL。**

## 根因分析

这不是社交采集逻辑的 bug，而是验证环境的坑：

1. 项目规则要求代码开发使用 git worktree
2. Finance 的关键运行时数据和凭证都在 `.gitignore` 范围内
3. 新 worktree 只有版本库文件，没有本地数据库、股票池快照和 `.env`
4. `update_data.py` 在完成目标步骤后，仍然执行面向完整生产数据环境的 `health_check()`

因此在 fresh worktree 中，**目标功能成功 != 脚本总退出码成功**。

## 教训

### 核心规则

**在 fresh worktree 里验证数据管线时，先确认忽略文件是否已准备好；否则不要把最终 health check 的 FAIL 当成这次改动的回归。**

### 正确做法

验证前至少确认这几类依赖：

```bash
test -f .env
test -f data/company.db
test -f data/market.db
test -f data/pool/universe.json
```

如果缺失，有两种安全验证路径：

1. **复制只读快照到 worktree**
   - 从主工作区复制 `data/market.db` / `data/company.db` / `data/pool/universe.json`
   - 从主工作区 source `.env`

2. **做目标化验证，不依赖全量 health check**
   - 直接查新增表 / 新增字段
   - 运行相关 pytest
   - 接受脚本最后因环境不完整而退出非零

### 这次的判定标准

这次应看：

- 新表是否自动创建
- row count 是否正确
- 真实 query 是否能查到数据

而不是只看 `update_data.py` 的最终返回码。

## 防范措施

- 每次在新 worktree 做数据脚本验证前，先跑一次“忽略文件预检”
- 如果只验证某个局部数据流程，优先配合 sqlite query + targeted pytest
- 看到 `health_check FAIL` 时，先区分是**环境缺件**还是**业务回归**
