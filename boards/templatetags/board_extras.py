import re

from django import template
from django.utils.html import escape
from django.utils.safestring import mark_safe

register = template.Library()

MENTION_RE = re.compile(r'@(\w+)')


@register.filter
def mentions(text):
    escaped = escape(text)
    highlighted = MENTION_RE.sub(r'<span class="mention">@\1</span>', escaped)
    return mark_safe(highlighted)
