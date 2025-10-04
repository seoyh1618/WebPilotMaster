Domain Priority Classifier Overview
1. domains.yaml 구성 정의와 활용 방식
- 구조 개요
- config/domains.yaml은 전역 설정(global_config)과 domains 배열로 구성됩니다.
- 각 도메인은 다음 공통 필드를 가지며, 휴리스틱 규칙과 가드레일을 통해 질의 매칭 로직을 정의합니다.
    - name, domain_id, urls, aliases
    - description, importance_weight, freshness_weight
    - is_default_fallback: 휴리스틱 폴백 시 기본 후보로 포함할지 여부
    - specialization: 도메인 범위(scope), 대상 사용자 등
    - key_features: Stage 2 프롬프트에 활용되는 대표 특징
    - heuristic: exclusive_signals, strong_signals, common_signals, negative_signals
    - guardrails: must_prioritize_patterns, exclude_patterns

- 일반대학원 도메인 예시
    - name: "일반대학원"
      ...
      heuristic:
        exclusive_signals:
          - "BK21"
          - "석박사통합"
        strong_signals:
          - "논문심사"
          - "논문제출"
        common_signals:
          - "등록금"
          - "장학금"
        negative_signals:
          - "재직자 전용"
          - "야간수업"
      guardrails:
        must_prioritize_patterns:
          - "논문.*심사"
          - "전일제.*과정"
        exclude_patterns:
          - "재직자.*야간"
          - "ITMBA"

- exclusive_signals / must_prioritize_patterns는 Stage 1 필터링에서 강제 포함 조건으로 사용되고, exclude_patterns는 즉시 제외 조건으로 작동합니다.
- is_default_fallback: true 덕분에 폴백 단계에서 다른 후보가 부족하면 자동으로 추가되는 효과가 있습니다.


- 로드 정의
- _load_domains()는 YAML 파일을 읽어 전역 설정과 도메인 리스트를 반환하며, @lru_cache(maxsize=1)로 최초 1회만 로딩합니다.
    @lru_cache(maxsize=1)
    def _load_domains() -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        data = yaml.safe_load(YAML_PATH.read_text(encoding="utf-8"))
        global_config = data.get("global_config", {})
        domains = data.get("domains", [])
        ...
        return global_config, domains

- 반환된 domains 리스트를 이후 단계가 직접 순회하며 휴리스틱/가드레일 정보에 접근합니다.
- 전역 설정(global_config)은 아직 제한적으로만 사용되지만, 이후 기능 확장 시 임계값이나 옵션 제어용으로 활용할 수 있도록 구조화돼 있습니다.

- 프롬프트 연계
- prompt.py의 INSTRUCTION 문자열은 LLM에게 동일한 도메인 목록과 역할 규칙(대안 도메인 필수, JSON 출력 등)을 명시해, 모델이 코드 로직과 통일된 도메인 집합을 인지하도록 돕습니다.
    # 도메인
    1. 일반대학원 ...
    2. ITMBA ...
    ...

2. 우선순위 선정 알고리즘 정의 (3-Stage Workflow)

2.1 Stage 1 — Rapid Filtering 정의 및 활용
1. 휴리스틱 기반 사전 필터링 (_heuristic_pre_filter)
도메인별 guardrails와 heuristic 설정을 순회하며 포함/제외 여부를 결정합니다.

     def _heuristic_pre_filter(query, domains):
         for domain in domains:
             guardrails = domain.get("guardrails", {})
             heuristic = domain.get("heuristic", {})
             if exclude_patterns 매칭 → continue
             elif must_prioritize_patterns 매칭 → must_include.append(domain)
             elif exclusive_signals 포함 → must_include.append(domain)
             else → candidates.append(domain)
         if must_include:
             기본 폴백 도메인 포함 → 상위 3개만 반환
         return candidates

- 정의 자체가 “휴리스틱 규칙을 우선 적용하고, must-include 집합이 있다면 fallback 후보를 추가한 뒤 상위 3개로 제한한다”는 정책을 명시합니다.
- 활용 측면에서 Stage 1 전체 후보의 폭을 줄여 Stage 2 LLM 호출 비용을 감소시키는 역할을 합니다.

