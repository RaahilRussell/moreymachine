"""Shared dataclass-based schema contracts.

The project intentionally uses dataclasses instead of adding a runtime schema
dependency. These contracts validate generated artifacts at the table level:
columns, enum values, provenance fields, non-null keys, and basic JSON/CSV/
Parquet readability.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

ALLOWED_DATA_MODES = (
    "real_api",
    "real_scraped",
    "real_manual",
    "derived",
    "missing",
)


@dataclass(frozen=True)
class ArtifactSchema:
    """A schema contract for one generated artifact."""

    name: str
    path: Path
    required_columns: tuple[str, ...]
    optional_columns: tuple[str, ...] = ()
    enum_columns: dict[str, tuple[str, ...]] = field(default_factory=dict)
    provenance_columns: tuple[str, ...] = ()
    non_null_columns: tuple[str, ...] = ()
    source_columns: tuple[str, ...] = ("source", "source_url", "source_note")
    freshness_columns: tuple[str, ...] = ("pulled_at", "effective_date")
    data_mode_column: str = "data_mode"
    missing_data_column: str = "missing_data_flags"
    required_artifact: bool = False
    artifact_type: str = "parquet"
    description: str = ""

    @property
    def all_defined_columns(self) -> tuple[str, ...]:
        """Return every column the schema knows about."""
        columns = [
            *self.required_columns,
            *self.optional_columns,
            *self.provenance_columns,
            *self.source_columns,
            *self.freshness_columns,
            self.data_mode_column,
            self.missing_data_column,
        ]
        return tuple(dict.fromkeys(c for c in columns if c))


@dataclass
class SchemaValidationResult:
    """Validation result for one artifact."""

    schema_name: str
    path: Path
    present: bool
    rows: int = 0
    columns: tuple[str, ...] = ()
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.present and not self.errors

    @property
    def skipped(self) -> bool:
        return not self.present and not self.errors


def read_artifact(schema: ArtifactSchema) -> pd.DataFrame | dict[str, Any]:
    """Read an artifact using its declared type."""
    if schema.artifact_type == "parquet":
        return pd.read_parquet(schema.path)
    if schema.artifact_type == "csv":
        return pd.read_csv(schema.path)
    if schema.artifact_type == "json":
        return json.loads(schema.path.read_text())
    raise ValueError(f"Unsupported artifact_type: {schema.artifact_type}")


def validate_artifact(schema: ArtifactSchema) -> SchemaValidationResult:
    """Validate one artifact against its schema."""
    if not schema.path.exists():
        result = SchemaValidationResult(
            schema_name=schema.name,
            path=schema.path,
            present=False,
        )
        if schema.required_artifact:
            result.errors.append("required artifact is missing")
        else:
            result.warnings.append("artifact not generated yet")
        return result

    try:
        artifact = read_artifact(schema)
    except Exception as exc:  # pragma: no cover - defensive IO boundary
        return SchemaValidationResult(
            schema_name=schema.name,
            path=schema.path,
            present=True,
            errors=[f"could not read artifact: {exc}"],
        )

    if isinstance(artifact, dict):
        return _validate_json_dict(schema, artifact)
    return validate_frame(schema, artifact)


def validate_frame(
    schema: ArtifactSchema,
    frame: pd.DataFrame,
) -> SchemaValidationResult:
    """Validate a DataFrame against a schema."""
    result = SchemaValidationResult(
        schema_name=schema.name,
        path=schema.path,
        present=True,
        rows=len(frame),
        columns=tuple(frame.columns),
    )
    columns = set(frame.columns)
    for column in schema.required_columns:
        if column not in columns:
            result.errors.append(f"missing required column: {column}")
    for column in schema.provenance_columns:
        if column not in columns:
            result.errors.append(f"missing provenance column: {column}")
    for column in schema.non_null_columns:
        if column in columns and frame[column].isna().any():
            result.errors.append(f"null values in non-null column: {column}")
    for column, allowed in schema.enum_columns.items():
        if column not in columns:
            continue
        values = set(frame[column].dropna().astype(str).unique())
        illegal = sorted(values - set(allowed))
        if illegal:
            result.errors.append(
                f"illegal values in {column}: {', '.join(illegal[:10])}"
            )
    if schema.data_mode_column in columns:
        values = set(frame[schema.data_mode_column].dropna().astype(str).unique())
        illegal = sorted(values - set(ALLOWED_DATA_MODES))
        if illegal:
            result.errors.append(
                f"illegal data_mode values: {', '.join(illegal[:10])}"
            )
    elif schema.data_mode_column:
        result.warnings.append(f"missing data mode column: {schema.data_mode_column}")
    if schema.missing_data_column and schema.missing_data_column not in columns:
        result.warnings.append(
            f"missing missing-data column: {schema.missing_data_column}"
        )
    _warn_if_no_source_or_freshness(schema, columns, result)
    return result


def _validate_json_dict(
    schema: ArtifactSchema,
    artifact: dict[str, Any],
) -> SchemaValidationResult:
    result = SchemaValidationResult(
        schema_name=schema.name,
        path=schema.path,
        present=True,
        rows=1,
        columns=tuple(artifact.keys()),
    )
    for key in schema.required_columns:
        if key not in artifact:
            result.errors.append(f"missing required key: {key}")
    return result


def _warn_if_no_source_or_freshness(
    schema: ArtifactSchema,
    columns: set[str],
    result: SchemaValidationResult,
) -> None:
    source_defined = any(column in columns for column in schema.source_columns)
    freshness_defined = any(column in columns for column in schema.freshness_columns)
    if not source_defined:
        result.warnings.append("no source/source_url/source_note column present")
    if not freshness_defined:
        result.warnings.append("no pulled_at/effective_date column present")


def summarize_results(results: list[SchemaValidationResult]) -> str:
    """Return a Markdown summary for schema validation results."""
    lines = [
        "# Schema Validation",
        "",
        "| Artifact | Status | Rows | Errors | Warnings |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for result in results:
        if result.passed:
            status = "PASS"
        elif result.skipped:
            status = "SKIP"
        else:
            status = "FAIL"
        lines.append(
            f"| {result.schema_name} | {status} | {result.rows} | "
            f"{len(result.errors)} | {len(result.warnings)} |"
        )
    lines.extend(["", "## Details", ""])
    for result in results:
        lines.append(f"### {result.schema_name}")
        lines.append("")
        lines.append(f"- Path: `{result.path}`")
        lines.append(f"- Present: `{result.present}`")
        if result.errors:
            lines.append("- Errors:")
            lines.extend(f"  - {error}" for error in result.errors)
        if result.warnings:
            lines.append("- Warnings:")
            lines.extend(f"  - {warning}" for warning in result.warnings)
        if not result.errors and not result.warnings:
            lines.append("- Clean.")
        lines.append("")
    return "\n".join(lines)

