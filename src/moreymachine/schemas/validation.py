"""Schema registry and validation entry points."""

from __future__ import annotations

from moreymachine.schemas import (
    acquisition,
    blueprints,
    compatibility,
    contracts,
    entities,
    explanations,
    gaps,
    player_profile,
    recommendations,
    roster_simulation,
    roster_world,
    scenarios,
    skills,
)
from moreymachine.schemas.common import (
    ArtifactSchema,
    SchemaValidationResult,
    validate_artifact,
)

SCHEMA_MODULES = (
    entities,
    contracts,
    roster_world,
    blueprints,
    gaps,
    skills,
    compatibility,
    roster_simulation,
    acquisition,
    scenarios,
    recommendations,
    explanations,
    player_profile,
)

ALL_SCHEMAS: tuple[ArtifactSchema, ...] = tuple(
    schema for module in SCHEMA_MODULES for schema in module.SCHEMAS
)


def validate_all_schemas() -> list[SchemaValidationResult]:
    """Validate every registered artifact schema."""
    return [validate_artifact(schema) for schema in ALL_SCHEMAS]


def failed_results(
    results: list[SchemaValidationResult],
) -> list[SchemaValidationResult]:
    """Return only failed schema validations."""
    return [result for result in results if result.errors]
