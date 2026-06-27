#!/usr/bin/env python
"""Build grounded team narrative artifacts."""

from __future__ import annotations

import argparse

from moreymachine.context.team_context import load_team_context
from moreymachine.llm.narrative_packets import build_team_narratives


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--team", default="PHI")
    parser.add_argument("--no-ollama", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    context = load_team_context(args.team)
    result = build_team_narratives(
        team=args.team,
        context=context,
        no_ollama=args.no_ollama,
    )
    print(f"{result.team}: {result.source}")
    print(f"Markdown: {result.markdown_path}")
    print(f"JSON: {result.json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
