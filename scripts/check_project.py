"""Verify that the MoreyMachine project skeleton is usable."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"

REQUIRED_DIRECTORIES = (
    REPO_ROOT / "src" / "moreymachine",
    REPO_ROOT / "src" / "moreymachine" / "utils",
    REPO_ROOT / "data",
    REPO_ROOT / "data" / "raw",
    REPO_ROOT / "data" / "raw" / "nba_api",
    REPO_ROOT / "data" / "processed",
    REPO_ROOT / "data" / "features",
    REPO_ROOT / "data" / "models",
    REPO_ROOT / "data" / "reports",
    REPO_ROOT / "notebooks",
    REPO_ROOT / "scripts",
    REPO_ROOT / "tests",
)

REQUIRED_MODULES = (
    "moreymachine",
    "moreymachine.utils.paths",
    "moreymachine.utils.logging",
    "moreymachine.utils.config",
    "moreymachine.data.cache",
    "moreymachine.data.fetch_nba",
)


def main() -> int:
    """Run project structure and import checks."""
    _make_src_importable()
    missing_directories = [path for path in REQUIRED_DIRECTORIES if not path.is_dir()]

    import_errors: dict[str, Exception] = {}
    for module_name in REQUIRED_MODULES:
        try:
            importlib.import_module(module_name)
        except Exception as exc:  # pragma: no cover - printed for CLI diagnostics.
            import_errors[module_name] = exc

    if missing_directories or import_errors:
        _print_failure(missing_directories, import_errors)
        return 1

    print("Project check passed.")
    print(f"Repository root: {REPO_ROOT}")
    print("Imports verified:")
    for module_name in REQUIRED_MODULES:
        print(f"  - {module_name}")
    return 0


def _make_src_importable() -> None:
    src_path = str(SRC_DIR)
    if src_path not in sys.path:
        sys.path.insert(0, src_path)


def _print_failure(
    missing_directories: list[Path],
    import_errors: dict[str, Exception],
) -> None:
    print("Project check failed.", file=sys.stderr)
    if missing_directories:
        print("Missing directories:", file=sys.stderr)
        for directory in missing_directories:
            print(f"  - {directory}", file=sys.stderr)
    if import_errors:
        print("Import errors:", file=sys.stderr)
        for module_name, exc in import_errors.items():
            print(f"  - {module_name}: {exc}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
