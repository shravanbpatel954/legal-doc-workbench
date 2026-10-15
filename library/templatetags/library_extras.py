import re

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def highlight(text, term):
    """Escape the text, then wrap every match of term in <mark>."""
    text = escape(text)
    if not term:
        return text
    pattern = re.compile(re.escape(escape(term)), re.IGNORECASE)
    return mark_safe(pattern.sub(lambda m: f"<mark>{m.group(0)}</mark>", text))
