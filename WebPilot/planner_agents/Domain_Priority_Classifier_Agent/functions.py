from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple
import json
import re
from functools import lru_cache
from pathlib import Path
import yaml
import logging
import time
import litellm

logger = logging.getLogger(__name__)

YAML_PATH: Path = Path(__file__).resolve().parents[2] / "config" / "domains.yaml"

@lru_cache(maxsize=1)
def _load_domains() -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """domains.yaml 로드"""
    try:
        if not YAML_PATH.exists():
            raise FileNotFoundError(f"domains.yaml을 찾을 수 없습니다: {YAML_PATH}")
        
        data = yaml.safe_load(YAML_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("domains.yaml 형식 오류")
        
        global_config = data.get("global_config", {})
        domains = data.get("domains", [])
        
        if not isinstance(domains, list):
            raise ValueError("domains는 리스트여야 합니다")
        
        logger.info(f"도메인 로드 완료: {len(domains)}개")
        return global_config, domains
        
    except Exception as e:
        logger.error(f"도메인 로드 실패: {str(e)}")
        raise

def _norm(s: str) -> str:
    """정규화"""
    return re.sub(r"\s+", "", (s or "").lower())

def _extract_json(text: str) -> Dict[str, Any]:
    """LLM 응답에서 JSON 추출"""
    if not text:
        return {}
    
    text = text.strip()
    code_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    if code_match:
        try:
            return json.loads(code_match.group(1))
        except json.JSONDecodeError:
            pass
    
    json_match = re.search(r"\{.*?\}", text, re.S)
    if json_match:
        try:
            return json.loads(json_match.group(0))
        except json.JSONDecodeError:
            pass
    
    return {}

def _check_pattern_match(text: str, patterns: List[str]) -> bool:
    """정규식 패턴 매칭"""
    if not patterns:
        return False
    for pattern in patterns:
        try:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        except re.error:
            pass
    return False

def _call_llm(llm_client: Any, messages: List[Dict[str, str]], temperature: float = 0) -> str:
    """LLM 클라이언트 호출 - litellm.completion() 직접 사용"""
    try:
        model_name = str(getattr(llm_client, "model", "") or "")
        request_kwargs = {
            "model": model_name or llm_client.model,
            "messages": messages,
            "timeout": 30,
        }

        adjusted_temperature = temperature
        if model_name.startswith("openai/o"):
            if temperature != 1:
                logger.info(f"O-시리즈 모델 감지 → temperature 조정: {temperature} → 1")
            adjusted_temperature = 1.0

        if adjusted_temperature is not None:
            request_kwargs["temperature"] = adjusted_temperature

        response = litellm.completion(**request_kwargs)

        if hasattr(response, "choices") and response.choices:
            content = response.choices[0].message.content
            logger.debug(f"LLM 응답: {content[:100]}...")
            return content

        return str(response)

    except Exception as e:
        logger.error(f"LLM 호출 실패: {type(e).__name__} - {str(e)}")
        raise
# Stage 1
def _heuristic_pre_filter(query: str, domains: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """휴리스틱 사전 필터링"""
    candidates = []
    must_include = []
    
    for domain in domains:
        domain_name = domain.get("name", "")
        guardrails = domain.get("guardrails", {})
        heuristic = domain.get("heuristic", {})
        
        exclude_patterns = guardrails.get("exclude_patterns", [])
        if _check_pattern_match(query, exclude_patterns):
            logger.debug(f"{domain_name}: Exclude → 제외")
            continue
        
        must_patterns = guardrails.get("must_prioritize_patterns", [])
        if _check_pattern_match(query, must_patterns):
            logger.info(f"{domain_name}: Must prioritize → 포함")
            must_include.append(domain)
            continue
        
        exclusive_signals = heuristic.get("exclusive_signals", [])
        if any(_norm(sig) in _norm(query) for sig in exclusive_signals):
            logger.info(f"{domain_name}: Exclusive signal → 포함")
            must_include.append(domain)
            continue
        
        candidates.append(domain)
    
    if must_include:
        result = must_include.copy()
        for d in candidates:
            if d.get("is_default_fallback"):
                result.append(d)
                break
        return result[:3]
    
    return candidates

def _llm_batch_relevance_check(query: str, domains: List[Dict[str, Any]], llm_client: Any) -> List[Dict[str, Any]]:
    """배치 LLM 필터링"""
    domains_summary = []
    for i, domain in enumerate(domains, 1):
        name = domain.get("name", "")
        scope = domain.get("specialization", {}).get("scope", "")
        domains_summary.append(f"{i}. {name}: {scope}")
    
    domains_text = "\n".join(domains_summary)
    
    system_prompt = """질의와 관련 있는 도메인을 모두 선택하세요.
JSON만 출력: {"selected": [1, 3, 5]}"""
    
    user_prompt = f"""질의: "{query}"

도메인:
{domains_text}

관련 있는 도메인 번호를 선택하세요."""
    
    try:
        response = _call_llm(llm_client, [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ], temperature=0)
        
        result = _extract_json(response)
        selected_indices = result.get("selected", [])
        
        candidates = []
        for idx in selected_indices:
            if isinstance(idx, int) and 1 <= idx <= len(domains):
                candidates.append(domains[idx - 1])
        
        if not candidates:
            return domains
        
        logger.info(f"LLM 배치 필터링: {len(domains)}개 → {len(candidates)}개")
        return candidates
        
    except Exception as e:
        logger.error(f"배치 LLM 실패: {e}")
        return domains

def _stage1_filter_domains(query: str, domains: List[Dict[str, Any]], llm_client: Any) -> List[Dict[str, Any]]:
    """Stage 1: Rapid Filtering"""
    logger.info("Stage 1 시작")
    start_time = time.time()
    
    pre_filtered = _heuristic_pre_filter(query, domains)
    
    if len(pre_filtered) <= 2:
        logger.info(f"Stage 1 완료(휴리스틱): {len(pre_filtered)}개")
        return pre_filtered
    
    try:
        candidates = _llm_batch_relevance_check(query, pre_filtered, llm_client)
    except Exception as e:
        logger.error(f"LLM 필터링 실패: {e}")
        candidates = pre_filtered
    
    elapsed = time.time() - start_time
    logger.info(f"Stage 1 완료: {len(domains)}개 → {len(candidates)}개 ({elapsed:.2f}s)")
    return candidates

# Stage 2
def _llm_comparative_ranking(query: str, candidates: List[Dict[str, Any]], llm_client: Any) -> List[Dict[str, Any]]:
    """LLM 상대 평가 (무조건 최소 2개 반환)"""
    candidates_info = []
    for i, domain in enumerate(candidates, 1):
        name = domain.get("name", "")
        features = ", ".join(domain.get("key_features", [])[:3])
        candidates_info.append(f"{i}. {name}: {features}")
    
    candidates_text = "\n".join(candidates_info)
    
    system_prompt = """당신은 도메인 분류 전문가입니다.

중요 규칙:
1. **무조건 최소 2개 이상**의 도메인을 반환하세요
2. 1순위가 명확해도 2순위(대안)를 반드시 포함하세요
3. 2순위는 낮은 점수와 "조건"을 명시하세요

JSON 형식으로만 응답:
{
  "ranking": [
    {
      "domain_name": "도메인1",
      "rank": 1,
      "score": 85,
      "confidence": "high",
      "reasoning": "이유"
    },
    {
      "domain_name": "도메인2",
      "rank": 2,
      "score": 70,
      "confidence": "medium",
      "reasoning": "이유",
      "condition": "특정 상황인 경우"
    }
  ]
}"""
    
    user_prompt = f"""질의: "{query}"

후보:
{candidates_text}

최소 2개 이상 순위를 매기세요."""
    
    response = _call_llm(llm_client, [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ], temperature=0)
    
    result = _extract_json(response)
    ranking_data = result.get("ranking", [])
    
    name_to_domain = {d.get("name", ""): d for d in candidates}
    
    ranked_results = []
    for item in ranking_data:
        domain_name = item.get("domain_name", "")
        domain_obj = name_to_domain.get(domain_name)
        
        if domain_obj:
            ranked_results.append({
                "domain": domain_obj,
                "rank": item.get("rank", 99),
                "score": float(item.get("score", 50.0)),
                "confidence": str(item.get("confidence", "medium")).strip().lower(),
                "reasoning": item.get("reasoning", ""),
                "condition": item.get("condition", "")
            })
    
    ranked_results.sort(key=lambda x: x["rank"])
    
    # ✅ LLM이 1개만 반환한 경우 2순위 자동 추가
    if len(ranked_results) == 1 and len(candidates) >= 2:
        first_score = ranked_results[0]["score"]
        for domain in candidates:
            if domain.get("name") != ranked_results[0]["domain"].get("name"):
                ranked_results.append({
                    "domain": domain,
                    "rank": 2,
                    "score": max(first_score - 15.0, 50.0),  # 1순위보다 낮은 점수
                    "confidence": "low",
                    "reasoning": "자동 추가된 대안 도메인",
                    "condition": "1순위가 적합하지 않은 경우"
                })
                break
    
    return ranked_results

def _fallback_ranking(query: str, candidates: List[Dict[str, Any]], error_detail: str) -> List[Dict[str, Any]]:
    """휴리스틱 폴백 (LLM 보완용)"""
    logger.warning(f"폴백 사용: {error_detail}")
    
    scored = []
    query_norm = _norm(query)
    
    for domain in candidates:
        heuristic = domain.get("heuristic", {})
        score = 0.0
        matched = []
        
        for sig in heuristic.get("exclusive_signals", []):
            if _norm(sig) in query_norm:
                score += 40.0
                matched.append(f"배타:{sig}")
        
        for sig in heuristic.get("strong_signals", []):
            if _norm(sig) in query_norm:
                score += 20.0
                matched.append(f"강:{sig}")
        
        if domain.get("is_default_fallback"):
            score += 30.0
            matched.append("기본폴백")
        
        confidence = "medium" if score >= 70 else "low" if score >= 40 else "very_low"
        
        scored.append({
            "domain": domain,
            "score": score,
            "confidence": confidence,
            "reasoning": f"휴리스틱 매칭: {', '.join(matched) if matched else '없음'}",
            "fallback_reason": error_detail,
            "matched_keywords": matched,
            "condition": ""
        })
    
    scored.sort(key=lambda x: x["score"], reverse=True)
    
    for i, item in enumerate(scored, 1):
        item["rank"] = i
    
    # ✅ 최소 2개 보장
    if len(scored) < 2 and len(candidates) >= 2:
        for domain in candidates:
            if domain not in [s["domain"] for s in scored]:
                scored.append({
                    "domain": domain,
                    "rank": len(scored) + 1,
                    "score": 0.0,
                    "confidence": "very_low",
                    "reasoning": "휴리스틱 자동 추가",
                    "fallback_reason": error_detail,
                    "condition": "다른 옵션이 적합하지 않은 경우"
                })
                if len(scored) >= 2:
                    break
    
    return scored

def _stage2_comparative_ranking(query: str, candidates: List[Dict[str, Any]], llm_client: Any) -> List[Dict[str, Any]]:
    """Stage 2: Comparative Ranking"""
    logger.info("Stage 2 시작")
    start_time = time.time()
    
    if len(candidates) == 0:
        return []
    
    if len(candidates) == 1:
        # 1개뿐이어도 반환
        return [{
            "domain": candidates[0],
            "rank": 1,
            "score": 85.0,
            "confidence": "medium",
            "reasoning": "유일한 후보",
            "condition": ""
        }]
    
    try:
        ranking_result = _llm_comparative_ranking(query, candidates, llm_client)
    except Exception as e:
        logger.error(f"LLM 순위 평가 실패: {type(e).__name__} - {str(e)}")
        ranking_result = _fallback_ranking(query, candidates, f"{type(e).__name__}: {str(e)}")
    
    elapsed = time.time() - start_time
    logger.info(f"Stage 2 완료: {len(ranking_result)}개 ({elapsed:.2f}s)")
    return ranking_result

# Stage 3
def _ensure_minimum_domains(ranked: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    무조건 primary 1개 + alternatives 1개 이상 보장
    
    규칙:
    - primary: 1순위 (무조건)
    - alternatives: 2순위 이상 (무조건 최소 1개)
    - 점수 임계값 없음
    """
    if not ranked:
        return [], {"reason": "후보 없음"}
    
    # primary는 무조건 1순위
    selected = [ranked[0]]
    
    # alternatives는 나머지 중 최소 1개
    if len(ranked) >= 2:
        # 2~4순위까지 포함 (최대 3개)
        alternatives_count = min(len(ranked) - 1, 3)
        selected.extend(ranked[1:1+alternatives_count])
    elif len(ranked) == 1:
        # 1개뿐이면 경고 로그
        logger.warning("후보가 1개뿐 - alternatives 없음")
    
    selection_info = {
        "total_candidates": len(ranked),
        "selected_count": len(selected),
        "primary_count": 1,
        "alternatives_count": len(selected) - 1,
        "selection_rule": "1순위 무조건 + 2순위 이상 최소 1개"
    }
    
    return selected, selection_info

def _score_to_priority(score: float) -> str:
    """점수를 우선순위로 변환"""
    if score >= 80.0:
        return "critical"
    elif score >= 65.0:
        return "high"
    elif score >= 50.0:
        return "medium"
    else:
        return "low"

def classify_domain_priorities(query: str, llm_client: Any, **kwargs) -> Dict[str, Any]:
    """3-Stage Cascading Classification (LLM 중심)"""
    start_time = time.time()
    
    if not query or not query.strip():
        return {
            "primary": None,
            "alternatives": [],
            "reason": "빈 쿼리"
        }
    
    try:
        global_config, domains = _load_domains()
        
        if not domains:
            return {
                "primary": None,
                "alternatives": [],
                "reason": "도메인 정보 없음"
            }
        
        logger.info(f"도메인 분류 시작: '{query[:50]}...'")
        
        # Stage 1: 휴리스틱 사전 필터링
        candidates = _stage1_filter_domains(query, domains, llm_client)
        
        if not candidates:
            return {
                "primary": None,
                "alternatives": [],
                "reason": "관련 도메인 없음"
            }
        
        # Stage 2: LLM 상대 평가 (최소 2개 보장)
        ranked = _stage2_comparative_ranking(query, candidates, llm_client)
        
        if not ranked:
            return {
                "primary": None,
                "alternatives": [],
                "reason": "순위 매기기 실패"
            }
        
        # Stage 3: primary 1개 + alternatives 1개 이상 보장
        selected, selection_info = _ensure_minimum_domains(ranked)
        
        # 출력 형식화
        primary = None
        alternatives = []
        
        for i, item in enumerate(selected):
            domain = item.get("domain", {})
            urls = domain.get("urls", [])
            uri = urls[0] if urls else ""
            
            formatted = {
                "domain": domain.get("name", ""),
                "uri": uri,
                "score": round(item.get("score", 0.0), 1),
                "priority": _score_to_priority(item.get("score", 0.0)),
                "confidence": item.get("confidence", "medium"),
                "reasoning": item.get("reasoning", ""),
                "condition": item.get("condition", "")
            }
            
            # 폴백 정보 포함
            if "fallback_reason" in item:
                formatted["_fallback"] = True
            
            if i == 0:
                primary = formatted
            else:
                alternatives.append(formatted)
        
        # reason 생성
        reason_parts = []
        if primary:
            reason_parts.append(primary["reasoning"][:80])
        
        total_time = time.time() - start_time
        reason_parts.append(
            f"({total_time:.2f}s, "
            f"{selection_info['primary_count']}+"
            f"{selection_info['alternatives_count']}개)"
        )
        
        reason = " | ".join(reason_parts)
        
        logger.info(
            f"분류 완료: {primary['domain'] if primary else 'None'}, "
            f"대안 {len(alternatives)}개 ({total_time:.2f}s)"
        )
        
        return {
            "primary": primary,
            "alternatives": alternatives,
            "reason": reason,
            "metadata": {
                "total_time": round(total_time, 2),
                "selection_info": selection_info
            }
        }
        
    except Exception as e:
        logger.error(f"분류 중 오류: {str(e)}", exc_info=True)
        return {
            "primary": None,
            "alternatives": [],
            "reason": f"오류: {type(e).__name__} - {str(e)}"
        }