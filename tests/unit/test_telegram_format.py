"""Tests for Telegram Markdown formatting."""

import pytest

from voice_agent.telegram_format import convert_markdown_to_telegram, escape_markdown


class TestEscapeMarkdown:
    """Tests for escape_markdown function."""

    def test_escapes_special_chars(self) -> None:
        assert escape_markdown("hello.world") == r"hello\.world"
        assert escape_markdown("test!") == r"test\!"
        assert escape_markdown("a-b") == r"a\-b"

    def test_escapes_multiple_chars(self) -> None:
        assert escape_markdown("a.b!c") == r"a\.b\!c"

    def test_preserves_plain_text(self) -> None:
        assert escape_markdown("hello world") == "hello world"


class TestConvertMarkdownToTelegram:
    """Tests for convert_markdown_to_telegram function."""

    def test_converts_bold_asterisks(self) -> None:
        result = convert_markdown_to_telegram("This is **bold** text")
        assert "*bold*" in result

    def test_converts_bold_underscores(self) -> None:
        result = convert_markdown_to_telegram("This is __bold__ text")
        assert "*bold*" in result

    def test_converts_italic_asterisk(self) -> None:
        result = convert_markdown_to_telegram("This is *italic* text")
        assert "_italic_" in result

    def test_converts_italic_underscore(self) -> None:
        result = convert_markdown_to_telegram("This is _italic_ text")
        assert "_italic_" in result

    def test_preserves_inline_code(self) -> None:
        result = convert_markdown_to_telegram("Run `npm install` please")
        assert "`npm install`" in result

    def test_preserves_code_blocks(self) -> None:
        text = "```python\nprint('hello')\n```"
        result = convert_markdown_to_telegram(text)
        assert "```python\nprint('hello')\n```" in result

    def test_converts_links(self) -> None:
        result = convert_markdown_to_telegram("Check [this](https://example.com)")
        assert "[this](https://example.com)" in result

    def test_escapes_special_chars_in_plain_text(self) -> None:
        result = convert_markdown_to_telegram("File: test.py")
        assert r"\." in result

    def test_mixed_formatting(self) -> None:
        text = "This is **bold** and *italic* with `code`"
        result = convert_markdown_to_telegram(text)
        assert "*bold*" in result
        assert "_italic_" in result
        assert "`code`" in result

    def test_empty_string(self) -> None:
        assert convert_markdown_to_telegram("") == ""

    def test_plain_text(self) -> None:
        result = convert_markdown_to_telegram("Hello world")
        assert result == "Hello world"
