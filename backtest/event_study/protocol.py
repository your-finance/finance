from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Literal, Optional, Protocol, Sequence

import pandas as pd


EventType = Literal["symbol_date"]
Frequency = Literal["daily"]
EntrySemantics = Literal["t_plus_1_open"]
ExitSemantics = Literal["t_plus_h_close"]
FdrFamily = Literal["per_window_return_type_all_horizon_bucket_pairs"]
DeoverlapMode = Literal["hard_window_exclusion"]
ClusterMode = Literal["by_event_date"]


def _validate_iso_date(value: Optional[str], field_name: str) -> None:
    if value is None:
        return
    try:
        date.fromisoformat(value)
    except ValueError as exc:  # pragma: no cover - defensive branch
        raise ValueError(f"{field_name} must be YYYY-MM-DD, got {value!r}") from exc


@dataclass(frozen=True)
class UniverseConfig:
    universe_name: str = "extended_true"
    market_cap_min_usd: float = 10_000_000_000.0
    audit_eligible_counts_by_year: bool = True

    def __post_init__(self) -> None:
        if self.market_cap_min_usd <= 0:
            raise ValueError("market_cap_min_usd must be positive")


@dataclass(frozen=True)
class ReturnConfig:
    entry: EntrySemantics = "t_plus_1_open"
    exit: ExitSemantics = "t_plus_h_close"
    horizons: tuple[int, ...] = (5, 10, 20, 60)
    benchmark_symbol: str = "SPY"
    benchmark_same_semantics: bool = True
    drop_missing_exit: bool = True
    emit_raw_and_excess: bool = True

    def __post_init__(self) -> None:
        if not self.horizons:
            raise ValueError("horizons must not be empty")
        if any(h <= 0 for h in self.horizons):
            raise ValueError("horizons must be positive integers")
        if tuple(sorted(self.horizons)) != self.horizons:
            raise ValueError("horizons must be sorted ascending")
        if len(set(self.horizons)) != len(self.horizons):
            raise ValueError("horizons must not contain duplicates")
        if not self.benchmark_symbol:
            raise ValueError("benchmark_symbol must not be empty")


@dataclass(frozen=True)
class OverlapPolicy:
    same_symbol_mode: DeoverlapMode = "hard_window_exclusion"
    cluster_mode: ClusterMode = "by_event_date"
    fdr_family: FdrFamily = "per_window_return_type_all_horizon_bucket_pairs"


@dataclass(frozen=True)
class ReportSplitConfig:
    oos_start_date: Optional[str] = None
    emit_full_window: bool = True
    emit_is_window: bool = True
    emit_oos_window: bool = True

    def __post_init__(self) -> None:
        _validate_iso_date(self.oos_start_date, "oos_start_date")


@dataclass(frozen=True)
class EventStudyConfig:
    study_name: str
    event_type: EventType = "symbol_date"
    frequency: Frequency = "daily"
    study_start_date: Optional[str] = None
    study_end_date: Optional[str] = None
    universe: UniverseConfig = field(default_factory=UniverseConfig)
    returns: ReturnConfig = field(default_factory=ReturnConfig)
    overlap: OverlapPolicy = field(default_factory=OverlapPolicy)
    report_split: ReportSplitConfig = field(default_factory=ReportSplitConfig)

    def __post_init__(self) -> None:
        if not self.study_name.strip():
            raise ValueError("study_name must not be empty")
        _validate_iso_date(self.study_start_date, "study_start_date")
        _validate_iso_date(self.study_end_date, "study_end_date")
        if self.study_start_date and self.study_end_date:
            if self.study_start_date > self.study_end_date:
                raise ValueError("study_start_date must be <= study_end_date")
        if self.report_split.oos_start_date:
            if self.study_start_date and self.report_split.oos_start_date < self.study_start_date:
                raise ValueError("oos_start_date must be >= study_start_date")
            if self.study_end_date and self.report_split.oos_start_date > self.study_end_date:
                raise ValueError("oos_start_date must be <= study_end_date")


class SymbolDateStudyAdapter(Protocol):
    """Protocol for stock-date event studies.

    Implementations return event buckets as:
    `{bucket_label: {symbol: [event_date, ...]}}`
    """

    name: str

    def build_feature_frames(
        self,
        price_dict: Dict[str, pd.DataFrame],
    ) -> Dict[str, pd.DataFrame]:
        ...

    def detect_events(
        self,
        feature_frames: Dict[str, pd.DataFrame],
    ) -> Dict[str, Dict[str, List[str]]]:
        ...


@dataclass(frozen=True)
class StudyOutcome:
    study_name: str
    status: Literal["pending", "not_implemented", "completed"] = "pending"
    summary_rows: Sequence[dict] = field(default_factory=tuple)
    artifact_paths: Dict[str, str] = field(default_factory=dict)
    notes: Sequence[str] = field(default_factory=tuple)
