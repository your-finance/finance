#!/usr/bin/env python3
"""Import initial portfolio holdings from a Python dict.

Usage:
    python scripts/import_holdings.py

Edit INITIAL_HOLDINGS and INITIAL_CASH below before running.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from terminal.company_store import get_store

# ============================================================
# Boss: 编辑此处后运行
# ============================================================
INITIAL_CASH = 0.0  # 现金余额 (USD)

INITIAL_HOLDINGS = [
    # {"symbol": "NVDA", "shares": 100, "avg_cost": 135.00, "date": "2026-01-15"},
    # {"symbol": "AAPL", "shares": 200, "avg_cost": 198.50, "date": "2025-11-20"},
]
# ============================================================


def main():
    store = get_store()

    # Validate: no existing open holdings
    existing = store.get_all_open_holdings()
    if existing:
        print(f"⚠️  已有 {len(existing)} 个 OPEN 持仓。请先清理后再导入。")
        for h in existing:
            print(f"   {h['symbol']}: {h['shares']} shares @ {h['avg_cost']}")
        sys.exit(1)

    # Set cash
    if INITIAL_CASH > 0:
        store.set_cash(INITIAL_CASH, notes="Initial import")
        print(f"💰 现金: ${INITIAL_CASH:,.2f}")

    # Import holdings
    for h in INITIAL_HOLDINGS:
        symbol = h["symbol"].upper()
        # Ensure company exists
        company = store.get_company(symbol)
        if not company:
            store.upsert_company(symbol)
            print(f"⚠️  {symbol} 不在 companies 表中，已创建空记录（需后续补充）")

        pid = store.insert_holding(symbol, shares=h["shares"],
                                    avg_cost=h["avg_cost"], open_date=h["date"])
        store.insert_transaction(pid, symbol, "BUY", shares=h["shares"],
                                  price=h["avg_cost"], date=h["date"],
                                  notes="Initial import")
        print(f"✅ {symbol}: {h['shares']} shares @ ${h['avg_cost']:.2f} (pid={pid})")

    print(f"\n导入完成: {len(INITIAL_HOLDINGS)} 持仓, 现金 ${INITIAL_CASH:,.2f}")
    print("运行 portfolio_status() 验证。")


if __name__ == "__main__":
    main()
