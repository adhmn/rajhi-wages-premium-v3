from __future__ import annotations

import os
from typing import Dict, List

from .utils import clean_text, normalize_iban, clean_digits, to_decimal


def _row_values_openpyxl(ws):
    for row in ws.iter_rows(values_only=True):
        yield list(row)


def _row_values_xlrd(path):
    import xlrd
    book = xlrd.open_workbook(path)
    sheet = book.sheet_by_index(0)
    for r in range(sheet.nrows):
        yield sheet.row_values(r)


def _load_rows(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == '.xls':
        return list(_row_values_xlrd(path))
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb.active
    return list(_row_values_openpyxl(ws))


def parse_rajhi_excel(path: str) -> List[Dict]:
    rows = _load_rows(path)
    employees: List[Dict] = []

    # Al Rajhi Wage Details template: details start after row containing mandatory row beneath fields.
    start_index = None
    for i, row in enumerate(rows):
        texts = [clean_text(v).lower() for v in row]
        joined = ' '.join(texts)
        if 'net amount to be paid' in joined or 'beneficiary' in joined:
            start_index = i + 2
            break

    if start_index is not None:
        for idx, row in enumerate(rows[start_index:], start=1):
            if len(row) < 12:
                continue
            first = clean_text(row[0])
            if not first or not first.replace('.', '', 1).isdigit():
                continue
            net = row[1]
            iban = normalize_iban(row[2])
            name = clean_text(row[3])
            if not iban or not name:
                continue
            employees.append({
                'name': name,
                'iban': iban,
                'gov_id': clean_digits(row[11]) if len(row) > 11 else '',
                'nationality': '',
                'worker_type': 'غير سعودي',
                'basic_salary': to_decimal(row[7] if len(row) > 7 else 0),
                'housing_allowance': to_decimal(row[8] if len(row) > 8 else 0),
                'other_earnings': to_decimal(row[9] if len(row) > 9 else 0),
                'deductions': to_decimal(row[10] if len(row) > 10 else 0),
                'bank_code': clean_text(row[4]) or 'RJHI',
                'payment_description': clean_text(row[5]) or 'Payroll',
                'transaction_reference': clean_text(row[12]) if len(row) > 12 else '',
            })
        return employees

    # Generic Excel fallback: detect header names.
    headers = []
    header_index = None
    for i, row in enumerate(rows[:20]):
        normalized = [clean_text(v).lower() for v in row]
        if any('iban' in x or 'آيبان' in x or 'الآيبان' in x for x in normalized) and any('name' in x or 'اسم' in x for x in normalized):
            headers = normalized
            header_index = i
            break
    if header_index is None:
        raise ValueError('لم يتم التعرف على نموذج Excel. أرسل ملف العمال أو نموذج الراجحي الصحيح.')

    def find(*keys):
        for key in keys:
            for i, h in enumerate(headers):
                if key in h:
                    return i
        return None

    idx_name = find('name', 'اسم')
    idx_iban = find('iban', 'آيبان', 'الآيبان')
    idx_gov = find('id', 'هوية', 'اقامة', 'إقامة')
    idx_basic = find('basic', 'راتب')
    idx_housing = find('housing', 'سكن')
    idx_other = find('other', 'بدلات', 'بدل')
    idx_ded = find('deduction', 'خصم')
    idx_type = find('نوع', 'سعودي')
    idx_nat = find('جنسية', 'nationality')

    for row in rows[header_index+1:]:
        name = clean_text(row[idx_name]) if idx_name is not None and idx_name < len(row) else ''
        iban = normalize_iban(row[idx_iban]) if idx_iban is not None and idx_iban < len(row) else ''
        if not name and not iban:
            continue
        employees.append({
            'name': name,
            'iban': iban,
            'gov_id': clean_digits(row[idx_gov]) if idx_gov is not None and idx_gov < len(row) else '',
            'nationality': clean_text(row[idx_nat]) if idx_nat is not None and idx_nat < len(row) else '',
            'worker_type': clean_text(row[idx_type]) if idx_type is not None and idx_type < len(row) else 'غير سعودي',
            'basic_salary': to_decimal(row[idx_basic]) if idx_basic is not None and idx_basic < len(row) else 0,
            'housing_allowance': to_decimal(row[idx_housing]) if idx_housing is not None and idx_housing < len(row) else 0,
            'other_earnings': to_decimal(row[idx_other]) if idx_other is not None and idx_other < len(row) else 0,
            'deductions': to_decimal(row[idx_ded]) if idx_ded is not None and idx_ded < len(row) else 0,
            'bank_code': 'RJHI',
            'payment_description': 'Payroll',
            'transaction_reference': '',
        })
    return employees
