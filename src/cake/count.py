"""Line classification for a physical source-line count.

A line is code when any of it is code, comment when it is only a comment,
and blank when it is empty. Detection is approximate: it understands the
common comment and string markers for each language and does not build a
real parse tree.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Style:
    line_marks: tuple[str, ...] = ()
    blocks: tuple[tuple[str, str], ...] = ()
    quotes: tuple[str, ...] = ()
    triples: bool = False


@dataclass
class LineCounts:
    code: int = 0
    comment: int = 0
    blank: int = 0

    @property
    def total(self) -> int:
        return self.code + self.comment + self.blank


STYLES: dict[str, Style] = {
    "python": Style(("#",), (), ('"', "'"), triples=True),
    "hash": Style(("#",), (), ('"', "'")),
    "slash": Style(("//",), (("/*", "*/"),), ('"', "'", "`")),
    "html": Style(("//",), (("<!--", "-->"), ("/*", "*/")), ('"', "'", "`")),
    "sql": Style(("--",), (("/*", "*/"),), ('"', "'")),
    "dash": Style(("--",), (), ('"', "'")),
    "semi": Style((";",), (), ('"', "'")),
    "percent": Style(("%",), (), ('"', "'")),
    "bang": Style(("!",), (), ('"', "'")),
    "hashslash": Style(("#", "//"), (("/*", "*/"),), ('"', "'")),
    "ocaml": Style((), (("(*", "*)"),), ('"',)),
}


def count_text(text: str, style: str) -> LineCounts:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if text == "":
        return LineCounts()
    if style == "none":
        return _count_plain(text)
    try:
        spec = STYLES[style]
    except KeyError as exc:
        raise ValueError(f"unknown comment style {style!r}") from exc
    return _scan(text, spec)


def _count_plain(text: str) -> LineCounts:
    lines = text.split("\n")
    if text.endswith("\n"):
        lines = lines[:-1]
    code = 0
    blank = 0
    for line in lines:
        if line.strip():
            code += 1
        else:
            blank += 1
    return LineCounts(code, 0, blank)


def _scan(text: str, style: Style) -> LineCounts:
    marks = tuple(sorted(style.line_marks, key=len, reverse=True))
    blocks = tuple(sorted(style.blocks, key=lambda pair: len(pair[0]), reverse=True))
    quotes = style.quotes
    triples = style.triples
    n = len(text)
    i = 0
    code = comment = blank = 0
    block_closer: str | None = None
    span: str | None = None
    has_code = False
    in_block_during = False
    comment_content = False

    def flush() -> None:
        nonlocal code, comment, blank, has_code, in_block_during, comment_content
        if has_code:
            code += 1
        elif in_block_during or comment_content:
            comment += 1
        else:
            blank += 1
        has_code = False
        comment_content = False
        in_block_during = block_closer is not None

    while i < n:
        if span is not None:
            if text.startswith(span, i):
                has_code = True
                i += len(span)
                span = None
                continue
            ch = text[i]
            if ch == "\n":
                flush()
                i += 1
                continue
            if not ch.isspace():
                has_code = True
            i += 1
            continue

        if block_closer is not None:
            in_block_during = True
            if text.startswith(block_closer, i):
                i += len(block_closer)
                block_closer = None
                continue
            ch = text[i]
            if ch == "\n":
                flush()
                i += 1
                continue
            if not ch.isspace():
                comment_content = True
            i += 1
            continue

        if text[i] == "\n":
            flush()
            i += 1
            continue

        if triples and (text.startswith('"""', i) or text.startswith("'''", i)):
            has_code = True
            span = text[i : i + 3]
            i += 3
            continue

        marked = False
        for mark in marks:
            if text.startswith(mark, i):
                comment_content = True
                i += len(mark)
                while i < n and text[i] != "\n":
                    i += 1
                marked = True
                break
        if marked:
            continue

        opened = False
        for opener, closer in blocks:
            if text.startswith(opener, i):
                block_closer = closer
                in_block_during = True
                i += len(opener)
                opened = True
                break
        if opened:
            continue

        if text[i] in quotes:
            quote = text[i]
            has_code = True
            i += 1
            while i < n and text[i] != "\n":
                if text[i] == "\\":
                    i += 2
                    continue
                if text[i] == quote:
                    i += 1
                    break
                i += 1
            continue

        if not text[i].isspace():
            has_code = True
        i += 1

    if not text.endswith("\n"):
        flush()
    return LineCounts(code, comment, blank)
