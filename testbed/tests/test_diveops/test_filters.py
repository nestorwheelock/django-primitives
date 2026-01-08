"""Tests for diveops template filters."""

import pytest
from django.utils.safestring import SafeString

from primitives_testbed.diveops.templatetags.diveops_filters import render_content


class TestRenderContentFilter:
    """Tests for the render_content template filter."""

    def test_empty_string_returns_empty(self):
        """Empty input returns empty string."""
        assert render_content("") == ""
        assert render_content(None) == ""

    def test_html_content_passed_through(self):
        """HTML content is returned as-is (marked safe)."""
        html = '<h2 class="title">Hello</h2><p>World</p>'
        result = render_content(html)
        assert isinstance(result, SafeString)
        assert '<h2 class="title">Hello</h2>' in result
        assert '<p>World</p>' in result

    def test_html_with_checkbox_preserved(self):
        """HTML with form elements is preserved."""
        html = '''<div class="space-y-2">
          <label class="flex items-start gap-2">
            <input type="checkbox" name="q1" class="mt-1">
            <span>Question text</span>
          </label>
        </div>'''
        result = render_content(html)
        assert isinstance(result, SafeString)
        assert 'type="checkbox"' in result
        assert 'name="q1"' in result

    def test_markdown_bold_converted(self):
        """Markdown bold syntax is converted to HTML."""
        md = "This is **bold** text"
        result = render_content(md)
        assert isinstance(result, SafeString)
        assert "<strong>bold</strong>" in result or "**bold**" not in result

    def test_markdown_headers_converted(self):
        """Markdown headers are converted to HTML."""
        md = "## Section Title\n\nParagraph text."
        result = render_content(md)
        assert isinstance(result, SafeString)
        # Should not contain raw markdown
        assert "## " not in result

    def test_detects_html_by_tags(self):
        """Content with HTML tags is detected as HTML."""
        # These should be detected as HTML and passed through
        html_samples = [
            '<p>Paragraph</p>',
            '<div class="container">Content</div>',
            '<h1>Title</h1>',
            '<ol><li>Item</li></ol>',
            '<ul><li>Item</li></ul>',
            '<strong>Bold</strong>',
            '<em>Italic</em>',
            '<table><tr><td>Cell</td></tr></table>',
        ]
        for html in html_samples:
            result = render_content(html)
            # HTML content should be returned as-is
            assert html in result or html.replace('"', "'") in result

    def test_mixed_content_with_html_treated_as_html(self):
        """Content with HTML tags is treated as HTML even if it has markdown-like text."""
        content = '<p>This has **bold** markdown syntax but is actually HTML</p>'
        result = render_content(content)
        # Should preserve HTML, including the ** characters
        assert '<p>' in result
        assert '</p>' in result
