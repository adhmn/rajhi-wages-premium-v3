from __future__ import annotations

import os
import shutil
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime

from .database import Database, DEFAULT_DB_PATH
from .importer import parse_rajhi_excel
from .exporter import generate_txt
from .utils import APP_VERSION, APP_NAME, money, is_valid_iban, is_valid_gov_id, app_base_dir, data_dir

BG = '#0f172a'
PANEL = '#111c32'
PANEL2 = '#17243c'
TEXT = '#f8fafc'
MUTED = '#94a3b8'
GOLD = '#f5c542'
BLUE = '#2563eb'
GREEN = '#16a34a'
RED = '#dc2626'
PURPLE = '#9333ea'
BORDER = '#334155'
WHITE = '#ffffff'

class PremiumRajhiApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f'{APP_NAME} - v{APP_VERSION}')
        self.geometry('1500x850')
        self.minsize(1200, 720)
        self.configure(bg=BG)
        self.selected_employee_id = None
        self.db = Database()
        self._build_style()
        self._build_layout()
        self.refresh_all()

    def _build_style(self):
        style = ttk.Style(self)
        style.theme_use('clam')
        style.configure('TNotebook', background=BG, borderwidth=0)
        style.configure('TNotebook.Tab', padding=(18, 10), background='#d8d3c7', foreground='#111827', font=('Tahoma', 10, 'bold'))
        style.map('TNotebook.Tab', background=[('selected', GOLD)], foreground=[('selected', '#111827')])
        style.configure('Treeview', background=WHITE, foreground='#0f172a', rowheight=30, fieldbackground=WHITE, font=('Tahoma', 10))
        style.configure('Treeview.Heading', background='#e5e7eb', foreground='#111827', font=('Tahoma', 10, 'bold'), padding=8)
        style.map('Treeview', background=[('selected', '#dbeafe')], foreground=[('selected', '#111827')])
        style.configure('Vertical.TScrollbar', gripcount=0, background='#cbd5e1', troughcolor='#e5e7eb')

    def _btn(self, parent, text, command, bg=BLUE, fg='white', width=14):
        b = tk.Button(parent, text=text, command=command, bg=bg, fg=fg, activebackground=bg,
                      activeforeground=fg, relief='flat', bd=0, padx=14, pady=10,
                      font=('Tahoma', 10, 'bold'), cursor='hand2', width=width)
        return b

    def _entry(self, parent, width=22):
        e = tk.Entry(parent, bg='#f8fafc', fg='#111827', insertbackground='#111827', relief='flat',
                     font=('Tahoma', 11), justify='right', width=width)
        return e

    def _label(self, parent, text, color=TEXT, size=10, bold=False):
        return tk.Label(parent, text=text, bg=parent['bg'] if 'bg' in parent.keys() else BG, fg=color,
                        font=('Tahoma', size, 'bold' if bold else 'normal'))

    def _build_layout(self):
        header = tk.Frame(self, bg=BG, height=80)
        header.pack(fill='x', padx=14, pady=(12, 6))
        header.pack_propagate(False)
        tk.Label(header, text='برنامج أجور الراجحي', bg=BG, fg=TEXT, font=('Tahoma', 20, 'bold')).pack(side='right', padx=10)
        self.stats_lbl = tk.Label(header, text='', bg=BG, fg=GOLD, font=('Tahoma', 12, 'bold'))
        self.stats_lbl.pack(side='left', padx=10)

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill='both', expand=True, padx=10, pady=6)
        self.tab_employees = tk.Frame(self.nb, bg=BG)
        self.tab_export = tk.Frame(self.nb, bg=BG)
        self.tab_settings = tk.Frame(self.nb, bg=BG)
        self.tab_runs = tk.Frame(self.nb, bg=BG)
        self.nb.add(self.tab_employees, text='العمال والرواتب')
        self.nb.add(self.tab_export, text='TXT توليد ملف')
        self.nb.add(self.tab_settings, text='إعدادات المنشأة والشبكة')
        self.nb.add(self.tab_runs, text='المسيرات السابقة')
        self._build_employees_tab()
        self._build_export_tab()
        self._build_settings_tab()
        self._build_runs_tab()

    def _build_employees_tab(self):
        topbar = tk.Frame(self.tab_employees, bg=PANEL, height=70, highlightbackground=BORDER, highlightthickness=1)
        topbar.pack(fill='x', padx=0, pady=0)
        topbar.pack_propagate(False)
        tk.Label(topbar, text='بحث:', bg=PANEL, fg=TEXT, font=('Tahoma', 10, 'bold')).pack(side='right', padx=(10, 6), pady=14)
        self.search_var = tk.StringVar()
        self.search_entry = self._entry(topbar, 28)
        self.search_entry.pack(side='right', padx=6, pady=14)
        self.search_entry.bind('<KeyRelease>', lambda e: self.refresh_employees())
        self._btn(topbar, 'تحديث', self.refresh_all, bg='#475569', width=10).pack(side='right', padx=4, pady=12)
        self._btn(topbar, 'تعديل جماعي', self.bulk_edit_dialog, bg=PURPLE, width=12).pack(side='right', padx=4, pady=12)
        self._btn(topbar, 'استيراد Excel العمال', self.import_excel, bg=GREEN, width=18).pack(side='right', padx=4, pady=12)

        form = tk.LabelFrame(self.tab_employees, text='بيانات العامل', bg=PANEL, fg=TEXT, font=('Tahoma', 11, 'bold'), labelanchor='ne', padx=12, pady=12)
        form.pack(fill='x', padx=0, pady=(0, 8))
        self.fields = {}
        labels = [
            ('name', 'اسم العامل'), ('gov_id', 'رقم الهوية/الإقامة'), ('iban', 'الآيبان'),
            ('nationality', 'الجنسية'), ('basic_salary', 'الراتب'), ('worker_type', 'سعودي/غير سعودي'),
            ('housing_allowance', 'بدل السكن'), ('other_earnings', 'بدلات أخرى'), ('deductions', 'خصومات')
        ]
        for idx, (key, label) in enumerate(labels):
            r = idx // 3
            c = (idx % 3) * 2
            tk.Label(form, text=label, bg=PANEL, fg=TEXT, font=('Tahoma', 10, 'bold')).grid(row=r, column=c+1, sticky='e', padx=8, pady=8)
            if key == 'worker_type':
                cb = ttk.Combobox(form, values=['غير سعودي', 'سعودي'], state='readonly', justify='right', font=('Tahoma', 10), width=24)
                cb.set('غير سعودي')
                cb.grid(row=r, column=c, sticky='ew', padx=8, pady=8)
                self.fields[key] = cb
            else:
                e = self._entry(form, 28)
                e.grid(row=r, column=c, sticky='ew', padx=8, pady=8)
                self.fields[key] = e
        for i in range(6):
            form.grid_columnconfigure(i, weight=1)
        btnrow = tk.Frame(form, bg=PANEL)
        btnrow.grid(row=3, column=0, columnspan=6, sticky='w', padx=8, pady=10)
        self._btn(btnrow, 'حفظ / تحديث العامل', self.save_employee, bg=BLUE, width=18).pack(side='right', padx=5)
        self._btn(btnrow, 'جديد', self.clear_form, bg='#64748b', width=10).pack(side='right', padx=5)
        self._btn(btnrow, 'حذف المحدد', self.delete_selected, bg=RED, width=12).pack(side='right', padx=5)

        table_frame = tk.Frame(self.tab_employees, bg=BG)
        table_frame.pack(fill='both', expand=True)
        cols = ('id','name','gov_id','iban','worker_type','basic_salary','housing_allowance','other_earnings','deductions','net_amount')
        headings = {'id':'#','name':'الاسم','gov_id':'الهوية/الإقامة','iban':'الآيبان','worker_type':'النوع','basic_salary':'الراتب','housing_allowance':'السكن','other_earnings':'بدلات','deductions':'خصومات','net_amount':'الصافي'}
        self.tree = ttk.Treeview(table_frame, columns=cols, show='headings')
        for col in cols:
            self.tree.heading(col, text=headings[col])
            self.tree.column(col, anchor='center', width=120 if col not in ('name','iban') else 230)
        self.tree.pack(side='left', fill='both', expand=True)
        sb = ttk.Scrollbar(table_frame, orient='vertical', command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side='right', fill='y')
        self.tree.bind('<<TreeviewSelect>>', self.on_select_employee)
        self.tree.bind('<Double-1>', self.on_select_employee)

    def _build_export_tab(self):
        box = tk.LabelFrame(self.tab_export, text='توليد ملف حماية الأجور TXT لبنك الراجحي', bg=PANEL, fg=TEXT, font=('Tahoma', 13, 'bold'), labelanchor='ne', padx=18, pady=18)
        box.pack(fill='x', padx=16, pady=16)
        self.export_month = self._entry(box, 18); self.export_value_date = self._entry(box, 18); self.export_debit_date = self._entry(box, 18)
        today = datetime.now().strftime('%Y%m%d')
        self.export_month.insert(0, datetime.now().strftime('%Y-%m'))
        self.export_value_date.insert(0, today)
        self.export_debit_date.insert(0, today)
        items = [(self.export_month, 'شهر المسير مثل 2026-06'), (self.export_value_date, 'تاريخ القيمة YYYYMMDD'), (self.export_debit_date, 'تاريخ الخصم YYYYMMDD')]
        for i, (entry, label) in enumerate(items):
            tk.Label(box, text=label, bg=PANEL, fg=TEXT, font=('Tahoma', 11, 'bold')).grid(row=0, column=i*2+1, sticky='e', padx=8, pady=12)
            entry.grid(row=0, column=i*2, sticky='ew', padx=8, pady=12)
        self._btn(box, 'توليد ملف TXT الآن', self.export_txt, bg=GOLD, fg='#111827', width=20).grid(row=1, column=0, columnspan=2, sticky='e', padx=8, pady=18)
        self.export_status = tk.Label(self.tab_export, text='الملف سيتم حفظه داخل فولدر exports بجانب البرنامج.', bg=BG, fg=MUTED, font=('Tahoma', 12, 'bold'), justify='right')
        self.export_status.pack(fill='x', padx=20, pady=10)

    def _build_settings_tab(self):
        self.settings_entries = {}
        box = tk.LabelFrame(self.tab_settings, text='إعدادات المنشأة المطلوبة في ملف الراجحي', bg=PANEL, fg=TEXT, font=('Tahoma', 13, 'bold'), labelanchor='ne', padx=18, pady=18)
        box.pack(fill='x', padx=16, pady=16)
        labels = [
            ('establishment_name','اسم المنشأة'), ('establishment_bank','بنك المنشأة'), ('establishment_id','رقم المنشأة بالبنك'),
            ('account_number','حساب المنشأة/الآيبان'), ('currency','العملة'), ('mol_establishment_id','رقم منشأة وزارة العمل'),
            ('file_reference_prefix','بادئة مرجع الملف'), ('export_format','صيغة التصدير'), ('shared_db_path','مسار قاعدة البيانات المشتركة')
        ]
        settings = self.db.get_settings()
        for idx,(key,label) in enumerate(labels):
            r = idx//2; c=(idx%2)*2
            tk.Label(box, text=label, bg=PANEL, fg=TEXT, font=('Tahoma',10,'bold')).grid(row=r,column=c+1,sticky='e',padx=8,pady=8)
            if key == 'export_format':
                e=ttk.Combobox(box, values=['rajhi_full','rajhi_basic','rajhi_full_with_return_code'], state='readonly', justify='right', font=('Tahoma',10), width=34)
                e.set(settings.get(key,'rajhi_full'))
            else:
                e=self._entry(box, 38)
                e.insert(0, settings.get(key,''))
            e.grid(row=r,column=c,sticky='ew',padx=8,pady=8)
            self.settings_entries[key]=e
        for i in range(4): box.grid_columnconfigure(i, weight=1)
        actions = tk.Frame(box,bg=PANEL)
        actions.grid(row=5,column=0,columnspan=4,sticky='w',pady=14)
        self._btn(actions,'حفظ الإعدادات',self.save_settings,bg=GREEN,width=16).pack(side='right',padx=5)
        self._btn(actions,'اختيار قاعدة شبكة',self.choose_shared_db,bg=BLUE,width=16).pack(side='right',padx=5)
        self._btn(actions,'نسخة احتياطية',self.backup_db,bg=GOLD,fg='#111827',width=14).pack(side='right',padx=5)

        note = tk.Label(self.tab_settings, text='تشغيل 3 أجهزة: ضع ملف قاعدة البيانات في فولدر Shared على الجهاز الرئيسي، ثم من كل جهاز اختر نفس ملف قاعدة البيانات من زر اختيار قاعدة شبكة.', bg=BG, fg=GOLD, font=('Tahoma', 12, 'bold'), wraplength=1200, justify='right')
        note.pack(fill='x', padx=20, pady=8)

    def _build_runs_tab(self):
        top = tk.Frame(self.tab_runs,bg=PANEL,pady=8)
        top.pack(fill='x')
        self._btn(top,'تحديث السجل',self.refresh_runs,bg=BLUE,width=14).pack(side='right',padx=8)
        self._btn(top,'فتح مجلد التصدير',self.open_exports,bg=GREEN,width=16).pack(side='right',padx=8)
        cols=('id','payroll_month','value_date','employee_count','total_amount','file_path','created_at')
        headings={'id':'#','payroll_month':'الشهر','value_date':'تاريخ القيمة','employee_count':'عدد العمال','total_amount':'الإجمالي','file_path':'مسار الملف','created_at':'وقت الإنشاء'}
        self.runs_tree=ttk.Treeview(self.tab_runs,columns=cols,show='headings')
        for col in cols:
            self.runs_tree.heading(col,text=headings[col]); self.runs_tree.column(col,anchor='center',width=150 if col!='file_path' else 450)
        self.runs_tree.pack(fill='both',expand=True,padx=0,pady=8)

    def refresh_all(self):
        self.refresh_employees(); self.refresh_stats(); self.refresh_runs()

    def refresh_stats(self):
        count,total = self.db.stats()
        self.stats_lbl.config(text=f'عدد العمال: {count} | صافي الرواتب: {money(total)} ريال')

    def refresh_employees(self):
        search = self.search_entry.get().strip() if hasattr(self,'search_entry') else ''
        for i in self.tree.get_children(): self.tree.delete(i)
        for r in self.db.list_employees(search):
            self.tree.insert('', 'end', iid=str(r['id']), values=(r['id'], r['name'], r['gov_id'], r['iban'], r['worker_type'], money(r['basic_salary']), money(r['housing_allowance']), money(r['other_earnings']), money(r['deductions']), money(r['net_amount'])))
        self.refresh_stats()

    def refresh_runs(self):
        if not hasattr(self,'runs_tree'): return
        for i in self.runs_tree.get_children(): self.runs_tree.delete(i)
        for r in self.db.list_payrolls():
            self.runs_tree.insert('', 'end', values=(r['id'], r['payroll_month'], r['value_date'], r['employee_count'], money(r['total_amount']), r['file_path'], r['created_at']))

    def field_data(self):
        return {k: (w.get() if hasattr(w,'get') else '') for k,w in self.fields.items()}

    def clear_form(self):
        self.selected_employee_id=None
        for k,w in self.fields.items():
            if isinstance(w, ttk.Combobox): w.set('غير سعودي')
            else: w.delete(0,'end')

    def on_select_employee(self, event=None):
        sel = self.tree.selection()
        if not sel: return
        emp_id = int(sel[0]); row=self.db.get_employee(emp_id)
        if not row: return
        self.selected_employee_id=emp_id
        mapping = {
            'name': row['name'], 'gov_id': row['gov_id'], 'iban': row['iban'], 'nationality': row['nationality'],
            'worker_type': row['worker_type'], 'basic_salary': money(row['basic_salary']), 'housing_allowance': money(row['housing_allowance']),
            'other_earnings': money(row['other_earnings']), 'deductions': money(row['deductions'])
        }
        for k,v in mapping.items():
            w=self.fields[k]
            if isinstance(w, ttk.Combobox): w.set(v or 'غير سعودي')
            else: w.delete(0,'end'); w.insert(0,str(v))

    def validate_employee(self, data):
        errors=[]
        if not data.get('name'): errors.append('اسم العامل مطلوب')
        if not is_valid_iban(data.get('iban','')): errors.append('الآيبان يجب أن يبدأ SA ويتكون من 24 خانة')
        if data.get('gov_id') and not is_valid_gov_id(data.get('gov_id')): errors.append('رقم الهوية/الإقامة غالبًا يجب أن يكون 10 أرقام')
        return errors

    def save_employee(self):
        data=self.field_data(); errors=self.validate_employee(data)
        if errors:
            if not messagebox.askyesno('تنبيه', '\n'.join(errors)+'\n\nهل تريد الحفظ رغم ذلك؟'): return
        self.db.upsert_employee(data, self.selected_employee_id)
        self.refresh_employees(); self.clear_form(); messagebox.showinfo('تم', 'تم حفظ بيانات العامل بنجاح')

    def delete_selected(self):
        if not self.selected_employee_id:
            messagebox.showwarning('تنبيه','اختر عامل أولاً'); return
        if messagebox.askyesno('تأكيد','هل تريد حذف العامل المحدد؟'):
            self.db.delete_employee(self.selected_employee_id); self.clear_form(); self.refresh_employees()

    def import_excel(self):
        path=filedialog.askopenfilename(title='اختر ملف العمال Excel', filetypes=[('Excel files','*.xls *.xlsx'),('All files','*.*')])
        if not path: return
        try:
            rows=parse_rajhi_excel(path)
            if not rows: raise ValueError('لم يتم العثور على عمال داخل الملف')
            count=self.db.bulk_import(rows)
            self.refresh_all()
            messagebox.showinfo('تم الاستيراد', f'تم استيراد/تحديث {count} عامل بنجاح')
        except Exception as e:
            messagebox.showerror('خطأ في الاستيراد', str(e))

    def bulk_edit_dialog(self):
        win=tk.Toplevel(self); win.title('تعديل جماعي'); win.geometry('430x260'); win.configure(bg=BG); win.resizable(False,False)
        tk.Label(win,text='تعديل جماعي لكل العمال الحاليين',bg=BG,fg=TEXT,font=('Tahoma',14,'bold')).pack(pady=12)
        frame=tk.Frame(win,bg=PANEL,padx=12,pady=12); frame.pack(fill='x',padx=12)
        mode=ttk.Combobox(frame,values=['زيادة بدل آخر بمبلغ ثابت','تغيير بدل السكن لكل العمال','تغيير الراتب الأساسي لكل العمال'],state='readonly',justify='right'); mode.set('زيادة بدل آخر بمبلغ ثابت'); mode.pack(fill='x',pady=8)
        amount=self._entry(frame,20); amount.pack(fill='x',pady=8); amount.insert(0,'0')
        def apply():
            import sqlite3
            val=float(amount.get() or 0); m=mode.get()
            if not messagebox.askyesno('تأكيد','سيتم تطبيق التعديل على كل العمال. متابعة؟'): return
            if m.startswith('زيادة'):
                self.db.conn.execute('UPDATE employees SET other_earnings=other_earnings+?, updated_at=CURRENT_TIMESTAMP',(val,))
            elif 'السكن' in m:
                self.db.conn.execute('UPDATE employees SET housing_allowance=?, updated_at=CURRENT_TIMESTAMP',(val,))
            else:
                self.db.conn.execute('UPDATE employees SET basic_salary=?, updated_at=CURRENT_TIMESTAMP',(val,))
            self.db.conn.commit(); self.db.log('bulk_edit',f'{m}: {val}'); self.refresh_all(); win.destroy()
        self._btn(frame,'تطبيق التعديل',apply,bg=PURPLE,width=16).pack(pady=10)

    def export_txt(self):
        try:
            path=filedialog.asksaveasfilename(title='حفظ ملف TXT', defaultextension='.txt', filetypes=[('Text files','*.txt')], initialfile=f"rajhi_wages_{datetime.now().strftime('%Y%m%d_%H%M')}.txt")
            if not path: return
            out=generate_txt(self.db,self.export_month.get(),self.export_value_date.get(),self.export_debit_date.get(),path)
            self.refresh_runs(); self.export_status.config(text=f'تم توليد الملف بنجاح: {out}', fg=GOLD)
            messagebox.showinfo('تم', f'تم توليد ملف TXT بنجاح\n{out}')
        except Exception as e:
            messagebox.showerror('خطأ في التصدير', str(e))

    def save_settings(self):
        data={k:w.get() for k,w in self.settings_entries.items()}
        self.db.save_settings(data); messagebox.showinfo('تم','تم حفظ الإعدادات')

    def choose_shared_db(self):
        path=filedialog.asksaveasfilename(title='اختيار/إنشاء قاعدة البيانات المشتركة',defaultextension='.db',filetypes=[('SQLite DB','*.db')],initialfile='rajhi_wages_shared.db')
        if not path: return
        if not os.path.exists(path): shutil.copy2(self.db.path, path)
        self.db.close(); self.db=Database(path)
        self.settings_entries['shared_db_path'].delete(0,'end'); self.settings_entries['shared_db_path'].insert(0,path)
        self.db.set_setting('shared_db_path',path); self.refresh_all(); messagebox.showinfo('تم','تم ربط البرنامج بقاعدة البيانات المشتركة')

    def backup_db(self):
        path=self.db.backup(); messagebox.showinfo('تم','تم إنشاء نسخة احتياطية:\n'+path)

    def open_exports(self):
        path=os.path.join(app_base_dir(),'exports')
        os.makedirs(path,exist_ok=True)
        os.startfile(path)


def run_app():
    app=PremiumRajhiApp()
    app.mainloop()
