#!/usr/bin/env python3
"""ClickUp AI Brain - Auth & API Discovery v3"""
import json, time
from pathlib import Path
from playwright.sync_api import sync_playwright

SAVE_DIR = Path(r"C:\Users\decyp\Desktop\clickup-cli")
SESSION_FILE = SAVE_DIR / "session.json"
API_LOG_FILE = SAVE_DIR / "api_log.json"

def main():
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
            if ("api" in url or "gateway" in url or "socket" in url) and "clickup.com" in url:
                req = response.request
                req_data = {
                    "url": url,
                    "method": req.method,
                    "status": response.status,
                    "headers": dict(req.headers),
                    "post_data": req.post_data,
                }
                try:
                    ct = response.headers.get("content-type", "")
                    if "json" in ct or "text" in ct:
                        req_data["response_body"] = response.text()[:2000]
                except:
                    pass
                api_requests.append(req_data)
                print(f"[{len(api_requests)}] {req.method} {url[:150]}")
        
        page.on("response", handle_response)
        page.goto("https://app.clickup.com/90121869092/ai/brain")
        
        print(f"\n=== ЖДУ 120 СЕКУНД ===")
        print("1. Залогинься в ClickUp")
        print("2. Открой AI Brain чат")
        print("3. Отправь сообщение (например 'привет')")
        print("========================\n")
        
        # Ждём 2 минуты
        for i in range(120, 0, -1):
            time.sleep(1)
            if i % 10 == 0:
                print(f"Осталось {i} сек... ({len(api_requests)} запросов перехвачено)")
        
        print(f"\n=== СОХРАНЯЮ ===")
        cookies = context.cookies()
        SESSION_FILE.write_text(json.dumps({"cookies": cookies}, indent=2, ensure_ascii=False))
        print(f"Session: {len(cookies)} cookies -> {SESSION_FILE}")
        
        API_LOG_FILE.write_text(json.dumps(api_requests, indent=2, ensure_ascii=False))
        print(f"API: {len(api_requests)} requests -> {API_LOG_FILE}")
        
        # AI endpoints
        ai_eps = set()
        for req in api_requests:
            u = req["url"].lower()
            if any(k in u for k in ["ai", "brain", "chat", "message", "conversation", "llm"]):
                ai_eps.add(f"{req['method']} {req['url'].split('?')[0]}")
        
        print(f"\nAI-related endpoints ({len(ai_eps)}):")
        for ep in sorted(ai_eps):
            print(f"  {ep}")
        
        # All unique endpoints
        all_eps = set()
        for req in api_requests:
            all_eps.add(f"{req['method']} {req['url'].split('?')[0]}")
        print(f"\nAll endpoints ({len(all_eps)}):")
        for ep in sorted(all_eps):
            print(f"  {ep}")
        
        browser.close()
        print("\nDONE")

if __name__ == "__main__":
    main()
