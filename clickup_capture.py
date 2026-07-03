#!/usr/bin/env python3
"""ClickUp AI Brain - Auto send message + capture API"""
import json, time, sys
from pathlib import Path
from playwright.sync_api import sync_playwright

SAVE_DIR = Path(r"C:\Users\decyp\Desktop\clickup-cli")
PROFILE_DIR = SAVE_DIR / "browser_profile"
API_LOG_FILE = SAVE_DIR / "api_log.json"

def main():
    api_requests = []
    
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            str(PROFILE_DIR),
            headless=False,
            viewport={"width": 1400, "height": 900},
        )
        page = context.pages[0] if context.pages else context.new_page()
        
        def handle_response(response):
            url = response.url
            # Перехватываем ВСЕ запросы к clickup.com (не только /api/)
            if "clickup.com" in url and response.status != 304:
                req = response.request
                req_data = {
                    "url": url,
                    "method": req.method,
                    "status": response.status,
                    "post_data": req.post_data,
                    "request_headers": dict(req.headers),
                }
                try:
                    ct = response.headers.get("content-type", "")
                    if "json" in ct:
                        req_data["response_body"] = response.text()[:5000]
                    elif "text" in ct:
                        req_data["response_body"] = response.text()[:1000]
                except:
                    pass
                api_requests.append(req_data)
                short = url.split("?")[0][:100]
                print(f"[{len(api_requests)}] {req.method} {response.status} {short}")
        
        page.on("response", handle_response)
        page.goto("https://app.clickup.com/90121869092/ai/brain")
        
        print("Загружаю страницу...")
        time.sleep(8)
        
        current_url = page.url
        print(f"Текущий URL: {current_url}")
        
        if "/login" in current_url:
            print("❌ Не авторизован! Нужно залогиниться.")
            time.sleep(300)
            context.close()
            return
        
        print("✅ Авторизован! Ищу поле ввода...")
        time.sleep(5)
        
        # Пробуем разные селекторы для поля ввода
        found = False
        selectors_to_try = [
            ('textarea', 'textarea'),
            ('[contenteditable="true"]', 'contenteditable'),
            ('div[role="textbox"]', 'role=textbox'),
            ('[data-placeholder]', 'data-placeholder'),
            ('input[type="text"]', 'input text'),
            ('.ql-editor', 'quill editor'),
            ('[placeholder*="message"]', 'placeholder message'),
            ('[placeholder*="ask"]', 'placeholder ask'),
            ('[placeholder*="Ask"]', 'placeholder Ask'),
        ]
        
        for sel, name in selectors_to_try:
            try:
                els = page.query_selector_all(sel)
                if els:
                    print(f"  Нашёл {len(els)} элементов с селектором: {name} ({sel})")
                    for i, el in enumerate(els):
                        vis = el.is_visible()
                        print(f"    [{i}] visible={vis}, text={el.inner_text()[:50] if vis else 'N/A'}")
                    found = True
            except Exception as e:
                pass
        
        if not found:
            print("  Поле не найдено через селекторы. Делаю скриншот...")
            page.screenshot(path=str(SAVE_DIR / "page.png"))
            print(f"  Скрин: {SAVE_DIR / 'page.png'}")
        
        # Попробуем ввести текст и отправить
        print("\nПытаюсь отправить сообщение...")
        try:
            # Скрин перед отправкой
            page.screenshot(path=str(SAVE_DIR / "before_send.png"))
            
            for sel, name in selectors_to_try:
                try:
                    el = page.query_selector(sel)
                    if el and el.is_visible():
                        print(f"  Использую: {name}")
                        el.click()
                        time.sleep(0.5)
                        el.fill("Привет, как дела?")
                        time.sleep(0.5)
                        page.keyboard.press("Enter")
                        print("  ✅ Отправил!")
                        break
                except Exception as e:
                    continue
        except Exception as e:
            print(f"  ❌ Ошибка: {e}")
        
        # Ждём ответ API
        print("\nЖду 20 сек для API ответа...")
        time.sleep(20)
        
        page.screenshot(path=str(SAVE_DIR / "after_send.png"))
        
        print(f"\n=== ИТОГО: {len(api_requests)} запросов ===")
        API_LOG_FILE.write_text(json.dumps(api_requests, indent=2, ensure_ascii=False))
        print(f"Saved: {API_LOG_FILE}")
        
        # Группируем
        groups = {}
        for req in api_requests:
            u = req["url"].split("?")[0]
            if u not in groups:
                groups[u] = []
            groups[u].append(req)
        
        print(f"\nУникальные эндпоинты ({len(groups)}):")
        for url, reqs in sorted(groups.items()):
            methods = set(r["method"] for r in reqs)
            print(f"  {','.join(methods)} {url}")
        
        print("\n✅ Готово!")
        time.sleep(3)
        context.close()

if __name__ == "__main__":
    main()
