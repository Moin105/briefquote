import pytest

from briefquote.estimate import BaselineEstimator, get_estimator
from briefquote.features import load_history


def _check(est):
    assert 0 <= est.hours_p10 <= est.hours_p50 <= est.hours_p90
    assert 0 <= est.price_p10 <= est.price_p50 <= est.price_p90
    assert 0.0 <= est.on_time_probability <= 1.0


def test_baseline(history_path, sample_scope):
    est = BaselineEstimator().fit(load_history(history_path)).predict(sample_scope)
    _check(est)
    assert est.method == "baseline"
    assert est.n_history == 30


def test_get_estimator_no_tabpfn():
    assert isinstance(get_estimator(prefer_tabpfn=False), BaselineEstimator)


@pytest.mark.slow
def test_tabpfn(history_path, sample_scope, monkeypatch):
    pytest.importorskip("tabpfn")
    from briefquote.estimate import TabPFNEstimator

    monkeypatch.setenv("TABPFN_NO_BROWSER", "1")  # never open a login page from tests
    try:
        model = TabPFNEstimator().fit(load_history(history_path))
    except Exception as exc:
        if "License" in type(exc).__name__ or "license" in str(exc).lower():
            pytest.skip("TabPFN weights need license acceptance / TABPFN_TOKEN")
        raise
    est = model.predict(sample_scope)
    _check(est)
    assert est.method == "tabpfn"


def test_bundled_history_detected(history_path, sample_scope, tmp_path):
    est = BaselineEstimator().fit(load_history(history_path)).predict(sample_scope)
    assert est.history_is_bundled_example is True
    custom = tmp_path / "mine.csv"
    custom.write_text(history_path.read_text(encoding="utf-8"), encoding="utf-8")
    est = BaselineEstimator().fit(load_history(custom)).predict(sample_scope)
    assert est.history_is_bundled_example is False
