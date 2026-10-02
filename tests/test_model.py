import pytest

from cake.model import (
    PRESETS,
    Settings,
    Subscription,
    cocomo_person_months,
    quote,
)


def test_cocomo_one_ksloc_matches_organic_basic():
    assert cocomo_person_months(1) == 2.4
    assert cocomo_person_months(0) == 0


def test_preset_speeds():
    assert PRESETS["classic"].throughput == 1.0
    assert PRESETS["review"].throughput == 1.6
    assert PRESETS["pair"].throughput == 2.5
    assert PRESETS["vibe"].throughput == 4.0


def test_bid_keeps_half_the_labor_savings():
    settings = Settings(
        hourly_rate=100,
        sloc_per_hour=10,
        preset="pair",
        keep_savings=0.5,
        warranty=0.0,
        subscriptions=[],
        hours_per_week=10,
    )
    result = quote(1000, settings)
    throughput = PRESETS["pair"].throughput
    unassisted = 1000 / 10
    ai = unassisted / throughput
    assert result.unassisted_hours == pytest.approx(unassisted)
    assert result.ai_hours == pytest.approx(ai)
    assert result.unassisted_labor == pytest.approx(unassisted * 100)
    assert result.ai_labor == pytest.approx(ai * 100)
    assert result.blended_labor == pytest.approx((unassisted + ai) / 2 * 100)
    assert result.savings_kept == pytest.approx(result.savings_shared)
    assert result.recommended == pytest.approx(result.blended_labor)
    assert result.floor == pytest.approx(result.ai_labor)
    assert result.recommended > result.floor


def test_classic_preset_has_no_savings():
    settings = Settings(
        preset="classic",
        warranty=0.15,
        subscriptions=[],
        hourly_rate=150,
        sloc_per_hour=15,
    )
    result = quote(150, settings)
    assert result.ai_hours == pytest.approx(result.unassisted_hours)
    assert result.savings == 0
    assert result.recommended == pytest.approx(result.floor)


def test_hours_override_still_prices_the_unassisted_gap():
    settings = Settings(
        hourly_rate=100,
        sloc_per_hour=10,
        preset="pair",
        keep_savings=0.5,
        warranty=0.0,
        subscriptions=[],
        hours_override=10,
    )
    result = quote(1000, settings)
    assert result.ai_hours == 10
    assert result.hours_source == "provided"
    assert result.unassisted_hours == pytest.approx(100)
    assert result.blended_labor == pytest.approx(100 * (10 + 0.5 * (100 - 10)))


def test_weeks_override_changes_subscriptions_not_hours():
    settings = Settings(
        hourly_rate=100,
        sloc_per_hour=10,
        preset="classic",
        warranty=0.0,
        subscriptions=[Subscription("Cursor Pro", 20)],
        hours_per_week=10,
        weeks_override=8,
    )
    result = quote(100, settings)
    assert result.ai_hours == pytest.approx(10)
    assert result.calendar_weeks == pytest.approx(8)
    assert result.tooling == pytest.approx(20 * (8 / (52 / 12)))
    assert len(result.schedule) == 8
    assert sum(week.amount for week in result.schedule) == pytest.approx(result.recommended, abs=0.02)


def test_loaded_cost_uses_salary_and_overhead():
    settings = Settings(subscriptions=[], warranty=0, hourly_rate=0, salary=120_000, overhead=2)
    result = quote(1000, settings)
    assert result.classic_person_months == pytest.approx(2.4)
    assert result.classic_hours == pytest.approx(2.4 * 152)
    assert result.classic_loaded == pytest.approx(2.4 * (120_000 * 2 / 12))


def test_reject_keep_savings_above_one():
    with pytest.raises(ValueError):
        quote(10, Settings(keep_savings=1.5))


def test_comparison_matches_the_selected_preset_and_splits_tools():
    settings = Settings(preset="pair", toolchain_monthly=24)
    result = quote(2000, settings)
    columns = {column.key: column for column in result.comparison}
    assert columns["pair"].this_quote
    assert columns["pair"].total == pytest.approx(result.recommended)
    assert columns["vibe"].this_quote is False
    assert columns["vibe"].total < columns["pair"].total
    assert columns["traditional"].hours == pytest.approx(result.classic_hours)
    assert columns["traditional"].labor == pytest.approx(result.classic_at_rate)
    assert columns["traditional"].warranty == 0
    assert columns["traditional"].people == pytest.approx(
        result.classic_person_months / result.classic_schedule_months
    )
    assert columns["traditional"].total == pytest.approx(
        columns["traditional"].labor + columns["traditional"].tools
    )
    assert columns["solo"].labor == pytest.approx(result.unassisted_labor)
    assert columns["solo"].warranty == pytest.approx(result.unassisted_labor * result.warranty_rate)
    assert columns["solo"].tools != columns["pair"].tools
    assert columns["pair"].tools == pytest.approx(result.tooling)
    assert not columns["traditional"].rough
    assert columns["traditional"].thin


def test_traditional_column_is_rough_below_1000_lines():
    small = quote(999, Settings(subscriptions=[]))
    at_boundary = quote(1000, Settings(subscriptions=[]))
    assert small.comparison[0].rough
    assert small.comparison[0].thin
    assert not at_boundary.comparison[0].rough
    assert at_boundary.comparison[0].thin


def test_traditional_column_is_thin_below_10000_lines():
    small_app = quote(9999, Settings(subscriptions=[]))
    at_boundary = quote(10000, Settings(subscriptions=[]))
    assert small_app.comparison[0].thin
    assert not small_app.comparison[0].rough
    assert not at_boundary.comparison[0].thin


def test_fractional_staff_still_buys_one_toolchain_seat():
    result = quote(100, Settings(toolchain_monthly=24, subscriptions=[], hourly_rate=0, warranty=0))
    traditional = result.comparison[0]
    assert traditional.people < 1
    assert traditional.tools == pytest.approx(24 * result.classic_schedule_months)


def test_entered_hours_are_not_labeled_as_the_model_column():
    result = quote(1000, Settings(preset="pair", hours_override=10, subscriptions=[]))
    assert all(not column.this_quote for column in result.comparison)
