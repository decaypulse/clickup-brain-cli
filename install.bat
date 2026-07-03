@echo off
REM Установка ClickUp Brain CLI
REM Запусти один раз после клонирования репозитория

setlocal enabledelayedexpansion

echo ========================================
echo  ClickUp Brain CLI - Установка
echo ========================================
echo.

REM Проверяем Python
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python не найден в PATH
    echo Установи Python 3.11+ и добавь в PATH
    pause
    exit /b 1
)

echo [1/3] Устанавливаю зависимости...
pip install -e .

echo.
echo [2/3] Устанавливаю браузер Chromium...
python -m playwright install chromium

echo.
echo [3/3] Создаю ярлык braincli...
echo Создаю braincli.bat в PATH...

REM Создаём батник в AppData (всегда в PATH)
set BAT_DIR=%APPDATA%\clickup-brain-cli
mkdir "%BAT_DIR%" >nul 2>nul

(
echo @echo off
echo cd /d "%CD%"
echo python clickup_agent.py %%*
) > "%BAT_DIR%\braincli.bat"

REM Добавляем в PATH если ещё нет
echo %PATH% | findstr /C:"%BAT_DIR%" >nul
if %ERRORLEVEL% neq 0 (
    echo Добавляю %BAT_DIR% в PATH...
    setx PATH "%PATH%;%BAT_DIR%" >nul
    echo.
    echo [!] Перезапусти терминал чтобы PATH обновился
)

echo.
echo ========================================
echo  Установка завершена!
echo ========================================
echo.
echo Теперь можешь запускать:
echo   braincli
echo.
echo Первый запуск:
echo   python clickup_capture.py  (авторизация)
echo   braincli                    (запуск агента)
echo.
pause
