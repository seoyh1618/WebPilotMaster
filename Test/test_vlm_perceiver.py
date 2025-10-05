# Test/test_vlm_perceiver.py
"""
Multimodal Perceiver Agent VLM 테스트
- 스크린샷 캡처
- HTML 파싱
- Vision 분석 (VLM)
- 전체 Perceiver Agent 워크플로우
"""
import sys
from pathlib import Path
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from WebPilot.executor_agents.multimodal_perceiver_agent import (
    MultilmodalPerceiverAgentClass,
    PerceiverInput,
    PageAnalysisResult
)
from WebPilot.executor_agents.multimodal_perceiver_agent.screenshot import ScreenshotCapture
from WebPilot.executor_agents.multimodal_perceiver_agent.html_parser import HTMLParser
from WebPilot.executor_agents.multimodal_perceiver_agent.vision_analyzer import VisionAnalyzer
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


# ============================================
# 1. 스크린샷 캡처 테스트
# ============================================

def test_screenshot_capture(url: str):
    """스크린샷 캡처 단독 테스트"""
    print_separator("스크린샷 캡처 테스트")
    print(f"URL: {url}\n")
    
    try:
        capture = ScreenshotCapture()
        
        logger.info("스크린샷 캡처 시작...")
        base64_image, html_content = capture.capture(url)
        
        print(f"✅ 캡처 성공!")
        print(f"  - 이미지 크기: {len(base64_image)} bytes")
        print(f"  - HTML 크기: {len(html_content)} bytes")
        print(f"  - 저장 위치: {constants.PERCEIVER_SCREENSHOT_DIR}")
        
        return base64_image, html_content
        
    except Exception as e:
        print(f"❌ 캡처 실패: {e}")
        logger.error(f"스크린샷 캡처 실패", exc_info=True)
        return None, None


# ============================================
# 2. HTML 파싱 테스트
# ============================================

def test_html_parser(html_content: str, url: str):
    """HTML 파싱 단독 테스트"""
    print_separator("HTML 파싱 테스트")
    
    try:
        parser = HTMLParser()
        
        logger.info("HTML 파싱 시작...")
        summary = parser.parse(html_content, base_url=url)
        
        print(f"✅ 파싱 성공!")
        print(f"  - 페이지 제목: {summary.get('title', 'N/A')}")
        print(f"  - 페이지 타입: {summary.get('page_type', 'N/A')}")
        print(f"  - 총 링크: {summary.get('total_links', 0)}개")
        print(f"  - 총 버튼: {summary.get('total_buttons', 0)}개")
        print(f"  - 네비게이션: {summary.get('has_navigation', False)}")
        print(f"  - 검색 기능: {summary.get('has_search', False)}")
        print(f"  - 로그인: {summary.get('has_login', False)}")
        
        if summary.get('links'):
            print(f"\n  상위 5개 링크:")
            for i, link in enumerate(summary['links'][:5], 1):
                print(f"    {i}. [{link.get('index', 'N/A')}] {link.get('text', 'N/A')[:50]}")
        
        return summary
        
    except Exception as e:
        print(f"❌ 파싱 실패: {e}")
        logger.error(f"HTML 파싱 실패", exc_info=True)
        return None


# ============================================
# 3. Vision Analyzer (VLM) 테스트
# ============================================

def test_vision_analyzer(base64_image: str, html_summary: Dict, query: str, url: str):
    """Vision Analyzer (VLM) 단독 테스트"""
    print_separator("Vision Analyzer (VLM) 테스트")
    print(f"질의: {query}\n")
    
    try:
        analyzer = VisionAnalyzer()
        
        logger.info("VLM 분석 시작...")
        analysis = analyzer.analyze(
            base64_image=base64_image,
            html_summary=html_summary,
            query=query,
            url=url
        )
        
        print(f"✅ VLM 분석 완료!")
        print_analysis_result(analysis)
        
        return analysis
        
    except Exception as e:
        print(f"❌ VLM 분석 실패: {e}")
        logger.error(f"VLM 분석 실패", exc_info=True)
        return None


# ============================================
# 4. 전체 Perceiver Agent 테스트
# ============================================

def test_perceiver_agent(url: str, query: str):
    """전체 Perceiver Agent 워크플로우 테스트"""
    print_separator("Perceiver Agent 통합 테스트")
    print(f"URL: {url}")
    print(f"질의: {query}\n")
    
    try:
        agent = MultilmodalPerceiverAgentClass()
        
        # 입력 생성
        input_data = {
            "url": url,
            "query": query,
            "screenshot_required": True,
            "depth": 0
        }
        
        logger.info("Perceiver Agent 실행...")
        result_json = agent.run(json.dumps(input_data, ensure_ascii=False))
        
        result = json.loads(result_json)
        
        print(f"✅ Agent 실행 완료!")
        print(f"  - 성공 여부: {result.get('success', False)}")
        print(f"  - 실행 시간: {result.get('execution_time', 0):.2f}초")
        print(f"  - 폴백 사용: {result.get('fallback_used', False)}")
        
        if result.get('error_message'):
            print(f"  ⚠️ 에러: {result['error_message']}")
        
        # 분석 결과 출력
        if result.get('analysis'):
            print("\n분석 결과:")
            analysis = result['analysis']
            print_analysis_dict(analysis)
        
        return result
        
    except Exception as e:
        print(f"❌ Agent 실행 실패: {e}")
        logger.error(f"Perceiver Agent 실행 실패", exc_info=True)
        return None


