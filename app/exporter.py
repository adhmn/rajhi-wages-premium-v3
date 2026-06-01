from __future__ import annotations

import os
from datetime import datetime
from typing import List

from .utils import exports_dir, rajhi_amount, yyyymmdd, transaction_reference, clean_text


def generate_txt(db, payroll_month: str, value_date: str, debit_date: str, output_path: str | None = None) -> str:
    settings = db.get_settings()
    employees = db.list_employees('')
    if not employees:
        raise ValueError('لا يوجد عمال لتوليد ملف الأجور.')

    value = yyyymmdd(value_date)
    debit = yyyymmdd(debit_date)
    month = payroll_month or datetime.now().strftime('%Y-%m')
    total = sum(float(r['net_amount']) for r in employees)

    if output_path is None:
        name = f"rajhi_wages_{month.replace('-', '')}_{datetime.now().strftime('%H%M%S')}.txt"
        output_path = os.path.join(exports_dir(), name)

    fmt = settings.get('export_format', 'rajhi_full')
    lines: List[str] = []

    if fmt == 'rajhi_full':
        header = [
            settings.get('establishment_bank','RJHI'),
            settings.get('establishment_id',''),
            settings.get('account_number',''),
            settings.get('currency','SAR'),
            value,
            rajhi_amount(total),
            debit,
            f"{settings.get('file_reference_prefix','PAYROLL')}{datetime.now().strftime('%Y%m%d%H%M%S')}",
            'P000',
            settings.get('mol_establishment_id',''),
        ]
        lines.append('\t'.join(header))

    for i, emp in enumerate(reversed(employees), start=1):
        tx = emp['transaction_reference'] or transaction_reference(value, i)
        cols = [
            rajhi_amount(emp['net_amount']),
            clean_text(emp['iban']),
            clean_text(emp['name']),
            clean_text(emp['bank_code'] or 'RJHI'),
            clean_text(emp['payment_description'] or 'Payroll'),
        ]
        if fmt == 'rajhi_full_with_return_code':
            cols.append('N/A')
        cols.extend([
            rajhi_amount(emp['basic_salary']),
            rajhi_amount(emp['housing_allowance']),
            rajhi_amount(emp['other_earnings']),
            rajhi_amount(emp['deductions']),
            clean_text(emp['gov_id']),
            tx,
        ])
        lines.append('\t'.join(cols))

    if fmt == 'rajhi_full':
        lines.append('-')

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
        f.write('\n'.join(lines))

    db.record_payroll(month, value, debit, len(employees), total, output_path)
    return output_path
