# ClickUp Brain AI Agent

**Полноценный AI ассистент с сессиями и памятью** — полный аналог Claude Code.

## 🚀 Быстрый старт

```bash
# 1. Клонируй репозиторий
git clone https://github.com/decaypulse/clickup-brain-cli.git
cd clickup-brain-cli

# 2. Установи (Windows)
install.bat

# 3. Авторизуйся (один раз)
python clickup_capture.py

# 4. Перезапусти терминал, затем запускай:
braincli
```

## ✨ Возможности

- 🧠 **Сессии и история** — все разговоры сохраняются в SQLite
- 📝 **Память** — можешь продолжить с того места где остановился
- 👻 **Невидимый браузер** — работает в фоне, не мешает
- 🎨 **Markdown рендеринг** — красивый вывод с подсветкой
- 🔄 **Постоянный агент** — не одноразовые вопросы, а полноценный ассистент

## 📋 Команды

| Команда | Описание |
|---------|----------|
| `/newsession` | Создать новую сессию |
| `/sessions` | Список всех сессий (с интерактивным выбором) |
| `/load <id>` | Загрузить сессию по ID |
| `/history` | История текущей сессии |
| `/help` | Справка |
| `/clear` | Очистить экран |
| `/exit` | Выход |

### Быстрые алиасы
- `/new` → `/newsession`
- `/ls` → `/sessions`
- `/h` → `/history`
- `/c` → `/clear`
- `/q` → `/exit`

## 💡 Пример работы

```bash
❯ braincli
╭─────────────────────────────────────────────────╮
│                                                 │
│  ClickUp Brain AI Agent                         │
│  Полноценный AI ассистент с сессиями и памятью  │
│                                                 │
╰─────────────────────────────────────────────────╯

✅ Браузер инициализирован (невидимый)
✅ Подключено к AI Brain

Введите сообщение или /help

❯ /newsession
✅ Новая сессия: a1b2c3d4

❯ Объясни async/await в Python
[AI думает...]

async/await — это синтаксис для работы с асинхронным кодом...

❯ /sessions
┌─────────────────────────────────────────┐
│ Сессии                                  │
├─────┬──────────────┬────────────────────┤
│ #   │ Название     │ ID                 │
├─────┼──────────────┼────────────────────┤
│ 1   │ Проект X     │ a1b2c3d4           │
│ 2   │ Python API   │ e5f6g7h8           │
└─────┴──────────────┴────────────────────┘
Выберите номер (1-2): 1
✅ Загружена сессия: Проект X

История:
👤 Объясни async/await
🤖 async/await — это синтаксис...

❯ Продолжим с того места где остановились
```

## 🛠 Установка (вручную)

Если `install.bat` не работает:

```bash
# Зависимости
pip install playwright rich prompt_toolkit requests

# Браузер
python -m playwright install chromium

# Авторизация
python clickup_capture.py

# Запуск
python clickup_agent.py
```

## 📦 Структура проекта

```
clickup-brain-cli/
├── clickup_agent.py        # Основной агент (headless)
├── clickup_capture.py      # Авторизация (один раз)
├── clickup_agent.bat       # Launcher для Windows
├── install.bat             # Установщик
├── setup.py                # Python package
├── browser_profile/        # Сессия браузера (невидимый)
├── sessions.db             # SQLite база сессий
└── .cli_history            # История команд
```

## ⚠️ Проблемы

### Браузер открывается (не headless)
Ты запустил **старую** `clickup_cli.py` вместо новой `clickup_agent.py`:
```bash
# Неправильно (видимый браузер):
python clickup_cli.py

# Правильно (невидимый):
python clickup_agent.py
# или
braincli
```

### Rate limit
ClickUp ограничивает запросы. Если видишь `Rate limit`, подожди 1-2 минуты.

### Сессия истекла
Если браузер разлогинился:
```bash
python clickup_capture.py
```

### Команда `braincli` не работает
Перезапусти терминал после установки — PATH должен обновиться.

Или используй полный путь:
```bash
python C:\Users\decyp\Desktop\clickup-cli\clickup_agent.py
```

## 🔐 Авторизация

Запусти **один раз**:
```bash
python clickup_capture.py
```

Откроется браузер — войди в ClickUp и закрой окно. Сессия сохранится в `browser_profile/`.

## 📊 База данных

Все сессии хранятся в `sessions.db` (SQLite):

```sql
-- Таблица сессий
sessions (id, title, created_at, updated_at)

-- Таблица сообщений
messages (id, session_id, role, content, timestamp)
```

Можешь делать backup:
```bash
copy sessions.db sessions.db.backup
```

## 🆚 Отличия от clickup_cli.py

| Функция | clickup_cli.py | clickup_agent.py |
|---------|----------------|------------------|
| Сессии | ❌ | ✅ |
| История | Только команды | ✅ Все сообщения |
| Память | ❌ | ✅ SQLite |
| Браузер | **Видимый** | **Невидимый** |
| Назначение | Быстрые вопросы | **Постоянный агент** |

## 🛣 Roadmap

- [ ] Экспорт сессий в Markdown
- [ ] Поиск по истории
- [ ] Теги для сессий
- [ ] MCP интеграция (чтение файлов)
- [ ] Плагины и инструменты

## 📄 Лицензия

MIT

## 🤝 Поддержка

Проблемы? Открой [issue](https://github.com/decaypulse/clickup-brain-cli/issues).
