"""Convert Markdown to Telegram MarkdownV2 format.

Telegram MarkdownV2 requires escaping special characters and has specific
formatting rules. This module converts standard Markdown to compatible format.
"""

import re


# Characters that must be escaped in MarkdownV2 (outside of code blocks)
ESCAPE_CHARS = r"_*[]()~`>#+=|{}.!-"


def escape_markdown(text: str) -> str:
    """Escape special characters for Telegram MarkdownV2.

    Args:
        text: Plain text to escape.

    Returns:
        Text with special characters escaped.
    """
    return re.sub(r"([" + re.escape(ESCAPE_CHARS) + r"])", r"\\\1", text)


def convert_markdown_to_telegram(text: str) -> str:
    """Convert standard Markdown to Telegram MarkdownV2 format.

    Handles:
    - **bold** or __bold__ -> *bold*
    - *italic* or _italic_ -> _italic_
    - `code` -> `code`
    - ```code blocks``` -> ```code blocks```
    - [link](url) -> [link](url)

    Args:
        text: Standard Markdown text.

    Returns:
        Telegram MarkdownV2 formatted text.
    """
    if not text:
        return text

    # Storage for protected elements
    protected: list[str] = []

    def protect(s: str) -> str:
        protected.append(s)
        return f"\x00P{len(protected) - 1}\x00"

    # Protect code blocks (``` ... ```)
    result = re.sub(r"```[\s\S]*?```", lambda m: protect(m.group(0)), text)

    # Protect inline code (` ... `)
    result = re.sub(r"`[^`]+`", lambda m: protect(m.group(0)), result)

    # Convert bold: **text** or __text__ -> *text*
    def convert_bold(match: re.Match[str]) -> str:
        content = escape_markdown(match.group(1))
        return protect(f"*{content}*")

    result = re.sub(r"\*\*(.+?)\*\*", convert_bold, result)
    result = re.sub(r"__(.+?)__", convert_bold, result)

    # Convert italic: *text* or _text_ -> _text_
    def convert_italic(match: re.Match[str]) -> str:
        content = escape_markdown(match.group(1))
        return protect(f"_{content}_")

    # Match italic only when not part of a word
    result = re.sub(r"(?<!\w)\*([^*]+?)\*(?!\w)", convert_italic, result)
    result = re.sub(r"(?<!\w)_([^_]+?)_(?!\w)", convert_italic, result)

    # Convert links: [text](url) -> [text](url)
    def convert_link(match: re.Match[str]) -> str:
        link_text = escape_markdown(match.group(1))
        url = match.group(2).replace("\\", "\\\\").replace(")", "\\)")
        return protect(f"[{link_text}]({url})")

    result = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", convert_link, result)

    # Escape remaining plain text
    parts = re.split(r"(\x00P\d+\x00)", result)
    escaped_parts = []
    for part in parts:
        if re.match(r"^\x00P\d+\x00$", part):
            escaped_parts.append(part)
        else:
            escaped_parts.append(escape_markdown(part))
    result = "".join(escaped_parts)

    # Restore protected elements
    for i, elem in enumerate(protected):
        result = result.replace(f"\x00P{i}\x00", elem)

    return result
