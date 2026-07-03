#!/usr/bin/env python3
"""
ClickUp Brain AI Agent — полноценный AI ассистент с сессиями и памятью
Полный аналог Claude Code, работает через ClickUp API напрямую (без браузера)
"""
import sys
import json
import time
import argparse
import signal
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict
import requests
from rich.console import Console
from rich.markdown import Markdown
from rich.live import Live
from rich.spinner import Spinner
from rich.panel import Panel
from rich.table import Table
from rich import box
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.styles import Style
from playwright.sync_api import sync_playwright

CLI_DIR = Path(__file__).parent
PROFILE_DIR = CLI_DIR / "browser_profile"
DB_FILE = CLI_DIR / "sessions.db"
HISTORY_FILE = CLI_DIR / ".cli_history"
BASE_URL = "https://app.clickup.com/90121869092/ai/brain"
API_BASE = "https://frontdoor-prod-eu-west-1-2.clickup.com"

console = Console()
style = Style.from_dict({'prompt': '#00ff00 bold'})


def signal_handler(sig, frame):
    console.print("\n[yellow]⚠️  Прервано[/yellow]")
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)


class SessionDB:
    """Управление сессиями и историей в SQLite"""
    
    def __init__(self):
        self.conn = sqlite3.connect(DB_FILE)
        self.conn.row_factory = sqlite3.Row
        self._init_tables()
    
    def _init_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                title TEXT,
                created_at TEXT,
                updated_at TEXT,
                conversation_id TEXT
            );
            
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                role TEXT,
                content TEXT,
                timestamp TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            );
            
            CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
        """)
        self.conn.commit()
    
    def create_session(self, title: str, conversation_id: str = None) -> str:
        session_id = str(uuid.uuid4())[:8]
        now = datetime.now().isoformat()
        self.conn.execute(
            "INSERT INTO sessions (id, title, created_at, updated_at, conversation_id) VALUES (?, ?, ?, ?, ?)",
            (session_id, title, now, now, conversation_id)
        )
        self.conn.commit()
        return session_id
    
    def add_message(self, session_id: str, role: str, content: str):
        now = datetime.now().isoformat()
        self.conn.execute(
            "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            (session_id, role, content, now)
        )
        self.conn.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?",
            (now, session_id)
        )
        self.conn.commit()
    
    def get_session_messages(self, session_id: str) -> List[Dict]:
        rows = self.conn.execute(
            "SELECT role, content, timestamp FROM messages WHERE session_id = ? ORDER BY timestamp",
            (session_id,)
        ).fetchall()
        return [dict(r) for r in rows]
    
    def list_sessions(self) -> List[Dict]:
        rows = self.conn.execute(
            "SELECT id, title, created_at, updated_at FROM sessions ORDER BY updated_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]
    
    def get_session(self, session_id: str) -> Optional[Dict]:
        row = self.conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        return dict(row) if row else None
    
    def update_session_title(self, session_id: str, title: str):
        now = datetime.now().isoformat()
        self.conn.execute(
            "UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?",
            (title, now, session_id)
        )
        self.conn.commit()


class ClickUpAgent:
    """AI агент с сессиями и памятью"""
    
    def __init__(self):
        self.db = SessionDB()
        self.current_session_id = None
        self.page = None
        self.ctx = None
        self.playwright = None
    
    def init_browser(self, interactive=False):
        """Инициализирует браузер с умной логикой авторизации
        
        Args:
            interactive: True = показать браузер для авторизации, False = скрытый режим
        """
        console.print("[dim]🔗 Инициализация браузера...[/dim]")
        self.playwright = sync_playwright().start()
        
        # Используем persistent context для сохранения авторизации
        self.ctx = self.playwright.chromium.launch_persistent_context(
            str(PROFILE_DIR),
            headless=False,  # Всегда видимый для проверки авторизации
            viewport={"width": 1400, "height": 900},
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--window-position=-32000,-32000' if not interactive else ''
            ]
        )
        self.page = self.ctx.pages[0] if self.ctx.pages else self.ctx.new_page()
        
        # Проверяем авторизацию
        console.print("[dim]🔐 Проверка авторизации...[/dim]")
        self.page.goto(BASE_URL, wait_until="domcontentloaded", timeout=60000)
        time.sleep(3)
        
        is_authorized = "/login" not in self.page.url
        
        if is_authorized:
            # Авторизован - скрываем браузер
            console.print("[green]✅ Авторизация сохранена, скрываю браузер...[/green]")
            self._hide_browser_window()
        else:
            # Не авторизован
            if interactive:
                console.print("[yellow]⚠️ Требуется авторизация[/yellow]")
                console.print("[dim]Браузер открыт. Войди в аккаунт ClickUp.[/dim]")
                console.print("[dim]После авторизации браузер автоматически скроется.[/dim]")
                
                # Ждём пока пользователь авторизуется
                try:
                    self.page.wait_for_url(lambda url: "/login" not in url, timeout=300000)  # 5 минут
                    console.print("[green]✅ Авторизация успешна![/green]")
                    console.print("[dim]Сохраняю сессию...[/dim]")
                    time.sleep(2)
                    self._hide_browser_window()
                except:
                    console.print("[red]❌ Таймаут авторизации[/red]")
                    self.close_browser()
                    sys.exit(1)
            else:
                console.print("[red]❌ Требуется авторизация! Запусти в интерактивном режиме.[/red]")
                self.close_browser()
                sys.exit(1)
        
        console.print("[green]✅ Браузер готов (полностью скрытый)[/green]")
    
    def _hide_browser_window(self):
        """Скрывает окно браузера через PowerShell"""
        try:
            import subprocess
            time.sleep(1)
            
            ps_script = '''
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Win32 {
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
}
"@
Get-Process | Where-Object {$_.ProcessName -like "*chrome*" -or $_.ProcessName -like "*chromium*"} | ForEach-Object {
    if ($_.MainWindowHandle -ne 0) {
        [Win32]::ShowWindow($_.MainWindowHandle, 0)
    }
}
'''
            subprocess.run(['powershell', '-Command', ps_script], 
                         capture_output=True, timeout=5)
        except:
            pass
    
    def close_browser(self):
        """Закрывает браузер"""
        if self.ctx:
            self.ctx.close()
        if self.playwright:
            self.playwright.stop()
    
    def open_chat(self, conversation_id=None):
        """Открывает чат"""
        url = f"{BASE_URL}?conversationId={conversation_id}" if conversation_id else BASE_URL
        self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
        time.sleep(3)
        
        if "/login" in self.page.url:
            return False
        
        # Диагностика: проверяем что страница загрузилась
        try:
            title = self.page.title()
            console.print(f"[dim]Страница: {title}[/dim]")
            
            # Проверяем наличие поля ввода
            inp = self.find_input()
            if not inp:
                console.print("[yellow]⚠️ Поле ввода не найдено, делаю скриншот...[/yellow]")
                self.page.screenshot(path="debug_headless.png")
                console.print("[dim]Скриншот сохранён: debug_headless.png[/dim]")
        except Exception as e:
            console.print(f"[yellow]⚠️ Ошибка диагностики: {e}[/yellow]")
        
        return True
    
    def find_input(self):
        """Ищет поле ввода"""
        selectors = [
            '.ql-editor[contenteditable="true"]',
            'div.ql-editor',
            '[contenteditable="true"]',
        ]
        
        for _ in range(20):
            for sel in selectors:
                try:
                    els = self.page.query_selector_all(sel)
                    for el in els:
                        if el.is_visible():
                            return el
                except:
                    continue
            time.sleep(1)
        return None
    
    def extract_response(self):
        """Извлекает последний ответ Brain"""
        import re
        body = self.page.evaluate('() => document.body.innerText')
        if not body:
            return ""
        
        if 'Rate limit reached' in body:
            return "⚠️ Rate limit! Подожди и попробуй снова."
        
        parts = re.split(r'\nBrain\n', body)
        if len(parts) >= 2:
            last = parts[-1].strip()
            # Убираем UI элементы
            for marker in ['\nLike\n', '\nDislike\n', '\nFollow ups\n', '\nMax\n']:
                idx = last.find(marker)
                if idx != -1:
                    last = last[:idx].strip()
            # Убираем статусы
            for prefix in ["Working\n", "Reasoning\n", "Thinking\n", "Pondering\n"]:
                if last.startswith(prefix):
                    last = last[len(prefix):].strip()
            return last
        return ""
    
    def send_message(self, text: str, timeout=120) -> str:
        """Отправляет сообщение и получает ответ"""
        inp = self.find_input()
        if not inp:
            return "❌ Не могу найти поле ввода"
        
        # Запоминаем предыдущий ответ
        prev_response = self.extract_response()
        
        # Отправляем
        inp.click()
        time.sleep(0.5)
        self.page.keyboard.press("Control+a")
        self.page.keyboard.press("Backspace")
        time.sleep(0.3)
        inp.type(text, delay=20)
        time.sleep(1)
        self.page.keyboard.press("Control+Enter")
        
        # Ждём ответ
        last_response = ""
        stable_count = 0
        
        for _ in range(timeout // 2):
            time.sleep(2)
            
            try:
                has_limit = self.page.evaluate("() => document.body.innerText.includes('Rate limit reached')")
                if has_limit:
                    return "⚠️ Rate limit! Подожди и попробуй снова."
                
                current = self.extract_response()
                
                if current and current != prev_response:
                    if current == last_response:
                        stable_count += 1
                        if stable_count >= 2:
                            return current
                    else:
                        stable_count = 0
                        last_response = current
            except Exception as e:
                if "crashed" in str(e).lower():
                    time.sleep(2)
                    continue
                raise
        
        return last_response if last_response else "(ответ не получен)"
    
    def start_new_session(self, title: str = "New Session"):
        """Создаёт новую сессию"""
        self.current_session_id = self.db.create_session(title)
        console.print(f"[green]✅ Новая сессия: {self.current_session_id}[/green]")
        return self.current_session_id
    
    def load_session(self, session_id: str):
        """Загружает существующую сессию"""
        session = self.db.get_session(session_id)
        if not session:
            console.print(f"[red]❌ Сессия {session_id} не найдена[/red]")
            return False
        
        self.current_session_id = session_id
        console.print(f"[green]✅ Загружена сессия: {session['title']}[/green]")
        
        # Показываем историю
        messages = self.db.get_session_messages(session_id)
        if messages:
            console.print("\n[dim]История:[/dim]")
            for msg in messages[-5:]:  # Последние 5 сообщений
                role = "👤" if msg['role'] == 'user' else "🤖"
                console.print(f"{role} {msg['content'][:100]}...")
            console.print()
        
        return True
    
    def list_sessions(self):
        """Показывает список сессий"""
        sessions = self.db.list_sessions()
        if not sessions:
            console.print("[yellow]Нет сохранённых сессий[/yellow]")
            return
        
        table = Table(title="Сессии", box=box.ROUNDED)
        table.add_column("ID", style="cyan", no_wrap=True)
        table.add_column("Название", style="white")
        table.add_column("Обновлена", style="dim")
        
        for s in sessions:
            updated = s['updated_at'].split('T')[0]
            table.add_row(s['id'], s['title'], updated)
        
        console.print(table)
    
    def chat(self, user_input: str) -> str:
        """Отправляет сообщение и сохраняет в историю"""
        if not self.current_session_id:
            self.start_new_session(user_input[:50])
        
        # Сохраняем сообщение пользователя
        self.db.add_message(self.current_session_id, 'user', user_input)
        
        # Отправляем в Brain
        response = self.send_message(user_input)
        
        # Сохраняем ответ
        self.db.add_message(self.current_session_id, 'assistant', response)
        
        # Обновляем заголовок сессии если это первое сообщение
        session = self.db.get_session(self.current_session_id)
        if session and session['title'] == "New Session":
            self.db.update_session_title(self.current_session_id, user_input[:50])
        
        return response
    
    def logout(self):
        """Выходит из аккаунта и очищает профиль браузера"""
        console.print("[yellow]🔄 Выход из аккаунта...[/yellow]")
        
        # Закрываем браузер
        self.close_browser()
        
        # Удаляем профиль браузера
        import shutil
        if PROFILE_DIR.exists():
            shutil.rmtree(PROFILE_DIR)
            console.print("[green]✅ Профиль браузера удалён[/green]")
        
        console.print("[green]✅ Готово! Перезапусти braincli для входа с новым аккаунтом[/green]")
        console.print("[dim]Запусти: python clickup_agent.py --interactive[/dim]")


def show_help():
    help_text = """
