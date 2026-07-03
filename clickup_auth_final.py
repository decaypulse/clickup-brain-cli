#!/usr/bin/env python3
"""ClickUp AI Brain - Persistent Auth + API Discovery"""
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
        # Persistent context — cookies сохраняются между запусками
        context = p.chromium.launch_persistent_context(
            str(PROFILE_DIR),
            headless=False,
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        )
        page = context.pages[0] if context.pages else context.new_page()
        
        def handle_response(response):
            url = response.url
            if "clickup.com" in url and response.status != 304:
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
                print(f"[{len(api_requests)}] {req.method} {response.status} {url[:150]}")
        
        page.on("response", handle_response)
        page.goto("https://app.clickup.com/90121869092/ai/brain")
        
        print(f"\n{'='*50}")
        print("ЖДУ 3 МИНУТЫ — времени хватит!")
        print("1. Залогинься в ClickUp (decaypulse@gmail.com)")
        print("2. Открой AI Brain чат")  
        print("3. Отправь сообщение 'привет'")
        print(f"{'='*50}\n")
        
        for i in range(180, 0, -1):
            time.sleep(1)
            if i % 15 == 0:
                print(f"Осталось {i} сек... ({len(api_requests)} запросов)")
        
        print(f"\n=== СОХРАНЯЮ ===")
        
        API_LOG_FILE.write_text(json.dumps(api_requests, indent=2, ensure_ascii=False))
        print(f"API: {len(api_requests)} requests -> {API_LOG_FILE}")
        
        ai_eps = set()
        for req in api_requests:
            u = req["url"].lower()
            if any(k in u for k in ["ai", "brain", "chat", "message", "conversation", "llm", "openai", "copilot"]):
                ai_eps.add(f"{req['method']} {req['url'].split('?')[0]}")
        
        print(f"\nAI endpoints ({len(ai_eps)}):")
        for ep in sorted(ai_eps):
            print(f"  {ep}")
        
        all_eps = set()
        for req in api_requests:
            all_eps.add(f"{req['method']} {req['url'].split('?')[0]}")
        print(f"\nAll endpoints ({len(all_eps)}):")
        for ep in sorted(all_eps)[:30]:
            print(f"  {ep}")
        if len(all_eps) > 30:
            print(f"  ... and {len(all_eps)-30} more")
        
        browser.close()
        print("\nDONE")

if __name__ == "__main__":
    main()
