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
    
    def init_browser(self):
        """Инициализирует браузер — автоматическая логика видимости.
        
        Если авторизован → headless (невидимый).
        Если нет → видимый браузер по центру экрана, ждём авторизации.
        """
        console.print("[dim]🔗 Инициализация браузера...[/dim]")
        self.playwright = sync_playwright().start()
        
        # Пробуем headless сначала (быстрее, невидимо)
        self.ctx = self.playwright.chromium.launch_persistent_context(
            str(PROFILE_DIR),
            headless=True,
            viewport={"width": 1400, "height": 900},
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox'
            ]
        )
        self.page = self.ctx.pages[0] if self.ctx.pages else self.ctx.new_page()
        
        # Идём на главную ClickUp — редирект на правильный workspace
        console.print("[dim]🔐 Проверка авторизации...[/dim]")
        self.page.goto("https://app.clickup.com", wait_until="domcontentloaded", timeout=60000)
        time.sleep(3)
        
        # Многофакторная проверка авторизации
        is_authorized = self._check_authorization()
        
        if is_authorized:
            # Получаем реальный URL workspace
            self._update_brain_url()
            
            # Переходим к AI Brain
            console.print("[dim]🧠 Переход к AI Brain...[/dim]")
            if not self._navigate_to_brain():
                # Если через UI не получилось — идём напрямую
                console.print("[dim]⚠ Навигация через UI не удалась, иду напрямую[/dim]")
                self.page.goto(BASE_URL, wait_until="domcontentloaded", timeout=60000)
                time.sleep(3)
            
            # Ждём загрузку страницы Brain
            try:
                self.page.wait_for_selector('textarea, [contenteditable="true"]', timeout=10000)
                console.print("[dim]✓ Страница Brain загружена[/dim]")
            except:
                console.print("[dim]⚠ Страница Brain загружается...[/dim]")
            
            console.print("[green]✅ Авторизация сохранена, браузер в headless режиме[/green]")
            console.print("[green]✅ Браузер готов[/green]")
            return
        
        # НЕ авторизован — закрываем headless и открываем видимый браузер
        console.print("[yellow]⚠️ Требуется авторизация — открываю браузер...[/yellow]")
        self.close_browser()
        
        # Запускаем видимый браузер по центру экрана
        self.playwright = sync_playwright().start()
        self.ctx = self.playwright.chromium.launch_persistent_context(
            str(PROFILE_DIR),
            headless=False,
            viewport={"width": 1400, "height": 900},
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--window-position=260,90'
            ]
        )
        self.page = self.ctx.pages[0] if self.ctx.pages else self.ctx.new_page()
        
        # Центрируем окно через PowerShell/Win32
        self._center_browser_window()
        
        console.print("[dim]Браузер открыт по центру экрана. Войди в аккаунт ClickUp.[/dim]")
        console.print("[dim]После авторизации браузер автоматически скроется.[/dim]")
        
        # Идём на главную — пользователь сам зайдёт и будет редирект на его workspace
        try:
            self.page.goto("https://app.clickup.com", wait_until="domcontentloaded", timeout=60000)
            
            console.print("[dim]Ожидание авторизации (каждые 3 сек проверяю)...[/dim]")
            start = time.time()
            check_count = 0
            while time.time() - start < 300:
                time.sleep(3)
                check_count += 1
                
                if check_count % 5 == 0:
                    console.print(f"[dim]Проверка #{check_count}: URL = {self.page.url[:80]}[/dim]")
                
                if self._check_authorization():
                    console.print("[green]✅ Авторизация успешна! Скрываю браузер...[/green]")
                    # Получаем реальный URL workspace
                    self._update_brain_url()
                    time.sleep(1)
                    
                    # Переходим к AI Brain
                    console.print("[dim]🧠 Переход к AI Brain...[/dim]")
                    if not self._navigate_to_brain():
                        console.print("[dim]⚠ Навигация через UI не удалась, иду напрямую[/dim]")
                        self.page.goto(BASE_URL, wait_until="domcontentloaded", timeout=60000)
                        time.sleep(3)
                    
                    # Ждём загрузку страницы Brain
                    try:
                        self.page.wait_for_selector('textarea, [contenteditable="true"]', timeout=10000)
                        console.print("[dim]✓ Страница Brain загружена[/dim]")
                    except:
                        console.print("[dim]⚠ Страница Brain загружается...[/dim]")
                    
                    self._hide_browser_window()
                    console.print("[green]✅ Браузер скрыт, продолжаю работу[/green]")
                    return
        except Exception as e:
            console.print(f"[red]❌ Ошибка: {e}[/red]")
        
        console.print("[red]❌ Таймаут авторизации![/red]")
        self.close_browser()
        sys.exit(1)
    
    def _update_brain_url(self):
        """Обновляет BASE_URL на реальный URL workspace текущего аккаунта"""
        global BASE_URL
        import re
        
        # Ждём полной загрузки страницы
        time.sleep(2)
        current_url = self.page.url
        
        console.print(f"[dim]🔍 Текущий URL: {current_url}[/dim]")
        
        # Сохраняем скриншот для отладки
        try:
            self.page.screenshot(path="debug_redirect.png")
            console.print("[dim]📸 Скриншот сохранён: debug_redirect.png[/dim]")
        except:
            pass
        
        # Пробуем числовой workspace ID: app.clickup.com/90121869092/...
        match = re.search(r'app\.clickup\.com/(\d+)', current_url)
        if match:
            workspace_id = match.group(1)
            BASE_URL = f"https://app.clickup.com/{workspace_id}/ai/brain"
            console.print(f"[dim]✓ Workspace из URL: {workspace_id}[/dim]")
            return
        
        # Пробуем team ID: app.clickup.com/t/TEAM_ID/...
        match = re.search(r'app\.clickup\.com/t/([^/]+)', current_url)
        if match:
            team_id = match.group(1)
            BASE_URL = f"https://app.clickup.com/t/{team_id}/ai/brain"
            console.print(f"[dim]✓ Team из URL: {team_id}[/dim]")
            return
        
        # Ищем workspace ID в DOM (data-test, мета-теги, JS переменные)
        console.print("[dim]🔍 Ищу workspace ID в DOM...[/dim]")
        try:
            workspace_id = self.page.evaluate("""() => {
                // Ищем в data-атрибутах
                const elements = document.querySelectorAll('[data-workspace-id], [data-team-id]');
                for (let el of elements) {
                    const id = el.dataset.workspaceId || el.dataset.teamId;
                    if (id && /^\\d+$/.test(id)) return id;
                }
                
                // Ищем в мета-тегах
                const metas = document.querySelectorAll('meta');
                for (let meta of metas) {
                    const content = meta.content || '';
                    if (/^\\d+$/.test(content)) return content;
                }
                
                // Ищем в window переменных
                if (window.__NUXT__ && window.__NUXT__.state && window.__NUXT__.state.workspace) {
                    return window.__NUXT__.state.workspace.id;
                }
                
                // Ищем в ссылках
                const links = document.querySelectorAll('a[href*="app.clickup.com"]');
                for (let link of links) {
                    const match = link.href.match(/app\\.clickup\\.com\\/(\\d+)/);
                    if (match) return match[1];
                }
                
                return null;
            }""")
            
            if workspace_id:
                BASE_URL = f"https://app.clickup.com/{workspace_id}/ai/brain"
                console.print(f"[dim]✓ Workspace из DOM: {workspace_id}[/dim]")
                return
        except Exception as e:
            console.print(f"[dim]⚠ Ошибка поиска в DOM: {e}[/dim]")
        
        # Fallback: идём на /ai/brain напрямую
        BASE_URL = "https://app.clickup.com/ai/brain"
        console.print(f"[dim]✓ URL brain (fallback): {BASE_URL}[/dim]")
    
    def _navigate_to_brain(self):
        """Навигирует к AI Brain через UI, а не через хардкод URL"""
        try:
            # Пробуем найти кнопку Brain в sidebar
            brain_selectors = [
                'text="Brain"',
                '[data-test="brain"]',
                'a[href*="brain"]',
                'button:has-text("Brain")',
                '[class*="brain"]',
            ]
            
            for sel in brain_selectors:
                try:
                    el = self.page.query_selector(sel)
                    if el and el.is_visible():
                        el.click()
                        time.sleep(2)
                        return True
                except:
                    continue
            
            # Если не нашли — идём напрямую
            self.page.goto(BASE_URL, wait_until="domcontentloaded", timeout=60000)
            return True
        except Exception as e:
            console.print(f"[dim]⚠ Ошибка навигации: {e}[/dim]")
            return False
    
    def _check_authorization(self):
        """Надёжная проверка авторизации через несколько факторов"""
        try:
            # Обновляем страницу чтобы получить актуальный URL
            current_url = self.page.url
            
            # 1. Проверяем URL (если содержит /login - не авторизован)
            if "/login" in current_url or "login" in current_url.lower():
                return False
            
            # 2. Проверяем наличие аватара пользователя (сильный сигнал)
            avatar = self.page.query_selector('[data-test="user-avatar"], .user-avatar, [class*="avatar"]')
            if avatar:
                console.print("[dim]✓ Найден аватар пользователя[/dim]")
                return True
            
            # 3. Проверяем наличие поля ввода (Quill editor)
            input_field = self.page.query_selector('.ql-editor[contenteditable="true"]')
            if input_field:
                console.print("[dim]✓ Найдено поле ввода[/dim]")
                return True
            
            # 4. Проверяем наличие UI элементов ClickUp (sidebar, workspace)
            sidebar = self.page.query_selector('[data-test="sidebar"], .sidebar, [class*="sidebar"]')
            if sidebar:
                console.print("[dim]✓ Найден sidebar[/dim]")
                return True
            
            # 5. Проверяем наличие кнопок/workspace элементов
            workspace = self.page.query_selector('[data-test*="workspace"], [class*="workspace"]')
            if workspace:
                console.print("[dim]✓ Найден workspace[/dim]")
                return True
            
            # 6. Проверяем текст на странице (ищем "Sign in" или "Log in")
            page_text = self.page.evaluate('() => document.body.innerText')
            if "Sign in" in page_text or "Log in" in page_text or "Sign up" in page_text:
                return False
            
            # 7. Если URL изменился и не содержит login - вероятно авторизован
            if "app.clickup.com" in current_url and "login" not in current_url.lower():
                console.print(f"[dim]✓ URL изменился: {current_url}[/dim]")
                return True
            
            return False
            
        except Exception as e:
            console.print(f"[dim]⚠ Ошибка проверки: {e}[/dim]")
            return False
    
    def _center_browser_window(self):
        """Центрирует окно браузера на экране через PowerShell"""
        try:
            import subprocess
            time.sleep(1)
            
            ps_script = '''
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Win32Center {
    [DllImport("user32.dll")] public static extern bool MoveWindow(IntPtr hWnd, int x, int y, int w, int h, bool repaint);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern int GetSystemMetrics(int nIndex);
}
"@

# Получаем размер экрана
$screenW = [Win32Center]::GetSystemMetrics(0)
$screenH = [Win32Center]::GetSystemMetrics(1)

# Размер окна браузера
$winW = 1400
$winH = 900

# Позиция по центру
$x = [Math]::Max(0, ($screenW - $winW) / 2)
$y = [Math]::Max(0, ($screenH - $winH) / 2)

Get-Process | Where-Object {$_.ProcessName -like "*chrome*" -or $_.ProcessName -like "*chromium*"} | ForEach-Object {
    if ($_.MainWindowHandle -ne 0) {
        [Win32Center]::MoveWindow($_.MainWindowHandle, [int]$x, [int]$y, $winW, $winH, $true)
        [Win32Center]::SetForegroundWindow($_.MainWindowHandle)
    }
}
'''
            subprocess.run(['powershell', '-Command', ps_script], 
                         capture_output=True, timeout=10)
        except:
            pass
    
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
        try:
            if self.ctx:
                self.ctx.close()
                self.ctx = None
            if self.playwright:
                self.playwright.stop()
                self.playwright = None
        except Exception as e:
            # Игнорируем ошибки при двойном закрытии
            if "already closed" not in str(e).lower() and "already stopped" not in str(e).lower():
                raise
    
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
        """Ищет поле ввода в ClickUp Brain"""
        # Пробуем разные селекторы, которые может использовать ClickUp
        selectors = [
            'textarea[placeholder*="message" i]',
            'textarea[placeholder*="Message" i]',
            'textarea',
            'input[type="text"]',
            '[role="textbox"]',
            '[contenteditable="true"]',
            '.ql-editor[contenteditable="true"]',
            'div.ql-editor',
            'div[contenteditable="true"]',
            # Более общие селекторы
            'input:not([type="hidden"]):not([type="checkbox"]):not([type="radio"])',
        ]
        
        # Делаем скриншот для дебага
        debug_screenshot = Path(__file__).parent / "debug_input.png"
        
        for attempt in range(30):
            for sel in selectors:
                try:
                    els = self.page.query_selector_all(sel)
                    for el in els:
                        if el.is_visible():
                            return el
                except Exception:
                    continue
            
            if attempt == 5:
                # Сохраняем скриншот для дебага
                try:
                    self.page.screenshot(path=str(debug_screenshot))
                    console.print(f"[dim]📸 Скриншот для дебага: {debug_screenshot}[/dim]")
                except Exception:
                    pass
            
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
        
        # Пытаемся закрыть/свернуть мешающие элементы (settings bar, фильтры)
        try:
            self.page.evaluate("""() => {
                const bars = document.querySelectorAll('.views-settings-bar, .view-filter-search__toggle-container');
                bars.forEach(bar => {
                    bar.style.display = 'none';
                });
            }""")
        except:
            pass
        
        # Отправляем
        inp.scroll_into_view_if_needed()
        time.sleep(0.3)
        inp.click(force=True)
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
    
    def swap_account(self):
        """Свап аккаунтов: logout + interactive auth в одной команде"""
        console.print("[cyan]🔄 Свап аккаунтов...[/cyan]\n")
        
        # Закрываем текущий браузер
        self.close_browser()
        
        # Удаляем профиль
        import shutil
        if PROFILE_DIR.exists():
            shutil.rmtree(PROFILE_DIR)
            console.print("[green]✅ Старый профиль удалён[/green]")
        
        console.print("\n[cyan]🔐 Запуск интерактивной авторизации...[/cyan]\n")
        
        # Запускаем интерактивную авторизацию
        self.init_browser(interactive=True)
        
        # Открываем чат
        if self.open_chat():
            console.print("[green]✅ Свап аккаунтов завершён![/green]\n")
        else:
            console.print("[red]❌ Ошибка открытия чата[/red]\n")
    
    def setup_mcp(self, mcp_url=None):
        """Автоматически настраивает MCP сервер в ClickUp Brain
        
        Args:
            mcp_url: URL MCP сервера (если None, использует дефолтный из serveo)
        """
        if not mcp_url:
            mcp_url = "https://4e46efbf263a6207-185-176-158-3.serveousercontent.com/sse"
        
        console.print(f"\n[cyan]🔧 Настройка MCP сервера...[/cyan]")
        console.print(f"[dim]URL: {mcp_url}[/dim]\n")
        
        try:
            # 1. Переходим в главный интерфейс ClickUp
            console.print("[dim]1. Открываю главный интерфейс ClickUp...[/dim]")
            self.page.goto(BASE_URL, wait_until="domcontentloaded", timeout=60000)
            time.sleep(3)
            
            # 2. Ищем и кликаем на APPS в боковой панели
            console.print("[dim]2. Ищу раздел APPS...[/dim]")
            
            apps_selectors = [
                'text=APPS',
                'button:has-text("APPS")',
                '[data-test*="apps" i]',
                'a:has-text("APPS")',
                '.apps-link',
                'nav >> text=APPS'
            ]
            
            apps_found = False
            for selector in apps_selectors:
                try:
                    element = self.page.query_selector(selector)
                    if element and element.is_visible():
                        element.click()
                        time.sleep(2)
                        apps_found = True
                        console.print(f"[dim]✓ Кликнул на APPS: {selector}[/dim]")
                        break
                except:
                    continue
            
            if not apps_found:
                console.print("[yellow]⚠️ Раздел APPS не найден, делаю скриншот...[/yellow]")
                self._save_debug_screenshot("debug_apps_section.png")
                console.print("[yellow]💡 Попробуй настроить вручную: APPS → MCP Servers → ADD Custom MCP Server[/yellow]")
                return False
            
            # 3. Ищем раздел MCP Servers
            console.print("[dim]3. Ищу раздел MCP Servers...[/dim]")
            time.sleep(2)
            
            mcp_selectors = [
                'text=MCP Servers',
                'text=MCP',
                '[data-test*="mcp" i]',
                'a[href*="mcp" i]',
                'button:has-text("MCP")',
                '.mcp-servers',
                'text=Model Context Protocol'
            ]
            
            mcp_found = False
            for selector in mcp_selectors:
                try:
                    element = self.page.query_selector(selector)
                    if element and element.is_visible():
                        element.click()
                        time.sleep(2)
                        mcp_found = True
                        console.print(f"[dim]✓ Нашёл MCP раздел: {selector}[/dim]")
                        break
                except:
                    continue
            
            if not mcp_found:
                console.print("[yellow]⚠️ Раздел MCP не найден, делаю скриншот...[/yellow]")
                self._save_debug_screenshot("debug_mcp_section.png")
                console.print("[yellow]💡 Попробуй настроить вручную: APPS → MCP Servers → ADD Custom MCP Server[/yellow]")
                return False
            
            # 4. Кликаем ADD Custom MCP Server
            console.print("[dim]4. Добавляю Custom MCP Server...[/dim]")
            add_selectors = [
                'button:has-text("Add Custom MCP Server")',
                'button:has-text("ADD Custom MCP Server")',
                'button:has-text("Add MCP")',
                '[data-test*="add-mcp" i]',
                'button:has-text("Add Server")'
            ]
            
            add_found = False
            for selector in add_selectors:
                try:
                    btn = self.page.query_selector(selector)
                    if btn and btn.is_visible():
                        btn.click()
                        time.sleep(2)
                        add_found = True
                        console.print("[dim]✓ Кликнул на Add[/dim]")
                        break
                except:
                    continue
            
            if not add_found:
                console.print("[yellow]⚠️ Кнопка Add не найдена[/yellow]")
                self._save_debug_screenshot("debug_add_mcp.png")
                return False
            
            # 5. Кликаем Next (если есть)
            console.print("[dim]5. Заполняю форму...[/dim]")
            time.sleep(1)
            
            try:
                next_btn = self.page.query_selector('button:has-text("Next"), button:has-text("Continue")')
                if next_btn and next_btn.is_visible():
                    next_btn.click()
                    time.sleep(1)
            except:
                pass
            
            # 6. Заполняем поля
            fields_filled = 0
            
            # Name
            name_selectors = [
                'input[name="name"]',
                'input[placeholder*="name" i]',
                'input[placeholder*="Name" i]',
                '#name',
                'input[type="text"]'
            ]
            for selector in name_selectors:
                try:
                    field = self.page.query_selector(selector)
                    if field and field.is_visible():
                        field.fill("Hermes MCP Server")
                        fields_filled += 1
                        console.print("[dim]✓ Заполнил Name[/dim]")
                        break
                except:
                    continue
            
            # Description (может быть необязательным)
            desc_selectors = [
                'textarea[name="description"]',
                'input[name="description"]',
                'textarea[placeholder*="description" i]',
                '#description'
            ]
            for selector in desc_selectors:
                try:
                    field = self.page.query_selector(selector)
                    if field and field.is_visible():
                        field.fill("Provides filesystem access to user files")
                        console.print("[dim]✓ Заполнил Description[/dim]")
                        break
                except:
                    continue
            
            # URL
            url_selectors = [
                'input[name="url"]',
                'input[placeholder*="url" i]',
                'input[placeholder*="URL" i]',
                'input[type="url"]',
                '#url'
            ]
            for selector in url_selectors:
                try:
                    field = self.page.query_selector(selector)
                    if field and field.is_visible():
                        field.fill(mcp_url)
                        fields_filled += 1
                        console.print("[dim]✓ Заполнил URL[/dim]")
                        break
                except:
                    continue
            
            if fields_filled < 2:
                console.print("[yellow]⚠️ Не удалось заполнить все поля[/yellow]")
                self._save_debug_screenshot("debug_mcp_form.png")
            
            # 7. Кликаем Next/Continue (если есть)
            console.print("[dim]6. Подтверждаю настройки...[/dim]")
            time.sleep(1)
            
            for selector in ['button:has-text("Next")', 'button:has-text("Continue")', 'button:has-text("Save")']:
                try:
                    btn = self.page.query_selector(selector)
                    if btn and btn.is_visible():
                        btn.click()
                        time.sleep(2)
                        break
                except:
                    continue
            
            # 8. Кликаем Finish/Done/Add
            finish_selectors = [
                'button:has-text("Finish")',
                'button:has-text("Done")',
                'button:has-text("Add")',
                'button:has-text("Save")',
                'button[type="submit"]'
            ]
            
            for selector in finish_selectors:
                try:
                    btn = self.page.query_selector(selector)
                    if btn and btn.is_visible():
                        btn.click()
                        time.sleep(2)
                        console.print("[green]✅ MCP сервер добавлен![/green]\n")
                        break
                except:
                    continue
            
            # 9. Возвращаемся в чат и отправляем сообщение
            console.print("[dim]7. Отправляю сообщение в чат...[/dim]")
            self.open_chat()
            
            message = f"Я подключил Custom MCP по ссылке {mcp_url} Теперь работаем только через этот MCP в моих папках"
            
            inp = self.find_input()
            if inp:
                inp.fill(message)
                time.sleep(0.5)
                inp.press("Enter")
                time.sleep(3)
                console.print("[green]✅ Сообщение отправлено![/green]\n")
                return True
            else:
                console.print("[yellow]⚠️ Не удалось найти поле ввода[/yellow]")
                return False
            
        except Exception as e:
            console.print(f"[red]❌ Ошибка настройки MCP: {e}[/red]")
            self._save_debug_screenshot("debug_mcp_error.png")
            console.print("[yellow]💡 Попробуй настроить вручную: APPS → MCP Servers → ADD Custom MCP Server[/yellow]")
            return False
    
    def _save_debug_screenshot(self, filename):
        """Сохраняет скриншот для дебага"""
        try:
            self.page.screenshot(path=filename)
            console.print(f"[dim]📸 Скриншот сохранён: {filename}[/dim]")
        except Exception as e:
            console.print(f"[dim]⚠️ Не удалось сделать скриншот: {e}[/dim]")


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
| `/swap` | Свап аккаунтов (logout + авторизация в одной команде) |
| `/setupmcp [url]` | Автоматически настроить MCP сервер |
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

