@echo off
chcp 65001 >nul
cd /d "%~dp0"
python build_report_today.py
pause



