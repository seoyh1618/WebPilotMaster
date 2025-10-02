import os
import requests
from dotenv import load_dotenv
load_dotenv()

def test_openai_api_key():
    """
    OpenAI API Key가 유효한지 간단히 테스트합니다.
    환경변수 OPENAI_API_KEY가 필요합니다.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ OPENAI_API_KEY 환경변수가 설정되어 있지 않습니다.")
        return

    url = "https://api.openai.com/v1/models"
    headers = {
        "Authorization": f"Bearer {api_key}"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            print("✅ OpenAI API Key가 유효합니다.")
        else:
            print(f"❌ OpenAI API Key가 유효하지 않습니다. (status: {response.status_code})")
    except Exception as e:
        print(f"❌ OpenAI API Key 테스트 중 오류 발생: {e}")

def test_gemini_api_key():
    """
    Google Gemini API Key가 유효한지 간단히 테스트합니다.
    환경변수 GEMINI_API_KEY 또는 GOOGLE_API_KEY가 필요합니다.
    """
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("❌ GEMINI_API_KEY 또는 GOOGLE_API_KEY 환경변수가 설정되어 있지 않습니다.")
        return

    url = f"https://generativelanguage.googleapis.com/v1/models?key={api_key}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            print("✅ Gemini API Key가 유효합니다.")
        else:
            print(f"❌ Gemini API Key가 유효하지 않습니다. (status: {response.status_code})")
    except Exception as e:
        print(f"❌ Gemini API Key 테스트 중 오류 발생: {e}")

if __name__ == "__main__":
    print("OpenAI API Key 테스트:")
    test_openai_api_key()
    print("\nGemini API Key 테스트:")
    test_gemini_api_key()
