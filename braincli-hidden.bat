@echo off
REM Полностью скрытый запуск ClickUp Brain AI Agent
REM Использует PowerShell для запуска в скрытом режиме

cd /d "%~dp0"
powershell -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0braincli-hidden.ps1"
