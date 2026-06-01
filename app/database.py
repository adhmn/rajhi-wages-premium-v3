from __future__ import annotations

import os
import sqlite3
import shutil
from datetime import datetime
from typing import Dict, Iterable, List, Optional

from .utils import data_dir, backups_dir, to_decimal, money

DEFAULT_DB_PATH = os.path.join(data_dir(), 'rajhi_wages.db')

SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS employees (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL DEFAULT '',
    gov_id TEXT NOT NULL DEFAULT '',
    iban TEXT NOT NULL DEFAULT '',
    nationality TEXT NOT NULL DEFAULT '',
    worker_type TEXT NOT NULL DEFAULT 'غير سعودي',
    basic_salary REAL NOT NULL DEFAULT 0,
    housing_allowance REAL NOT NULL DEFAULT 0,
    other_earnings REAL NOT NULL DEFAULT 0,
    deductions REAL NOT NULL DEFAULT 0,
    bank_code TEXT NOT NULL DEFAULT 'RJHI',
    payment_description TEXT NOT NULL DEFAULT 'Payroll',
    transaction_reference TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_employees_name ON employees(name);
CREATE INDEX IF NOT EXISTS idx_employees_gov_id ON employees(gov_id);
CREATE INDEX IF NOT EXISTS idx_employees_iban ON employees(iban);
CREATE TABLE IF NOT EXISTS payroll_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    payroll_month TEXT NOT NULL,
    value_date TEXT NOT NULL,
    debit_date TEXT NOT NULL,
    employee_count INTEGER NOT NULL DEFAULT 0,
    total_amount REAL NOT NULL DEFAULT 0,
    file_path TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action TEXT NOT NULL,
    details TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

DEFAULT_SETTINGS = {
    'establishment_name': 'شركة ساحل التميز للمقاولات شركة شخص واحد',
    'establishment_bank': 'RJHI',
    'establishment_id': '00079259',
    'mol_establishment_id': '2515736',
    'account_number': 'SA3880000129608016910669',
    'currency': 'SAR',
    'file_reference_prefix': 'PAYROLL',
    'export_format': 'rajhi_full',
    'shared_db_path': '',
}

class Database:
    def __init__(self, path: Optional[str] = None):
        self.path = path or DEFAULT_DB_PATH
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute('PRAGMA foreign_keys=ON')
        self.conn.executescript(SCHEMA)
        self.conn.commit()
        self.seed_settings()

    def seed_settings(self):
        for k, v in DEFAULT_SETTINGS.items():
            self.conn.execute('INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)', (k, v))
        self.conn.commit()

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass

    def backup(self) -> str:
        stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        target = os.path.join(backups_dir(), f'rajhi_wages_backup_{stamp}.db')
        self.conn.commit()
        shutil.copy2(self.path, target)
        self.log('backup', target)
        return target

    def log(self, action: str, details: str = ''):
        self.conn.execute('INSERT INTO audit_log(action, details) VALUES(?,?)', (action, details))
        self.conn.commit()

    def get_settings(self) -> Dict[str, str]:
        rows = self.conn.execute('SELECT key,value FROM settings').fetchall()
        return {r['key']: r['value'] for r in rows}

    def set_setting(self, key: str, value: str):
        self.conn.execute('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value', (key, str(value)))
        self.conn.commit()

    def save_settings(self, settings: Dict[str, str]):
        for k, v in settings.items():
            self.set_setting(k, v)
        self.log('settings_saved', 'تم حفظ إعدادات المنشأة')

    def employee_payload(self, data: Dict) -> Dict:
        basic = to_decimal(data.get('basic_salary'))
        housing = to_decimal(data.get('housing_allowance'))
        other = to_decimal(data.get('other_earnings'))
        deductions = to_decimal(data.get('deductions'))
        return {
            'name': str(data.get('name', '')).strip(),
            'gov_id': str(data.get('gov_id', '')).strip(),
            'iban': str(data.get('iban', '')).replace(' ', '').upper().strip(),
            'nationality': str(data.get('nationality', '')).strip(),
            'worker_type': str(data.get('worker_type', 'غير سعودي')).strip() or 'غير سعودي',
            'basic_salary': float(basic),
            'housing_allowance': float(housing),
            'other_earnings': float(other),
            'deductions': float(deductions),
            'bank_code': str(data.get('bank_code', 'RJHI')).strip() or 'RJHI',
            'payment_description': str(data.get('payment_description', 'Payroll')).strip() or 'Payroll',
            'transaction_reference': str(data.get('transaction_reference', '')).strip(),
        }

    def upsert_employee(self, data: Dict, employee_id: Optional[int] = None) -> int:
        p = self.employee_payload(data)
        if employee_id:
            self.conn.execute('''UPDATE employees SET name=?,gov_id=?,iban=?,nationality=?,worker_type=?,basic_salary=?,housing_allowance=?,other_earnings=?,deductions=?,bank_code=?,payment_description=?,transaction_reference=?,updated_at=CURRENT_TIMESTAMP WHERE id=?''',
                              (p['name'],p['gov_id'],p['iban'],p['nationality'],p['worker_type'],p['basic_salary'],p['housing_allowance'],p['other_earnings'],p['deductions'],p['bank_code'],p['payment_description'],p['transaction_reference'],employee_id))
            self.conn.commit(); self.log('employee_updated', p['name']); return int(employee_id)
        # prefer update by gov_id if exists
        existing = None
        if p['gov_id']:
            existing = self.conn.execute('SELECT id FROM employees WHERE gov_id=?', (p['gov_id'],)).fetchone()
        if existing:
            return self.upsert_employee(p, int(existing['id']))
        cur = self.conn.execute('''INSERT INTO employees(name,gov_id,iban,nationality,worker_type,basic_salary,housing_allowance,other_earnings,deductions,bank_code,payment_description,transaction_reference) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',
                                (p['name'],p['gov_id'],p['iban'],p['nationality'],p['worker_type'],p['basic_salary'],p['housing_allowance'],p['other_earnings'],p['deductions'],p['bank_code'],p['payment_description'],p['transaction_reference']))
        self.conn.commit(); self.log('employee_created', p['name']); return int(cur.lastrowid)

    def bulk_import(self, rows: Iterable[Dict]) -> int:
        count = 0
        for row in rows:
            if not row.get('name') and not row.get('gov_id') and not row.get('iban'):
                continue
            self.upsert_employee(row)
            count += 1
        self.log('employees_imported', f'{count} عامل')
        return count

    def delete_employee(self, employee_id: int):
        self.conn.execute('DELETE FROM employees WHERE id=?', (employee_id,))
        self.conn.commit(); self.log('employee_deleted', str(employee_id))

    def delete_all_employees(self):
        self.conn.execute('DELETE FROM employees')
        self.conn.commit(); self.log('employees_deleted_all', '')

    def list_employees(self, search: str = '') -> List[sqlite3.Row]:
        if search:
            like = f'%{search}%'
            return self.conn.execute('''SELECT *, (basic_salary+housing_allowance+other_earnings-deductions) as net_amount FROM employees WHERE name LIKE ? OR gov_id LIKE ? OR iban LIKE ? ORDER BY id DESC''', (like, like, like)).fetchall()
        return self.conn.execute('''SELECT *, (basic_salary+housing_allowance+other_earnings-deductions) as net_amount FROM employees ORDER BY id DESC''').fetchall()

    def get_employee(self, employee_id: int):
        return self.conn.execute('SELECT *, (basic_salary+housing_allowance+other_earnings-deductions) as net_amount FROM employees WHERE id=?', (employee_id,)).fetchone()

    def stats(self):
        row = self.conn.execute('SELECT COUNT(*) c, COALESCE(SUM(basic_salary+housing_allowance+other_earnings-deductions),0) total FROM employees').fetchone()
        return int(row['c']), float(row['total'])

    def record_payroll(self, payroll_month: str, value_date: str, debit_date: str, count: int, total: float, file_path: str):
        self.conn.execute('''INSERT INTO payroll_runs(payroll_month,value_date,debit_date,employee_count,total_amount,file_path) VALUES(?,?,?,?,?,?)''', (payroll_month, value_date, debit_date, count, total, file_path))
        self.conn.commit(); self.log('payroll_exported', file_path)

    def list_payrolls(self):
        return self.conn.execute('SELECT * FROM payroll_runs ORDER BY id DESC').fetchall()

    def audit(self, limit=200):
        return self.conn.execute('SELECT * FROM audit_log ORDER BY id DESC LIMIT ?', (limit,)).fetchall()
