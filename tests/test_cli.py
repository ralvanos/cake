import json
from pathlib import Path

import pytest

from cake.cli import main


def test_json_quote_for_a_small_tree(tmp_path: Path, capsys):
    (tmp_path / "a.py").write_text("x = 1\ny = 2\n# c\n\n", encoding="utf-8")
    code = main(
        [
            "--json",
            "--no-config",
            "--no-subs",
            "--preset",
            "classic",
            "--rate",
            "100",
            "--warranty",
            "0.15",
            "--sloc-per-hour",
            "15",
            str(tmp_path),
        ]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    python = payload["source"]["languages"][0]
    assert python["language"] == "Python"
    assert python["code"] == 2
    assert payload["quote"]["hours"]["used"] == payload["quote"]["hours"]["unassisted"]
    assert payload["quote"]["invoice"]["recommended"] > 0


def test_entered_hours_above_the_estimate_do_not_invent_savings(tmp_path: Path, capsys):
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    code = main(
        ["--plain", "--no-config", "--no-subs", "--hours", "40", str(tmp_path)]
    )
    assert code == 0
    output = capsys.readouterr().out.replace("\n", " ")
    assert "no speed savings to split" in output
    assert "Time and materials per hour is" in output


def test_help_lists_the_options(capsys):
    with pytest.raises(SystemExit) as caught:
        main(["--help"])
    assert caught.value.code == 0
    text = capsys.readouterr().out
    for flag in (
        "--rate",
        "--preset",
        "--hours",
        "--weeks",
        "--keep",
        "--warranty",
        "--toolchain",
        "--sub",
        "--json",
        "--explain",
        "--init",
        "--user",
        "Written by ralvanos.",
        "ralvanos@protonmail.com",
        "https://github.com/ralvanos/cake",
    ):
        assert flag in text


def test_help_command_lists_the_options(capsys):
    assert main(["help"]) == 0
    assert "--toolchain" in capsys.readouterr().out


def test_no_path_prints_an_error_and_help(capsys):
    assert main([]) == 2
    captured = capsys.readouterr()
    assert "Pass the file or directory to scan." in captured.err
    assert "--rate" in captured.out
    assert "examples:" in captured.out


def test_missing_path_returns_2(tmp_path: Path, capsys):
    missing = tmp_path / "nope"
    assert main(["--no-config", str(missing)]) == 2
    assert "No such path" in capsys.readouterr().err


def test_init_command_writes_config(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert main(["init"]) == 0
    assert (tmp_path / "cake.toml").is_file()
    captured = capsys.readouterr()
    assert "Wrote" in captured.err


def test_settings_order_is_flag_then_project_then_personal(tmp_path: Path, monkeypatch, capsys):
    personal = tmp_path / "personal" / "cake.toml"
    personal.parent.mkdir()
    personal.write_text(
        """
[rates]
hourly = 200

[model]
preset = "vibe"

[subscriptions]
""",
        encoding="utf-8",
    )
    monkeypatch.setattr("cake.config.user_config_path", lambda: personal)
    project = tmp_path / "app"
    project.mkdir()
    (project / "a.py").write_text("x = 1\n", encoding="utf-8")

    assert main(["--json", str(project)]) == 0
    first = json.loads(capsys.readouterr().out)
    assert first["quote"]["invoice"]["hourly_rate"] == 200
    assert first["quote"]["preset"] == "vibe"
    assert first["quote"]["invoice"]["subscriptions"] == []

    (project / "cake.toml").write_text("[rates]\nhourly = 180\n", encoding="utf-8")
    assert main(["--json", str(project)]) == 0
    second = json.loads(capsys.readouterr().out)
    assert second["quote"]["invoice"]["hourly_rate"] == 180
    assert second["quote"]["preset"] == "vibe"

    assert main(["--json", "--rate", "150", str(project)]) == 0
    third = json.loads(capsys.readouterr().out)
    assert third["quote"]["invoice"]["hourly_rate"] == 150
    assert third["quote"]["preset"] == "vibe"


def test_no_config_and_explicit_config_skip_the_personal_file(tmp_path: Path, monkeypatch, capsys):
    personal = tmp_path / "personal" / "cake.toml"
    personal.parent.mkdir()
    personal.write_text('[rates]\nhourly = 200\n[model]\npreset = "vibe"\n', encoding="utf-8")
    monkeypatch.setattr("cake.config.user_config_path", lambda: personal)
    project = tmp_path / "app"
    project.mkdir()
    (project / "a.py").write_text("x = 1\n", encoding="utf-8")
    explicit = tmp_path / "only.toml"
    explicit.write_text("[rates]\nhourly = 90\n", encoding="utf-8")

    assert main(["--json", "--no-config", str(project)]) == 0
    skipped = json.loads(capsys.readouterr().out)
    assert skipped["quote"]["invoice"]["hourly_rate"] == 150
    assert skipped["quote"]["preset"] == "pair"

    assert main(["--json", "--config", str(explicit), str(project)]) == 0
    chosen = json.loads(capsys.readouterr().out)
    assert chosen["quote"]["invoice"]["hourly_rate"] == 90
    assert chosen["quote"]["preset"] == "pair"


def test_init_user_command(tmp_path: Path, monkeypatch, capsys):
    target = tmp_path / "config" / "cake" / "cake.toml"
    monkeypatch.setattr("cake.config.user_config_path", lambda: target)
    assert main(["init", "--user"]) == 0
    assert target.is_file()
    assert "Wrote" in capsys.readouterr().err
    assert main(["init", "--user"]) == 2
    assert "already exists" in capsys.readouterr().err


def test_report_lists_unrecognized_suffixes_and_marks_a_small_traditional_column(
    tmp_path: Path, capsys
):
    (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "app.properties").write_text("a=1\n", encoding="utf-8")
    (tmp_path / "secret.keystore").write_bytes(b"key")
    assert main(["--plain", "--no-config", "--no-subs", str(tmp_path)]) == 0
    output = capsys.readouterr().out
    assert ".properties (1)" in output
    assert "keystore" not in output.lower()
    assert "rough below 1,000 billable lines" in output
    assert "runs high on a small tree" in output


def test_extension_weight_from_config_is_billed(tmp_path: Path, capsys):
    (tmp_path / "app.properties").write_text("a=1\n# c\n", encoding="utf-8")
    config = tmp_path / "rates.toml"
    config.write_text('[weights]\n".properties" = 0.5\n[subscriptions]\n', encoding="utf-8")
    assert main(["--plain", "--config", str(config), str(tmp_path)]) == 0
    output = capsys.readouterr().out
    assert ".properties" in output
    assert "unrecognized" not in output


def test_midsize_tree_says_the_traditional_formula_runs_high(tmp_path: Path, capsys):
    (tmp_path / "a.py").write_text("x = 1\n" * 1000, encoding="utf-8")
    assert main(["--plain", "--no-config", "--no-subs", str(tmp_path)]) == 0
    output = " ".join(capsys.readouterr().out.split())
    assert "runs high below 10,000 billable lines" in output
    assert "rough below 1,000" not in output


def test_user_flag_without_init_is_rejected(tmp_path: Path, capsys):
    assert main(["--user", str(tmp_path)]) == 2
    assert "--user is only used with init" in capsys.readouterr().err
