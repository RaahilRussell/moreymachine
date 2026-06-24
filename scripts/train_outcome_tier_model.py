"""Train the playoff outcome tier model from team fingerprint features."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from moreymachine.features.team_fingerprints import TEAM_FINGERPRINTS_PATH  # noqa: E402
from moreymachine.models.outcome_tier_model import (  # noqa: E402
    OUTCOME_TIER_METRICS_PATH,
    OUTCOME_TIER_MODEL_PATH,
    OUTCOME_TIER_PREDICTIONS_PATH,
    train_outcome_tier_model,
)


def main() -> int:
    """CLI entry point for playoff outcome tier model training."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=TEAM_FINGERPRINTS_PATH)
    parser.add_argument("--model-output", type=Path, default=OUTCOME_TIER_MODEL_PATH)
    parser.add_argument(
        "--metrics-output", type=Path, default=OUTCOME_TIER_METRICS_PATH
    )
    parser.add_argument(
        "--predictions-output",
        type=Path,
        default=OUTCOME_TIER_PREDICTIONS_PATH,
    )
    parser.add_argument("--validation-seasons", type=int, default=2)
    parser.add_argument(
        "--cutoff-season",
        help="Last season to include in training; later seasons are validation.",
    )
    parser.add_argument("--random-state", type=int, default=42)
    args = parser.parse_args()

    result = train_outcome_tier_model(
        input_path=args.input,
        model_path=args.model_output,
        metrics_path=args.metrics_output,
        predictions_path=args.predictions_output,
        validation_seasons=args.validation_seasons,
        cutoff_season=args.cutoff_season,
        random_state=args.random_state,
    )

    print(f"Selected model: {result.selected_model_name}")
    print(f"Train seasons: {', '.join(result.train_seasons)}")
    print(f"Validation seasons: {', '.join(result.test_seasons)}")
    print(f"Model: {result.model_path}")
    print(f"Metrics: {result.metrics_path}")
    print(f"Predictions: {result.predictions_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
