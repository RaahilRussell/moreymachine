#!/usr/bin/env python
"""Build evidence-based explanation artifacts."""

from __future__ import annotations

from moreymachine.models.explanation_engine_v2 import build_explanations_v2


def main() -> int:
    result = build_explanations_v2()
    print(f"Claims: {result.claims}")
    print(f"Evidence objects: {result.evidence_objects}")
    print(f"Player explanations: {result.player_explanations}")
    print(f"Claims output: {result.claims_path}")
    print(f"Evidence output: {result.evidence_path}")
    print(f"Explanations output: {result.explanations_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
