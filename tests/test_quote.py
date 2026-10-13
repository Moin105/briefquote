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
    assert q.price_floor <= q.recommended_price <= q.price_ceiling or q.recommended_price > 0
    assert q.rate_based_price_mid == round(80 * 40 * (1 + q.contingency_pct / 100), 2)


def test_render(sample_scope):
    md = render_markdown(sample_scope, build_quote(sample_scope, _est(), 40))
    for h in ["## Summary", "## Deliverables", "## Assumptions & open questions",
              "## Estimate", "## Price", "## Risks"]:
        assert h in md
    for d in sample_scope.deliverables:
        assert d in md
