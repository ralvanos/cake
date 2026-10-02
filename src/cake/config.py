"""Load cake.toml and turn it into settings."""

from __future__ import annotations

import os
import tomllib
from collections.abc import Mapping
from pathlib import Path

from cake.model import PRESETS, Settings, Subscription

INIT_TEMPLATE = """\
# cake quote settings. Monthly prices use the currency below.
# Edit these to the bills you actually pay. Plan prices change.

[rates]
hourly = 150
hours_per_week = 30
currency = "USD"
# Employer loaded cost in the comparison. This is not the bid.
salary = 140000
overhead = 2.4

[model]
# Finished, accepted lines per focused hour with no AI tools.
sloc_per_hour = 15
# classic | review | pair | vibe
preset = "pair"
# Fraction of the unassisted-vs-AI labor gap to keep on a fixed bid.
# 0.5 bills the midpoint. 0 bills AI time only. 1 bills the unassisted estimate.
keep_savings = 0.5
# Added on top of labor for warranty and leftover fixes.
warranty = 0.15

[subscriptions]
"Cursor Pro" = 20
"Claude Pro" = 20
# "ChatGPT Plus" = 20
# "GitHub Copilot" = 10
# "API usage" = 40

[traditional]
# Per person, per month, comparison only. A stand-in for a paid git host and editor.
# Not a live vendor price. One seat when staffing is under one person.
toolchain_monthly = 24

# Optional multipliers on code lines. 0 drops those lines from the bid.
# A language name changes that language. A suffix prices files cake does not know.
# # lines in a priced suffix count as comments.
# [weights]
# Markdown = 0
# JSON = 0
# ".properties" = 0.05
"""


class ConfigError(ValueError):
    pass


def user_config_path() -> Path:
    """Personal settings. Used when a project has no cake.toml of its own."""
    return config_file_for(os.name, os.environ, Path.home())


def config_file_for(system: str, env: Mapping[str, str], home: Path) -> Path:
    if system == "nt":
        base = env.get("APPDATA")
        root = Path(base) if base else home / "AppData" / "Roaming"
    else:
        base = env.get("XDG_CONFIG_HOME")
        root = Path(base) if base else home / ".config"
    return root / "cake" / "cake.toml"


def find_config(start: Path) -> Path | None:
    current = start if start.is_dir() else start.parent
    current = current.resolve()
    for directory in (current, *current.parents):
        candidate = directory / "cake.toml"
        if candidate.is_file():
            return candidate
    return None


def load_settings(start: Path) -> Settings:
    """Built-in defaults, then the personal file, then the nearest project file."""
    settings = Settings()
    personal = user_config_path()
    if personal.is_file():
        apply_file(settings, personal)
    found = find_config(start)
    if found is not None and found.resolve() != personal.resolve():
        apply_file(settings, found)
    return settings


def load_file(path: Path) -> Settings:
    settings = Settings()
    apply_file(settings, path)
    return settings


def apply_file(settings: Settings, path: Path) -> None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"Could not read {path}: {exc}") from exc
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{path} must be a TOML table.")
    apply_mapping(settings, data, path)


def settings_from_mapping(data: dict, path: Path | None = None) -> Settings:
    settings = Settings()
    apply_mapping(settings, data, path)
    return settings


def apply_mapping(settings: Settings, data: dict, path: Path | None = None) -> None:
    where = str(path) if path is not None else "settings"
    _reject_unknown(data, {"rates", "model", "subscriptions", "traditional", "weights"}, where)
    rates = _table(data.get("rates", {}), f"{where} [rates]")
    model = _table(data.get("model", {}), f"{where} [model]")
    traditional = _table(data.get("traditional", {}), f"{where} [traditional]")
    weights_raw = data.get("weights", None)
    subs_raw = data.get("subscriptions", None)

    _reject_unknown(
        rates,
        {"hourly", "hours_per_week", "currency", "salary", "overhead"},
        f"{where} [rates]",
    )
    _reject_unknown(
        model,
        {"sloc_per_hour", "preset", "keep_savings", "warranty"},
        f"{where} [model]",
    )
    _reject_unknown(traditional, {"toolchain_monthly"}, f"{where} [traditional]")

    if "hourly" in rates:
        settings.hourly_rate = _number(rates["hourly"], "hourly")
    if "hours_per_week" in rates:
        settings.hours_per_week = _number(rates["hours_per_week"], "hours_per_week")
    if "currency" in rates:
        currency = rates["currency"]
        if not isinstance(currency, str) or not currency.strip():
            raise ConfigError("currency must be a non-empty string.")
        settings.currency = currency.strip().upper()
    if "salary" in rates:
        settings.salary = _number(rates["salary"], "salary")
    if "overhead" in rates:
        settings.overhead = _number(rates["overhead"], "overhead")
    if "sloc_per_hour" in model:
        settings.sloc_per_hour = _number(model["sloc_per_hour"], "sloc_per_hour")
    if "preset" in model:
        preset = model["preset"]
        if not isinstance(preset, str) or preset not in PRESETS:
            names = ", ".join(PRESETS)
            raise ConfigError(f"preset must be one of: {names}.")
        settings.preset = preset
    if "keep_savings" in model:
        settings.keep_savings = _number(model["keep_savings"], "keep_savings")
    if "warranty" in model:
        settings.warranty = _number(model["warranty"], "warranty")
    if "toolchain_monthly" in traditional:
        settings.toolchain_monthly = _number(traditional["toolchain_monthly"], "toolchain_monthly")

    if subs_raw is not None:
        subs = _table(subs_raw, f"{where} [subscriptions]")
        parsed: list[Subscription] = []
        for name, monthly in subs.items():
            parsed.append(Subscription(str(name), _number(monthly, f"subscription {name}")))
        settings.subscriptions = parsed

    if weights_raw is not None:
        weights = _table(weights_raw, f"{where} [weights]")
        overrides: dict[str, float] = {}
        for name, weight in weights.items():
            overrides[str(name)] = _number(weight, f"weight {name}")
        settings.weight_overrides = overrides


def write_default_config(directory: Path) -> Path:
    directory = directory.resolve()
    if not directory.is_dir():
        raise ConfigError(f"{directory} is not a directory.")
    target = directory / "cake.toml"
    if target.exists():
        raise ConfigError(f"{target} already exists.")
    target.write_text(INIT_TEMPLATE, encoding="utf-8")
    return target


def write_user_config() -> Path:
    target = user_config_path()
    if target.exists():
        raise ConfigError(f"{target} already exists.")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(INIT_TEMPLATE, encoding="utf-8")
    return target


def _table(value: object, label: str) -> dict:
    if not isinstance(value, dict):
        raise ConfigError(f"{label} must be a table.")
    return value


def _reject_unknown(data: dict, allowed: set[str], label: str) -> None:
    unknown = sorted(set(data) - allowed)
    if unknown:
        names = ", ".join(unknown)
        raise ConfigError(f"Unknown setting in {label}: {names}.")


def _number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"{label} must be a number.")
    return float(value)
