from pathlib import Path

import pytest

from cake.config import (
    INIT_TEMPLATE,
    ConfigError,
    config_file_for,
    load_file,
    load_settings,
    write_default_config,
    write_user_config,
)


def test_load_replaces_subscriptions_and_reads_rates(tmp_path: Path):
    path = tmp_path / "cake.toml"
    path.write_text(
        """
[rates]
hourly = 175
currency = "eur"

[model]
preset = "vibe"
keep_savings = 0.25

[subscriptions]
"Cursor Pro" = 60

[traditional]
toolchain_monthly = 10

[weights]
JSON = 0
""",
        encoding="utf-8",
    )
    settings = load_file(path)
    assert settings.hourly_rate == 175
    assert settings.currency == "EUR"
    assert settings.preset == "vibe"
    assert settings.keep_savings == 0.25
    assert settings.toolchain_monthly == 10
    assert [(item.name, item.monthly) for item in settings.subscriptions] == [("Cursor Pro", 60)]
    assert settings.weight_overrides == {"JSON": 0}


def test_unknown_key_is_rejected(tmp_path: Path):
    path = tmp_path / "cake.toml"
    path.write_text("[rates]\nhourlyy = 10\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="hourlyy"):
        load_file(path)


def test_example_file_matches_init_template():
    example = Path(__file__).resolve().parents[1] / "cake.toml.example"
    assert example.read_text(encoding="utf-8") == INIT_TEMPLATE


def test_init_writes_once(tmp_path: Path):
    target = write_default_config(tmp_path)
    assert target.name == "cake.toml"
    assert "keep_savings" in target.read_text(encoding="utf-8")
    with pytest.raises(ConfigError, match="already exists"):
        write_default_config(tmp_path)


def test_personal_file_location(tmp_path: Path):
    appdata = tmp_path / "Roaming"
    assert config_file_for("nt", {"APPDATA": str(appdata)}, tmp_path) == appdata / "cake" / "cake.toml"
    assert (
        config_file_for("nt", {}, tmp_path)
        == tmp_path / "AppData" / "Roaming" / "cake" / "cake.toml"
    )
    assert (
        config_file_for("posix", {}, tmp_path)
        == tmp_path / ".config" / "cake" / "cake.toml"
    )
    config_home = tmp_path / "cfg"
    assert (
        config_file_for("posix", {"XDG_CONFIG_HOME": str(config_home)}, tmp_path)
        == config_home / "cake" / "cake.toml"
    )


def test_project_file_overrides_personal_keys_only(tmp_path: Path, monkeypatch):
    personal = tmp_path / "personal" / "cake.toml"
    personal.parent.mkdir()
    personal.write_text(
        """
[rates]
hourly = 200

[model]
preset = "vibe"

[subscriptions]
"Cursor Pro" = 60
""",
        encoding="utf-8",
    )
    monkeypatch.setattr("cake.config.user_config_path", lambda: personal)
    project = tmp_path / "app"
    project.mkdir()
    (project / "cake.toml").write_text("[rates]\nhourly = 175\n", encoding="utf-8")
    settings = load_settings(project)
    assert settings.hourly_rate == 175
    assert settings.preset == "vibe"
    assert [(item.name, item.monthly) for item in settings.subscriptions] == [("Cursor Pro", 60)]


def test_init_user_writes_personal_file_once(tmp_path: Path, monkeypatch):
    target = tmp_path / "config" / "cake" / "cake.toml"
    monkeypatch.setattr("cake.config.user_config_path", lambda: target)
    written = write_user_config()
    assert written == target
    assert written.read_text(encoding="utf-8") == INIT_TEMPLATE
    with pytest.raises(ConfigError, match="already exists"):
        write_user_config()
