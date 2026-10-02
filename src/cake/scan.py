"""Walk a tree and total physical source lines by language."""

from __future__ import annotations

import os
from collections import Counter
from dataclasses import dataclass, field, replace
from pathlib import Path

from cake.count import LineCounts, count_text
from cake.languages import Language, language_for

SKIP_DIRS = frozenset(
    {
        ".git",
        ".svn",
        ".hg",
        ".venv",
        "venv",
        "virtualenv",
        "node_modules",
        "bower_components",
        "jspm_packages",
        "vendor",
        "third_party",
        "site-packages",
        "dist",
        "build",
        "out",
        "target",
        "coverage",
        "htmlcov",
        ".next",
        ".nuxt",
        ".turbo",
        ".parcel-cache",
        ".cache",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".tox",
        ".gradle",
        ".idea",
        "pods",
        "obj",
    }
)

BINARY_EXTENSIONS = frozenset(
    {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".ico",
        ".bmp",
        ".pdf",
        ".zip",
        ".gz",
        ".tgz",
        ".bz2",
        ".7z",
        ".rar",
        ".woff",
        ".woff2",
        ".ttf",
        ".eot",
        ".otf",
        ".mp3",
        ".mp4",
        ".mov",
        ".wav",
        ".exe",
        ".dll",
        ".so",
        ".dylib",
        ".class",
        ".jar",
        ".war",
        ".pyc",
        ".pyo",
        ".wasm",
        ".db",
        ".sqlite",
        ".sqlite3",
        ".bin",
        ".o",
        ".a",
        ".lib",
        ".pdb",
        ".svg",
        ".keystore",
        ".jks",
    }
)

GENERATED_NAMES = frozenset(
    {
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "bun.lock",
        "cargo.lock",
        "composer.lock",
        "gemfile.lock",
        "poetry.lock",
        "packages.lock.json",
        "go.sum",
        "shrinkwrap.json",
    }
)

GENERATED_SUFFIXES = (
    ".min.js",
    ".min.css",
    ".min.mjs",
    ".pb.go",
    ".pb.cc",
    ".pb.h",
    ".generated.cs",
    ".designer.cs",
    ".lock",
)

DEFAULT_MAX_BYTES = 1_000_000


@dataclass
class LanguageTotal:
    name: str
    category: str
    weight: float
    files: int = 0
    code: int = 0
    comment: int = 0
    blank: int = 0

    @property
    def effective(self) -> float:
        return self.code * self.weight

    def to_dict(self) -> dict:
        return {
            "language": self.name,
            "category": self.category,
            "weight": self.weight,
            "files": self.files,
            "code": self.code,
            "comment": self.comment,
            "blank": self.blank,
            "billable": round(self.effective, 2),
        }


@dataclass
class ScanStats:
    generated: int = 0
    binary: int = 0
    large: int = 0
    unknown: int = 0
    hidden: int = 0
    unreadable: int = 0
    pruned_dirs: int = 0
    unknown_extensions: dict[str, int] = field(default_factory=dict)


@dataclass
class Scan:
    root: Path
    languages: list[LanguageTotal]
    stats: ScanStats

    @property
    def effective_sloc(self) -> float:
        return sum(lang.effective for lang in self.languages)

    @property
    def code_lines(self) -> int:
        return sum(lang.code for lang in self.languages)

    def to_dict(self) -> dict:
        return {
            "root": str(self.root),
            "billable_lines": round(self.effective_sloc, 2),
            "code_lines": self.code_lines,
            "languages": [lang.to_dict() for lang in self.languages],
            "skipped": {
                "generated": self.stats.generated,
                "binary": self.stats.binary,
                "large": self.stats.large,
                "unknown": self.stats.unknown,
                "hidden": self.stats.hidden,
                "unreadable": self.stats.unreadable,
                "pruned_dirs": self.stats.pruned_dirs,
                "unknown_extensions": self.stats.unknown_extensions,
            },
        }


