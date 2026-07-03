# Полностью невидимый режим — запуск на другом рабочем столе

## Вариант 1: Простой (рекомендуется)

```bash
braincli-invisible.bat
```

Или через PowerShell:
```bash
powershell -ExecutionPolicy Bypass -File braincli-invisible.ps1
```

Это запустит:
- Python через `pythonw.exe` (без консоли)
- PowerShell скрипт скроет все Chrome окна через Win32 API

**Как пользоваться:**
- Открой PowerShell/Terminal
- Запусти `braincli-invisible.ps1`
- PowerShell окно останется для ввода команд
- Браузер будет полностью скрыт

## Вариант 2: Виртуальный рабочий стол

```bash
braincli-workspace.bat
```

Это создаст новый виртуальный рабочий стол и запустит всё там.

**Переключение между рабочими столами:**
- `Ctrl + Win + →` — следующий рабочий стол
- `Ctrl + Win + ←` — предыдущий рабочий стол
- `Ctrl + Win + D` — создать новый
- `Ctrl + Win + F4` — закрыть текущий

## Если session истекла

```bash
python clickup_capture.py
```

После авторизации запусти снова `braincli-invisible.bat`.

## Глобальная команда

После установки (`install.bat`) можешь использовать:
```bash
braincli
```

Но это откроет браузер на текущем рабочем столе (минимизированный).

Для полностью скрытого режима используй `braincli-invisible.bat`.