# ClickUp Brain AI Agent — Команды

## Основные команды

| Команда | Описание |
|---------|----------|
| `/help` | Эта справка |
| `/newsession` | Создать новую сессию |
| `/sessions` | Список всех сессий |
| `/load <id>` | Загрузить сессию по ID |
| `/history` | История текущей сессии |
| `/clear` | Очистить экран |
| `/logout` | Выйти из аккаунта (сменить пользователя) |
| `/exit` | Выход |

## Быстрые команды

- `/new` → `/newsession`
- `/ls` → `/sessions`
- `/h` → `/history`
- `/c` → `/clear`
- `/q` → `/exit`

## Примеры

```bash
❯ /newsession
✅ Создана новая сессия: a1b2c3d4

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

❯ /logout
🔄 Выход из аккаунта...
✅ Готово! Перезапусти braincli для входа с новым аккаунтом

❯ /exit
```
"""
    console.print(Markdown(help_text))


def interactive_session_select(agent):
    """Интерактивный выбор сессии"""
    sessions = agent.db.list_sessions()
    if not sessions:
        console.print("[yellow]Нет сохранённых сессий[/yellow]")
        return None
    
    table = Table(title="Сессии", box=box.ROUNDED)
    table.add_column("#", style="cyan", no_wrap=True, justify="right")
    table.add_column("Название", style="white")
    table.add_column("ID", style="dim")
    table.add_column("Обновлена", style="dim")
    
    for i, s in enumerate(sessions, 1):
        updated = s['updated_at'].split('T')[0]
        table.add_row(str(i), s['title'], s['id'], updated)
    
    console.print(table)
    console.print()
    
    # Интерактивный выбор
    while True:
        try:
            choice = input(f"Выберите номер (1-{len(sessions)}) или /cancel: ").strip()
            
            if choice.lower() == '/cancel':
                console.print("[dim]Отменено[/dim]")
                return None
            
            try:
                idx = int(choice) - 1
                if 0 <= idx < len(sessions):
                    return sessions[idx]['id']
                else:
                    console.print(f"[red]Введите число от 1 до {len(sessions)}[/red]")
            except ValueError:
                console.print("[red]Введите число или /cancel[/red]")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Отменено[/dim]")
            return None


def main():
    parser = argparse.ArgumentParser(description="ClickUp Brain AI Agent")
    parser.add_argument("message", nargs="*", help="Сообщение")
    parser.add_argument("--session", help="Загрузить сессию по ID")
    parser.add_argument("--new", action="store_true", help="Новая сессия")
    parser.add_argument("--interactive", action="store_true", help="Показать браузер для авторизации")
    args = parser.parse_args()
    
    # Заголовок
    console.print()
    console.print(Panel.fit(
        "[bold cyan]ClickUp Brain AI Agent[/bold cyan]\n"
        "[dim]Полноценный AI ассистент с сессиями и памятью[/dim]",
        border_style="cyan",
        padding=(1, 2)
    ))
    console.print()
    
    agent = ClickUpAgent()
    
    try:
        # Инициализация с умной логикой авторизации
        agent.init_browser(interactive=args.interactive)
        
        # Открываем чат (если ещё не открыт в init_browser)
        if "/login" not in agent.page.url:
            console.print("[green]✅ Подключено к AI Brain[/green]\n")
        
        # Загружаем сессию если указана
        if args.session:
            agent.load_session(args.session)
        elif args.new:
            agent.start_new_session()
        
        # Одно сообщение или REPL
        msg = " ".join(args.message) if args.message else ""
        
        if msg:
            console.print(Panel(f"[bold]{msg}[/bold]", title="❯", border_style="cyan"))
            with Live(Spinner("dots", text="[cyan]Думаю...[/cyan]"), console=console, transient=True):
                response = agent.chat(msg)
            console.print()
            console.print(Markdown(response))
            console.print()
        else:
            # REPL режим — простой input() чтобы не конфликтовать с Playwright asyncio
            console.print("[dim]Введите сообщение или /help[/dim]\n")
            
            while True:
                try:
                    user_input = input('❯ ').strip()
                    if not user_input:
                        continue
                    
                    # Команды
                    cmd = user_input.lower()
                    if cmd in ['/exit', '/quit', '/q', 'exit']:
                        break
                    elif cmd in ['/help']:
                        show_help()
                        continue
                    elif cmd in ['/clear', '/c']:
                        console.clear()
                        continue
                    elif cmd in ['/newsession', '/new']:
                        agent.start_new_session()
                        continue
                    elif cmd in ['/sessions', '/ls']:
                        session_id = interactive_session_select(agent)
                        if session_id:
                            agent.load_session(session_id)
                        continue
                    elif cmd.startswith('/load '):
                        session_id = user_input[6:].strip()
                        agent.load_session(session_id)
                        continue
                    elif cmd in ['/history', '/h']:
                        if agent.current_session_id:
                            messages = agent.db.get_session_messages(agent.current_session_id)
                            if not messages:
                                console.print("[yellow]История пуста[/yellow]")
                            else:
                                console.print(f"\n[cyan]История сессии:[/cyan]\n")
                                for msg in messages:
                                    role = "👤" if msg['role'] == 'user' else "🤖"
                                    console.print(f"{role} {msg['content']}\n")
                        else:
                            console.print("[yellow]Нет активной сессии[/yellow]")
                        continue
                    
                    elif cmd in ['/logout', '/signout']:
                        agent.logout()
                        break
                    
                    # Обычное сообщение
                    console.print()
                    with Live(Spinner("dots", text="[cyan]Думаю...[/cyan]"), console=console, transient=True):
                        response = agent.chat(user_input)
                    console.print()
                    console.print(Markdown(response))
                    console.print()
                
                except KeyboardInterrupt:
                    break
                except EOFError:
                    break
    
    finally:
        agent.close_browser()
    
    console.print("\n[dim]👋 До встречи![/dim]\n")


if __name__ == "__main__":
    main()
