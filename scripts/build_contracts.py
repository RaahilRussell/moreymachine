"""Build the rich, unambiguous contracts table from real sources + manual import."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from moreymachine.data.contracts_loader import (  # noqa: E402
    MANUAL_OVERRIDE_COLUMNS,
    build_rich_contracts,
)
from moreymachine.utils.paths import MANUAL_CONTRACTS_PATH  # noqa: E402

MANUAL_TEMPLATE_COLUMNS = (
    "player_name",
    "player_id",
    "current_team",
    *MANUAL_OVERRIDE_COLUMNS,
    "pulled_at",
    "data_mode",
    "missing_data_flags",
)


def _write_manual_template() -> None:
    """Create an empty real-data manual contracts template if none exists."""
    if MANUAL_CONTRACTS_PATH.exists():
        return
    MANUAL_CONTRACTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    header = ",".join(MANUAL_TEMPLATE_COLUMNS)
    MANUAL_CONTRACTS_PATH.write_text(header + "\n", encoding="utf-8")
    print(f"Wrote manual contracts template: {MANUAL_CONTRACTS_PATH}")


def main() -> int:
    """CLI entry point for the rich contracts build."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--no-refresh",
        action="store_true",
        help="Use the cached raw scrape instead of re-downloading.",
    )
    args = parser.parse_args()

    _write_manual_template()
    result = build_rich_contracts(refresh=not args.no_refresh)
    print(
        f"Contracts: {result.rows} rows, {result.matched_player_ids} id-matched, "
        f"{result.manual_overrides} manual overrides"
    )
    print("Contract status counts:")
    for status, count in sorted(result.status_counts.items()):
        print(f"  {status}: {count}")
    print(f"Output: {result.output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
