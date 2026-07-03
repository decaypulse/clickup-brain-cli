@echo off
REM ClickUp AI Brain CLI Launcher
REM Использование:
REM   clickup-cli.bat "Твой вопрос"
REM   clickup-cli.bat (интерактивный режим)

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
python -c "import playwright, rich, prompt_toolkit" >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo Устанавливаю зависимости...
    pip install playwright rich prompt_toolkit
    python -m playwright install chromium
)

REM Проверяем наличие browser_profile
if not exist "browser_profile" (
    echo [!] browser_profile не найден. Запусти сначала clickup_capture.py
    pause
    exit /b 1
)

REM Запускаем CLI
if "%~1"=="" (
    python clickup_cli.py
) else (
    python clickup_cli.py %*
)
