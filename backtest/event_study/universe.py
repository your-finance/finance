from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence

import pandas as pd

from backtest.event_study.protocol import UniverseConfig
from backtest.pipeline.paths import resolve_shared_data_root


@dataclass(frozen=True)
class EventUniverseAudit:
    by_date: pd.DataFrame
    by_year: pd.DataFrame
    summary: Dict[str, object]

    def to_frame(self) -> pd.DataFrame:
        date_rows = self.by_date.copy()
        date_rows.insert(0, "audit_type", "by_date")

        year_rows = self.by_year.copy()
        year_rows.insert(0, "audit_type", "by_year")

        summary_rows = pd.DataFrame(
            [
                {
                    "audit_type": "summary",
                    "metric": key,
                    "value": value,
                }
                for key, value in sorted(self.summary.items())
            ]
        )
        return pd.concat([date_rows, year_rows, summary_rows], ignore_index=True, sort=False)


class EventUniverseGate:
    """Build a daily eligibility matrix for event studies.

    Performance path is intentionally fixed:
    1. bulk-load `historical_market_cap` rows for candidate symbols once
    2. reindex each symbol with as-of semantics onto computation dates
    3. threshold the resulting market-cap matrix

    This avoids the old `slice_to_date()` per-date loop that became too slow
    on daily extended-universe studies.
    """

    def __init__(
        self,
        config: UniverseConfig,
        market_db_path: Optional[str | Path] = None,
        candidate_symbols: Optional[Sequence[str]] = None,
    ):
        data_root = resolve_shared_data_root()
        self._config = config
        self._market_db_path = (
            Path(market_db_path)
            if market_db_path is not None
            else data_root / "data" / "market.db"
        )
        self._candidate_symbols = tuple(candidate_symbols) if candidate_symbols is not None else None
        self._last_market_cap_matrix: Optional[pd.DataFrame] = None
        self._last_hmc_range: Dict[str, Optional[str]] = {"min_date": None, "max_date": None}

    def build_eligibility_matrix(
        self,
        computation_dates: Sequence[str],
        candidate_symbols: Optional[Sequence[str]] = None,
    ) -> pd.DataFrame:
        dates = self._normalize_dates(computation_dates)
        symbols = self._resolve_candidate_symbols(candidate_symbols)
        market_cap_matrix = self.build_market_cap_matrix(dates, symbols)
        eligible = market_cap_matrix.ge(self._config.market_cap_min_usd)
        eligible = eligible.fillna(False).astype(bool)
        eligible.index.name = "date"
        return eligible

    def build_market_cap_matrix(
        self,
        computation_dates: Sequence[str],
        candidate_symbols: Optional[Sequence[str]] = None,
    ) -> pd.DataFrame:
        dates = self._normalize_dates(computation_dates)
        symbols = self._resolve_candidate_symbols(candidate_symbols)
        if not dates:
            return pd.DataFrame(index=pd.Index([], name="date"), columns=list(symbols), dtype=float)

        hmc = self._load_historical_market_caps(symbols=symbols, max_date=dates[-1])
        self._last_hmc_range = {
            "min_date": None if hmc.empty else str(hmc["date"].min())[:10],
            "max_date": None if hmc.empty else str(hmc["date"].max())[:10],
        }

        date_index = pd.to_datetime(dates)
        matrix_data: Dict[str, List[float]] = {}
        if hmc.empty:
            for symbol in symbols:
                matrix_data[symbol] = [float("nan")] * len(dates)
            result = pd.DataFrame(matrix_data, index=dates)
            result.index.name = "date"
            self._last_market_cap_matrix = result
            return result

        for symbol in symbols:
            symbol_rows = hmc[hmc["symbol"] == symbol]
            if symbol_rows.empty:
                matrix_data[symbol] = [float("nan")] * len(dates)
                continue

            series = (
                symbol_rows.assign(date_dt=pd.to_datetime(symbol_rows["date"]))
                .sort_values("date_dt")
                .drop_duplicates(subset=["date_dt"], keep="last")
                .set_index("date_dt")["market_cap"]
            )
            reindexed = series.reindex(date_index, method="ffill")
            matrix_data[symbol] = reindexed.tolist()

        result = pd.DataFrame(matrix_data, index=dates)
        result.index.name = "date"
        self._last_market_cap_matrix = result
        return result

    def build_universe_audit(
        self,
        eligibility_matrix: pd.DataFrame,
        market_cap_matrix: Optional[pd.DataFrame] = None,
        loaded_symbol_count: Optional[int] = None,
        json_universe_count: Optional[int] = None,
    ) -> EventUniverseAudit:
        if market_cap_matrix is None:
            market_cap_matrix = self._last_market_cap_matrix

        by_date = pd.DataFrame(index=eligibility_matrix.index)
        by_date.index.name = "date"
        by_date["year"] = by_date.index.to_series().astype(str).str[:4]
        by_date["candidate_count"] = len(eligibility_matrix.columns)
        by_date["eligible_count"] = eligibility_matrix.sum(axis=1).astype(int)
        by_date = by_date.reset_index()

        by_year = (
            by_date.groupby("year", as_index=False)
            .agg(
                n_dates=("date", "count"),
                first_date=("date", "min"),
                last_date=("date", "max"),
                candidate_count=("candidate_count", "max"),
                eligible_count_min=("eligible_count", "min"),
                eligible_count_median=("eligible_count", "median"),
                eligible_count_max=("eligible_count", "max"),
                eligible_count_mean=("eligible_count", "mean"),
            )
        )
        by_year["eligible_count_mean"] = by_year["eligible_count_mean"].round(2)

        summary = {
            "candidate_count": len(eligibility_matrix.columns),
            "json_universe_count": json_universe_count if json_universe_count is not None else len(eligibility_matrix.columns),
            "loaded_symbol_count": loaded_symbol_count if loaded_symbol_count is not None else len(eligibility_matrix.columns),
            "computation_date_count": len(eligibility_matrix.index),
            "eligible_count_min": int(by_date["eligible_count"].min()) if not by_date.empty else 0,
            "eligible_count_median": float(by_date["eligible_count"].median()) if not by_date.empty else 0.0,
            "eligible_count_max": int(by_date["eligible_count"].max()) if not by_date.empty else 0,
            "historical_market_cap_min_date": self._last_hmc_range.get("min_date"),
            "historical_market_cap_max_date": self._last_hmc_range.get("max_date"),
        }
        if market_cap_matrix is not None and not market_cap_matrix.empty:
            non_null = market_cap_matrix.notna().sum(axis=1)
            summary["covered_symbol_count_min"] = int(non_null.min())
            summary["covered_symbol_count_max"] = int(non_null.max())

        return EventUniverseAudit(
            by_date=by_date,
            by_year=by_year,
            summary=summary,
        )

    def _resolve_candidate_symbols(
        self,
        candidate_symbols: Optional[Sequence[str]] = None,
    ) -> List[str]:
        if candidate_symbols is not None:
            return sorted(set(candidate_symbols))
        if self._candidate_symbols is not None:
            return sorted(set(self._candidate_symbols))
        if self._config.universe_name == "extended_true":
            from src.data.delisted_universe_manager import get_extended_true_symbols

            return get_extended_true_symbols()
        raise ValueError(f"Unsupported universe_name: {self._config.universe_name}")

    @staticmethod
    def _normalize_dates(computation_dates: Sequence[str]) -> List[str]:
        normalized = sorted({str(value)[:10] for value in computation_dates})
        return normalized

    def _load_historical_market_caps(
        self,
        symbols: Sequence[str],
        max_date: str,
    ) -> pd.DataFrame:
        if not symbols:
            return pd.DataFrame(columns=["symbol", "date", "market_cap"])

        query = """
            SELECT symbol, date, market_cap
            FROM historical_market_cap
            WHERE date <= ?
              AND symbol IN ({placeholders})
            ORDER BY symbol, date
        """
        frames: List[pd.DataFrame] = []
        with sqlite3.connect(self._market_db_path) as conn:
            for chunk in self._chunk_symbols(symbols):
                sql = query.format(placeholders=",".join("?" for _ in chunk))
                params = [max_date, *chunk]
                frames.append(pd.read_sql_query(sql, conn, params=params))

        if not frames:
            return pd.DataFrame(columns=["symbol", "date", "market_cap"])
        return pd.concat(frames, ignore_index=True)

    @staticmethod
    def _chunk_symbols(symbols: Sequence[str], size: int = 400) -> List[List[str]]:
        return [list(symbols[idx : idx + size]) for idx in range(0, len(symbols), size)]
