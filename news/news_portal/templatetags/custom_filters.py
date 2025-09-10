from django import template
register = template.Library()
from .bad_words import BAD_WORDS

@register.filter()
def currency(value):
    if not value:
        return value
    
    for word in BAD_WORDS:
        # Заменяем слово на первую букву + звёздочки
        censored_word = word[0] + '*' * (len(word) - 1)
        value = value.replace(word, censored_word)
    
    return value