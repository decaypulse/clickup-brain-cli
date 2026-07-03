#!/usr/bin/env python3
"""
ClickUp AI Brain CLI - Auth & API Discovery v2
"""
import json
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

SAVE_DIR = Path(r"C:\Users\decyp\Desktop\clickup-cli")
SESSION_FILE = SAVE_DIR / "session.json"
API_LOG_FILE = SAVE_DIR / "api_log.json"

def main():
    print("Запускаю браузер для авторизации...")
    print("Залогинься и открой AI Brain, потом вернись сюда")
    
    api_requests = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        def handle_response(response):
            url = response.url
            if "api" in url and "clickup.com" in url:
                req = response.request
                req_data = {
                    "url": url,
                    "method": req.method,
                    "status": response.status,
                    "headers": dict(req.headers),
                    "response_headers": dict(response.headers),
                    "post_data": req.post_data,
                }
                # Try to capture response body
                try:
                    if "json" in response.headers.get("content-type", ""):
                        req_data["response_body"] = response.json()
                except:
                    pass
                api_requests.append(req_data)
                print(f"API: {req.method} {url[:120]}")
        
        page.on("response", handle_response)
        
        page.goto("https://app.clickup.com/90121869092/ai/brain")
        
        # Wait for user to login
        print("Жду логин... (нажми Enter когда готов)")
        input()
        
        # Try to find and interact with chat
        print("Ищу поле ввода...")
        try:
            page.wait_for_timeout(2000)
            
            # Try various selectors for chat input
            selectors = [
                'textarea',
                '[contenteditable="true"]',
                'input[type="text"]',
                '[role="textbox"]',
            ]
            
            for sel in selectors:
                el = page.query_selector(sel)
                if el:
                    print(f"Нашёл поле: {sel}")
                    el.fill("Привет, это тест")
                    page.wait_for_timeout(500)
                    el.press("Enter")
                    print("Отправил!")
                    break
            else:
                print("Поле не найдено, но продолжаю...")
            
            page.wait_for_timeout(5000)
        except Exception as e:
            print(f"Ошибка: {e}")
        
        print(f"\nСохраняю...")
        cookies = context.cookies()
        
        SESSION_FILE.write_text(json.dumps({"cookies": cookies}, indent=2, ensure_ascii=False))
        print(f"Session: {SESSION_FILE}")
        
        API_LOG_FILE.write_text(json.dumps(api_requests, indent=2, ensure_ascii=False))
        print(f"API log: {API_LOG_FILE} ({len(api_requests)} requests)")
        
        # Show AI-related endpoints
        ai_eps = set()
        for req in api_requests:
            u = req["url"].lower()
            if any(k in u for k in ["ai", "brain", "chat", "message", "conversation"]):
                ai_eps.add(req["url"].split("?")[0])
        
        print("\nAI endpoints found:")
        for ep in sorted(ai_eps):
            print(f"  {ep}")
        
        if not ai_eps:
            print("  (none - try sending a message in AI Brain chat)")
        
        input("Нажми Enter чтобы закрыть...")
        browser.close()

if __name__ == "__main__":
    main()
