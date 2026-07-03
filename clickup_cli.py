#!/usr/bin/env python3
"""
ClickUp AI Brain CLI — клон Claude Code
Использование:
  python clickup_cli.py "Твой вопрос"
  python clickup_cli.py                    # интерактивный режим (REPL)
"""
import sys
import json
import time
import re
import argparse
import signal
from pathlib import Path
from typing import Optional
from playwright.sync_api import sync_playwright
from rich.console import Console
from rich.markdown import Markdown
from rich.live import Live
from rich.spinner import Spinner
from rich.panel import Panel
from rich.text import Text
from rich.layout import Layout
from rich.table import Table
from rich.align import Align
from rich import box
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.styles import Style

CLI_DIR = Path(__file__).parent
PROFILE_DIR = CLI_DIR / "browser_profile"
BASE_URL = "https://app.clickup.com/90121869092/ai/brain"
HISTORY_FILE = CLI_DIR / ".cli_history"

console = Console()

# Prompt toolkit style
style = Style.from_dict({
    'prompt': '#00ff00 bold',
})


def signal_handler(sig, frame):
    """Обработка Ctrl+C"""
    console.print("\n[yellow]⚠️  Прервано пользователем[/yellow]")
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)


def find_chat_links(page):
    """Ищет доступные чаты в сайдбаре"""
    return page.evaluate('''() => {
        const links = document.querySelectorAll('a.recent-item[href*="conversationId="]');
        return Array.from(links).map(l => ({
            href: l.getAttribute('href'),
            text: (l.innerText || '').trim()
        }));
    }''')


def wait_for_sidebar(page, timeout=15):
    """Ждёт загрузки сайдбара с чатами"""
    for i in range(timeout):
        chats = find_chat_links(page)
        if chats:
            return chats
        time.sleep(1)
    return []


def open_chat(page, chat_id=None, new_chat=False):
    """Открывает конкретный чат, создаёт новый, или открывает первый доступный"""
    page.goto(BASE_URL, wait_until="domcontentloaded", timeout=60000)
    time.sleep(3)

    # Проверяем авторизацию
    if "/login" in page.url:
        return False

    if new_chat:
        return True

    if chat_id:
        url = f"{BASE_URL}?conversationId={chat_id}"
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        time.sleep(5)
        return True

    # Ждём сайдбар и открываем первый чат
    chats = wait_for_sidebar(page)
    if chats:
        first_chat = chats[0]
        page.goto(first_chat['href'], wait_until="domcontentloaded", timeout=60000)
        time.sleep(5)
        return True

    return True


def find_input(page):
    """Ищет Quill editor поле ввода"""
    selectors = [
        '.ql-editor[contenteditable="true"]',
        'div.ql-editor',
        '[contenteditable="true"]',
    ]

    for attempt in range(20):
        for sel in selectors:
            try:
                els = page.query_selector_all(sel)
                for el in els:
                    if el.is_visible():
                        return el
            except Exception:
                continue
        time.sleep(1)

    return None


def extract_body_messages(page):
    """Извлекает последнее сообщение Brain из body текста"""
    body = page.evaluate('() => document.body.innerText')
    if not body:
        return ""

    # Проверяем rate limit
    if 'Rate limit reached' in body:
        return "⚠️ Rate limit! Подожди немного и попробуй снова."

    # Структура: user message → "Thinking" → "Brain" → AI response
    parts = re.split(r'\nBrain\n', body)
    if len(parts) >= 2:
        last_response = parts[-1].strip()
        # Убираем trailing UI элементы
        for marker in ['\nLike\n', '\nDislike\n', '\nFollow ups\n', '\nMax\n', '\n===',
                      '\nInvite', '\nUpgrade', '\nAsk or Create', '\nConnections\n',
                      '\nBrain AI uses']:
            idx = last_response.find(marker)
            if idx != -1:
                last_response = last_response[:idx].strip()
        # Убираем статус-индикаторы ClickUp в начале
        for prefix in ["Working\n", "Cookin'\n", 'Cooking\n', "Thinkin'\n",
                      'Thinking\n', 'Pondering\n', 'Reasoning\n']:
            if last_response.startswith(prefix):
                last_response = last_response[len(prefix):].strip()
        # Убираем одиночные слова-статусы в начале
        if last_response in ['Working', "Cookin'", 'Cooking', "Thinkin'",
                             'Thinking', 'Pondering', 'Reasoning', '']:
            return ""
        return last_response

    return ""


