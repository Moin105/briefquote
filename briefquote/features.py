from __future__ import annotations

from pathlib import Path
from typing import get_args

import pandas as pd

from briefquote.schema import ScopeExtraction

PROJECT_TYPES: tuple[str, ...] = get_args(ScopeExtraction.model_fields["project_type"].annotation)

FEATURE_COLUMNS = [
    "project_type",
    "complexity",
    "deliverables_count",
    "integrations_count",
    "has_design_provided",
    "has_clear_requirements",
]
BUNDLED_HISTORY = (Path(__file__).resolve().parent.parent / "data" / "past_jobs.csv").resolve()
BUNDLED_WARNING = (
    "warning: using the bundled example history (data/past_jobs.csv), which is synthetic demo "
    "data, not real client work. Pass --history your_jobs.csv to use your own past jobs."
)


def is_bundled_history(path) -> bool:
    """True when `path` resolves to the synthetic example history shipped with briefquote."""
    try:
        return Path(path).resolve() == BUNDLED_HISTORY
    except (OSError, ValueError, TypeError):
        return False


def history_is_bundled(df: pd.DataFrame) -> bool:
    return bool(df.attrs.get("bundled_example", False))


REQUIRED_COLUMNS = FEATURE_COLUMNS + ["hours_actual", "price_usd", "outcome"]


def encode_project_type(value: str) -> int:
    """Stable integer code for a project type (order of the schema Literal)."""
    try:
        return PROJECT_TYPES.index(value)
    except ValueError:
        return PROJECT_TYPES.index("other")


def featurize(scope: ScopeExtraction) -> dict:
    return {
        "project_type": str(scope.project_type),
        "complexity": scope.complexity,
        "deliverables_count": len(scope.deliverables),
        "integrations_count": scope.integrations_count,
        "has_design_provided": scope.has_design_provided,
        "has_clear_requirements": scope.has_clear_requirements,
    }


def load_history(path) -> pd.DataFrame:
    """Read past jobs and validate columns.

    Cancelled rows are kept here because the on-time classifier uses them;
    call `regression_rows` to drop them for the hours/price targets.
    """
    df = pd.read_csv(path)
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"history file {path} is missing columns: {', '.join(missing)}")
    for c in ("has_design_provided", "has_clear_requirements"):
        df[c] = df[c].astype(str).str.strip().str.lower().isin(["true", "1", "yes"])
    df["outcome"] = df["outcome"].astype(str).str.strip().str.lower()
    df = df.reset_index(drop=True)
    df.attrs["bundled_example"] = is_bundled_history(path)
    return df


def regression_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Rows usable as hours/price targets (cancelled jobs have no true actuals)."""
    return df[df["outcome"] != "cancelled"].reset_index(drop=True)


def feature_matrix(rows: list[dict] | pd.DataFrame) -> pd.DataFrame:
    """Numeric matrix, project_type integer-encoded, in FEATURE_COLUMNS order."""
    df = pd.DataFrame(rows)[FEATURE_COLUMNS].copy()
    df["project_type"] = df["project_type"].map(encode_project_type)
    for c in ("has_design_provided", "has_clear_requirements"):
        df[c] = df[c].astype(int)
    return df.astype(float)
