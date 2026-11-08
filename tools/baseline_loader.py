"""Load and verify the frozen upstream ``SqliteRunner`` used for comparison."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = PROJECT_ROOT / "baseline" / "upstream_sql_runner.py"
#: SHA256 of src/vanna/integrations/sqlite/sql_runner.py at upstream commit
#: 365d0617c1a4567ffee1b19b40c27feb4206bfcf (frozen by the supervisor).
BASELINE_SHA256 = "830dd109940121c871af4f9a6c16950f36e70a92745a224bca4152e448681ca6"


def sha256_file(path: Path) -> str | None:
    if not path.exists():
        return None
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_baseline_runner() -> Any:
    """Import the frozen upstream file by path, refusing a modified baseline."""

    actual = sha256_file(BASELINE_PATH)
    if actual != BASELINE_SHA256:
        raise SystemExit(
            "baseline/upstream_sql_runner.py hash mismatch:\n"
            f"  expected {BASELINE_SHA256}\n  actual   {actual}\n"
            "Refusing to run: the frozen baseline must stay byte-identical."
        )
    spec = importlib.util.spec_from_file_location(
        "g1_upstream_sql_runner", BASELINE_PATH
    )
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise SystemExit(f"cannot load baseline module from {BASELINE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.SqliteRunner
