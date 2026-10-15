from briefquote.estimate import Estimate
from briefquote.quote import build_quote, render_markdown


def _est():
    return Estimate(60.0, 80.0, 110.0, 2000.0, 3100.0, 4500.0, 0.7, "baseline", 30, [])


def test_contingency_base(sample_scope):
    s = sample_scope.model_copy(update={"has_clear_requirements": True, "risk_flags": []})
    assert build_quote(s, _est(), 40).contingency_pct == 10


def test_contingency_capped(sample_scope):
    s = sample_scope.model_copy(update={"has_clear_requirements": False, "risk_flags": ["a", "b", "c"]})
    assert build_quote(s, _est(), 40).contingency_pct == 35


def test_recommended_price(sample_scope):
    q = build_quote(sample_scope, _est(), 40)
    assert q.recommended_price % 50 == 0
    assert q.price_floor <= q.recommended_price <= q.price_ceiling
    assert q.rate_based_price_mid == round(80 * 40 * (1 + q.contingency_pct / 100), 2)


def test_render(sample_scope):
    md = render_markdown(sample_scope, build_quote(sample_scope, _est(), 40))
    for h in ["## Summary", "## Deliverables", "## Assumptions & open questions",
              "## Estimate", "## Price", "## Risks"]:
        assert h in md
    for d in sample_scope.deliverables:
        assert d in md


def _invariant(q):
    assert q.price_floor <= q.recommended_price <= q.price_ceiling
    for v in (q.price_floor, q.recommended_price, q.price_ceiling):
        assert v % 50 == 0


def test_range_tabpfn_numbers(sample_scope):
    e = Estimate(80.1, 91.9, 102.4, 3250.0, 3700.0, 4050.0, 0.98, "tabpfn", 30, [])
    _invariant(build_quote(sample_scope, e, 40))


def test_range_crossing_quantiles(sample_scope):
    e = Estimate(110.0, 80.0, 60.0, 4500.0, 3100.0, 2000.0, 0.7, "baseline", 30, [])
    assert e.hours_p10 <= e.hours_p50 <= e.hours_p90
    assert e.price_p10 <= e.price_p50 <= e.price_p90
    _invariant(build_quote(sample_scope, e, 40))


def test_on_time_clamped():
    hi = Estimate(1, 2, 3, 1, 2, 3, 0.98, "tabpfn", 30, [])
    lo = Estimate(1, 2, 3, 1, 2, 3, 0.0, "baseline", 30, [])
    assert hi.on_time_probability == 0.95
    assert lo.on_time_probability == 0.05


def test_small_history_wording(sample_scope):
    e = Estimate(60.0, 80.0, 110.0, 2000.0, 3100.0, 4500.0, 0.98, "tabpfn", 30, [])
    md = render_markdown(sample_scope, build_quote(sample_scope, e, 40))
    assert "rough guide" in md
    assert "small history of 30 past jobs" in md
    assert "95%" in md and "98%" not in md
    big = Estimate(60.0, 80.0, 110.0, 2000.0, 3100.0, 4500.0, 0.7, "baseline", 150, [])
    md = render_markdown(sample_scope, build_quote(sample_scope, big, 40))
    assert "small history" not in md
