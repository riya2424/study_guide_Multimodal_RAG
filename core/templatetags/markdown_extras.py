import markdown as md
from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter(name="markdown")
def markdown_filter(text):
    if not text:
        return ""
    html = md.markdown(text, extensions=["extra", "sane_lists"])
    return mark_safe(html)
