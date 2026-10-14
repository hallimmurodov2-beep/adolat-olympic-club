"""Babel/CLDR catalogs shared by the Python API and TypeScript interface."""
from __future__ import annotations
import json
from functools import lru_cache
from babel import Locale
from .config import ROOT

@lru_cache(maxsize=2)
def catalog(locale: str) -> dict:
    return json.loads((ROOT / 'locales' / f'{locale if locale in ("ru", "en") else "ru"}.json').read_text('utf-8'))


def translate(key: str, locale: str = 'ru', **params) -> str:
    messages = catalog(locale)
    value = messages.get(key, messages.get('error.unexpected', ''))
    if isinstance(value, dict):
        value = value.get(str(Locale.parse(locale).plural_form(params.get('count', 0))), value.get('other', ''))
    for name, replacement in params.items():
        value = value.replace('{' + name + '}', str(replacement))
    return value
