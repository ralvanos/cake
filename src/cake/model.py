"""Turn billable lines into hours and a price.

Two hour figures come out of the same tree:

- Unassisted hours are billable lines divided by a focused lines-per-hour rate.
- AI hours divide that by a preset (autocomplete, pairing, or vibe coding).

The fixed bid keeps part of the gap between those two labor numbers, then adds
a warranty reserve and the AI subscriptions for the AI calendar, at cost.

Basic COCOMO organic mode is reported beside that bid. It is the same shape
sloccount uses (person-months = 2.4 × KSLOC^1.05). It prices a full team
lifecycle, so it is a comparison, not the invoice.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace


COCOMO_A = 2.4
COCOMO_B = 1.05
COCOMO_SCHEDULE_C = 2.5
COCOMO_SCHEDULE_D = 0.38
HOURS_PER_PERSON_MONTH = 152
WEEKS_PER_MONTH = 52 / 12
# COCOMO organic was fit to systems of roughly this size and up.
TRADITIONAL_RELIABLE_LINES = 1000
# Below this, the staffed figure is still a large-project formula and runs high.
TRADITIONAL_SMALL_APP_LINES = 10_000
# Planning allowance per person-month of calendar: a paid git host plus a paid editor.
# Not a live vendor price.
DEFAULT_TOOLCHAIN_MONTHLY = 24.0


@dataclass(frozen=True)
class Preset:
    throughput: float
    summary: str


PRESETS: dict[str, Preset] = {
    "classic": Preset(1.0, "No AI tools. You write and revise it yourself."),
    "review": Preset(1.6, "Autocomplete and small suggestions. You still set the structure."),
    "pair": Preset(2.5, "Daily agent pairing. You steer, review, and integrate."),
    "vibe": Preset(4.0, "Agents draft most of the code. You specify, accept, and fix."),
}


@dataclass(frozen=True)
class Subscription:
    name: str
    monthly: float


def default_subscriptions() -> list[Subscription]:
    return [
        Subscription("Cursor Pro", 20.0),
        Subscription("Claude Pro", 20.0),
    ]


@dataclass
class Settings:
    hourly_rate: float = 150.0
    hours_per_week: float = 30.0
    currency: str = "USD"
    salary: float = 140_000.0
    overhead: float = 2.4
    sloc_per_hour: float = 15.0
    preset: str = "pair"
    keep_savings: float = 0.5
    warranty: float = 0.15
    subscriptions: list[Subscription] = field(default_factory=default_subscriptions)
    toolchain_monthly: float = DEFAULT_TOOLCHAIN_MONTHLY
    hours_override: float | None = None
    weeks_override: float | None = None
    weight_overrides: dict[str, float] = field(default_factory=dict)


@dataclass
class SubCharge:
    name: str
    monthly: float
    allocated: float

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "monthly": round(self.monthly, 2),
            "allocated": round(self.allocated, 2),
        }


@dataclass
class WeekCharge:
    week: int
    labor: float
    tooling: float
    amount: float
    cumulative: float

    def to_dict(self) -> dict:
        return {
            "week": self.week,
            "labor": round(self.labor, 2),
            "tooling": round(self.tooling, 2),
            "amount": round(self.amount, 2),
            "cumulative": round(self.cumulative, 2),
        }


@dataclass
class CompareColumn:
    key: str
    label: str
    people: float
    calendar: float
    calendar_unit: str
    hours: float
    labor: float
    tools: float
    warranty: float
    total: float
    rough: bool = False
    thin: bool = False
    this_quote: bool = False

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "people": round(self.people, 4),
            "calendar": round(self.calendar, 4),
            "calendar_unit": self.calendar_unit,
            "hours": round(self.hours, 4),
            "labor": round(self.labor, 2),
            "tools": round(self.tools, 2),
            "warranty": round(self.warranty, 2),
            "total": round(self.total, 2),
            "rough": self.rough,
            "thin": self.thin,
            "this_quote": self.this_quote,
        }


@dataclass
class Quote:
    preset: str
    preset_summary: str
    throughput: float
    effective_sloc: float
    sloc_per_hour: float
    unassisted_hours: float
    estimated_ai_hours: float
    ai_hours: float
    hours_source: str
    calendar_weeks: float
    weeks_source: str
    hours_per_week: float
    hourly_rate: float
    currency: str
    unassisted_labor: float
    ai_labor: float
    savings: float
    keep_savings: float
    savings_kept: float
    savings_shared: float
    blended_labor: float
    warranty_rate: float
    floor_warranty: float
    warranty: float
    subscriptions: list[SubCharge]
    tooling: float
    floor: float
    recommended: float
    classic_ksloc: float
    classic_person_months: float
    classic_hours: float
    classic_schedule_months: float
    classic_at_rate: float
    classic_loaded: float
    salary: float
    overhead: float
    toolchain_monthly: float = DEFAULT_TOOLCHAIN_MONTHLY
    sensitivity: dict[str, float] = field(default_factory=dict)
    schedule: list[WeekCharge] = field(default_factory=list)
    comparison: list[CompareColumn] = field(default_factory=list)

    @property
    def achieved_sloc_per_hour(self) -> float:
        if self.ai_hours <= 0:
            return 0.0
        return self.effective_sloc / self.ai_hours

    def per(self, amount: float, divisor: float) -> float | None:
        if divisor <= 0:
            return None
        return amount / divisor

    def to_dict(self) -> dict:
        def rate(amount: float, divisor: float) -> float | None:
            value = self.per(amount, divisor)
            if value is None:
                return None
            return round(value, 2)

        ksloc = self.effective_sloc / 1000 if self.effective_sloc else 0.0
        return {
            "preset": self.preset,
            "throughput": self.throughput,
            "billable_lines": round(self.effective_sloc, 2),
            "hours": {
                "unassisted": round(self.unassisted_hours, 4),
                "estimated_with_ai": round(self.estimated_ai_hours, 4),
                "used": round(self.ai_hours, 4),
                "source": self.hours_source,
                "lines_per_hour_unassisted": self.sloc_per_hour,
                "lines_per_hour_with_ai": round(self.achieved_sloc_per_hour, 4),
                "calendar_weeks": round(self.calendar_weeks, 4),
                "weeks_source": self.weeks_source,
                "hours_per_week": self.hours_per_week,
            },
            "invoice": {
                "currency": self.currency,
                "hourly_rate": self.hourly_rate,
                "unassisted_labor": round(self.unassisted_labor, 2),
                "ai_labor": round(self.ai_labor, 2),
                "savings": round(self.savings, 2),
                "keep_savings": self.keep_savings,
                "savings_kept": round(self.savings_kept, 2),
                "savings_shared": round(self.savings_shared, 2),
                "blended_labor": round(self.blended_labor, 2),
                "warranty_rate": self.warranty_rate,
                "warranty": round(self.warranty, 2),
                "subscriptions": [item.to_dict() for item in self.subscriptions],
                "tooling": round(self.tooling, 2),
                "floor": round(self.floor, 2),
                "recommended": round(self.recommended, 2),
                "per_hour_floor": rate(self.floor, self.ai_hours),
                "per_hour_recommended": rate(self.recommended, self.ai_hours),
                "per_week_floor": rate(self.floor, self.calendar_weeks),
                "per_week_recommended": rate(self.recommended, self.calendar_weeks),
                "per_ksloc_recommended": rate(self.recommended, ksloc),
            },
            "classic": {
                "ksloc": round(self.classic_ksloc, 4),
                "person_months": round(self.classic_person_months, 4),
                "hours": round(self.classic_hours, 4),
                "schedule_months": round(self.classic_schedule_months, 4),
                "at_rate": round(self.classic_at_rate, 2),
                "loaded": round(self.classic_loaded, 2),
                "salary": self.salary,
                "overhead": self.overhead,
                "toolchain_monthly": self.toolchain_monthly,
            },
            "comparison": [column.to_dict() for column in self.comparison],
            "sensitivity": {name: round(amount, 2) for name, amount in self.sensitivity.items()},
            "schedule": [week.to_dict() for week in self.schedule],
        }


class QuoteError(ValueError):
    pass


def validate(settings: Settings) -> None:
    if settings.preset not in PRESETS:
        names = ", ".join(PRESETS)
        raise QuoteError(f"Unknown preset {settings.preset!r}. Use one of: {names}.")
    if settings.hourly_rate < 0:
        raise QuoteError("Hourly rate cannot be negative.")
    if settings.hours_per_week <= 0:
        raise QuoteError("Hours per week must be greater than zero.")
    if settings.sloc_per_hour <= 0:
        raise QuoteError("Lines per hour must be greater than zero.")
    if not 0 <= settings.keep_savings <= 1:
        raise QuoteError("keep_savings must be between 0 and 1.")
    if not 0 <= settings.warranty <= 1:
        raise QuoteError("Warranty must be between 0 and 1.")
    if settings.salary < 0 or settings.overhead < 0:
        raise QuoteError("Salary and overhead cannot be negative.")
    if settings.toolchain_monthly < 0:
        raise QuoteError("Toolchain cost cannot be negative.")
    if settings.hours_override is not None and settings.hours_override < 0:
        raise QuoteError("Hours cannot be negative.")
    if settings.weeks_override is not None and settings.weeks_override <= 0:
        raise QuoteError("Weeks must be greater than zero.")
    for sub in settings.subscriptions:
        if sub.monthly < 0:
            raise QuoteError(f"Subscription {sub.name!r} cannot be negative.")
    for name, weight in settings.weight_overrides.items():
        if weight < 0:
            raise QuoteError(f"Weight for {name} cannot be negative.")


def cocomo_person_months(ksloc: float) -> float:
    if ksloc <= 0:
        return 0.0
    return COCOMO_A * (ksloc**COCOMO_B)


def cocomo_schedule_months(person_months: float) -> float:
    if person_months <= 0:
        return 0.0
    return COCOMO_SCHEDULE_C * (person_months**COCOMO_SCHEDULE_D)


def quote(effective_sloc: float, settings: Settings) -> Quote:
    validate(settings)
    result = build_quote(effective_sloc, settings)
    if settings.hours_override is None:
        result.sensitivity = {
            name: build_quote(
                effective_sloc,
                replace(settings, preset=name, hours_override=None, weeks_override=None),
            ).recommended
            for name in PRESETS
        }
    result.schedule = engagement_schedule(
        result.recommended,
        result.tooling,
        result.calendar_weeks,
        result.weeks_source,
    )
    result.comparison = comparison_columns(effective_sloc, settings, result)
    return result


def build_quote(effective_sloc: float, settings: Settings) -> Quote:
    preset = PRESETS[settings.preset]
    unassisted_hours = effective_sloc / settings.sloc_per_hour if settings.sloc_per_hour else 0.0
    estimated_ai_hours = unassisted_hours / preset.throughput
    if settings.hours_override is None:
        ai_hours = estimated_ai_hours
        hours_source = "estimated"
    else:
        ai_hours = settings.hours_override
        hours_source = "provided"
    if settings.weeks_override is None:
        calendar_weeks = ai_hours / settings.hours_per_week
        weeks_source = "estimated"
    else:
        calendar_weeks = settings.weeks_override
        weeks_source = "provided"

    rate = settings.hourly_rate
    unassisted_labor = unassisted_hours * rate
    ai_labor = ai_hours * rate
    savings = max(0.0, unassisted_labor - ai_labor)
    savings_kept = savings * settings.keep_savings
    savings_shared = savings - savings_kept
    blended_labor = ai_labor + savings_kept
    floor_warranty = ai_labor * settings.warranty
    warranty = blended_labor * settings.warranty

    months = calendar_weeks / WEEKS_PER_MONTH
    charges = [
        SubCharge(sub.name, sub.monthly, sub.monthly * months) for sub in settings.subscriptions
    ]
    tooling = sum(item.allocated for item in charges)
    floor = ai_labor + floor_warranty + tooling
    recommended = blended_labor + warranty + tooling

    ksloc = effective_sloc / 1000
    person_months = cocomo_person_months(ksloc)
    classic_hours = person_months * HOURS_PER_PERSON_MONTH
    loaded_month = settings.salary * settings.overhead / 12
    return Quote(
        preset=settings.preset,
        preset_summary=preset.summary,
        throughput=preset.throughput,
        effective_sloc=effective_sloc,
        sloc_per_hour=settings.sloc_per_hour,
        unassisted_hours=unassisted_hours,
        estimated_ai_hours=estimated_ai_hours,
        ai_hours=ai_hours,
        hours_source=hours_source,
        calendar_weeks=calendar_weeks,
        weeks_source=weeks_source,
        hours_per_week=settings.hours_per_week,
        hourly_rate=rate,
        currency=settings.currency,
        unassisted_labor=unassisted_labor,
        ai_labor=ai_labor,
        savings=savings,
        keep_savings=settings.keep_savings,
        savings_kept=savings_kept,
        savings_shared=savings_shared,
        blended_labor=blended_labor,
        warranty_rate=settings.warranty,
        floor_warranty=floor_warranty,
        warranty=warranty,
        subscriptions=charges,
        tooling=tooling,
        floor=floor,
        recommended=recommended,
        classic_ksloc=ksloc,
        classic_person_months=person_months,
        classic_hours=classic_hours,
        classic_schedule_months=cocomo_schedule_months(person_months),
        classic_at_rate=classic_hours * rate,
        classic_loaded=person_months * loaded_month,
        salary=settings.salary,
        overhead=settings.overhead,
        toolchain_monthly=settings.toolchain_monthly,
    )


def comparison_columns(
    effective_sloc: float,
    settings: Settings,
    current: Quote,
) -> list[CompareColumn]:
    return [
        _traditional_column(current, settings),
        _solo_column(effective_sloc, settings),
        _ai_column(effective_sloc, settings, "pair", current),
        _ai_column(effective_sloc, settings, "vibe", current),
    ]


def _traditional_column(current: Quote, settings: Settings) -> CompareColumn:
    people = 0.0
    if current.classic_schedule_months > 0:
        people = current.classic_person_months / current.classic_schedule_months
    tools = _toolchain_cost(settings.toolchain_monthly, current.classic_schedule_months, people)
    labor = current.classic_at_rate
    return CompareColumn(
        key="traditional",
        label="Traditional",
        people=people,
        calendar=current.classic_schedule_months,
        calendar_unit="months",
        hours=current.classic_hours,
        labor=labor,
        tools=tools,
        warranty=0.0,
        total=labor + tools,
        rough=current.effective_sloc < TRADITIONAL_RELIABLE_LINES,
        thin=current.effective_sloc < TRADITIONAL_SMALL_APP_LINES,
    )


def _solo_column(effective_sloc: float, settings: Settings) -> CompareColumn:
    hours = effective_sloc / settings.sloc_per_hour if settings.sloc_per_hour else 0.0
    labor = hours * settings.hourly_rate
    warranty = labor * settings.warranty
    weeks = hours / settings.hours_per_week if settings.hours_per_week else 0.0
    people = 1.0 if hours > 0 else 0.0
    tools = _toolchain_cost(settings.toolchain_monthly, weeks / WEEKS_PER_MONTH, people)
    return CompareColumn(
        key="solo",
        label="Solo, no AI",
        people=people,
        calendar=weeks,
        calendar_unit="weeks",
        hours=hours,
        labor=labor,
        tools=tools,
        warranty=warranty,
        total=labor + warranty + tools,
    )


def _ai_column(
    effective_sloc: float,
    settings: Settings,
    preset: str,
    current: Quote,
) -> CompareColumn:
    estimated = build_quote(
        effective_sloc,
        replace(settings, preset=preset, hours_override=None, weeks_override=None),
    )
    this_quote = (
        current.preset == preset
        and current.hours_source == "estimated"
        and current.weeks_source == "estimated"
    )
    people = 1.0 if estimated.ai_hours > 0 else 0.0
    return CompareColumn(
        key=preset,
        label=f"AI {preset}",
        people=people,
        calendar=estimated.calendar_weeks,
        calendar_unit="weeks",
        hours=estimated.ai_hours,
        labor=estimated.blended_labor,
        tools=estimated.tooling,
        warranty=estimated.warranty,
        total=estimated.recommended,
        this_quote=this_quote,
    )


def _toolchain_cost(monthly: float, months: float, people: float) -> float:
    if months <= 0 or people <= 0 or monthly <= 0:
        return 0.0
    seats = people if people >= 1 else 1.0
    return monthly * months * seats


def engagement_schedule(
    recommended: float,
    tooling: float,
    weeks: float,
    weeks_source: str,
) -> list[WeekCharge]:
    if weeks_source != "provided" or abs(weeks - round(weeks)) > 0.01:
        return []
    count = int(round(weeks))
    if not 1 <= count <= 12:
        return []
    recommended_cents = int(round(recommended * 100))
    tooling_cents = min(int(round(tooling * 100)), recommended_cents)
    labor_parts = _split_cents(recommended_cents - tooling_cents, count)
    tool_parts = _split_cents(tooling_cents, count)
    schedule: list[WeekCharge] = []
    cumulative = 0.0
    for index, (labor, tools) in enumerate(zip(labor_parts, tool_parts, strict=True), start=1):
        amount = round(labor + tools, 2)
        cumulative = round(cumulative + amount, 2)
        schedule.append(WeekCharge(index, labor, tools, amount, cumulative))
    return schedule


def _split_cents(cents: int, parts: int) -> list[float]:
    base, remainder = divmod(cents, parts)
    return [(base + (1 if index < remainder else 0)) / 100 for index in range(parts)]
