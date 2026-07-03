# Умная авторизация ClickUp Brain AI Agent

## Как это работает

### Первый запуск (нет авторизации)

```bash
python clickup_agent.py --interactive
```

1. Браузер открывается **видимым**
2. Ты входишь в аккаунт ClickUp вручную
3. После успешного входа браузер **автоматически скрывается**
4. Сессия сохраняется в `browser_profile/`

### Последующие запуски (уже авторизован)

```bash
braincli
```

или

```bash
python clickup_agent.py
```

1. Браузер проверяет сохранённую сессию
2. Если авторизация действительна → **сразу скрытый режим**
3. Если сессия истекла → просит запустить с `--interactive`

### Смена аккаунта

```bash
python clickup_agent.py
```

В REPL режиме:
```
❯ /logout
🔄 Выход из аккаунта...
✅ Профиль браузера удалён
✅ Готово! Перезапусти braincli для входа с новым аккаунтом
```

Затем:
```bash
python clickup_agent.py --interactive
```

## Команды

| Команда | Описание |
|---------|----------|
| `--interactive` | Показать браузер для авторизации |
| `/logout` | Выйти из аккаунта и очистить профиль |
| `/sessions` | Список сохранённых сессий |
| `/load <id>` | Загрузить сессию |
| `/newsession` | Создать новую сессию |

## Файлы

- `browser_profile/` — сохранённая сессия браузера (cookies, localStorage)
- `sessions.db` — база данных твоих сессий (история сообщений)
- `.gitignore` — исключает `browser_profile/` из Git

## Примеры

### Первый раз

```bash
git clone https://github.com/decaypulse/clickup-brain-cli.git
cd clickup-brain-cli
install.bat
python clickup_agent.py --interactive
# Браузер откроется, войди в аккаунт
# После входа браузер скроется автоматически
```

### Обычное использование

```bash
braincli
❯ Привет, как дела?
🤖 Привет! Всё отлично, чем могу помочь?
❯ /exit
```

### Смена аккаунта

```bash
braincli
❯ /logout
🔄 Выход из аккаунта...
✅ Профиль браузера удалён

python clickup_agent.py --interactive
# Войди с новым аккаунтом
```

## Решение проблем

### "Требуется авторизация"

```bash
python clickup_agent.py --interactive
```

### Браузер не скрывается

Проверь что PowerShell разрешён:
```bash
powershell -ExecutionPolicy Bypass -Command "Get-Process chrome"
```

### Сессия не сохраняется

Убедись что `browser_profile/` не в `.gitignore` (должен быть исключён из Git, но существовать локально).

## Технические детали

- **Persistent Context**: Playwright сохраняет cookies, localStorage, sessionStorage
- **Win32 API**: PowerShell скрывает окно через `ShowWindow(hWnd, 0)`
- **Проверка авторизации**: Проверяет URL после открытия ClickUp (если `/login` → не авторизован)
- **Таймаут**: 5 минут на авторизацию в интерактивном режиме
