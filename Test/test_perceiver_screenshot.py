# Test/test_perceiver_screenshot.py
"""
Multimodal Perceiver Agent 스크린샷 생성 테스트
"""
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from WebPilot.executor_agents.multimodal_perceiver_agent.agent import MultilmodalPerceiverAgentClass
from WebPilot.constants import constants
import json
import logging

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def test_screenshot_capture():
    """스크린샷 캡처 및 저장 테스트"""
    
    # 현재 설정 확인
    logger.info("=== 현재 스크린샷 설정 ===")
    logger.info(f"SAVE_SCREENSHOTS: {constants.PERCEIVER_SAVE_SCREENSHOTS}")
    logger.info(f"SCREENSHOT_DIR: {constants.PERCEIVER_SCREENSHOT_DIR}")
    logger.info("")
    
    # Agent 생성
    logger.info("Agent 생성 중...")
    agent = MultilmodalPerceiverAgentClass()
    
    # 테스트 입력
    test_input = {
        "url": "https://grad.ssu.ac.kr/",
        "query": "공지사항 찾기",
        "screenshot_required": True
        # depth 제거 - PerceiverInput 모델에 정의되지 않음
    }
    
    logger.info(f"테스트 실행: {test_input['url']}")
    logger.info("")
    
    # Agent 실행
    result = agent.run(json.dumps(test_input, ensure_ascii=False))
    
    # 결과 출력
    result_dict = json.loads(result)
    logger.info("=== 실행 결과 ===")
    #logger.info(f"성공 여부: {result_dict['success']}")
    logger.info(f"실행 시간: {result_dict}")    
    # 스크린샷 디렉토리 확인
    screenshot_dir = Path(constants.PERCEIVER_SCREENSHOT_DIR)
    logger.info("")
    logger.info("=== 스크린샷 디렉토리 확인 ===")
    logger.info(f"경로: {screenshot_dir.absolute()}")
    logger.info(f"존재 여부: {screenshot_dir.exists()}")
    
    if screenshot_dir.exists():
        screenshots = list(screenshot_dir.glob("*.png"))
        logger.info(f"스크린샷 파일 수: {len(screenshots)}")
        if screenshots:
            logger.info("파일 목록:")
            for img in screenshots:
                logger.info(f"  - {img.name} ({img.stat().st_size / 1024:.1f} KB)")
    else:
        logger.warning("⚠ 디렉토리가 생성되지 않았습니다!")
    
    return result_dict

if __name__ == "__main__":
    try:
        test_screenshot_capture()
    except Exception as e:
        logger.error(f"테스트 실패: {e}", exc_info=True)