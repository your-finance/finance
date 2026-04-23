"""Standardized daily event-study framework."""

from backtest.event_study.protocol import (
    EventStudyConfig,
    OverlapPolicy,
    ReportSplitConfig,
    ReturnConfig,
    StudyOutcome,
    UniverseConfig,
)
from backtest.event_study.runner import EventStudyRunner

__all__ = [
    "EventStudyConfig",
    "EventStudyRunner",
    "OverlapPolicy",
    "ReportSplitConfig",
    "ReturnConfig",
    "StudyOutcome",
    "UniverseConfig",
]
