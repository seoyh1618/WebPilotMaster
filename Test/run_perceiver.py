import json
import logging
import os

from WebPilot.executor_agents.multimodal_perceiver_agent.agent import MultilmodalPerceiverAgentClass


def main():
    # 필요 시 DEBUG로 상세 로그 확인
    os.environ.setdefault("WEBPILOT_LOG_LEVEL", "INFO")

    logger = logging.getLogger(__name__)
    logger.info("Perceiver 테스트 실행")

    agent = MultilmodalPerceiverAgentClass()

    sample_input = {
        "url": "https://grad.ssu.ac.kr/",
        "query": "숭실 대학원 사물함 신청을 어떻게 하는지 찾아주세요.",
        "screenshot_required": True,
        "depth": 0,
    }

    output = agent.run(json.dumps(sample_input, ensure_ascii=False))
    print("\n=== Perceiver Output ===")
    print(output)


if __name__ == "__main__":
    main()


