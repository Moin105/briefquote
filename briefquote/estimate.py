from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Literal, Protocol

import numpy as np
import pandas as pd

from briefquote.features import (
    FEATURE_COLUMNS,
    feature_matrix,
    featurize,
    history_is_bundled,
    regression_rows,
)
from briefquote.schema import ScopeExtraction

QUANTILES = [0.1, 0.5, 0.9]
ON_TIME_MIN = 0.05
ON_TIME_MAX = 0.95
SMALL_HISTORY = 100


@dataclass
class Estimate:
    hours_p10: float
    hours_p50: float
    hours_p90: float
    price_p10: float
    price_p50: float
    price_p90: float
    on_time_probability: float
    method: Literal["tabpfn", "baseline"]
    n_history: int
    notes: list[str] = field(default_factory=list)
    # True when the history is the synthetic data/past_jobs.csv shipped with briefquote.
    history_is_bundled_example: bool = False

    def __post_init__(self) -> None:
        # Models can return crossing quantiles; keep p10 <= p50 <= p90.
        self.hours_p10, self.hours_p50, self.hours_p90 = sorted(
            (self.hours_p10, self.hours_p50, self.hours_p90)
        )
        self.price_p10, self.price_p50, self.price_p90 = sorted(
            (self.price_p10, self.price_p50, self.price_p90)
        )
        # A classifier fit on a small history is never this certain.
        self.on_time_probability = min(max(self.on_time_probability, ON_TIME_MIN), ON_TIME_MAX)


class Estimator(Protocol):
    def fit(self, df: pd.DataFrame) -> "Estimator": ...
    def predict(self, scope: ScopeExtraction) -> Estimate: ...


def _clean(vals) -> tuple[float, float, float]:
    """Non-negative, monotone, rounded to 1 decimal."""
    v = np.sort(np.clip(np.asarray(vals, dtype=float), 0, None))
    return tuple(round(float(x), 1) for x in v)  # type: ignore[return-value]


class BaselineEstimator:
    """k-nearest-neighbour estimator. No ML dependencies."""

    def __init__(self, k: int = 5, notes: list[str] | None = None):
        self.k = k
        self.notes = list(notes or [])
        self._bundled = False
        self._df: pd.DataFrame | None = None

    def fit(self, df: pd.DataFrame) -> "BaselineEstimator":
        self._bundled = history_is_bundled(df)
        self._df = df.reset_index(drop=True)
        return self

    def _neighbours(self, df: pd.DataFrame, f: dict) -> pd.DataFrame:
        d = (
            (df["project_type"] != f["project_type"]).astype(float) * 3.0
            + (df["complexity"] - f["complexity"]).abs()
            + (df["integrations_count"] - f["integrations_count"]).abs()
            + (df["deliverables_count"] - f["deliverables_count"]).abs() * 0.5
        )
        order = d.sort_values(kind="stable").index[: self.k]
        return df.loc[order]

    def predict(self, scope: ScopeExtraction) -> Estimate:
        if self._df is None or self._df.empty:
            raise RuntimeError("fit() must be called with a non-empty history first")
        f = featurize(scope)
        reg = regression_rows(self._df)
        if reg.empty:
            raise RuntimeError("history has no usable (non-cancelled) rows")
        nb = self._neighbours(reg, f)
        h = np.percentile(nb["hours_actual"], [10, 50, 90])
        p = np.percentile(nb["price_usd"], [10, 50, 90])
        nb_all = self._neighbours(self._df, f)
        on_time = float((nb_all["outcome"] == "delivered").mean())
        return Estimate(
            *_clean(h),
            *_clean(p),
            on_time_probability=round(on_time, 3),
            method="baseline",
            n_history=len(self._df),
            notes=list(self.notes) + [f"nearest {len(nb)} past jobs used"],
            history_is_bundled_example=self._bundled,
        )


