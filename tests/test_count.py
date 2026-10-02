from cake.count import count_text


def test_hash_comments_and_blanks():
    text = "x = 1  # note\n# only\n\ny = 2\n"
    counts = count_text(text, "hash")
    assert counts.code == 2
    assert counts.comment == 1
    assert counts.blank == 1


def test_hash_inside_a_string_is_code():
    counts = count_text('s = "http://x#y"\n', "python")
    assert counts.code == 1
    assert counts.comment == 0


def test_python_multiline_string_stays_code():
    text = 's = """\n# title\nbody\n"""\n'
    counts = count_text(text, "python")
    assert counts.code == 4
    assert counts.comment == 0
    assert counts.blank == 0


def test_python_docstring_line_is_code():
    text = 'def add(a, b):\n    """Add two numbers."""\n    return a + b  # sum\n'
    counts = count_text(text, "python")
    assert counts.code == 3
    assert counts.comment == 0


def test_slash_line_and_block_comments():
    text = "int x = 1; // hi\n/* a\n b */\nint y = 2;\n"
    counts = count_text(text, "slash")
    assert counts.code == 2
    assert counts.comment == 2
    assert counts.blank == 0


def test_code_after_a_block_comment_on_the_same_line():
    counts = count_text("/* c */ int y = 2;\n", "slash")
    assert counts.code == 1
    assert counts.comment == 0


def test_url_inside_a_string_is_not_a_comment():
    counts = count_text('const u = "http://example.com";\n', "slash")
    assert counts.code == 1
    assert counts.comment == 0


def test_html_comment():
    text = "<div>hi</div>\n<!-- note -->\n\n<p>x</p>\n"
    counts = count_text(text, "html")
    assert counts.code == 2
    assert counts.comment == 1
    assert counts.blank == 1


def test_plain_text_counts_non_blank_lines_as_code():
    counts = count_text("hello\n\nworld\n", "none")
    assert counts.code == 2
    assert counts.blank == 1
    assert counts.comment == 0


def test_empty_file():
    counts = count_text("", "python")
    assert counts.total == 0
