from __future__ import annotations

from pathlib import Path

from backtest.event_study import cli
from backtest.event_study.protocol import StudyOutcome


def test_cli_builds_config_with_frozen_defaults() -> None:
    parser = cli.build_parser()
    args = parser.parse_args(
        [
            "--study",
            "rvol_up2",
            "--universe",
            "extended_true",
            "--mcap-threshold",
            "10000000000",
            "--start-date",
            "2024-01-01",
            "--end-date",
            "2024-12-31",
            "--oos-start",
            "2024-09-01",
        ]
    )

    config = cli.make_config(args)

    assert config.study_name == "rvol_up2"
    assert config.universe.universe_name == "extended_true"
    assert config.universe.market_cap_min_usd == 10_000_000_000.0
    assert config.report_split.oos_start_date == "2024-09-01"


def test_cli_main_runs_runner(monkeypatch, tmp_path: Path) -> None:
    class _FakeRunner:
        def __init__(self, config, study):
            self._config = config
            self._study = study

        def run(self, output_dir=None):
            target = Path(output_dir)
            target.mkdir(parents=True, exist_ok=True)
            fake_report = target / "report.md"
            fake_report.write_text("# report", encoding="utf-8")
            return StudyOutcome(
                study_name=self._config.study_name,
                status="completed",
                artifact_paths={"report.md": str(fake_report)},
                notes=("ok",),
            )

    monkeypatch.setattr("backtest.event_study.cli.EventStudyRunner", _FakeRunner)

    exit_code = cli.main(
        [
            "--study",
            "rvol_up2",
            "--output-dir",
            str(tmp_path),
        ]
    )

    assert exit_code == 0
    assert (tmp_path / "report.md").exists()
