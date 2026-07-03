@echo off
REM ClickUp AI Agent Launcher
REM Использование:
REM   clickup-agent.bat "Твой вопрос"
REM   clickup-agent.bat (интерактивный режим)
REM   clickup-agent.bat --session <id> (загрузить сессию)

setlocal enabledelayedexpansion

cd /d "C:\Users\decyp\Desktop\clickup-cli"

REM Проверяем наличие Python
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo ERROR: Python не найден в PATH
    pause
    exit /b 1
)

REM Проверяем наличие зависимостей
python -c "import playwright, rich, prompt_toolkit, requests" >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo Устанавливаю зависимости...
    pip install playwright rich prompt_toolkit requests
    python -m playwright install chromium
)

REM Проверяем наличие browser_profile
if not exist "browser_profile" (
    echo [!] browser_profile не найден. Запусти сначала clickup_capture.py
    pause
    exit /b 1
)

REM Запускаем агент
if "%~1"=="" (
    python clickup_agent.py
) else (
    python clickup_agent.py %*
)
