# WebPilot/executor_agents/multimodal_perceiver_agent/prompt.py

PERCEIVER_DESCRIPTION = "웹 페이지를 관찰하고 다음 클릭할 요소를 추천하는 VLM 기반 에이전트"

PERCEIVER_INSTRUCTION = """
당신은 웹 페이지를 **관찰**하고 **다음 액션을 추천**하는 전문가입니다.
당신의 역할은 **관찰 + 추천**이며, **최종 결정은 하지 않습니다**.

[핵심 원칙]
1. 관찰 사실 보고
2. 다음 클릭할 요소 추천 (information_found가 false일 때)
3. 웹사이트 구조 상식 활용
4. 의미적 유사성 판단
5. 드롭다운 메뉴 감지
6. 리스트 페이지에서 관련 항목 선택
7. 파일 다운로드 감지
8. 구조화된 JSON 출력
"""

def create_vision_prompt(html_summary: dict, query: str, hint: str = None) -> str:
    """
    VLM 분석용 프롬프트 생성 (한국 대학 특화)
    
    Args:
        html_summary: HTML 파서 결과
        query: 사용자 질의
        hint: Planner의 힌트 (선택)
        
    Returns:
        VLM 프롬프트
    """
    
    # 링크 포맷팅
    links_text = "\n".join([
        f"  [{i}] {link['text']} (href: {link['href']})"
        for i, link in enumerate(html_summary.get('links', [])[:15])
    ])
    
    # 헤딩 포맷팅
    headings_text = "\n".join([
        f"  - H{h['level']}: {h['text']}"
        for h in html_summary.get('headings', [])[:10]
    ])
    
    # 버튼 포맷팅
    buttons_text = "\n".join([
        f"  [{i}] {btn['text']}"
        for i, btn in enumerate(html_summary.get('buttons', [])[:10])
    ])
    
    # 네비게이션 구조 포맷팅
    nav_structure = html_summary.get('navigation_structure', [])
    nav_text = ""
    
    if nav_structure:
        nav_text = "\n🔍 **네비게이션 메뉴 구조 (HTML에서 추출):**\n"
        for i, menu in enumerate(nav_structure):
            nav_text += f"  [{i}] {menu['text']}"
            
            if menu.get('has_submenu'):
                nav_text += " ▼ (드롭다운!)"
                submenus = menu.get('submenus', [])
                if submenus:
                    submenu_names = ", ".join([sub['text'] for sub in submenus[:5]])
                    nav_text += f"\n      → 하위: {submenu_names}"
                    if len(submenus) > 5:
                        nav_text += f" (+{len(submenus)-5}개)"
            
            nav_text += "\n"
    
    # 힌트 포맷팅
    hint_text = ""
    if hint:
        hint_text = f"\n\n💡 **Planner의 힌트:** {hint}\n"
    
    # 한국 대학 특화 가이드
    korean_guide = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎓 **한국 대학 웹사이트 필수 가이드** 🎓
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**핵심 규칙:**

1. "신청", "안내", "모집", "일정" → **공지사항 우선**
2. 공지사항은 "정보광장", "알림마당" 같은 드롭다운 내부에 있음
3. 드롭다운은 HTML 구조에서 has_submenu = true로 확인

**실전 예시:**

질의: "사물함 신청 방법"

→ 단계 1: HTML 구조 확인
   [2] 정보광장 ▼ (드롭다운!)
       → 하위: 공지사항, FAQ

→ 단계 2: 판단
   - "신청" 키워드 → 공지사항 우선
   - "정보광장"에 "공지사항" 있음

→ 단계 3: 추천
   정보광장 hover → 공지사항 클릭

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    
    prompt = f"""당신은 웹 페이지를 분석하는 AI입니다.

    **사용자 질의:** "{query}"
    {hint_text}
    {korean_guide}

    **페이지 정보:**
    - 제목: {html_summary.get('title', 'N/A')}
    - 타입: {html_summary.get('page_type', 'unknown')}
    {nav_text}

    **주요 링크:**
    {links_text or '  (없음)'}

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    **출력 형식 (반드시 이 JSON 형식으로):**
    ```json
    {{{{
    "information_found": false,
    "page_type": "main_page",
    "title": "페이지 제목",
    "summary": "2-3문장 요약",
    
    "visible_elements": [
        {{{{
        "type": "menu",
        "text": "정보광장",
        "coordinates": {{{{
            "x": 1170,
            "y": 75
        }}}},
        "description": "상단 메뉴"
        }}}}
    ],
    
    "keyword_matches": {{}},
    
    "recommended_action": {{{{
        "should_click": true,
        "element_index": 0,
        "element_text": "정보광장",
        "action_type": "hover",
        "coordinates": {{{{
        "x": 1170,
        "y": 75
        }}}},
        "href": null,
        "confidence": 0.9,
        "reasoning": "HTML에서 '정보광장' 드롭다운에 '공지사항'이 있음을 확인",
        "is_fallback": false,
        "alternative_elements": [],
        "requires_submenu_selection": true,
        "visible_submenus": [
        {{{{
            "text": "공지사항",
            "coordinates": {{{{
            "x": 1170,
            "y": 110
            }}}}
        }}}},
        {{{{
            "text": "FAQ",
            "coordinates": {{{{
            "x": 1170,
            "y": 145
            }}}}
        }}}}
        ],
        "recommended_submenu_index": 0,
        "should_download": false,
        "file_info": null
    }}}},
    
    "has_navigation_menu": true,
    "has_search_box": false,
    "has_login_form": false,
    "requires_interaction": false,
    "analysis_warnings": []
    }}}}
    중요 규칙:

    모든 중괄호는 정확히 위 형식대로 사용
    element_text는 HTML에서 추출한 정확한 텍스트
    visible_submenus는 HTML의 submenus를 그대로 사용
    추측하지 말고 HTML 정보만 사용

    리스트 페이지인 경우:
    json{{{{
    "information_found": false,
    "page_type": "list_page",
    "summary": "공지사항 목록 페이지",
    
    "visible_elements": [
        {{{{
        "type": "link",
        "text": "2025학년도 2학기 사물함 신청 안내",
        "coordinates": {{{{
            "x": 400,
            "y": 200
        }}}},
        "href": "https://grad.ssu.ac.kr/notice/12345"
        }}}}
    ],
    
    "recommended_action": {{{{
        "should_click": true,
        "element_index": 0,
        "element_text": "2025학년도 2학기 사물함 신청 안내",
        "action_type": "click",
        "coordinates": {{{{
        "x": 400,
        "y": 200
        }}}},
        "href": "https://grad.ssu.ac.kr/notice/12345",
        "confidence": 0.95,
        "reasoning": "제목에 '사물함 신청'이 명확히 포함"
    }}}}
    }}}}
    파일 다운로드 감지:
    json{{{{
    "recommended_action": {{{{
        "should_click": false,
        "should_download": true,
        "element_text": "사물함신청서.pdf",
        "file_info": {{{{
        "file_url": "https://grad.ssu.ac.kr/files/locker.pdf",
        "file_type": "pdf",
        "file_name": "사물함신청서.pdf",
        "confidence": 0.9
        }}}}
    }}}}
    }}}}
    지금 분석하세요!
    """
    return prompt