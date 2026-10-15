from __future__ import annotations

from dataclasses import dataclass

from briefquote.estimate import SMALL_HISTORY, Estimate
from briefquote.schema import ScopeExtraction


@dataclass
class Quote:
    estimate: Estimate
    hourly_rate: float
    contingency_pct: float
    rate_based_price_mid: float
    recommended_price: float
    price_floor: float
    price_ceiling: float


def contingency_pct(scope: ScopeExtraction) -> float:
    pct = 10.0
    if not scope.has_clear_requirements:
        pct += 10.0
    pct += 5.0 * len(scope.risk_flags)
    return min(pct, 35.0)


def _round50(x: float) -> float:
    return float(round(x / 50.0) * 50)


def build_quote(scope: ScopeExtraction, estimate: Estimate, hourly_rate: float) -> Quote:
    pct = contingency_pct(scope)
    mult = 1 + pct / 100.0
    rate_mid = estimate.hours_p50 * hourly_rate * mult

    def blend(model_price: float, hours: float) -> float:
        return _round50((model_price + hours * hourly_rate * mult) / 2.0)

    return Quote(
        estimate=estimate,
        hourly_rate=hourly_rate,
        contingency_pct=pct,
        rate_based_price_mid=round(rate_mid, 2),
        recommended_price=blend(estimate.price_p50, estimate.hours_p50),
        price_floor=blend(estimate.price_p10, estimate.hours_p10),
        price_ceiling=blend(estimate.price_p90, estimate.hours_p90),
    )


def _money(x: float) -> str:
    return f"${x:,.0f}"


def render_markdown(scope: ScopeExtraction, quote: Quote) -> str:
    e = quote.estimate
    lines = ["# Project quote", "", "## Summary", "", scope.summary, "", "## Deliverables", ""]
    lines += [f"- {d}" for d in scope.deliverables] or ["- To be confirmed"]
    lines += ["", "## Assumptions & open questions", ""]
    lines += [f"- {u}" for u in scope.unknowns] or ["- None identified"]
    lines += [
        "",
        "## Estimate",
        "",
        f"Expected effort is about {e.hours_p50:g} hours, with a likely range of "
        f"{e.hours_p10:g} to {e.hours_p90:g} hours.",
        "",
        (
            f"Based on a small history of {e.n_history} past jobs, this is a rough guide: "
            f"roughly a {e.on_time_probability * 100:.0f}% chance of delivering on time."
            if e.n_history < SMALL_HISTORY
            else f"Based on comparable past work, there is roughly a "
            f"{e.on_time_probability * 100:.0f}% chance of delivering on time."
        ),
        "",
        f"_Method: {e.method}, based on {e.n_history} past jobs."
        + (f" Note: {'; '.join(e.notes)}." if e.notes and e.method == "baseline" else "")
        + "_",
        "",
        "## Price",
        "",
        f"- Recommended: **{_money(quote.recommended_price)}**",
        f"- Floor: {_money(quote.price_floor)}",
        f"- Ceiling: {_money(quote.price_ceiling)}",
        "",
        f"Includes a {quote.contingency_pct:g}% contingency (10% base, +10% if requirements are "
        f"unclear, +5% per risk flag, capped at 35%) on the hourly-rate estimate at "
        f"{_money(quote.hourly_rate)}/hour.",
        "",
        "## Risks",
        "",
    ]
    lines += [f"- {r}" for r in scope.risk_flags] or ["- None identified"]
    return "\n".join(lines) + "\n"