class TabPFNEstimator:
    """TabPFN (Prior Labs tabular foundation model) for hours, price and on-time."""

    def __init__(self, device: str = "cpu"):
        self.device = device
        self._n = 0
        self._bundled = False
        self._notes: list[str] = []
        try:
            import tabpfn  # noqa: F401
        except ImportError as exc:
            raise ImportError("tabpfn is not installed (pip install 'briefquote[estimator]')") from exc

    def _make(self, cls):
        kwargs: dict = {"device": self.device}
        params = inspect.signature(cls.__init__).parameters
        if "categorical_features_indices" in params:
            kwargs["categorical_features_indices"] = [FEATURE_COLUMNS.index("project_type")]
        elif "project_type integer-encoded" not in " ".join(self._notes):
            self._notes.append("project_type integer-encoded (no categorical option in this tabpfn)")
        return cls(**kwargs)

    def fit(self, df: pd.DataFrame) -> "TabPFNEstimator":
        from tabpfn import TabPFNClassifier, TabPFNRegressor

        self._n = len(df)
        self._bundled = history_is_bundled(df)
        self._notes = []
        reg = regression_rows(df)
        X = feature_matrix(reg).values
        yh = reg["hours_actual"].astype(float).values
        yp = reg["price_usd"].astype(float).values
        self._hours = self._make(TabPFNRegressor).fit(X, yh)
        self._price = self._make(TabPFNRegressor).fit(X, yp)
        self._hours_std = float(np.std(yh))
        self._price_std = float(np.std(yp))
        y = (df["outcome"] == "delivered").astype(int).values
        self._clf = None
        self._const_on_time = float(y[0]) if len(set(y)) < 2 else None
        if self._const_on_time is None:
            self._clf = self._make(TabPFNClassifier).fit(feature_matrix(df).values, y)
        return self

    def _quantiles(self, model, X, std: float) -> list[float]:
        try:
            out = model.predict(X, output_type="quantiles", quantiles=QUANTILES)
            return [float(np.asarray(q).ravel()[0]) for q in out]
        except Exception:
            mid = float(model.predict(X)[0])
            if "quantile output unavailable" not in " ".join(self._notes):
                self._notes.append("quantile output unavailable; spread derived from training std")
            return [mid - 0.32 * std, mid, mid + 0.32 * std]

    def predict(self, scope: ScopeExtraction) -> Estimate:
        X = feature_matrix([featurize(scope)]).values
        h = self._quantiles(self._hours, X, self._hours_std)
        p = self._quantiles(self._price, X, self._price_std)
        if self._clf is None:
            on_time = self._const_on_time or 0.0
        else:
            classes = list(self._clf.classes_)
            proba = self._clf.predict_proba(X)[0]
            on_time = float(proba[classes.index(1)]) if 1 in classes else 0.0
        return Estimate(
            *_clean(h),
            *_clean(p),
            on_time_probability=round(on_time, 3),
            method="tabpfn",
            n_history=self._n,
            notes=list(self._notes),
            history_is_bundled_example=self._bundled,
        )


def get_estimator(prefer_tabpfn: bool = True) -> Estimator:
    """TabPFN when installed, otherwise the baseline with the reason in notes."""
    if not prefer_tabpfn:
        return BaselineEstimator(notes=["TabPFN disabled (--no-tabpfn)"])
    try:
        return TabPFNEstimator()
    except Exception as exc:
        return BaselineEstimator(notes=[f"TabPFN unavailable: {exc}"])


def fit_estimator(df: pd.DataFrame, prefer_tabpfn: bool = True) -> Estimator:
    """get_estimator + fit; if TabPFN fails while loading weights, fall back to baseline."""
    est = get_estimator(prefer_tabpfn)
    try:
        return est.fit(df)
    except Exception as exc:
        if isinstance(est, TabPFNEstimator):
            reason = " ".join(str(exc).split())
            if len(reason) > 160:
                reason = reason[:157] + "..."
            note = f"TabPFN failed to load or fit ({type(exc).__name__}: {reason})"
            return BaselineEstimator(notes=[note]).fit(df)
        raise