def send_message_with_stream(page, text, timeout=120):
    """Отправляет сообщение и стримит ответ в реальном времени"""
    input_el = find_input(page)
    if not input_el:
        raise RuntimeError("Не могу найти поле ввода (пробовал 20 сек)")

    # Запоминаем ТЕКСТ последнего ответа ПЕРЕД отправкой
    prev_response = extract_body_messages(page)
    prev_body_len = page.evaluate('() => document.body.innerText.length')

    # Кликаем и вводим текст
    input_el.click()
    time.sleep(0.5)

    # Очищаем поле
    page.keyboard.press("Control+a")
    time.sleep(0.2)
    page.keyboard.press("Backspace")
    time.sleep(0.3)

    # Вводим текст
    input_el.type(text, delay=20)
    time.sleep(1)

    # Отправляем
    page.keyboard.press("Control+Enter")

    # Стриминг ответа
    last_response = ""
    stable_count = 0
    start_time = time.time()

    console.print("[dim]📤 Отправлено, жду ответ...[/dim]")

    with Live(Spinner("dots", text="[cyan]AI думает...[/cyan]"), console=console, refresh_per_second=10, transient=True) as live:
        for i in range(timeout // 2):
            time.sleep(2)

            try:
                # Проверяем rate limit сразу
                has_rate_limit = page.evaluate("() => document.body.innerText.includes('Rate limit reached')")
                if has_rate_limit:
                    return "⚠️ Rate limit! Подожди немного и попробуй снова."

                # Проверяем статус только в ПОСЛЕДНЕМ блоке
                status = page.evaluate(r'''() => {
                    const body = document.body.innerText;
                    const parts = body.split('\nBrain\n');
                    const lastBlock = parts[parts.length - 1] || '';
                    const statusWords = ['Working', 'Cooking', 'Pondering', 'Thinking', "Cookin'", "Thinkin'", 'Reasoning'];
                    for (const w of statusWords) {
                        if (lastBlock.trim() === w || lastBlock.startsWith(w + '\n')) return w;
                    }
                    return null;
                }''')

                if status:
                    elapsed = int(time.time() - start_time)
                    live.update(Spinner("dots", text=f"[cyan]AI {status.lower()}... ({elapsed}с)[/cyan]"))
                    stable_count = 0
                    continue

                # Извлекаем текущий ответ
                current = extract_body_messages(page)

                # Проверяем что ответ НОВЫЙ (не тот что был до отправки)
                if current and current != prev_response and len(current) > 0:
                    if current == last_response:
                        stable_count += 1
                        if stable_count >= 2:  # Стабилен 4 секунды
                            return current
                    else:
                        stable_count = 0
                        last_response = current
                        # Показываем стриминг
                        live.update(Markdown(f"**[ответ появляется...]**\n\n{current}"))
            except Exception as e:
                if "crashed" in str(e).lower():
                    live.update(Spinner("dots", text="[yellow]⚠️  Страница крашнулась, восстанавливаю...[/yellow]"))
                    time.sleep(2)
                    continue
                raise

    # Финальная попытка
    if not last_response:
        last_response = extract_body_messages(page)

    return last_response.strip() if last_response else "(ответ не получен)"


def show_help():
    """Показывает справку"""
    help_text = """
# Справка по ClickUp Brain CLI

## Команды

| Команда | Описание |
|---------|----------|
| `/help`, `/h` | Показать эту справку |
| `/clear`, `/c` | Очистить экран |
| `/exit`, `/quit`, `/q` | Выйти из CLI |
| `/new` | Создать новый чат |
| `/list` | Список доступных чатов |
| `/chat <id>` | Переключиться на чат по ID |

## Горячие клавиши

- `Ctrl+C` — прервать текущий запрос
- `↑` / `↓` — навигация по истории
- `Tab` — автодополнение из истории

## Примеры

```
❯ Как написать функцию на Python?
❯ Объясни разницу между async и threading
❯ /list
```
"""
    console.print(Markdown(help_text))


def show_chat_list(page):
    """Показывает список доступных чатов"""
    chats = find_chat_links(page)
    if not chats:
        console.print("[yellow]⚠️  Нет доступных чатов[/yellow]")
        return

    table = Table(title="Доступные чаты", box=box.ROUNDED)
    table.add_column("ID", style="cyan", no_wrap=True)
    table.add_column("Название", style="white")

    for chat in chats:
        # Извлекаем ID из href
        match = re.search(r'conversationId=(\d+)', chat['href'])
        chat_id = match.group(1) if match else "N/A"
        table.add_row(chat_id, chat['text'])

    console.print(table)


def main():
    parser = argparse.ArgumentParser(description="ClickUp AI Brain CLI")
    parser.add_argument("message", nargs="*", help="Сообщение для AI Brain")
    parser.add_argument("--chat-id", help="ID конкретного чата")
    parser.add_argument("--new", action="store_true", help="Создать новый чат")
    parser.add_argument("--timeout", type=int, default=120, help="Таймаут ожидания ответа (сек)")
    args = parser.parse_args()

    if not PROFILE_DIR.exists():
        console.print("[red]❌ Сессия не найдена! Запусти сначала: python clickup_capture.py[/red]")
        sys.exit(1)

    # Заголовок
    console.print()
    console.print(Panel.fit(
        "[bold cyan]ClickUp Brain CLI[/bold cyan]\n"
        "[dim]Версия 2.0 | Аналог Claude Code[/dim]",
        border_style="cyan",
        padding=(1, 2)
    ))
    console.print()

    # Инициализация Playwright
    console.print("[dim]🔗 Подключение к ClickUp Brain...[/dim]")
    p = sync_playwright().start()
    ctx = p.chromium.launch_persistent_context(
        str(PROFILE_DIR),
        headless=False,
        viewport={"width": 1400, "height": 900},
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
    )
    page = ctx.pages[0] if ctx.pages else ctx.new_page()

    try:
        if not open_chat(page, chat_id=args.chat_id, new_chat=args.new):
            console.print("[red]❌ Сессия истекла! Запусти: python clickup_capture.py[/red]")
            sys.exit(1)

        console.print("[green]✅ Подключено к AI Brain[/green]\n")

        # Одно сообщение или REPL
        msg = " ".join(args.message) if args.message else ""

        if msg:
            # Одно сообщение
            console.print(Panel(f"[bold]{msg}[/bold]", title="[bold cyan]❯[/bold cyan]", border_style="cyan"))
            try:
                response = send_message_with_stream(page, msg, timeout=args.timeout)
                console.print()
                console.print(Markdown(response))
                console.print()
            except KeyboardInterrupt:
                console.print("\n[yellow]⚠️  Прервано[/yellow]")
            except Exception as e:
                console.print(f"\n[red]❌ Ошибка: {e}[/red]\n")
        else:
            # REPL режим
            session = PromptSession(
                history=FileHistory(str(HISTORY_FILE)),
                auto_suggest=AutoSuggestFromHistory(),
                style=style
            )

            console.print("[dim]Введите сообщение или /help для справки[/dim]\n")

            while True:
                try:
                    user_input = session.prompt('❯ ', style=style).strip()
                    if not user_input:
                        continue

                    # Команды
                    if user_input.lower() in ['/exit', '/quit', '/q', 'exit', 'quit']:
                        break
                    elif user_input.lower() in ['/help', '/h']:
                        show_help()
                        continue
                    elif user_input.lower() in ['/clear', '/c']:
                        console.clear()
                        continue
                    elif user_input.lower() == '/new':
                        console.print("[dim]🔄 Создание нового чата...[/dim]")
                        if open_chat(page, new_chat=True):
                            console.print("[green]✅ Новый чат создан[/green]\n")
                        else:
                            console.print("[red]❌ Не удалось создать чат[/red]\n")
                        continue
                    elif user_input.lower() == '/list':
                        show_chat_list(page)
                        console.print()
                        continue
                    elif user_input.lower().startswith('/chat '):
                        chat_id = user_input[6:].strip()
                        console.print(f"[dim]🔄 Переключение на чат {chat_id}...[/dim]")
                        if open_chat(page, chat_id=chat_id):
                            console.print("[green]✅ Переключено[/green]\n")
                        else:
                            console.print("[red]❌ Чат не найден[/red]\n")
                        continue

                    # Обычное сообщение
                    console.print()
                    try:
                        response = send_message_with_stream(page, user_input, timeout=args.timeout)
                        console.print()
                        console.print(Markdown(response))
                        console.print()
                    except KeyboardInterrupt:
                        console.print("\n[yellow]⚠️  Прервано[/yellow]\n")
                    except Exception as e:
                        console.print(f"\n[red]❌ Ошибка: {e}[/red]\n")

                except KeyboardInterrupt:
                    break
                except EOFError:
                    break

    finally:
        ctx.close()
        p.stop()

    console.print("\n[dim]👋 До встречи![/dim]\n")


if __name__ == "__main__":
    main()
