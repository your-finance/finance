from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import pandas as pd

from src.indicators.rvol import calculate_rvol_series


@dataclass(frozen=True)
class RVOLStudyParams:
    rvol_lookback: int = 150
    rvol_threshold: float = 2.0


class RVOLStudyAdapter:
    """Standardized RVOL threshold-cross event adapter.

    First phase deliberately supports only one bucket: `rvol_up2_all`.
    """

    name = "rvol_up2"
    bucket_labels = ("rvol_up2_all",)

    def __init__(self, params: RVOLStudyParams | None = None):
        self._params = params or RVOLStudyParams()

    @property
    def params(self) -> RVOLStudyParams:
        return self._params

    def research_question(self) -> str:
        return "当 RVOL 上穿阈值后，未来数个日频持有期是否存在稳定的原始收益和超额收益？"

    def build_feature_frames(
        self,
        price_dict: Dict[str, pd.DataFrame],
    ) -> Dict[str, pd.DataFrame]:
        frames: Dict[str, pd.DataFrame] = {}
        for symbol, raw in price_dict.items():
            frame = self._build_symbol_feature_frame(raw)
            if not frame.empty:
                frames[symbol] = frame
        return frames

    def detect_events(
        self,
        feature_frames: Dict[str, pd.DataFrame],
    ) -> Dict[str, Dict[str, List[str]]]:
        bucket_events: Dict[str, Dict[str, List[str]]] = {
            "rvol_up2_all": {},
        }
        for symbol, frame in feature_frames.items():
            ordered = frame.sort_values("date").reset_index(drop=True)
            dates = ordered.loc[ordered["rvol_up2"], "date"].astype(str).str[:10].tolist()
            if dates:
                bucket_events["rvol_up2_all"][symbol] = dates
        return bucket_events

    def build_event_level_frame(
        self,
        feature_frames: Dict[str, pd.DataFrame],
        bucket_events: Dict[str, Dict[str, List[str]]],
    ) -> pd.DataFrame:
        rows: List[dict] = []
        event_lookup = bucket_events.get("rvol_up2_all", {})
        for symbol, event_dates in event_lookup.items():
            frame = feature_frames[symbol].copy()
            frame["date"] = frame["date"].astype(str).str[:10]
            for date_str in event_dates:
                matched = frame[frame["date"] == date_str]
                if matched.empty:
                    continue
                row = matched.iloc[-1]
                rows.append(
                    {
                        "bucket": "rvol_up2_all",
                        "symbol": symbol,
                        "date": date_str,
                        "rvol": float(row["rvol"]),
                        "close": float(row["close"]),
                        "volume": float(row["volume"]),
                    }
                )
        return pd.DataFrame(rows)

    def _build_symbol_feature_frame(self, df: pd.DataFrame) -> pd.DataFrame:
        ordered = df.sort_values("date").reset_index(drop=True).copy()
        if ordered.empty:
            return ordered

        ordered["date"] = ordered["date"].astype(str).str[:10]
        volume = ordered["volume"].astype(float)
        rvol = calculate_rvol_series(volume, lookback=self._params.rvol_lookback)
        ordered["rvol"] = rvol
        ordered["rvol_up2"] = (
            (rvol.shift(1) <= self._params.rvol_threshold)
            & (rvol > self._params.rvol_threshold)
        ).fillna(False)
        return ordered
