from __future__ import annotations

import os
import re
import sys
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from datetime import datetime

APP_NAME = "برنامج أجور الراجحي"
APP_VERSION = "3.0.0"


def app_base_dir() -> str:
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def ensure_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path


def data_dir() -> str:
    return ensure_dir(os.path.join(app_base_dir(), 'data'))


def exports_dir() -> str:
    return ensure_dir(os.path.join(app_base_dir(), 'exports'))


def backups_dir() -> str:
    return ensure_dir(os.path.join(app_base_dir(), 'backups'))


def clean_text(value) -> str:
    if value is None:
        return ''
    value = str(value).strip()
    value = re.sub(r'\s+', ' ', value)
    return value


def clean_digits(value) -> str:
    return re.sub(r'\D+', '', clean_text(value))


def normalize_iban(value) -> str:
    return clean_text(value).replace(' ', '').upper()


def to_decimal(value) -> Decimal:
    if value is None or value == '':
        return Decimal('0.00')
    text = clean_text(value).replace(',', '.')
    try:
        return Decimal(text).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return Decimal('0.00')


def money(value) -> str:
    return f"{to_decimal(value):,.2f}".replace(',', '')


def rajhi_amount(value) -> str:
    # Al Rajhi sample uses fixed 10 digits before comma + 2 decimals: 0000004500,00
    cents = int((to_decimal(value) * 100).to_integral_value(rounding=ROUND_HALF_UP))
    whole = cents // 100
    frac = cents % 100
    return f"{whole:010d},{frac:02d}"


def yyyymmdd(date_value=None) -> str:
    if date_value is None or date_value == '':
        return datetime.now().strftime('%Y%m%d')
    if isinstance(date_value, datetime):
        return date_value.strftime('%Y%m%d')
    text = clean_text(date_value)
    for fmt in ('%Y%m%d', '%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y'):
        try:
            return datetime.strptime(text, fmt).strftime('%Y%m%d')
        except ValueError:
            pass
    return datetime.now().strftime('%Y%m%d')


def transaction_reference(prefix_date: str, row_number: int) -> str:
    # Stable monthly unique reference, 14 digits-ish.
    return f"{prefix_date[-6:]}{row_number:08d}"


def is_valid_iban(iban: str) -> bool:
    iban = normalize_iban(iban)
    return bool(re.fullmatch(r'SA\d{22}', iban))


def is_valid_gov_id(gov_id: str) -> bool:
    gov_id = clean_digits(gov_id)
    return len(gov_id) in (10,)
