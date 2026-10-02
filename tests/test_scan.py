from pathlib import Path

from cake.scan import scan_path, with_weights


def test_scan_counts_code_and_skips_dependencies(tmp_path: Path):
    source = tmp_path / "src"
    source.mkdir()
    (source / "app.py").write_text("x = 1\ny = 2\n# c\n\n", encoding="utf-8")
    modules = tmp_path / "node_modules"
    modules.mkdir()
    (modules / "dep.py").write_text("print('nope')\n", encoding="utf-8")
    (tmp_path / "package-lock.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Hi\n\nBody\n", encoding="utf-8")
    (tmp_path / "logo.png").write_bytes(b"\x89PNG\r\n")
    (tmp_path / "notes.xyz").write_text("mystery\n", encoding="utf-8")

    scan = scan_path(tmp_path)
    by_name = {lang.name: lang for lang in scan.languages}
    assert by_name["Python"].code == 2
    assert by_name["Python"].comment == 1
    assert by_name["Python"].blank == 1
    assert by_name["Python"].effective == 2
    assert by_name["Markdown"].code == 2
    assert by_name["Markdown"].effective == 0
    assert scan.effective_sloc == 2
    assert scan.stats.pruned_dirs == 1
    assert scan.stats.generated == 1
    assert scan.stats.binary == 1
    assert scan.stats.unknown == 1


def test_weight_override_is_case_insensitive(tmp_path: Path):
    (tmp_path / "README.md").write_text("hello\n", encoding="utf-8")
    scan = with_weights(scan_path(tmp_path), {"markdown": 1})
    assert scan.languages[0].weight == 1
    assert scan.effective_sloc == 1


def test_uppercase_extension_crlf_and_mixed_case_deps(tmp_path: Path):
    (tmp_path / "APP.PY").write_bytes(b"x = 1\r\ny = 2\r\n")
    (tmp_path / "Makefile").write_text("all:\n\t@true\n", encoding="utf-8")
    modules = tmp_path / "Node_Modules"
    modules.mkdir()
    (modules / "skip.py").write_text("z = 1\n", encoding="utf-8")

    scan = scan_path(tmp_path)
    by_name = {lang.name: lang for lang in scan.languages}
    assert by_name["Python"].code == 2
    assert by_name["Makefile"].code == 2
    assert scan.stats.pruned_dirs == 1


def test_extension_weight_prices_unknown_suffix_and_keystore_is_binary(tmp_path: Path):
    (tmp_path / "app.properties").write_text("a=1\n# c\n\n", encoding="utf-8")
    (tmp_path / "secret.keystore").write_bytes(b"not a source file")
    (tmp_path / "notes.xyz").write_text("mystery\n", encoding="utf-8")

    scan = scan_path(tmp_path, extension_weights={".properties": 0.5})
    by_name = {lang.name: lang for lang in scan.languages}
    assert by_name[".properties"].code == 1
    assert by_name[".properties"].comment == 1
    assert by_name[".properties"].effective == 0.5
    assert scan.stats.binary == 1
    assert scan.stats.unknown == 1
    assert scan.stats.unknown_extensions == {".xyz": 1}


def test_large_files_are_skipped(tmp_path: Path):
    (tmp_path / "big.py").write_text("x = 1\n" * 50, encoding="utf-8")
    scan = scan_path(tmp_path, max_bytes=20)
    assert scan.languages == []
    assert scan.stats.large == 1
