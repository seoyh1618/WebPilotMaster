from playwright.sync_api import sync_playwright


from playwright.async_api import async_playwright, Browser, BrowserContext, Page
# Playwright 실행
with sync_playwright() as p:
    # Chromium 브라우저 시작
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    
    # 페이지 이동
    page.goto("https://www.naver.com")
    print("Page Title:", page.title())  # 페이지 제목 출력
    
    # 브라우저 종료
    browser.close()