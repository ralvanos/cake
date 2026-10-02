"""Language names, comment styles, and how much a line should influence a bid.

Weights scale code lines into billable lines. Application code counts in full.
Markup counts less. Config counts a little. Docs are shown and not billed,
because a README is not a thousand-line feature.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Language:
    name: str
    category: str
    weight: float
    style: str
    extensions: tuple[str, ...] = ()
    filenames: tuple[str, ...] = ()


LANGUAGES: tuple[Language, ...] = (
    Language("Python", "code", 1.0, "python", (".py", ".pyw")),
    Language("TypeScript", "code", 1.0, "slash", (".ts", ".tsx", ".mts", ".cts")),
    Language("JavaScript", "code", 1.0, "slash", (".js", ".jsx", ".mjs", ".cjs")),
    Language("Vue", "code", 0.75, "html", (".vue",)),
    Language("Svelte", "code", 0.75, "html", (".svelte",)),
    Language("Go", "code", 1.0, "slash", (".go",)),
    Language("Rust", "code", 1.0, "slash", (".rs",)),
    Language("Java", "code", 1.0, "slash", (".java",)),
    Language("Kotlin", "code", 1.0, "slash", (".kt", ".kts")),
    Language("C", "code", 1.0, "slash", (".c", ".h")),
    Language("C++", "code", 1.0, "slash", (".cpp", ".cc", ".cxx", ".hpp", ".hh", ".hxx", ".ipp")),
    Language("C#", "code", 1.0, "slash", (".cs",)),
    Language("F#", "code", 1.0, "slash", (".fs", ".fsx")),
    Language("Swift", "code", 1.0, "slash", (".swift",)),
    Language("Objective-C", "code", 1.0, "slash", (".m", ".mm")),
    Language("Ruby", "code", 1.0, "hash", (".rb", ".rake"), ("gemfile", "rakefile")),
    Language("PHP", "code", 1.0, "slash", (".php",)),
    Language("Scala", "code", 1.0, "slash", (".scala", ".sc")),
    Language("Shell", "code", 1.0, "hash", (".sh", ".bash", ".zsh", ".ps1", ".psm1")),
    Language("Lua", "code", 1.0, "dash", (".lua",)),
    Language("Perl", "code", 1.0, "hash", (".pl", ".pm")),
    Language("R", "code", 1.0, "hash", (".r",)),
    Language("Dart", "code", 1.0, "slash", (".dart",)),
    Language("Elixir", "code", 1.0, "hash", (".ex", ".exs")),
    Language("Erlang", "code", 1.0, "percent", (".erl", ".hrl")),
    Language("Haskell", "code", 1.0, "dash", (".hs", ".lhs")),
    Language("OCaml", "code", 1.0, "ocaml", (".ml", ".mli")),
    Language("Clojure", "code", 1.0, "semi", (".clj", ".cljs", ".cljc")),
    Language("Lisp", "code", 1.0, "semi", (".lisp", ".el")),
    Language("Julia", "code", 1.0, "hash", (".jl",)),
    Language("Zig", "code", 1.0, "slash", (".zig",)),
    Language("Nim", "code", 1.0, "hash", (".nim",)),
    Language("Crystal", "code", 1.0, "hash", (".cr",)),
    Language("Groovy", "code", 1.0, "slash", (".groovy",)),
    Language("Fortran", "code", 1.0, "bang", (".f90", ".f95")),
    Language("CUDA", "code", 1.0, "slash", (".cu", ".cuh")),
    Language("Assembly", "code", 1.0, "semi", (".s", ".asm")),
    Language("SQL", "code", 0.7, "sql", (".sql",)),
    Language("Protobuf", "code", 0.8, "slash", (".proto",)),
    Language("GraphQL", "code", 0.7, "hash", (".graphql", ".gql")),
    Language("Terraform", "code", 0.8, "hashslash", (".tf", ".tfvars")),
    Language("Go module", "code", 0.2, "hash", filenames=("go.mod",)),
    Language("Makefile", "code", 0.5, "hash", (".mk",), ("makefile",)),
    Language("CMake", "code", 0.5, "hash", (".cmake",), ("cmakelists.txt",)),
    Language("Dockerfile", "code", 0.5, "hash", filenames=("dockerfile",)),
    Language("HTML", "markup", 0.4, "html", (".html", ".htm")),
    Language("CSS", "markup", 0.4, "slash", (".css", ".scss", ".sass", ".less")),
    Language("JSON", "data", 0.05, "none", (".json",)),
    Language("JSONC", "data", 0.05, "slash", (".jsonc",)),
    Language("YAML", "data", 0.05, "hash", (".yml", ".yaml")),
    Language("TOML", "data", 0.05, "hash", (".toml",)),
    Language("XML", "data", 0.05, "html", (".xml",)),
    Language("Markdown", "docs", 0.0, "none", (".md", ".markdown", ".mdx")),
    Language("ReStructuredText", "docs", 0.0, "none", (".rst",)),
    Language("AsciiDoc", "docs", 0.0, "none", (".adoc", ".asciidoc")),
    Language("Text", "docs", 0.0, "none", (".txt",), ("license", "copying", "notice")),
)


def _index() -> tuple[dict[str, Language], dict[str, Language]]:
    by_ext: dict[str, Language] = {}
    by_name: dict[str, Language] = {}
    for language in LANGUAGES:
        for ext in language.extensions:
            by_ext[ext.lower()] = language
        for filename in language.filenames:
            by_name[filename.lower()] = language
    return by_ext, by_name


BY_EXT, BY_NAME = _index()


def language_for(path: Path) -> Language | None:
    by_name = BY_NAME.get(path.name.lower())
    if by_name is not None:
        return by_name
    return BY_EXT.get(path.suffix.lower())


def classify_weights(overrides: dict[str, float]) -> tuple[dict[str, float], dict[str, float]]:
    """Split cake.toml weights into known languages and new extensions.

    ``JSON`` and ``.json`` both change the JSON language. ``.properties``
    prices files cake does not already recognize.
    """
    languages: dict[str, float] = {}
    extensions: dict[str, float] = {}
    names = {language.name.lower(): language.name for language in LANGUAGES}
    for raw, weight in overrides.items():
        key = str(raw).strip()
        lowered = key.lower()
        if not lowered or lowered == ".":
            raise ValueError(f"Weight name {raw!r} is empty.")
        if lowered in names:
            languages[names[lowered]] = weight
            continue
        suffix = lowered if lowered.startswith(".") else f".{lowered}"
        known = BY_EXT.get(suffix)
        if known is not None:
            languages[known.name] = weight
            continue
        extensions[suffix] = weight
    return languages, extensions


def weight_target(key: str) -> str:
    languages, extensions = classify_weights({key: 0.0})
    if languages:
        return next(iter(languages))
    return next(iter(extensions))
