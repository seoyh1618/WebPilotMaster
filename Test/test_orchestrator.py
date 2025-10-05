# Test/test_orchestrator.py
"""
WebPilot Orchestrator 통합 테스트
전체 Agent 워크플로우를 테스트합니다.
"""
import sys
from pathlib import Path
import json
import logging
from datetime import datetime

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from WebPilot.agent import run_webpilot
from WebPilot.constants import constants

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def print_separator(title="", char="=", length=80):
    """구분선 출력"""
    if title:
        padding = (length - len(title) - 2) // 2
        line = char * padding + f" {title} " + char * padding
        print("\n" + line)
    else:
        print("\n" + char * length)


def print_result(result: dict):
    """결과를 보기 좋게 출력"""
    print_separator("최종 결과")
    
    status = result.get("status", "unknown")
    print(f"\n상태: {status}")
    
    if status == "success":
        print(f"✅ 성공!")
        print(f"\n답변:")
        print("-" * 80)
        print(result.get("answer", "N/A"))
        print("-" * 80)
        
        print(f"\n신뢰도: {result.get('confidence', 0):.2f}")
        print(f"출처 URL: {result.get('source_url', 'N/A')}")
        print(f"시도 횟수: {result.get('attempts', 0)}")
        
        # 파일 정보가 있는 경우
        if result.get("file_url"):
            print(f"\n📎 파일 정보:")
            print(f"  - 파일명: {result.get('file_name', 'N/A')}")
            print(f"  - 파일 URL: {result.get('file_url')}")
            print(f"  - 파일 타입: {result.get('file_type', 'N/A')}")
            
            if result.get("note"):
                print(f"\n참고: {result.get('note')}")
        
        print(f"\n방문한 URL 목록:")
        for i, url in enumerate(result.get('visited_urls', []), 1):
            print(f"  {i}. {url}")
    
    elif status == "error":
        print(f"❌ 실패")
        print(f"\n에러 메시지: {result.get('error_message', 'Unknown error')}")
        print(f"시도 횟수: {result.get('attempts', 0)}")
        
        if result.get('visited_urls'):
            print(f"\n방문한 URL 목록:")
            for i, url in enumerate(result.get('visited_urls', []), 1):
                print(f"  {i}. {url}")
    
    print_separator()


def check_screenshots():
    """생성된 스크린샷 확인"""
    screenshot_dir = Path(constants.PERCEIVER_SCREENSHOT_DIR)
    
    print_separator("스크린샷 확인")
    print(f"\n디렉토리: {screenshot_dir.absolute()}")
    print(f"존재 여부: {screenshot_dir.exists()}")
    
    if screenshot_dir.exists():
        screenshots = sorted(
            screenshot_dir.glob("*.png"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )
        
        print(f"총 파일 수: {len(screenshots)}")
        
        if screenshots:
            print(f"\n최근 생성된 파일 (최대 5개):")
            for i, img in enumerate(screenshots[:5], 1):
                size_kb = img.stat().st_size / 1024
                mtime = datetime.fromtimestamp(img.stat().st_mtime)
                print(f"  {i}. {img.name}")
                print(f"     크기: {size_kb:.1f} KB, 생성: {mtime.strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        print("⚠ 디렉토리가 생성되지 않았습니다!")
    
    print_separator()


def test_orchestrator(query: str):
    """Orchestrator 테스트"""
    print_separator("WebPilot Orchestrator 테스트 시작", "=")
    print(f"\n질의: {query}")
    print(f"시작 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 현재 설정 출력
    print_separator("환경 설정")
    print(f"PERCEIVER_SAVE_SCREENSHOTS: {constants.PERCEIVER_SAVE_SCREENSHOTS}")
    print(f"PERCEIVER_SCREENSHOT_DIR: {constants.PERCEIVER_SCREENSHOT_DIR}")
    print(f"PLAYWRIGHT_HEADLESS: {constants.PLAYWRIGHT_HEADLESS}")
    print_separator()
    
    try:
        # Orchestrator 실행
        result = run_webpilot(query)
        
        # 결과 출력
        print_result(result)
        
        # 스크린샷 확인
        check_screenshots()
        
        # JSON 파일로 저장 (선택)
        save_result_to_file(query, result)
        
        return result
        
    except Exception as e:
        logger.error(f"테스트 실패: {e}", exc_info=True)
        print_separator("테스트 실패", "!")
        print(f"\n에러: {e}")
        print_separator("!", "!")
        return None


def save_result_to_file(query: str, result: dict):
    """결과를 JSON 파일로 저장"""
    results_dir = Path("Test/results")
    results_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"orchestrator_test_{timestamp}.json"
    
    output = {
        "query": query,
        "timestamp": datetime.now().isoformat(),
        "result": result
    }
    
    filepath = results_dir / filename
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    logger.info(f"결과 저장: {filepath}")


# ============================================
# 테스트 시나리오
# ============================================

TEST_QUERIES = [
    "숭실대학원 사물함 신청 방법 알려줘",
    "일반대학원 공지사항 확인",
    "대학원 등록금 납부 기한",
]


def run_all_tests():
    """모든 테스트 실행"""
    print("\n" + "="*80)
    print(" WebPilot Orchestrator 통합 테스트")
    print("="*80)
    
    results = []
    
    for i, query in enumerate(TEST_QUERIES, 1):
        print(f"\n\n{'='*80}")
        print(f" 테스트 {i}/{len(TEST_QUERIES)}")
        print(f"{'='*80}\n")
        
        result = test_orchestrator(query)
        results.append({
            "query": query,
            "result": result,
            "success": result and result.get("status") == "success"
        })
        
        # 테스트 간 대기 (API rate limit 고려)
        if i < len(TEST_QUERIES):
            import time
            print("\n⏱ 다음 테스트까지 5초 대기...")
            time.sleep(5)
    
    # 전체 결과 요약
    print_separator("전체 테스트 결과 요약", "=")
    
    success_count = sum(1 for r in results if r["success"])
    total_count = len(results)
    
    print(f"\n총 테스트: {total_count}개")
    print(f"성공: {success_count}개")
    print(f"실패: {total_count - success_count}개")
    print(f"성공률: {success_count / total_count * 100:.1f}%")
    
    print("\n개별 결과:")
    for i, r in enumerate(results, 1):
        status_icon = "✅" if r["success"] else "❌"
        print(f"  {i}. {status_icon} {r['query'][:50]}...")
    
    print_separator("", "=")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="WebPilot Orchestrator 테스트")
    parser.add_argument(
        "--query",
        type=str,
        help="테스트할 단일 질의"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="모든 테스트 시나리오 실행"
    )
    
    args = parser.parse_args()
    
    if args.all:
        run_all_tests()
    elif args.query:
        test_orchestrator(args.query)
    else:
        # 기본: 첫 번째 테스트 실행
        test_orchestrator(TEST_QUERIES[0])