2. LLM 기반 배치 필터링 (_llm_batch_relevance_check)
- 휴리스틱 후 후보가 3개 이상일 때, 각 도메인의 scope를 요약해 LLM에 제시합니다.
- LLM에게 JSON 배열 형태로 “관련 도메인 번호”만 돌려 달라 요구하고, 결과 인덱스를 검증해서 후보를 좁힙니다.

     system_prompt = "질의와 관련 있는 도메인을 모두 선택..."
     user_prompt = f"""질의: "{query}" ...
     result = _extract_json(response)
     selected_indices = result.get("selected", [])

- LLM 응답이 비정상인 경우 실패 로그를 남기고 원래 후보를 그대로 사용합니다.

2.2 Stage 2 — Comparative Ranking 정의 및 활용

1. LLM 비교 랭킹 (_llm_comparative_ranking)
Stage 1 후보가 2개 이상일 때 실행하며, 도메인 별 key_features를 활용해 프롬프트를 구성합니다

     system_prompt = """당신은 도메인 분류 전문가... 최소 2개 반환"""
     user_prompt = f"""질의: "{query}" ..."""
     response = _call_llm(...)
     ranking_data = result.get("ranking", [])

- LLM이 JSON을 정확히 반환하면, domain_name을 기준으로 원본 도메인 객체와 매핑해 리스트를 구성합니다.
- 결과 목록을 rank 오름차순으로 정렬하고, 1개만 존재하면 자동으로 두 번째 후보를 추가하여 최소 2개를 보장합니다.

2. 휴리스틱 폴백 (_fallback_ranking)
- LLM 호출 실패, JSON 파싱 실패, 혹은 결과가 비어 있을 때 실행하도록 정의된 함수입니다

     score = 40 (exclusive) + 20 (strong) + 30 (is_default_fallback)
     confidence = score 기준으로 medium/low/very_low
     ...
     최소 2개 보장 로직 포함


- 질의를 _norm(query)로 소문자/공백 제거 정규화 후 각 신호를 비교하여 점수를 누적합니다.
- is_default_fallback이 true인 도메인은 자동으로 30점을 추가 받아 기본 후보 역할을 수행하게 됩니다.

3. Stage 2 컨트롤러 (_stage2_comparative_ranking)
- 위 두 함수 정의를 감싸 Stage 2 전체를 관장합니다.

     if len(candidates) == 1: 유일 후보 반환
     try:
         ranking_result = _llm_comparative_ranking(...)
     except Exception:
         ranking_result = _fallback_ranking(...)
- 최근 수정으로, LLM이 빈 결과를 반환하는 경우에도 폴백 로직을 호출하도록 추가 보강이 필요합니다(추후 개선 예정).

2.3 Stage 3 — Selection Guarantee 정의 및 활용
- 최소 결과 보장 (_ensure_minimum_domains)
- Stage 2 결과를 받아 primary와 alternatives 배열을 구성합니다.

     selected = [ranked[0]]
     if len(ranked) >= 2:
         alternatives_count = min(len(ranked) - 1, 3)
         selected.extend(ranked[1:1+alternatives_count])
     selection_info = {...}

- 반환값은 (selected, selection_info) 튜플입니다.
- 이 정의 덕분에 최종 결과가 항상 primary 1개와 최대 3개의 대안으로 구성되며, Stage 2에서 1개만 나온 경우라도 경고 로그를 남겨 후속 보강 필요성을 알립니다.



3. 사용자 쿼리 처리 전체 흐름
1. 에이전트 초기화
- Domain_Priority_Classifier_Agent는 planner_agents/.../agent.py에서 초기화되며, LiteLlm 인스턴스와 _classify_handler가 도구로 등록됩니다.
- INSTRUCTION, DESCRIPTION이 모델에 제공되어 역할과 출력 형식이 명시됩니다.
2. 입력 처리 (_classify_handler)
- 공백 질의는 즉시 {primary: None, alternatives: [], reason: "빈 쿼리"}를 반환합니다.
- 유효 질의는 classify_domain_priorities(query, get_llm_client())를 호출합니다.
- 예외 발생 시 로그를 남기고 휴리스틱 폴백 결과를 반환합니다.

classify_domain_priorities 파이프라인
   def classify_domain_priorities(query, llm_client):
       global_config, domains = _load_domains()
       candidates = _stage1_filter_domains(query, domains, llm_client)
       ranked = _stage2_comparative_ranking(query, candidates, llm_client)
       selected, selection_info = _ensure_minimum_domains(ranked)
       primary/alternatives 포맷팅 후 메타데이터와 함께 반환

→ Stage 1 -> Stage 2 -> Stage 3 순으로 수행되며, 각 단계에서 실패 시 폴백 정의를 사용해 결과를 채웁니다.
→ 최종 포맷은 primary, alternatives, reason, metadata 구조를 갖는 dict입니다.

[ 출력 가공 ]
  → test_classification(), batch_test() 함수는 반환된 dict를 콘솔 친화적인 텍스트로 변환해 개발자가 결과를 확인할 수 있게 합니다.
  → metadata.selection_info에는 후보 수, 선택된 대안 수 등을 기록해 디버깅 및 품질 평가에 활용할 수 있습니다.

4. 흐름 요약 (텍스트 시그널 맵)
[사용자 질의] 
   → (Stage 0) _classify_handler: 입력 검증 및 LLM 클라이언트 획득
   → (Stage 1) 휴리스틱 필터 + (조건부) LLM 배치 필터
        정의: guardrails/heuristic 기반 포함·제외 규칙
        활용: 후보 수를 2~3개로 축소, LLM 비용 절감
   → (Stage 2) LLM 상대 평가 or 휴리스틱 폴백
        정의: 최소 2개 랭킹 JSON 요구
        활용: 점수, 신뢰도, condition 생성
   → (Stage 3) 결과 보장 및 포맷팅
        정의: primary 1 + alternative ≥ 1, 최대 3개
        활용: `_score_to_priority`, `metadata` 작성
   → 최종 dict 반환 (primary, alternatives, reason, metadata)