# ============================================
# 결과 출력 헬퍼
# ============================================

def print_analysis_result(analysis: PageAnalysisResult):
    """PageAnalysisResult 객체 출력"""
    print(f"\n📊 분석 결과:")
    print(f"  - 정보 발견: {analysis.information_found}")
    print(f"  - 신뢰도: {analysis.confidence:.2f}")
    print(f"  - 페이지 타입: {analysis.page_type}")
    print(f"  - 제목: {analysis.title}")
    
    if analysis.summary:
        print(f"  - 요약: {analysis.summary[:100]}...")
    
    if analysis.extracted_info:
        print(f"\n📝 추출된 정보:")
        print(f"  {analysis.extracted_info[:200]}...")
    
    # 보이는 요소
    if analysis.visible_elements:
        print(f"\n👁️ 보이는 요소 ({len(analysis.visible_elements)}개):")
        for i, elem in enumerate(analysis.visible_elements[:5], 1):
            print(f"  {i}. [{elem.type}] {elem.text[:40]}")
            if elem.href:
                print(f"     링크: {elem.href[:60]}")
    
    # 키워드 매칭
    if analysis.keyword_matches:
        print(f"\n🔍 키워드 매칭:")
        for keyword, contexts in list(analysis.keyword_matches.items())[:3]:
            print(f"  '{keyword}': {len(contexts)}개 발견")
            for ctx in contexts[:2]:
                print(f"    - {ctx[:60]}...")
    
    # 추천 액션
    if analysis.recommended_action:
        print(f"\n🎯 추천 액션:")
        rec = analysis.recommended_action
        print(f"  - 클릭 여부: {rec.should_click}")
        
        if rec.should_click:
            print(f"  - 요소 인덱스: [{rec.element_index}]")
            print(f"  - 요소 텍스트: {rec.element_text}")
            print(f"  - 액션 타입: {rec.action_type}")
            print(f"  - Confidence: {rec.confidence:.2f}")
            print(f"  - 폴백 여부: {rec.is_fallback}")
            
            if rec.href:
                print(f"  - 링크: {rec.href}")
            
            if rec.coordinates:
                print(f"  - 좌표: ({rec.coordinates['x']}, {rec.coordinates['y']})")
            
            print(f"  - 이유: {rec.reasoning[:150]}...")
            
            # 대안 요소
            if rec.alternative_elements:
                print(f"  - 대안 요소: {rec.alternative_elements}")
            
            # 드롭다운
            if rec.requires_submenu_selection:
                print(f"  - 드롭다운: 하위 메뉴 선택 필요")
                print(f"  - 하위 메뉴 수: {len(rec.visible_submenus)}개")
                if rec.recommended_submenu_index is not None:
                    print(f"  - 추천 하위 메뉴: [{rec.recommended_submenu_index}]")
            
            # 파일 다운로드
            if rec.should_download and rec.file_info:
                print(f"  - 파일 다운로드: {rec.file_info.file_name}")
                print(f"  - 파일 타입: {rec.file_info.file_type}")
                print(f"  - 파일 URL: {rec.file_info.file_url}")
    else:
        print(f"\n🎯 추천 액션: 없음")
    
    # 경고
    if analysis.analysis_warnings:
        print(f"\n⚠️ 경고 ({len(analysis.analysis_warnings)}개):")
        for warning in analysis.analysis_warnings[:3]:
            print(f"  - {warning}")


def print_analysis_dict(analysis: Dict):
    """Dict 형태의 분석 결과 출력"""
    print(f"  - 정보 발견: {analysis.get('information_found', False)}")
    print(f"  - 신뢰도: {analysis.get('confidence', 0):.2f}")
    print(f"  - 페이지 타입: {analysis.get('page_type', 'N/A')}")
    
    if analysis.get('extracted_info'):
        print(f"\n  추출된 정보:")
        print(f"  {analysis['extracted_info'][:200]}...")
    
    if analysis.get('recommended_action'):
        rec = analysis['recommended_action']
        if rec.get('should_click'):
            print(f"\n  추천 액션: [{rec.get('element_index')}] {rec.get('element_text')}")
            print(f"  Confidence: {rec.get('confidence', 0):.2f}")


# ============================================
# 시나리오 테스트
# ============================================

TEST_SCENARIOS = [
    {
        "name": "숭실대학원 사물함 정보",
        "url": "https://grad.ssu.ac.kr/",
        "query": "사물함 신청 방법 알려줘"
    },
    {
        "name": "공지사항 탐색",
        "url": "https://grad.ssu.ac.kr/",
        "query": "공지사항에서 최신 글 확인"
    },
    {
        "name": "등록금 정보",
        "url": "https://grad.ssu.ac.kr/",
        "query": "등록금 납부 기한 확인"
    },
]


