# ClickUp Brain AI Agent

**Полноценный AI ассистент с сессиями и памятью** — полный аналог Claude Code.

## 🚀 Быстрый старт

```bash
# 1. Клонируй репозиторий
git clone https://github.com/decaypulse/clickup-brain-cli.git
cd clickup-brain-cli

# 2. Установи зависимости
install.bat

# 3. Первый запуск (авторизация)
python clickup_agent.py --interactive
```

Браузер откроется видимым → войди в аккаунт ClickUp → браузер автоматически скроется.

## 📖 Использование

```bash
# Запуск (если уже авторизован)
braincli

# Или напрямую
python clickup_agent.py
```

### Команды

| Команда | Описание |
|---------|----------|
| `/help` | Справка |
| `/newsession` | Новая сессия |
| `/sessions` | Список сессий с интерактивным выбором |
| `/load <id>` | Загрузить сессию |
| `/history` | История текущей сессии |
| `/logout` | Выйти из аккаунта (сменить пользователя) |
| `/clear` | Очистить экран |
| `/exit` | Выход |

### Быстрые команды

- `/new` → `/newsession`
- `/ls` → `/sessions`
- `/h` → `/history`
- `/c` → `/clear`
- `/q` → `/exit`

## 🔐 Умная авторизация

### Первый запуск (нет авторизации)

```bash
python clickup_agent.py --interactive
```

- Браузер открывается **видимым**
- Ты входишь в аккаунт ClickUp
- После входа браузер **автоматически скрывается**
- Сессия сохраняется в `browser_profile/`

### Последующие запуски

```bash
braincli
```

- Проверяет сохранённую сессию
- Если действительна → **сразу скрытый режим**
- Браузер полностью невидим (скрыт через Win32 API)

### Смена аккаунта

```bash
❯ /logout
🔄 Выход из аккаунта...
✅ Профиль браузера удалён

python clickup_agent.py --interactive
```

## 📁 Структура проекта

```
clickup-brain-cli/
├── clickup_agent.py          # Основной AI агент
├── sessions.db                # База данных сессий
├── browser_profile/           # Сохранённая авторизация
├── install.bat                # Установка braincli
├── setup.py                   # Конфигурация пакета
├── SMART-AUTH.md              # Документация авторизации
├── INVISIBLE-MODE.md          # Скрытый режим
└── README.md                  # Этот файл
```

## 🛠️ Технические детали

- **Persistent Context**: Playwright сохраняет cookies, localStorage, sessionStorage
- **Win32 API**: PowerShell скрывает окно через `ShowWindow(hWnd, 0)`
- **Проверка авторизации**: Многофакторная (URL + Quill editor + UI элементы)
- **Таймаут**: 5 минут на авторизацию в интерактивном режиме

## 📚 Документация

- [SMART-AUTH.md](SMART-AUTH.md) — Умная авторизация
- [INVISIBLE-MODE.md](INVISIBLE-MODE.md) — Полностью скрытый режим

## 🔧 Требования

- Python 3.8+
- Playwright
- Rich
- Windows 10/11 (для Win32 API)

## 📝 Лицензия

MIT
