#!/usr/bin/env python3
"""ClickUp AI Brain - Wait for login in Playwright browser"""
import json, time
from pathlib import Path
from playwright.sync_api import sync_playwright

SAVE_DIR = Path(r"C:\Users\decyp\Desktop\clickup-cli")
PROFILE_DIR = SAVE_DIR / "browser_profile"
API_LOG_FILE = SAVE_DIR / "api_log.json"

def main():
    PROFILE_DIR.mkdir(exist_ok=True)
    api_requests = []
    
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            str(PROFILE_DIR),
            headless=False,
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        )
        page = context.pages[0] if context.pages else context.new_page()
        
        def handle_response(response):
            url = response.url
            if "clickup.com" in url and "api" in url and response.status != 304:
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
                    if "json" in ct:
                        req_data["response_body"] = response.text()[:5000]
                except:
                    pass
                api_requests.append(req_data)
                print(f"[{len(api_requests)}] {req.method} {response.status} {url[:120]}")
        
        page.on("response", handle_response)
        page.goto("https://app.clickup.com/90121869092/ai/brain")
        
        print(f"\n{'='*60}")
        print("ВАЖНО: Залогинься ИМЕННО В ЭТОМ БРАУЗЕРЕ (не в твоём обычном!)")
        print("1. В открывшемся окне залогинься: decaypulse@gmail.com")
        print("2. Открой AI Brain чат")
        print("3. Отправь сообщение 'привет'")
        print("4. Я буду ждать пока URL не станет /ai/brain")
        print(f"{'='*60}\n")
        
        # Ждём пока URL не станет правильным (не /login)
        print("Жду авторизацию...")
        max_wait = 300  # 5 минут
        for i in range(max_wait):
            time.sleep(1)
            current_url = page.url
            if "/login" not in current_url and "/ai/brain" in current_url:
                print(f"\n✅ Авторизован! URL: {current_url}")
                break
            if i % 30 == 0 and i > 0:
                print(f"Всё ещё жду... ({i} сек, {len(api_requests)} запросов)")
        else:
            print("⚠️ Таймаут — не дождался авторизации")
        
        # Ждём ещё 30 сек для API запросов
        print("\nЖду 30 сек для сбора API запросов...")
        time.sleep(30)
        
        print(f"\n=== СОХРАНЯЮ ({len(api_requests)} запросов) ===")
        API_LOG_FILE.write_text(json.dumps(api_requests, indent=2, ensure_ascii=False))
        print(f"Saved: {API_LOG_FILE}")
        
        # AI endpoints
        ai_eps = []
        for req in api_requests:
            u = req["url"].lower()
            if any(k in u for k in ["ai", "brain", "chat", "message", "conversation", "llm", "openai", "copilot", "thread"]):
                ai_eps.append(req)
        
        print(f"\nAI endpoints ({len(ai_eps)}):")
        for ep in ai_eps:
            print(f"  {ep['method']} {ep['url']}")
        
        print("\n✅ Готово! Можешь закрыть браузер вручную.")
        context.close()

if __name__ == "__main__":
    main()
