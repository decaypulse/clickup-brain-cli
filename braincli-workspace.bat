@echo off
REM Полностью невидимый запуск ClickUp Brain AI Agent
REM Создаёт новый виртуальный рабочий стол и запускает там

cd /d "%~dp0"

echo Создаю новый виртуальный рабочий стол...
powershell -ExecutionPolicy Bypass -Command "$desktop = New-Object -ComObject 'Microsoft.Windows.Desktop'; $desktop.CreateVirtualDesktop(); Start-Sleep -Milliseconds 500"

echo Переключаюсь на новый рабочий стол...
powershell -ExecutionPolicy Bypass -Command "$desktop = New-Object -ComObject 'Microsoft.Windows.Desktop'; $desktop.SwitchToLastDesktop(); Start-Sleep -Milliseconds 500"

echo Запускаю ClickUp Brain AI Agent...
start "" pythonw.exe clickup_agent.py %*

echo ✅ ClickUp Brain AI Agent запущен на другом рабочем столе!
echo.
echo Для переключения между рабочими столами:
echo   - Ctrl + Win + Стрелка влево/вправо
echo.
echo Чтобы вернуться обратно: Ctrl + Win + ←
timeout /t 3
