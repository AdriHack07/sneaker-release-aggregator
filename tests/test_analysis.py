"""Unit tests for the profit/margin/filter/rank core."""

from datetime import date, timedelta

import pytest

from sneaker_aggregator.analysis import (
    evaluate,
    find_opportunities,
    in_window,
    net_payout,
)
from sneaker_aggregator.config import Config, Fees
from sneaker_aggregator.models import Release


def make_release(**kw) -> Release:
    base = dict(
        sku="DZ5485-612",
        name="Air Jordan 1 High Test",
        brand="Jordan",
        retail_price=180.0,
        release_date=date.today(),
        lowest_ask=400.0,
        avg_price=420.0,
        sales_count=50,
    )
    base.update(kw)
    return Release(**base)


def default_config(**overrides) -> Config:
    cfg = Config()
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


# ----- net_payout -------------------------------------------------------------


def test_net_payout_applies_fees_and_shipping():
    fees = Fees(commission_pct=0.09, payment_processing_pct=0.03, shipping_cost=10.0)
    # 400 * (1 - 0.12) - 10 = 352 - 10 = 342
    assert net_payout(400.0, fees) == pytest.approx(342.0)


# ----- evaluate ---------------------------------------------------------------


def test_evaluate_profitable_release_qualifies():
    cfg = default_config()
    opp = evaluate(make_release(), cfg)
    assert opp is not None
    # 400 * 0.88 = 352 net; profit = 352 - 180 = 172
    assert opp.net_payout == pytest.approx(352.0)
    assert opp.profit == pytest.approx(172.0)
    assert opp.margin == pytest.approx(172.0 / 180.0, rel=1e-3)


def test_evaluate_uses_average_when_lowest_ask_missing():
    cfg = default_config()
    opp = evaluate(make_release(lowest_ask=None), cfg)
    assert opp is not None
    assert opp.resale_price == 420.0  # fell back to avg_price


def test_evaluate_below_profit_threshold_rejected():
    cfg = default_config()
    # resale barely above retail -> tiny profit
    assert evaluate(make_release(lowest_ask=200.0), cfg) is None


def test_evaluate_below_margin_threshold_rejected():
    cfg = default_config()
    cfg.thresholds.min_profit = 0.0
    cfg.thresholds.min_margin = 1.50  # demand 150% margin (actual is ~96%)
    assert evaluate(make_release(), cfg) is None


def test_evaluate_illiquid_release_rejected():
    cfg = default_config()
    cfg.thresholds.min_sales_count = 10
    assert evaluate(make_release(sales_count=2), cfg) is None


def test_evaluate_missing_prices_returns_none():
    cfg = default_config()
    assert evaluate(make_release(retail_price=None), cfg) is None
    assert evaluate(make_release(lowest_ask=None, avg_price=None), cfg) is None


# ----- in_window --------------------------------------------------------------


def test_in_window_keeps_today_and_future_within_bounds():
    cfg = default_config()
    today = date(2026, 6, 23)
    assert in_window(make_release(release_date=today), cfg.window, today)
    assert in_window(
        make_release(release_date=today + timedelta(days=cfg.window.future_days)),
        cfg.window,
        today,
    )
    assert not in_window(
        make_release(release_date=today + timedelta(days=cfg.window.future_days + 1)),
        cfg.window,
        today,
    )


def test_in_window_excludes_past_releases():
    cfg = default_config()
    today = date(2026, 6, 23)
    assert not in_window(make_release(release_date=today - timedelta(days=1)), cfg.window, today)
    assert not in_window(make_release(release_date=today - timedelta(days=60)), cfg.window, today)


def test_in_window_keeps_undated():
    cfg = default_config()
    assert in_window(make_release(release_date=None), cfg.window, date.today())


# ----- find_opportunities -----------------------------------------------------


def test_find_opportunities_filters_brand_and_ranks_by_profit():
    cfg = default_config()
    releases = [
        make_release(sku="A", name="Low profit", lowest_ask=300.0),   # profit 84
        make_release(sku="B", name="High profit", lowest_ask=600.0),  # profit 348
        make_release(sku="C", name="Adidas", brand="Adidas", lowest_ask=600.0),  # wrong brand
    ]
    opps = find_opportunities(releases, cfg, today=date.today())
    assert [o.release.sku for o in opps] == ["B", "A"]


def test_find_opportunities_sort_by_date():
    cfg = default_config()
    cfg.sort_by = "date"
    today = date(2026, 6, 23)
    releases = [
        make_release(sku="LATER", release_date=date(2026, 7, 20), lowest_ask=600.0),
        make_release(sku="SOONER", release_date=date(2026, 6, 25), lowest_ask=600.0),
        make_release(sku="UNDATED", release_date=None, lowest_ask=600.0),
    ]
    opps = find_opportunities(releases, cfg, today=today)
    # Soonest release first; undated sorts last.
    assert [o.release.sku for o in opps] == ["SOONER", "LATER", "UNDATED"]


def test_find_opportunities_respects_max_results():
    cfg = default_config()
    cfg.max_results = 1
    releases = [
        make_release(sku="A", lowest_ask=300.0),
        make_release(sku="B", lowest_ask=600.0),
    ]
    opps = find_opportunities(releases, cfg, today=date.today())
    assert len(opps) == 1
    assert opps[0].release.sku == "B"


def test_find_opportunities_excludes_past_releases():
    cfg = default_config()
    today = date(2026, 6, 25)
    releases = [
        make_release(sku="PAST", release_date=today - timedelta(days=5), lowest_ask=600.0),
        make_release(sku="FUTURE", release_date=today + timedelta(days=5), lowest_ask=600.0),
        make_release(sku="UNDATED", release_date=None, lowest_ask=600.0),
    ]
    opps = find_opportunities(releases, cfg, today=today)
    skus = {o.release.sku for o in opps}
    assert "PAST" not in skus
    assert {"FUTURE", "UNDATED"} <= skus
