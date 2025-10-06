# test_playwright.py (프로젝트 루트)

import asyncio
from playwright.async_api import async_playwright

async def test_playwright():
    print("Playwright 테스트 시작...")
    
    try:
        async with async_playwright() as p:
            print("✓ Playwright 초기화 성공")
            
            browser = await p.chromium.launch(headless=True)
            print("✓ 브라우저 실행 성공")
            
            page = await browser.new_page()
            print("✓ 페이지 생성 성공")
            
            await page.goto("https://grad.ssu.ac.kr/")
            print("✓ 페이지 로딩 성공")
            
            screenshot = await page.screenshot()
            print(f"✓ 스크린샷 캡처 성공: {len(screenshot)} bytes")
            
            await browser.close()
            
            print("="*80)
            print("✅ Playwright 정상 작동!")
            return True
            
    except Exception as e:
        print(f"❌ Playwright 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    result = asyncio.run(test_playwright())
    print(f"테스트 결과: {'성공' if result else '실패'}")