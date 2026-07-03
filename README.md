# ClickUp Brain AI Agent

**Полноценный AI ассистент с сессиями и памятью** — полный аналог Claude Code.

## 🚀 Быстрый старт

```bash
# 1. Клонируй репозиторий
git clone https://github.com/decaypulse/clickup-brain-cli.git
cd clickup-brain-cli

# 2. Установи (Windows)
install.bat

# 3. Авторизуйся (один раз, браузер видимый)
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

# Авторизация (один раз, браузер видимый)
python clickup_capture.py

# Запуск агента (браузер невидимый)
python clickup_agent.py
```

## 📦 Структура проекта

```
clickup-brain-cli/
├── clickup_agent.py        # Основной агент (headless=True)
├── clickup_capture.py      # Авторизация (headless=False, один раз)
├── clickup_cli.py          # Старая версия (видимый браузер) - НЕ используй
├── clickup-agent.bat       # Launcher для Windows
├── braincli-global.bat     # Глобальная команда (если braincli не работает)
├── install.bat             # Установщик
├── setup.py                # Python package
├── browser_profile/        # Сессия браузера (невидимый)
├── sessions.db             # SQLite база сессий
└── .cli_history            # История команд
```

## ⚠️ Важно: Браузер открывается видимый?

**Причина:** Ты запустил старую `clickup_cli.py` вместо новой `clickup_agent.py`.

**Решение:**

```bash
# ❌ Неправильно (видимый браузер):
python clickup_cli.py

# ✅ Правильно (невидимый браузер):
python clickup_agent.py
# или
braincli
```

**Исключение:** `clickup_capture.py` **должен** открывать видимый браузер — это для авторизации (один раз).

## 🔧 Если `braincli` не работает

Перезапусти терминал после установки (PATH обновится).

Или используй:
```bash
# Вариант 1: прямой запуск
python clickup_agent.py

# Вариант 2: батник
braincli-global.bat

# Вариант 3: полный путь
C:\Users\decyp\Desktop\clickup-cli\clickup-agent.bat
```

## ⚠️ Проблемы

### Rate limit
ClickUp ограничивает запросы. Если видишь `Rate limit`, подожди 1-2 минуты.

### Сессия истекла
Если браузер разлогинился:
```bash
python clickup_capture.py
```

### База данных повреждена
```bash
# Удали и начни заново
del sessions.db
braincli
```

## 🔐 Авторизация

Запусти **один раз**:
```bash
python clickup_capture.py
```

Откроется браузер (видимый) — войди в ClickUp и закрой окно. Сессия сохранится в `browser_profile/`.

После этого агент будет работать с **невидимым** браузером.

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

## 🆚 Разница между файлами

| Файл | Браузер | Назначение |
|------|---------|------------|
| `clickup_agent.py` | **Невидимый** ✅ | Основной агент |
| `clickup_cli.py` | Видимый ❌ | Старая версия (не используй) |
| `clickup_capture.py` | Видимый ✅ | Авторизация (один раз) |

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
