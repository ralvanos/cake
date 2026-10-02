"""Command line for cake."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from rich.console import Console
from rich.text import Text

from cake import __version__
from cake.config import (
    ConfigError,
    load_file,
    load_settings,
    write_default_config,
    write_user_config,
)
from cake.languages import classify_weights, weight_target
from cake.model import PRESETS, Settings, Subscription, quote
from cake.report import payload, render
from cake.scan import scan_path, with_weights


def main(argv: list[str] | None = None) -> int:
    _utf8()
    parser = _parser()
    args = parser.parse_args(argv)
    err = Console(stderr=True, highlight=False)
    try:
        if args.path == "help":
            parser.print_help()
            return 0
        if args.user and not (args.init or args.path == "init"):
            err.print(Text("--user is only used with init."))
            return 2
        if args.init or args.path == "init":
            if args.user:
                target = write_user_config()
            else:
                directory = Path.cwd() if args.path in (None, "init") else Path(args.path)
                target = write_default_config(directory)
            err.print(Text(f"Wrote {target}"))
            return 0
        if args.path is None:
            err.print(Text("Pass the file or directory to scan."))
            parser.print_help()
            return 2
        path = Path(args.path)
        if not path.exists():
            err.print(Text(f"No such path: {path}"))
            return 2
        settings = _settings(path, args)
        language_weights, extension_weights = classify_weights(settings.weight_overrides)
        scan = scan_path(path, max_bytes=args.max_bytes, extension_weights=extension_weights)
        scan = with_weights(scan, language_weights)
        present = {lang.name.lower() for lang in scan.languages}
        missing = sorted(
            name for name in settings.weight_overrides if weight_target(name).lower() not in present
        )
        result = quote(scan.effective_sloc, settings)
    except (ConfigError, OSError, ValueError) as exc:
        err.print(Text(str(exc)))
        return 2

    warnings = [f"No files used the weight override for {name}." for name in missing]
    if args.json:
        for warning in warnings:
            err.print(Text(warning))
        print(json.dumps(payload(scan, result), indent=2))
        return 0
    render(scan, result, explain=args.explain, plain=args.plain, warnings=warnings)
    return 0


def _settings(path: Path, args: argparse.Namespace) -> Settings:
    if args.no_config:
        settings = Settings()
    elif args.config is not None:
        config = Path(args.config)
        if not config.is_file():
            raise ConfigError(f"No config file at {config}.")
        settings = load_file(config)
    else:
        settings = load_settings(path)

    if args.rate is not None:
        settings.hourly_rate = args.rate
    if args.hours_per_week is not None:
        settings.hours_per_week = args.hours_per_week
    if args.preset is not None:
        settings.preset = args.preset
    if args.keep is not None:
        settings.keep_savings = args.keep
    if args.warranty is not None:
        settings.warranty = args.warranty
    if args.sloc_per_hour is not None:
        settings.sloc_per_hour = args.sloc_per_hour
    if args.hours is not None:
        settings.hours_override = args.hours
    if args.weeks is not None:
        settings.weeks_override = args.weeks
    if args.salary is not None:
        settings.salary = args.salary
    if args.overhead is not None:
        settings.overhead = args.overhead
    if args.toolchain is not None:
        settings.toolchain_monthly = args.toolchain
    if args.currency is not None:
        settings.currency = args.currency.strip().upper()
    if args.no_subs:
        settings.subscriptions = []
    if args.sub:
        by_name = {item.name: item for item in settings.subscriptions}
        for raw in args.sub:
            parsed = _parse_sub(raw)
            by_name[parsed.name] = parsed
        settings.subscriptions = list(by_name.values())
    return settings


def _parse_sub(raw: str) -> Subscription:
    if "=" not in raw:
        raise ConfigError('--sub must look like "Cursor Pro=20".')
    name, value = raw.rsplit("=", 1)
    name = name.strip().strip('"')
    if not name:
        raise ConfigError("--sub needs a name before '='.")
    token = value.strip().lstrip("$").replace(",", "")
    try:
        monthly = float(token)
    except ValueError as exc:
        raise ConfigError(f"Could not read a price from {raw!r}.") from exc
    if monthly < 0:
        raise ConfigError(f"Subscription {name!r} cannot be negative.")
    return Subscription(name, monthly)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cake",
        description=(
            "Scan source code and print a time-and-materials total, a fixed bid, "
            "and a traditional-versus-AI comparison. Reads files only. Uploads nothing.\n"
            "Written by ralvanos."
        ),
        epilog=(
            "examples:\n"
            "  cake .\n"
            "  cake examples/sample --rate 175 --preset vibe\n"
            "  cake examples/sample --hours 80 --weeks 3\n"
            "  cake help\n"
            "  cake init\n"
            "  cake init --user\n"
            "\n"
            "Paths use the form of the system you are on, such as\n"
            "E:\\Projects\\app or /home/me/app. Forward slashes also work on Windows.\n"
            "\n"
            "Questions, ideas, or bug reports are welcome.\n"
            "Email ralvanos@protonmail.com, or contribute at\n"
            "https://github.com/ralvanos/cake\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=None,
        help=(
            "File or directory to scan. Required. "
            "Pass . to scan the current directory. "
            "'help' prints this text. 'init' writes cake.toml in the project. "
            "'init --user' writes your personal settings file."
        ),
    )
    parser.add_argument(
        "--init",
        action="store_true",
        help="Write cake.toml in the path and exit. Does not edit source files. With --user, write the personal file instead.",
    )
    parser.add_argument(
        "--user",
        action="store_true",
        help=(
            "With init, write the personal settings file. "
            "Windows: %%APPDATA%%\\cake\\cake.toml. "
            "Linux and macOS: ~/.config/cake/cake.toml."
        ),
    )
    quote_args = parser.add_argument_group("quote")
    quote_args.add_argument("--rate", type=float, help="Hourly rate you charge. Default: 150.")
    quote_args.add_argument("--hours-per-week", type=float, help="Focused hours in a week. Default: 30.")
    quote_args.add_argument(
        "--preset",
        choices=list(PRESETS),
        help="Quote speed: classic (1x, solo, no AI), review (1.6x), pair (2.5x, default), vibe (4x). The comparison table still shows solo, pair, and vibe.",
    )
    quote_args.add_argument(
        "--keep",
        type=float,
        help="Fraction of the unassisted-vs-AI labor savings to keep on the fixed bid, from 0 to 1. Default: 0.5.",
    )
    quote_args.add_argument("--warranty", type=float, help="Warranty reserve as a fraction of bid labor. Default: 0.15. Not added again on the traditional column.")
    quote_args.add_argument("--sloc-per-hour", type=float, help="Finished lines per unassisted focused hour. Default: 15.")
    quote_args.add_argument("--hours", type=float, help="Use these hours for the invoice instead of the estimate from lines.")
    quote_args.add_argument("--weeks", type=float, help="Calendar weeks for subscription proration and the weekly rate.")
    quote_args.add_argument("--currency", help="Currency code, such as USD, EUR, or GBP. Default: USD.")
    quote_args.add_argument(
        "--sub",
        action="append",
        default=[],
        metavar="NAME=MONTHLY",
        help='Add or replace a monthly AI subscription, for example --sub "API usage=40".',
    )
    quote_args.add_argument("--no-subs", action="store_true", help="Drop AI subscription costs from the quote.")
    traditional = parser.add_argument_group("traditional comparison")
    traditional.add_argument("--salary", type=float, help="Annual salary for the employer loaded cost. Default: 140000. Not the bid.")
    traditional.add_argument("--overhead", type=float, help="Multiplier on that salary. Default: 2.4.")
    traditional.add_argument(
        "--toolchain",
        type=float,
        help="Traditional toolchain per person per month. Default: 24. Comparison only. One seat when staffing is under one person.",
    )
    output = parser.add_argument_group("output")
    output.add_argument(
        "--config",
        help="Use this cake.toml and skip the project file and the personal file.",
    )
    output.add_argument(
        "--no-config",
        action="store_true",
        help="Ignore the project file and the personal file. Use built-in defaults.",
    )
    output.add_argument("--max-bytes", type=int, default=1_000_000, help="Skip files larger than this many bytes. Default: 1000000.")
    output.add_argument("--json", action="store_true", help="Print the quote as JSON.")
    output.add_argument("--explain", action="store_true", help="Print how the hours, the bid, and the comparison were chosen.")
    output.add_argument("--plain", action="store_true", help="Print without color.")
    output.add_argument("--version", action="version", version=f"cake {__version__}")
    return parser


def _utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass

