# ClickUp AI Brain CLI

CLI интерфейс для ClickUp AI Brain в стиле Claude Code.

## Возможности

- 🎨 **Markdown рендеринг** — ответы форматируются с подсветкой синтаксиса
- 📡 **Стриминг** — ответы появляются в реальном времени
- 💬 **REPL режим** — интерактивный чат с историей команд
- 📜 **История** — навигация стрелками ↑↓, автодополнение Tab
- 🔧 **MCP интеграция** — AI Brain может читать файлы через туннель

## Установка

```bash
# Установить зависимости
pip install playwright rich prompt_toolkit

# Установить браузер
python -m playwright install chromium

# Авторизоваться в ClickUp (откроется браузер)
python clickup_capture.py
```

## Использование

### Одно сообщение
```bash
python clickup_cli.py "Твой вопрос"
python clickup_cli.py --chat-id 7002043329165107963 "Привет!"
```

### Интерактивный режим
```bash
python clickup_cli.py
```

### Через батку (Windows)
```cmd
clickup-cli.bat "Твой вопрос"
clickup-cli.bat
```

## Команды REPL

| Команда | Описание |
|---------|----------|
| `/help`, `/h` | Справка |
| `/list` | Список чатов |
| `/chat <id>` | Переключиться на чат |
| `/new` | Создать новый чат |
| `/clear`, `/c` | Очистить экран |
| `/exit`, `/quit`, `/q` | Выход |

## Горячие клавиши

- `Ctrl+C` — прервать запрос
- `↑` / `↓` — история команд
- `Tab` — автодополнение

## MCP туннель

AI Brain может читать файлы через MCP:

```
URL: https://4e46efbf263a6207-185-176-158-3.serveousercontent.com/sse
```

Запуск туннеля:
```cmd
start_mcp_tunnel.bat
```

## Структура

```
clickup-cli/
├── clickup_cli.py          # Основной CLI
├── clickup_capture.py      # Авторизация
├── clickup-cli.bat         # Launcher для Windows
├── browser_profile/        # Сессия браузера
└── .cli_history           # История команд
```

## Проблемы

### Rate limit
ClickUp ограничивает количество запросов. Если видишь `Rate limit reached`, подожди 1-2 минуты.

### Сессия истекла
Если браузер не авторизован:
```bash
python clickup_capture.py
```

### Туннель упал
Перезапусти:
```cmd
start_mcp_tunnel.bat
```

## Требования

- Python 3.11+
- Playwright
- rich
- prompt_toolkit
- Активный аккаунт ClickUp с AI Brain
