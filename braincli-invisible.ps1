# Скрытый запуск ClickUp Brain AI Agent через PowerShell
# Полностью скрывает и консоль, и браузер

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonScript = Join-Path $scriptDir "clickup_agent.py"

# Запуск через pythonw.exe (без консоли)
$pythonProcess = Start-Process pythonw.exe -ArgumentList "`"$pythonScript`"" -WorkingDirectory $scriptDir -PassThru -WindowStyle Hidden

# Ждём 2 секунды пока браузер запустится
Start-Sleep -Seconds 2

# Скрываем все Chrome/Chromium окна
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Win32 {
    [DllImport("user32.dll")]
    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
}
"@

Get-Process | Where-Object {
    $_.ProcessName -like "*chrome*" -or $_.ProcessName -like "*chromium*"
} | ForEach-Object {
    if ($_.MainWindowHandle -ne 0) {
        [Win32]::ShowWindow($_.MainWindowHandle, 0)  # 0 = SW_HIDE
    }
}

Write-Host "✅ ClickUp Brain AI Agent запущен в скрытом режиме" -ForegroundColor Green
Write-Host "Используй команды в этой консоли для общения с AI" -ForegroundColor Cyan
