"""Artifact lineage helpers."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from moreymachine.config.teams import ensure_team_output_dirs, normalize_team


@dataclass(frozen=True)
class ArtifactMetadata:
    """Metadata sidecar for a generated artifact."""

    artifact_name: str
    created_at: str
    run_id: str
    source_files: tuple[str, ...]
    source_urls: tuple[str, ...]
    rows: int | None
    columns: tuple[str, ...]
    seasons: tuple[str, ...]
    data_mode: tuple[str, ...]
    upstream_artifacts: tuple[str, ...]
    known_limitations: tuple[str, ...]


def new_run_id() -> str:
    """Create a short unique run ID."""
    return f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"


def make_run_id() -> str:
    """Compatibility alias for team-scoped product code."""
    return new_run_id()


def metadata_path(path: str | Path) -> Path:
    """Return the same-file-name metadata sidecar path."""
    artifact_path = Path(path)
    return artifact_path.with_name(f"{artifact_path.name}.metadata.json")


def infer_artifact_metadata(
    path: str | Path,
    *,
    run_id: str,
    source_files: list[str | Path] | tuple[str | Path, ...] = (),
    source_urls: list[str] | tuple[str, ...] = (),
    upstream_artifacts: list[str | Path] | tuple[str | Path, ...] = (),
    known_limitations: list[str] | tuple[str, ...] = (),
) -> ArtifactMetadata:
    """Infer metadata for a local artifact."""
    artifact_path = Path(path)
    rows: int | None = None
    columns: tuple[str, ...] = ()
    seasons: tuple[str, ...] = ()
    data_mode: tuple[str, ...] = ()

    if artifact_path.suffix == ".parquet" and artifact_path.exists():
        frame = pd.read_parquet(artifact_path)
        rows = len(frame)
        columns = tuple(map(str, frame.columns))
        seasons = _unique_column_values(frame, "season") or _unique_column_values(
            frame, "target_season"
        )
        data_mode = _unique_column_values(frame, "data_mode")
    elif artifact_path.suffix == ".csv" and artifact_path.exists():
        frame = pd.read_csv(artifact_path)
        rows = len(frame)
        columns = tuple(map(str, frame.columns))
        seasons = _unique_column_values(frame, "season") or _unique_column_values(
            frame, "target_season"
        )
        data_mode = _unique_column_values(frame, "data_mode")
    elif artifact_path.suffix == ".json" and artifact_path.exists():
        payload = json.loads(artifact_path.read_text())
        rows = 1
        if isinstance(payload, dict):
            columns = tuple(map(str, payload.keys()))
    elif artifact_path.exists():
        rows = None

    return ArtifactMetadata(
        artifact_name=artifact_path.name,
        created_at=datetime.now(UTC).isoformat(),
        run_id=run_id,
        source_files=tuple(_display_path(Path(p)) for p in source_files),
        source_urls=tuple(source_urls),
        rows=rows,
        columns=columns,
        seasons=seasons,
        data_mode=data_mode,
        upstream_artifacts=tuple(_display_path(Path(p)) for p in upstream_artifacts),
        known_limitations=tuple(known_limitations),
    )


def write_artifact_metadata(
    path: str | Path,
    metadata: ArtifactMetadata,
) -> Path:
    """Write sidecar metadata next to an artifact."""
    sidecar = metadata_path(path)
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = asdict(metadata)
    sidecar.write_text(json.dumps(payload, indent=2, sort_keys=True))
    return sidecar


def write_metadata_for_artifact(
    path: str | Path,
    *,
    run_id: str,
    source_files: list[str | Path] | tuple[str | Path, ...] = (),
    source_urls: list[str] | tuple[str, ...] = (),
    upstream_artifacts: list[str | Path] | tuple[str | Path, ...] = (),
    known_limitations: list[str] | tuple[str, ...] = (),
) -> Path:
    """Infer and write sidecar metadata for an artifact."""
    metadata = infer_artifact_metadata(
        path,
        run_id=run_id,
        source_files=source_files,
        source_urls=source_urls,
        upstream_artifacts=upstream_artifacts,
        known_limitations=known_limitations,
    )
    return write_artifact_metadata(path, metadata)


def write_artifact(
    df: pd.DataFrame,
    path: str | Path,
    metadata: dict[str, Any] | None = None,
) -> Path:
    """Write a tabular artifact and same-file metadata sidecar."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.suffix == ".csv":
        df.to_csv(output, index=False)
    else:
        df.to_parquet(output, index=False)
    _write_dict_metadata(output, _metadata_payload(output, metadata, frame=df))
    return output


