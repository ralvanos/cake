"""Pretty-print a quote. The numbers come from cake.model."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from cake import __version__
from cake.model import PRESETS, Quote
from cake.scan import Scan, unknown_summary

SYMBOLS = {
    "USD": "$",
    "EUR": "€",
    "GBP": "£",
    "CAD": "CA$",
    "AUD": "A$",
}


def render(
    scan: Scan,
    result: Quote,
    *,
    explain: bool = False,
    plain: bool = False,
    console: Console | None = None,
    warnings: list[str] | None = None,
) -> None:
    out = console or Console(no_color=plain, highlight=False, soft_wrap=False)
    if warnings:
        for warning in warnings:
            out.print(Text(warning, style="yellow"))
        out.print()
    out.print(_header(scan, result))
    out.print()
    out.print(_languages(scan, result))
    out.print()
    out.print(_hours(result))
    out.print(Text(_hour_formula(result), style="dim"))
    pace = _pace_note(result)
    if pace:
        out.print(Text(pace, style="yellow"))
    out.print()
    out.print(_bill(result))
    out.print()
    out.print(_savings(result))
    if result.subscriptions:
        out.print()
        for line in _subscription_lines(result):
            out.print(Text(line, style="dim"))
    out.print()
    out.print(_rates(result))
    out.print(Text(_tm_rate_note(result), style="dim"))
    short = _short_engagement(result)
    if short:
        out.print(Text(short, style="dim"))
    out.print()
    out.print(Text(_advice(result), style="bold"))
    if result.comparison:
        out.print()
        out.print(_comparison(result))
        out.print(Text(_proposal(result)))
        out.print(Text(_comparison_note(result), style="dim"))
    if result.schedule:
        out.print()
        out.print(_schedule(result))
        out.print(Text("Even burn across the weeks you entered. Real work will not land this evenly.", style="dim"))
    if scan.effective_sloc <= 0:
        out.print()
        out.print(
            Text(
                "Nothing billable. Zero-weight files such as Markdown are listed and not priced. "
                "Set a weight in cake.toml if you sell that work.",
                style="yellow",
            )
        )
    if explain:
        out.print()
        out.print(_explain(scan, result))


def payload(scan: Scan, result: Quote) -> dict:
    return {
        "cake": __version__,
        "path": str(scan.root),
        "source": scan.to_dict(),
        "quote": result.to_dict(),
    }


def _header(scan: Scan, result: Quote) -> Panel:
    body = Text()
    body.append("cake ", style="bold")
    body.append(__version__)
    body.append("\n")
    body.append(str(scan.root))
    body.append("\n")
    body.append(f"{result.preset}  ·  {result.preset_summary}")
    body.append("\n")
    body.append(
        f"{_money(result.hourly_rate, result.currency)}/h"
        f"  ·  {result.hours_per_week:g} h/week"
        f"  ·  keep {result.keep_savings:.0%} of the speed savings"
    )
    body.append("\n")
    body.append("Estimated from finished lines, not a timer. Nothing is uploaded.", style="dim")
    return Panel(body, border_style="yellow")


def _table(title: str, *, dim: bool = False) -> Table:
    return Table(
        title=title,
        title_style="dim" if dim else "bold",
        style="dim" if dim else None,
        padding=(0, 1),
    )


def _languages(scan: Scan, result: Quote) -> Table:
    table = _table("Source")
    for heading, align in (
        ("Language", "left"),
        ("Files", "right"),
        ("Code", "right"),
        ("Comment", "right"),
        ("Blank", "right"),
        ("Billable", "right"),
        ("Share", "right"),
    ):
        table.add_column(heading, justify=align)
    total_effective = result.effective_sloc
    files = code = comment = blank = 0
    for lang in scan.languages:
        share = (lang.effective / total_effective) if total_effective else 0.0
        style = "dim" if lang.weight == 0 else None
        table.add_row(
            Text(lang.name, style=style),
            Text(f"{lang.files:,}", style=style),
            Text(f"{lang.code:,}", style=style),
            Text(f"{lang.comment:,}", style=style),
            Text(f"{lang.blank:,}", style=style),
            Text(_lines(lang.effective), style=style),
            Text("—" if total_effective <= 0 else f"{share:.0%}", style=style),
        )
        files += lang.files
        code += lang.code
        comment += lang.comment
        blank += lang.blank
    table.add_section()
    table.add_row(
        "Total",
        f"{files:,}",
        f"{code:,}",
        f"{comment:,}",
        f"{blank:,}",
        _lines(total_effective),
        "100%" if total_effective else "—",
    )
    caption = _skip_caption(scan)
    if caption:
        table.caption = caption
        table.caption_justify = "left"
    return table


def _hours(result: Quote) -> Table:
    table = _table("Hours")
    table.add_column("")
    table.add_column("Unassisted", justify="right")
    ai_heading = "With AI" if result.hours_source == "estimated" else "Entered"
    table.add_column(ai_heading, justify="right")
    table.add_row(
        "Lines / focused hour",
        f"{result.sloc_per_hour:,.1f}",
        f"{result.achieved_sloc_per_hour:,.1f}",
    )
    table.add_row(
        "Hours",
        _hours_cell(result.unassisted_hours),
        _hours_cell(result.ai_hours),
    )
    week_label = f"Weeks at {result.hours_per_week:g} h" if result.weeks_source == "estimated" else "Weeks"
    unassisted_weeks = result.unassisted_hours / result.hours_per_week if result.hours_per_week else 0
    table.add_row(week_label, _weeks_cell(unassisted_weeks), _weeks_cell(result.calendar_weeks))
    return table


def _bill(result: Quote) -> Table:
    table = _table("What to charge")
    table.add_column("Item")
    table.add_column("Time and materials", justify="right")
    table.add_column("Recommended bid", justify="right")
    table.add_row(
        "Labor",
        _money(result.ai_labor, result.currency),
        _money(result.blended_labor, result.currency),
    )
    warranty_label = f"Warranty ({result.warranty_rate:.0%})"
    table.add_row(
        warranty_label,
        _money(result.floor_warranty, result.currency),
        _money(result.warranty, result.currency),
    )
    table.add_row(
        "AI subscriptions",
        _money(result.tooling, result.currency),
        _money(result.tooling, result.currency),
    )
    table.add_section()
    table.add_row(
        Text("Total", style="bold"),
        Text(_money(result.floor, result.currency), style="bold"),
        Text(_money(result.recommended, result.currency), style="bold green"),
    )
    return table


def _rates(result: Quote) -> Table:
    table = _table("Per hour and per week")
    table.add_column("")
    table.add_column("Time and materials", justify="right")
    table.add_column("Recommended bid", justify="right")
    ksloc = result.effective_sloc / 1000
    full_week = result.calendar_weeks >= 1
    rows = (
        ("Per hour", result.ai_hours),
        ("Per week" if full_week else "Weekly run rate", result.calendar_weeks),
        (
            "Per weekday (week ÷ 5)" if full_week else "Weekday run rate",
            result.calendar_weeks * 5 if result.calendar_weeks else 0,
        ),
        ("Per 1,000 billable lines", ksloc),
    )
    for label, divisor in rows:
        floor = result.per(result.floor, divisor)
        bid = result.per(result.recommended, divisor)
        table.add_row(
            label,
            "—" if floor is None else _money(floor, result.currency),
            "—" if bid is None else _money(bid, result.currency),
        )
    return table


def _comparison(result: Quote) -> Table:
    table = _table("Traditional and AI")
    table.add_column("")
    for column in result.comparison:
        heading = column.label + (" · this quote" if column.this_quote else "")
        table.add_column(Text(heading, style="bold" if column.this_quote else None), justify="right")
    rows = (
        ("People", lambda column: _people(column.people)),
        ("Calendar", _calendar_cell),
        ("Hours", lambda column: _hours_cell(column.hours)),
        ("Labor", lambda column: _money(column.labor, result.currency)),
        ("Tools", lambda column: _money(column.tools, result.currency)),
        ("Warranty", lambda column: _money(column.warranty, result.currency)),
        ("Total", lambda column: _money(column.total, result.currency)),
    )
    for label, cell in rows:
        if label == "Total":
            table.add_section()
        style = "bold" if label == "Total" else None
        table.add_row(Text(label, style=style), *[Text(cell(column), style=style) for column in result.comparison])
    return table


def _proposal(result: Quote) -> str:
    traditional = next(column for column in result.comparison if column.key == "traditional")
    currency = result.currency
    opening = (
        f"A traditional lifecycle for this tree is {_money(traditional.total, currency)} "
        f"over {traditional.calendar:.1f} months "
        f"({_people(traditional.people)}, {_hours_cell(traditional.hours)} hours)."
    )
    if result.hours_source == "provided" or result.weeks_source == "provided":
        bid = (
            f"The invoice above is {_money(result.recommended, currency)} "
            "and uses the hours or weeks you entered."
        )
    else:
        bid = f"The {result.preset} bid is {_money(result.recommended, currency)}."
    gap = traditional.total - result.recommended
    if traditional.total <= 0:
        relation = ""
    elif gap > 0.005:
        relation = (
            f" That is {_money(gap, currency)} lower, "
            f"{gap / traditional.total:.0%} under the traditional price."
        )
    elif gap < -0.005:
        relation = f" That is {_money(-gap, currency)} higher than the traditional price."
    else:
        relation = " That matches the traditional price."
    return f"{opening} {bid}{relation}{_traditional_caution(traditional)}"


def _traditional_caution(column) -> str:
    if column.rough:
        return (
            " Traditional is rough below 1,000 billable lines. "
            "This large-project formula runs high on a small tree."
        )
    if column.thin:
        return " Traditional is a large-project formula and runs high below 10,000 billable lines."
    return ""


def _comparison_note(result: Quote) -> str:
    return (
        f"Traditional hours are basic COCOMO, organic: "
        f"2.4 × ({result.classic_ksloc:,.3f} KSLOC)^1.05, then × 152 hours. "
        "Staffing is person-months divided by the schedule. "
        f"That labor is priced at your rate. The employer loaded cost of the same hours is "
        f"{_money(result.classic_loaded, result.currency)} "
        f"({_money(result.salary, result.currency)} salary × {result.overhead:g}). "
        f"Toolchain is {_money(result.toolchain_monthly, result.currency)} per person per month, "
        "with one seat when staffing is under one person. "
        "That column adds no extra warranty, because the lifecycle model already includes rework. "
        "Solo uses the same toolchain and adds the warranty. "
        f"AI pair and AI vibe use the AI subscriptions, add the warranty, and keep "
        f"{result.keep_savings:.0%} of the speed savings."
    )


def _calendar_cell(column) -> str:
    if column.calendar_unit == "months":
        return f"{column.calendar:.1f} mo"
    return f"{_weeks_cell(column.calendar)} wk"


def _people(people: float) -> str:
    if people <= 0:
        return "0"
    nearest = round(people)
    if abs(people - nearest) < 0.05:
        count = int(nearest)
        noun = "person" if count == 1 else "people"
        return f"{count} {noun}"
    return f"{people:.1f} people"


def _schedule(result: Quote) -> Table:
    table = _table("Week by week")
    table.add_column("Week", justify="right")
    table.add_column("Labor and warranty", justify="right")
    table.add_column("Subscriptions", justify="right")
    table.add_column("Bid", justify="right")
    table.add_column("Cumulative", justify="right")
    for week in result.schedule:
        table.add_row(
            str(week.week),
            _money(week.labor, result.currency),
            _money(week.tooling, result.currency),
            _money(week.amount, result.currency),
            _money(week.cumulative, result.currency),
        )
    return table


def _explain(scan: Scan, result: Quote) -> Text:
    lines = [
        "How to read this",
        "",
        "Billable lines are code lines multiplied by a language weight. "
        "Comments and blank lines are shown and not billed. "
        "Docs default to zero. Markup and config count less than application code.",
        "",
        _hour_formula(result),
        "",
        "Presets, as multipliers on the unassisted lines-per-hour rate:",
    ]
    for name, preset in PRESETS.items():
        mark = " (selected)" if name == result.preset else ""
        lines.append(f"  {name} ×{preset.throughput:g}{mark} — {preset.summary}")
    lines.extend(
        [
            "",
            "Time and materials is the hourly contract: AI hours × your rate, plus warranty on that labor, "
            "plus subscriptions for the calendar those hours occupy. "
            "Per hour under that column is the all-in rate. The rate in the header is labor only.",
            "The recommended bid is a fixed price. Bid labor is AI labor plus the share of the "
            "unassisted gap you keep (half, unless you change keep_savings). Warranty is charged on "
            "that blended labor. Subscriptions are not marked up.",
            "Traditional in the comparison table is a staffed lifecycle, basic COCOMO organic. "
            "Solo, no AI is one person at the unassisted rate. The classic preset is that solo case. "
            "It is not the traditional column.",
            "",
            "Not in either number: meetings, product management, visual design, hosting, "
            "app-store fees, and on-call. Raise the hours, the warranty, or the rate when the "
            "engagement includes them.",
            "",
            "Comment detection is approximate. Python triple-quoted strings, including docstrings, "
            "count as code. An extension priced in cake.toml is listed under that suffix. "
            "# lines in that file count as comments. Dependency and build directories are skipped, "
            "along with lockfiles, minified bundles, and signing files such as .keystore.",
        ]
    )
    if result.sensitivity:
        lines.extend(["", _sensitivity(result)])
    lines.extend(["", "Language weights used in this scan:"])
    if scan.languages:
        for lang in scan.languages:
            lines.append(f"  {lang.name}: ×{lang.weight:g} ({lang.category})")
    else:
        lines.append("  (no recognized files)")
    if scan.stats.unknown:
        lines.append("")
        lines.append(f"Unrecognized files: {scan.stats.unknown}.")
        summary = unknown_summary(scan.stats)
        if summary:
            lines.append(f"  {summary}")
    if scan.stats.hidden:
        lines.append(f"Hidden files skipped: {scan.stats.hidden}.")
    return Text("\n".join(lines))


def _pace_note(result: Quote) -> str | None:
    if result.hours_source != "provided" or result.weeks_source != "provided":
        return None
    if result.calendar_weeks <= 0 or result.hours_per_week <= 0:
        return None
    pace = result.ai_hours / result.calendar_weeks
    if abs(pace - result.hours_per_week) / result.hours_per_week <= 0.2:
        return None
    return (
        f"Those hours over those weeks are {pace:,.1f} h/week, "
        f"not the {result.hours_per_week:g} h/week in settings. Subscriptions use the weeks you entered."
    )


def _hour_formula(result: Quote) -> str:
    estimated = (
        f"{_lines(result.effective_sloc)} billable lines ÷ {result.sloc_per_hour:g} per hour "
        f"= {_hours_cell(result.unassisted_hours)} unassisted hours ÷ {result.throughput:g} "
        f"({result.preset}) = {_hours_cell(result.estimated_ai_hours)} AI hours"
    )
    if result.hours_source == "provided":
        return f"{estimated}. The bill uses the {_hours_cell(result.ai_hours)} hours you entered."
    if result.weeks_source == "provided":
        return (
            f"{estimated}. Subscriptions use the {_hours_cell(result.calendar_weeks)} weeks you entered."
        )
    return estimated + "."


def _savings(result: Quote) -> Text:
    currency = result.currency
    if result.ai_labor > result.unassisted_labor + 0.005:
        return Text(
            "Those hours cost more than the unassisted estimate, so there is no speed savings to split. "
            "The bid is the hours you entered, plus warranty, plus subscriptions."
        )
    if result.savings <= 0.005:
        return Text(
            "AI labor matches the unassisted estimate, so the bid is time plus warranty plus subscriptions."
        )
    text = Text()
    text.append("Unassisted labor would be ")
    text.append(_money(result.unassisted_labor, currency), style="bold")
    text.append(". AI labor is ")
    text.append(_money(result.ai_labor, currency), style="bold")
    text.append(". Of the ")
    text.append(_money(result.savings, currency), style="bold")
    text.append(" difference, this bid keeps ")
    text.append(_money(result.savings_kept, currency), style="bold")
    text.append(" and the client keeps ")
    text.append(_money(result.savings_shared, currency), style="bold")
    text.append(".")
    return text


def _subscription_lines(result: Quote) -> list[str]:
    months = result.calendar_weeks / (52 / 12) if result.calendar_weeks else 0.0
    lines = [
        f"Subscriptions cover {months:,.2f} months ({_weeks_cell(result.calendar_weeks)} weeks), at cost:"
    ]
    for item in result.subscriptions:
        lines.append(
            f"  {item.name}  {_money(item.monthly, result.currency)}/mo  →  "
            f"{_money(item.allocated, result.currency)}"
        )
    return lines


def _advice(result: Quote) -> str:
    if abs(result.recommended - result.floor) < 0.01:
        return "Recommended matches the time-and-materials total. That is the number to send."
    return (
        "Send the recommended bid as a fixed price. "
        "Use the time-and-materials total if the contract is hourly."
    )


def _tm_rate_note(result: Quote) -> str:
    labor = f"{_money(result.hourly_rate, result.currency)}/h"
    per_hour = result.per(result.floor, result.ai_hours)
    if per_hour is None:
        return f"The header rate, {labor}, is labor only."
    return (
        f"Time and materials per hour is {_money(per_hour, result.currency)}/h: "
        f"labor, warranty, and subscriptions. The header rate, {labor}, is labor only."
    )


def _sensitivity(result: Quote) -> str:
    parts = []
    for name, amount in result.sensitivity.items():
        label = _money(amount, result.currency)
        if name == result.preset:
            label = f"{label} (this quote)"
        parts.append(f"{name} {label}")
    return "Same rules, other presets: " + "  ·  ".join(parts)


def _skip_caption(scan: Scan) -> str:
    stats = scan.stats
    parts = []
    if stats.pruned_dirs:
        parts.append(f"pruned {stats.pruned_dirs} dependency or build dirs")
    if stats.generated:
        parts.append(f"skipped {stats.generated} generated")
    if stats.binary:
        parts.append(f"skipped {stats.binary} binary")
    if stats.large:
        parts.append(f"skipped {stats.large} large")
    if stats.unknown:
        summary = unknown_summary(stats)
        label = f"{stats.unknown} unrecognized"
        if summary:
            label = f"{label}: {summary}"
        parts.append(label)
    return " · ".join(parts)


def _short_engagement(result: Quote) -> str | None:
    if not 0 < result.calendar_weeks < 1:
        return None
    return (
        f"This is {_hours_cell(result.ai_hours)} hours, under a week "
        f"({_weeks_cell(result.calendar_weeks)} wk). "
        "Weekly figures are the run rate for a full week at this pace, not a second invoice."
    )


def _money(amount: float, currency: str) -> str:
    symbol = SYMBOLS.get(currency, f"{currency} ")
    sign = "-" if amount < 0 else ""
    magnitude = abs(amount)
    if magnitude >= 100 and abs(magnitude - round(magnitude)) < 0.005:
        return f"{sign}{symbol}{magnitude:,.0f}"
    return f"{sign}{symbol}{magnitude:,.2f}"


def _hours_cell(value: float) -> str:
    return f"{value:,.1f}"


def _weeks_cell(value: float) -> str:
    if abs(value) >= 10:
        return f"{value:,.1f}"
    return f"{value:,.2f}"


def _lines(value: float) -> str:
    if abs(value - round(value)) < 0.05:
        return f"{round(value):,}"
    return f"{value:,.1f}"
