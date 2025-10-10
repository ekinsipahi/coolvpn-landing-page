# landing/templatetags/seo_extras.py
from django import template
import json

register = template.Library()

@register.filter
def tojson(value):
    """Python objesini JSON stringe çevirir."""
    return json.dumps(value, ensure_ascii=False)