def write_json_artifact(
    obj: Any,
    path: str | Path,
    metadata: dict[str, Any] | None = None,
) -> Path:
    """Write a JSON artifact and same-file metadata sidecar."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")
    _write_dict_metadata(output, _metadata_payload(output, metadata, obj=obj))
    return output


def load_artifact(path: str | Path) -> Any:
    """Load an artifact by suffix."""
    artifact = Path(path)
    if artifact.suffix == ".parquet":
        return pd.read_parquet(artifact)
    if artifact.suffix == ".csv":
        return pd.read_csv(artifact)
    if artifact.suffix == ".json":
        return json.loads(artifact.read_text(encoding="utf-8"))
    return artifact.read_text(encoding="utf-8")


def artifact_exists(team: str, artifact_name: str) -> bool:
    """Return whether a team-scoped artifact exists."""
    root = ensure_team_output_dirs(normalize_team(team))["root"]
    direct = root / artifact_name
    if direct.exists():
        return True
    return any(path.name == artifact_name for path in root.rglob(artifact_name))


def artifact_path(team: str, kind: str, filename: str) -> Path:
    """Return a standard team-scoped artifact path."""
    dirs = ensure_team_output_dirs(normalize_team(team))
    directory = dirs.get(kind)
    if directory is None:
        directory = dirs["root"] / kind
        directory.mkdir(parents=True, exist_ok=True)
    return directory / filename


def discover_artifacts(root: str | Path) -> list[Path]:
    """Discover generated artifacts that should receive lineage sidecars."""
    root_path = Path(root)
    suffixes = {".parquet", ".csv", ".json", ".md"}
    ignored_names = {".gitkeep"}
    paths = []
    for path in root_path.rglob("*"):
        if not path.is_file() or path.name in ignored_names:
            continue
        if path.name.endswith(".metadata.json"):
            continue
        if path.suffix in suffixes:
            paths.append(path)
    return sorted(paths)


def _metadata_payload(
    path: Path,
    metadata: dict[str, Any] | None,
    *,
    frame: pd.DataFrame | None = None,
    obj: Any = None,
) -> dict[str, Any]:
    payload = dict(metadata or {})
    payload.setdefault("artifact_name", path.name)
    payload.setdefault("created_at", datetime.now(UTC).isoformat())
    payload.setdefault("run_id", new_run_id())
    payload.setdefault("source_files", [])
    payload.setdefault("source_urls", [])
    payload.setdefault("upstream_artifacts", [])
    payload.setdefault("known_limitations", [])
    payload.setdefault("data_mode", "derived")
    if frame is not None:
        payload["rows"] = len(frame)
        payload["columns"] = [str(column) for column in frame.columns]
    elif isinstance(obj, list):
        payload.setdefault("rows", len(obj))
        payload.setdefault("columns", [])
    elif isinstance(obj, dict):
        payload.setdefault("rows", 1)
        payload.setdefault("columns", list(map(str, obj.keys())))
    else:
        payload.setdefault("rows", None)
        payload.setdefault("columns", [])
    return _json_ready(payload)


def _write_dict_metadata(path: Path, payload: dict[str, Any]) -> Path:
    sidecar = metadata_path(path)
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    sidecar.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return sidecar


def _json_ready(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_ready(item) for item in value]
    if isinstance(value, Path):
        return _display_path(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "item"):
        return value.item()
    return value


def _unique_column_values(frame: pd.DataFrame, column: str) -> tuple[str, ...]:
    if column not in frame.columns:
        return ()
    return tuple(sorted(set(frame[column].dropna().astype(str))))


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return str(path)
