@echo off
REM Полностью скрытый запуск ClickUp Brain AI Agent
REM Использует pythonw.exe (без консоли) и PowerShell для скрытия браузера

cd /d "%~dp0"

REM Запуск через pythonw.exe (без окна консоли)
start "" pythonw.exe clickup_agent.py %*

REM Ждём 2 секунды пока браузер запустится
timeout /t 2 /nobreak >nul

REM Скрываем все Chrome окна через PowerShell
powershell -ExecutionPolicy Bypass -Command "Get-Process | Where-Object {$_.ProcessName -like '*chrome*' -or $_.ProcessName -like '*chromium*'} | ForEach-Object { if ($_.MainWindowHandle -ne 0) { Add-Type -TypeDefinition 'using System; using System.Runtime.InteropServices; public class Win32 { [DllImport(\"user32.dll\")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow); }'; [Win32]::ShowWindow($_.MainWindowHandle, 0) } }"
