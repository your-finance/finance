from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from backtest.event_study.protocol import EventStudyConfig, ReportSplitConfig, UniverseConfig
from backtest.event_study.runner import EventStudyRunner
from backtest.event_study.studies import RVOLStudyAdapter


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run standardized daily event study")
    parser.add_argument("--study", required=True, choices=["rvol_up2"])
    parser.add_argument("--universe", default="extended_true")
    parser.add_argument("--mcap-threshold", type=float, default=10_000_000_000.0)
    parser.add_argument("--start-date", type=str)
    parser.add_argument("--end-date", type=str)
    parser.add_argument("--oos-start", type=str)
    parser.add_argument("--output-dir", type=str)
    return parser


def make_config(args: argparse.Namespace) -> EventStudyConfig:
    return EventStudyConfig(
        study_name=args.study,
        study_start_date=args.start_date,
        study_end_date=args.end_date,
        universe=UniverseConfig(
            universe_name=args.universe,
            market_cap_min_usd=args.mcap_threshold,
            audit_eligible_counts_by_year=True,
        ),
        report_split=ReportSplitConfig(oos_start_date=args.oos_start),
    )


def make_study_adapter(study_name: str):
    if study_name == "rvol_up2":
        return RVOLStudyAdapter()
    raise ValueError(f"Unsupported study: {study_name}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = make_config(args)
    study = make_study_adapter(args.study)
    runner = EventStudyRunner(config=config, study=study)
    outcome = runner.run(output_dir=Path(args.output_dir) if args.output_dir else None)
    print(f"study={outcome.study_name} status={outcome.status}")
    for name, path in sorted(outcome.artifact_paths.items()):
        print(f"{name}: {path}")
    return 0
