from django import template
register = template.Library()

@register.filter
def stars(value):
    try:
        value = int(value)
    except:
        value = 0

    return "★" * value + "☆" * (5 - value)
