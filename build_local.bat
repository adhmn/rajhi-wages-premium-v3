@echo off
chcp 65001
python -m pip install --upgrade pip
pip install -r requirements.txt
pyinstaller --onefile --windowed --name "Rajhi-Wages-Premium" --hidden-import openpyxl --hidden-import xlrd run.py
pause