def run_scenario_test(scenario: Dict):
    """단일 시나리오 테스트"""
    print_separator(f"시나리오: {scenario['name']}", "=")
    print(f"URL: {scenario['url']}")
    print(f"질의: {scenario['query']}")
    
    result = test_perceiver_agent(scenario['url'], scenario['query'])
    
    # 결과 저장
    if result:
        save_test_result(scenario, result)
    
    return result


def run_all_scenarios():
    """모든 시나리오 실행"""
    print_separator("VLM Perceiver 시나리오 테스트", "=")
    
    results = []
    
    for i, scenario in enumerate(TEST_SCENARIOS, 1):
        print(f"\n\n{'='*80}")
        print(f" 시나리오 {i}/{len(TEST_SCENARIOS)}")
        print(f"{'='*80}\n")
        
        result = run_scenario_test(scenario)
        
        results.append({
            "scenario": scenario['name'],
            "success": result and result.get('success', False),
            "result": result
        })
        
        # 테스트 간 대기
        if i < len(TEST_SCENARIOS):
            import time
            print("\n⏱ 다음 테스트까지 3초 대기...")
            time.sleep(3)
    
    # 전체 결과 요약
    print_separator("전체 시나리오 결과", "=")
    
    success_count = sum(1 for r in results if r['success'])
    total_count = len(results)
    
    print(f"\n총 시나리오: {total_count}개")
    print(f"성공: {success_count}개")
    print(f"실패: {total_count - success_count}개")
    
    print("\n개별 결과:")
    for i, r in enumerate(results, 1):
        status = "✅" if r['success'] else "❌"
        print(f"  {i}. {status} {r['scenario']}")


# ============================================
# 단계별 테스트 (디버깅용)
# ============================================

def run_step_by_step_test(url: str, query: str):
    """각 컴포넌트를 단계별로 테스트"""
    print_separator("단계별 VLM 테스트", "=")
    print(f"URL: {url}")
    print(f"질의: {query}\n")
    
    # Step 1: 스크린샷 캡처
    base64_image, html_content = test_screenshot_capture(url)
    if not base64_image or not html_content:
        print("\n❌ 스크린샷 캡처 실패로 중단")
        return
    
    # Step 2: HTML 파싱
    html_summary = test_html_parser(html_content, url)
    if not html_summary:
        print("\n❌ HTML 파싱 실패로 중단")
        return
    
    # Step 3: Vision 분석
    analysis = test_vision_analyzer(base64_image, html_summary, query, url)
    if not analysis:
        print("\n❌ Vision 분석 실패")
        return
    
    print_separator("✅ 모든 단계 성공!", "=")


# ============================================
# 결과 저장
# ============================================

def save_test_result(scenario: Dict, result: Dict):
    """테스트 결과를 JSON 파일로 저장"""
    results_dir = Path("Test/results/vlm_tests")
    results_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    scenario_name = scenario['name'].replace(' ', '_')
    filename = f"vlm_{scenario_name}_{timestamp}.json"
    
    output = {
        "scenario": scenario,
        "timestamp": datetime.now().isoformat(),
        "result": result
    }
    
    filepath = results_dir / filename
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    logger.info(f"결과 저장: {filepath}")


def check_screenshots():
    """생성된 스크린샷 확인"""
    screenshot_dir = Path(constants.PERCEIVER_SCREENSHOT_DIR)
    
    print_separator("스크린샷 파일 확인")
    print(f"디렉토리: {screenshot_dir.absolute()}")
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


# ============================================
# 메인 실행
# ============================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Multimodal Perceiver VLM 테스트")
    parser.add_argument("--url", type=str, help="테스트할 URL")
    parser.add_argument("--query", type=str, help="질의")
    parser.add_argument("--step-by-step", action="store_true", help="단계별 테스트")
    parser.add_argument("--all-scenarios", action="store_true", help="모든 시나리오 실행")
    parser.add_argument("--check-screenshots", action="store_true", help="스크린샷 확인만")
    
    args = parser.parse_args()
    
    if args.check_screenshots:
        check_screenshots()
    
    elif args.all_scenarios:
        run_all_scenarios()
    
    elif args.step_by_step and args.url and args.query:
        run_step_by_step_test(args.url, args.query)
    
    elif args.url and args.query:
        test_perceiver_agent(args.url, args.query)
        check_screenshots()
    
    else:
        # 기본: 첫 번째 시나리오 실행
        print("기본 모드: 첫 번째 시나리오 실행\n")
        print("사용법:")
        print("  python Test/test_vlm_perceiver.py --url <URL> --query <질의>")
        print("  python Test/test_vlm_perceiver.py --all-scenarios")
        print("  python Test/test_vlm_perceiver.py --step-by-step --url <URL> --query <질의>")
        print("  python Test/test_vlm_perceiver.py --check-screenshots\n")
        
        run_scenario_test(TEST_SCENARIOS[0])
        check_screenshots()