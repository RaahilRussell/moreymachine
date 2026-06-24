"""Build player role archetype clusters."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from moreymachine.features.player_archetypes import (  # noqa: E402
    DEFAULT_K,
    DEFAULT_MIN_MINUTES,
    DEFAULT_PCA_COMPONENTS,
    PLAYER_ARCHETYPE_SUMMARY_PATH,
    PLAYER_ARCHETYPES_PATH,
    PLAYER_SEASONS_BASIC_PATH,
    build_player_archetypes,
)


def main() -> int:
    """CLI entry point for player archetype clustering."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=PLAYER_SEASONS_BASIC_PATH)
    parser.add_argument("--output", type=Path, default=PLAYER_ARCHETYPES_PATH)
    parser.add_argument(
        "--summary-output", type=Path, default=PLAYER_ARCHETYPE_SUMMARY_PATH
    )
    parser.add_argument("--min-minutes", type=float, default=DEFAULT_MIN_MINUTES)
    parser.add_argument("--k", type=int, default=DEFAULT_K)
    parser.add_argument("--pca-components", type=int, default=DEFAULT_PCA_COMPONENTS)
    parser.add_argument("--random-state", type=int, default=42)
    args = parser.parse_args()

    result = build_player_archetypes(
        input_path=args.input,
        output_path=args.output,
        summary_path=args.summary_output,
        min_minutes=args.min_minutes,
        k=args.k,
        pca_components=args.pca_components,
        random_state=args.random_state,
    )

    print(f"Built rows: {result.rows}")
    print(f"Clusters: {result.clusters}")
    print(f"Features: {', '.join(result.feature_columns)}")
    print(f"Assignments: {result.output_path}")
    print(f"Summary: {result.summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