def with_weights(scan: Scan, overrides: dict[str, float]) -> Scan:
    if not overrides:
        return scan
    folded = {name.lower(): weight for name, weight in overrides.items()}
    languages = []
    for lang in scan.languages:
        weight = folded.get(lang.name.lower())
        if weight is None:
            languages.append(lang)
        else:
            languages.append(replace(lang, weight=weight))
    return replace(scan, languages=languages)


def scan_path(
    path: Path,
    max_bytes: int = DEFAULT_MAX_BYTES,
    extension_weights: dict[str, float] | None = None,
) -> Scan:
    path = path.resolve()
    weights = {key.lower(): value for key, value in (extension_weights or {}).items()}
    stats = ScanStats()
    totals: dict[str, LanguageTotal] = {}
    if path.is_file():
        _consume(path, totals, stats, max_bytes, weights)
        root = path.parent
    else:
        root = path
        for dirpath, dirnames, filenames in os.walk(path, followlinks=False):
            kept: list[str] = []
            for name in dirnames:
                lowered = name.lower()
                if lowered in SKIP_DIRS or lowered.endswith((".egg-info", ".dist-info")):
                    stats.pruned_dirs += 1
                    continue
                kept.append(name)
            dirnames[:] = kept
            folder = Path(dirpath)
            for name in filenames:
                _consume(folder / name, totals, stats, max_bytes, weights)
    languages = sorted(
        totals.values(),
        key=lambda lang: (-lang.effective, -lang.code, lang.name.lower()),
    )
    return Scan(root, languages, stats)


def _consume(
    path: Path,
    totals: dict[str, LanguageTotal],
    stats: ScanStats,
    max_bytes: int,
    extension_weights: dict[str, float],
) -> None:
    if path.is_symlink():
        return
    name = path.name
    if name.startswith(".") and language_for(path) is None:
        stats.hidden += 1
        return
    if _is_generated(path):
        stats.generated += 1
        return
    suffix = path.suffix.lower()
    if suffix in BINARY_EXTENSIONS:
        stats.binary += 1
        return
    try:
        size = path.stat().st_size
    except OSError:
        stats.unreadable += 1
        return
    if size > max_bytes:
        stats.large += 1
        return
    language = language_for(path)
    if language is None:
        custom = extension_weights.get(suffix)
        if suffix and custom is not None:
            language = Language(suffix, "custom", custom, "hash", (suffix,))
        else:
            stats.unknown += 1
            key = suffix or "(no extension)"
            stats.unknown_extensions[key] = stats.unknown_extensions.get(key, 0) + 1
            return
    try:
        data = path.read_bytes()
    except OSError:
        stats.unreadable += 1
        return
    if b"\0" in data[:8192]:
        stats.binary += 1
        return
    text = data.decode("utf-8", errors="replace")
    counts = count_text(text, language.style)
    _add(totals, language, counts)


def _is_generated(path: Path) -> bool:
    name = path.name.lower()
    if name in GENERATED_NAMES:
        return True
    return any(name.endswith(suffix) for suffix in GENERATED_SUFFIXES)


def _add(totals: dict[str, LanguageTotal], language: Language, counts: LineCounts) -> None:
    total = totals.get(language.name)
    if total is None:
        total = LanguageTotal(language.name, language.category, language.weight)
        totals[language.name] = total
    total.files += 1
    total.code += counts.code
    total.comment += counts.comment
    total.blank += counts.blank


def unknown_summary(stats: ScanStats, limit: int = 6) -> str:
    ranked = Counter(stats.unknown_extensions).most_common()
    if not ranked:
        return ""
    shown = ranked[:limit]
    text = ", ".join(f"{ext} ({count})" for ext, count in shown)
    extra = len(ranked) - len(shown)
    if extra:
        text = f"{text}, and {extra} more"
    return text
