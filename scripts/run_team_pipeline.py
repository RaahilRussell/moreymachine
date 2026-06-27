#!/usr/bin/env python
"""Run the team-scoped GM product pipeline."""

from __future__ import annotations

import argparse

from moreymachine.pipeline.team_pipeline import (
    available_pipeline_teams,
    run_team_pipeline,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--team", default="PHI", help="Team abbreviation or ALL")
    parser.add_argument("--skip-refresh", action="store_true")
    parser.add_argument("--stages", default="", help="Optional comma-separated stages")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--no-ollama", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    stages = [item.strip() for item in args.stages.split(",") if item.strip()] or None
    exit_code = 0
    for team in available_pipeline_teams(args.team):
        result = run_team_pipeline(
            team,
            skip_refresh=args.skip_refresh,
            stages=stages,
            force=args.force,
            no_ollama=args.no_ollama,
        )
        print(f"{result.team}: {result.status} ({result.run_id})")
        for stage in result.stages:
            print(f"  {stage.stage_name}: {stage.status} - {stage.message}")
        if result.status != "success":
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