❯ /swap
🔄 Свап аккаунтов...
✅ Старый профиль удалён
🔐 Запуск интерактивной авторизации...
✅ Свап аккаунтов завершён!

❯ /setupmcp
🔧 Настройка MCP сервера...
URL: https://4e46efbf263a6207-185-176-158-3.serveousercontent.com/sse
1. Открываю APPS...
2. Открываю MCP Servers...
3. Добавляю Custom MCP Server...
4. Заполняю форму...
5. Подтверждаю настройки...
✅ MCP сервер добавлен!
6. Отправляю сообщение в чат...
✅ Сообщение отправлено!

❯ /logout
🔄 Выход из аккаунта...
✅ Готово! Перезапусти braincli для входа с новым аккаунтом

❯ /exit
```
"""
    console.print(Markdown(help_text))


def get_prompt_session():
    """Создаёт prompt_toolkit сессию с автозаполнением команд"""
    from prompt_toolkit.completion import WordCompleter
    from prompt_toolkit.history import FileHistory
    
    commands = [
        '/help', '/newsession', '/new', '/sessions', '/ls', '/load', 
        '/history', '/h', '/clear', '/c', '/logout', '/swap', 
        '/setupmcp', '/exit', '/quit', '/q'
    ]
    
    completer = WordCompleter(commands, sentence=True)
    history = FileHistory(str(HISTORY_FILE))
    
    return PromptSession(
        completer=completer,
        history=history,
        auto_suggest=AutoSuggestFromHistory()
    )


def show_command_suggestions(current_input, commands):
    """Показывает подсказки команд (используется только для отладки)"""
    if not current_input.startswith('/'):
        return
    
    # Фильтруем команды по введённому тексту
    filtered = [cmd for cmd in commands if cmd.startswith(current_input.lower())]
    
    if filtered:
        # Сохраняем текущую позицию курсора
        print('\033[s', end='', flush=True)
        
        # Перемещаемся на строку ниже
        print('\033[1E', end='', flush=True)
        print('\033[2K', end='', flush=True)  # Очищаем строку
        
        # Показываем подсказки
        suggestions = '  '.join([f'\033[36m{cmd}\033[0m' for cmd in filtered[:5]])
        print(suggestions, end='', flush=True)
        
        # Возвращаемся на исходную позицию
        print('\033[u', end='', flush=True)


def custom_input(prompt_text='❯ '):
    """Кастомный input с вертикальным автодополнением команд через prompt_toolkit"""
    import threading
    
    result = [None]
    error = [None]
    
    def _run_prompt():
        try:
            import asyncio
            # Создаём новый event loop для этого потока
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            from prompt_toolkit.completion import Completer, Completion
            from prompt_toolkit.formatted_text import HTML
            
            commands = [
                ('/help', 'Показать справку'),
                ('/newsession', 'Новая сессия'),
                ('/new', 'Новая сессия (короткая)'),
                ('/sessions', 'Список сессий'),
                ('/ls', 'Список сессий (короткая)'),
                ('/load', 'Загрузить сессию'),
                ('/history', 'История сообщений'),
                ('/h', 'История (короткая)'),
                ('/clear', 'Очистить экран'),
                ('/c', 'Очистить (короткая)'),
                ('/logout', 'Выйти из аккаунта'),
                ('/swap', 'Сменить аккаунт'),
                ('/setupmcp', 'Настроить MCP'),
                ('/exit', 'Выход'),
                ('/quit', 'Выход'),
                ('/q', 'Выход (короткая)')
            ]
            
            class CommandCompleter(Completer):
                """Комплетер для команд с вертикальным отображением"""
                
                def get_completions(self, document, complete_event):
                    text = document.text_before_cursor
                    
                    # Показываем все команды при вводе /
                    if text.startswith('/'):
                        for cmd, desc in commands:
                            if cmd.startswith(text.lower()):
                                # Вертикальное отображение: команда + описание
                                display = HTML(f"<b>{cmd:<15}</b> <dim>{desc}</dim>")
                                yield Completion(
                                    cmd,
                                    start_position=-len(text),
                                    display=display
                                )
            
            completer = CommandCompleter()
            history = FileHistory(str(HISTORY_FILE))
            
            session = PromptSession(
                completer=completer,
                history=history,
                auto_suggest=AutoSuggestFromHistory(),
                complete_while_typing=True
            )
            
            result[0] = session.prompt(prompt_text)
            loop.close()
        except Exception as e:
            error[0] = e
    
    t = threading.Thread(target=_run_prompt)
    t.start()
    t.join()
    
    if error[0]:
        if isinstance(error[0], KeyboardInterrupt):
            raise KeyboardInterrupt
        raise error[0]
    
    return result[0] or ''


def interactive_session_select(agent):
    """Интерактивный выбор сессии через prompt_toolkit со стрелками"""
    import threading
    
    sessions = agent.db.list_sessions()
    if not sessions:
        console.print("[yellow]Нет сохранённых сессий[/yellow]")
        return None
    
    result = [None]
    error = [None]
    
    def _run_prompt():
        try:
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            from prompt_toolkit.completion import Completer, Completion
            from prompt_toolkit.document import Document
            from prompt_toolkit.formatted_text import HTML
            from prompt_toolkit.shortcuts import prompt
            
            class SessionCompleter(Completer):
                """Комплетер для сессий с отображением списка"""
                
                def get_completions(self, document, complete_event):
                    for i, s in enumerate(sessions):
                        updated = s['updated_at'].split('T')[0]
                        display = f"{s['title']} | {s['id']} | {updated}"
                        yield Completion(
                            s['id'],
                            start_position=-len(document.text),
                            display=HTML(f"▶ <b>{display}</b>") if True else display,
                            display_meta=f"Обновлена: {updated}"
                        )
            
            completer = SessionCompleter()
            
            # Показываем список сессий перед вводом
            console.print("\n[bold cyan]📚 Сессии[/bold cyan]")
            console.print("[dim]Выбери сессию стрелками ↑↓ или введи номер/ID:[/dim]\n")
            
            for i, s in enumerate(sessions):
                updated = s['updated_at'].split('T')[0]
                console.print(f"  [{i+1}] {s['title']:<30} | {s['id']:<8} | {updated}")
            
            console.print()
            
            user_input = prompt(
                'Выбери сессию: ',
                completer=completer,
                complete_while_typing=True
            )
            
            # Проверяем если ввели номер
            try:
                idx = int(user_input) - 1
                if 0 <= idx < len(sessions):
                    result[0] = sessions[idx]['id']
                    return
            except (ValueError, TypeError):
                pass
            
            # Проверяем если ввели ID
            for s in sessions:
                if user_input and (s['id'].startswith(user_input) or user_input == s['id']):
                    result[0] = s['id']
                    return
            
            loop.close()
        except Exception as e:
            error[0] = e
    
    t = threading.Thread(target=_run_prompt)
    t.start()
    t.join()
    
    if error[0]:
        if isinstance(error[0], KeyboardInterrupt):
            console.print("\n[dim]Отменено[/dim]\n")
            return None
        raise error[0]
    
    if result[0]:
        console.print(f"\n[green]✅ Выбрана сессия[/green]\n")
    
    return result[0]


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
        # Инициализация с автоматической логикой авторизации
        agent.init_browser()
        
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
                    user_input = custom_input('❯ ').strip()
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
                    
                    elif cmd in ['/swap']:
                        agent.swap_account()
                        continue
                    
                    elif cmd.startswith('/setupmcp'):
                        # Проверяем есть ли URL в команде
                        parts = user_input.split(maxsplit=1)
                        mcp_url = parts[1] if len(parts) > 1 else None
                        agent.setup_mcp(mcp_url)
                        continue
                    
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
