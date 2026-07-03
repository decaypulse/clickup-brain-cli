#!/usr/bin/env python3
"""
ClickUp авторизация — один раз логинимся, сохраняем cookies и access_token
"""
import json
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

CLI_DIR = Path(__file__).parent
AUTH_FILE = CLI_DIR / "auth.json"

def main():
    print("🔐 Открываю браузер для авторизации...")
    print("   Войди в ClickUp и закрой окно когда готово\n")
    
    p = sync_playwright().start()
    
    # Headless=False чтобы пользователь мог залогиниться
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    
    # Перехватываем access_token
    access_token = None
    
    def handle_response(response):
        nonlocal access_token
        url = response.url
        if 'access-token' in url or 'access_tokens' in url:
            try:
                data = response.json()
                if 'token' in data:
                    access_token = data['token']
                    print(f"✅ Access token получен: {access_token[:20]}...")
            except:
                pass
    
    page.on('response', handle_response)
    
    # Открываем ClickUp
    page.goto('https://app.clickup.com')
    
    print("⏳ Жду авторизации...")
    print("   (закрой окно когда войдёшь в аккаунт)\n")
    
    # Ждём пока пользователь закроет окно или залогинится
    try:
        page.wait_for_selector('a[href*="ai/brain"]', timeout=300000)  # 5 минут
        print("✅ Авторизация успешна!")
    except:
        print("⚠️ Таймаут или окно закрыто")
    
    # Сохраняем cookies и storage state
    storage_state = context.storage_state()
    
    # Если не перехватили token из response, попробуем из localStorage
    if not access_token:
        access_token = page.evaluate("""() => {
            // Ищем в localStorage
            for (let key in localStorage) {
                let val = localStorage.getItem(key);
                if (val && val.includes('eyJ')) {  // JWT token
                    try {
                        let obj = JSON.parse(val);
                        if (obj.token) return obj.token;
                    } catch(e) {}
                }
            }
            return null;
        }""")
    
    # Сохраняем auth data
    auth_data = {
        'storage_state': storage_state,
        'access_token': access_token,
        'workspace_id': '90121869092'
    }
    
    with open(AUTH_FILE, 'w') as f:
        json.dump(auth_data, f, indent=2)
    
    print(f"✅ Auth data сохранена в {AUTH_FILE}")
    
    browser.close()
    p.stop()
    
    print("\n🎉 Готово! Теперь можешь запускать clickup_agent.py")

if __name__ == '__main__':
    main()
