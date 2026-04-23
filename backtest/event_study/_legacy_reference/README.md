# Legacy Reference Snapshot

This directory freezes the event-study prototypes that currently live only in the main workspace's dirty/untracked area.

Purpose:
- keep migration references inside this worktree
- avoid cross-workspace reads during implementation
- make the standardization effort reproducible for later agents

Rules:
- files here are read-only references
- do not treat them as the new standard entrypoints
- migrate logic into `backtest/event_study/`, do not extend these files

Copied from:
- `/Users/owen/CC workspace/Finance/backtest/research/*.py`
- `/Users/owen/CC workspace/Finance/scripts/run_*signal_stats.py`

Copied on:
- `2026-04-23`
