PERCEIVER_DESCRIPTION = "웹 페이지 스크린샷과 HTML을 분석하여 페이지 타입을 감지하고 다음 액션을 추천하는 VLM 기반 에이전트"

PERCEIVER_INSTRUCTION = """
당신은 웹 페이지를 **관찰**하고 **다음 액션을 추천**하는 전문가입니다.

[핵심 원칙]
1. **스크린샷 우선**: 이미지에서 실제로 보이는 요소만 분석
2. HTML 데이터는 참고용 (스크린샷 확인용)
3. 존재하지 않는 요소를 만들어내지 않음
4. 단계별로 사고하여 할루시네이션 방지
5. **페이지 타입을 정확히 감지** ⭐
"""

def create_vision_prompt_with_cot(html_summary: dict, query: str, hint: str = None) -> str:
    """
    스크린샷 중심 CoT 프롬프트 (페이지 타입 감지 강화)
    """
    
    # HTML 데이터 포맷팅 (참고용)
    nav_structure = html_summary.get('navigation_structure', [])
    nav_text = ""
    
    if nav_structure:
        nav_text = "**참고: HTML에서 추출한 네비게이션 (스크린샷 확인용):**\n"
        for i, menu in enumerate(nav_structure[:12]):
            nav_text += f"  [{i}] {menu['text']}"
            if menu.get('has_submenu'):
                nav_text += " [드롭다운]"
                submenus = menu.get('submenus', [])[:6]
                if submenus:
                    nav_text += f" (하위: {', '.join([s['text'] for s in submenus])})"
            nav_text += "\n"
    
    links = html_summary.get('links', [])[:15]
    links_text = ""
    links_start = len(nav_structure)
    
    if links:
        links_text = f"\n**참고: HTML에서 추출한 링크 (인덱스 {links_start}부터):**\n"
        for i, link in enumerate(links):
            links_text += f"  [{links_start + i}] {link['text']}\n"
    
    hint_text = f"\n💡 **힌트:** {hint}\n" if hint else ""
    
    # 프롬프트 생성
    prompt = f"""🖼️ **이 메시지와 함께 웹페이지 스크린샷이 제공되었습니다.**

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ CRITICAL INSTRUCTION ⚠️
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You MUST analyze the screenshot image provided with this message.

**FORBIDDEN RESPONSES:**
- ❌ "I cannot see the screenshot"
- ❌ "I don't have access to the image"
- ❌ "현재 페이지에서 스크린샷을 확인할 수 없어"
- ❌ Any generic advice without image analysis

**REQUIRED:**
- ✅ Describe what you see in the screenshot
- ✅ Identify specific UI elements (menus, buttons, links)
- ✅ **Detect page type accurately** ⭐
- ✅ Provide exact coordinates from the image
- ✅ If you genuinely cannot see the image, output: {{"image_analysis_status": "failed"}}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 USER QUERY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Query:** "{query}"{hint_text}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📄 PAGE METADATA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

- Title: {html_summary.get('title', 'N/A')}
- Initial Type: {html_summary.get('page_type', 'unknown')}
- URL: {html_summary.get('url', 'N/A')}

{nav_text}{links_text}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 PAGE TYPE DETECTION (CRITICAL) ⭐
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

You MUST determine the page type. Choose ONE:

**1. main_page** - 메인/홈페이지
   Visual cues:
   - Navigation menu at top
   - Search box
   - Homepage layout
   - Minimal content

**2. list_page** - 리스트/게시판 ⭐
   Visual cues:
   - Repeating pattern of items (3+ similar items)
   - Table with rows
   - List of links with dates
   - Pagination at bottom (1, 2, 3, ... Next)
   - Examples: 공지사항, 게시판, 검색 결과
   
   **IMPORTANT**: If you see 3+ similar items in a list/table → list_page
   **Delegate to**: crawler

**3. detail_page** - 상세 페이지
   Visual cues:
   - Single article/content
   - Long text body
   - Attachments/files
   - No repeating items

**4. search_results_page** - 검색 결과
   Visual cues:
   - Search query shown
   - List of results
   - "Results for ..." header
   
   **Delegate to**: crawler

**5. filter_page** - 필터 페이지 (NEW) ⭐
   Visual cues:
   - 2+ dropdown selects (학년도, 학기, 학과 등)
   - "검색" or "조회" button
   - Empty table/result area (not filled yet)
   - URL contains "sap" or "webdynpro"
   
   **IMPORTANT**: If you see multiple dropdowns + search button → filter_page
   **Delegate to**: filter_based_page_handler

**6. login_page** - 로그인
   Visual cues:
   - Username/password inputs
   - Login button

**7. error_page** - 에러
   Visual cues:
   - 404, 500 error message

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🧠 ANALYSIS PROCEDURE (Screenshot-First)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Step 1: Visual Observation (MANDATORY)**
Look at the screenshot and describe:
- What UI elements are visible at the top of the page?
- What menus/navigation items can you see?
- Are there any dropdown indicators (▼)?
- **Is this a list/table with repeating items?** ⭐
- **Are there multiple dropdown selects?** ⭐
- What is the layout (header, sidebar, main content)?

**Step 2: Page Type Detection** ⭐
Based on visual cues:
- Count repeating items → if 3+ → list_page
- Count dropdowns + search button → if 2+ → filter_page
- Check URL for "sap" → likely filter_page
- Single content block → detail_page

**Step 3: Element Identification**
For each visible element in the screenshot:
- Exact text displayed
- Position on screen (approximate x, y coordinates)
- Type (menu, button, link, dropdown)
- Visual appearance (color, size, styling)

**Step 4: Query Matching**
Based on the query "{query}":
- Which visible element is most relevant?
- Why? (based on text/position/common web patterns)

**Step 5: Delegation Decision** ⭐
If page_type is:
- "list_page" → delegate to crawler
- "filter_page" → delegate to filter_based_page_handler
- Other → provide navigation recommendation

**Step 6: Confidence Assessment**
- High (0.8-1.0): Element clearly visible and directly relevant
- Medium (0.5-0.8): Element visible but indirect match
- Low (0.3-0.5): Weak visual cues
- Very Low (0.0-0.3): Guessing

**Step 7: Recommendation**
- Click/hover which element?
- What are the exact coordinates?
- Should delegate to another agent?

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📤 OUTPUT FORMAT (JSON ONLY)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{{
  "image_analysis_status": "success",
  
  "screenshot_description": "Describe what you see: e.g., 'Top navigation bar with 5 menu items: 학사안내, 정보광장 (with dropdown icon ▼), 학생지원, ...'",
  
  "reasoning_process": {{
    "step1_visual_observation": "What I see in the screenshot",
    "step2_page_type_detection": "Detected as list_page because I see 10+ repeating items in a table format",
    "step3_elements_identified": ["Element 1 at position (x, y)", "Element 2 at position (x, y)"],
    "step4_query_matching": "Why element X matches the query",
    "step5_delegation_decision": "Should delegate to crawler",
    "step6_confidence": "High - element clearly visible",
    "step7_decision": "Click element X OR delegate to crawler"
  }},
  
  "information_found": false,
  "extracted_info": null,
  "confidence": 0.85,
  "page_type": "main_page|list_page|detail_page|search_results_page|filter_page|login_page|error_page",
  "title": "{html_summary.get('title', '')}",
  "summary": "Brief summary based on screenshot",
  
  "visible_elements": [
    {{
      "type": "menu|link|button|dropdown|table_row",
      "text": "Exact text from screenshot",
      "coordinates": {{"x": 150, "y": 40}},
      "description": "Visual description: position, color, etc."
    }}
  ],

  "recommended_action": {{
    "should_click": true,
    "delegate_to": "crawler|filter_based_page_handler|null",
    "element_index": 0,
    "element_text": "Exact text from visible_elements",
    "action_type": "click|hover",
    "coordinates": {{"x": 150, "y": 40}},
    "href": null,
    "confidence": 0.85,
    "reasoning": "This element is visible in the screenshot at coordinates (150, 40). [Detailed reasoning based on what you SEE]",
    "is_fallback": false,
    "alternative_elements": [],
    "requires_submenu_selection": false,
    "visible_submenus": [],
    "recommended_submenu_index": null,
    "should_download": false,
    "file_info": null
  }},
  
  "has_navigation_menu": true,
  "has_search_box": false,
  "has_login_form": false,
  "requires_interaction": false,
  
  "list_page_info": {{
    "is_list": false,
    "item_count_estimated": 0,
    "has_pagination": false
  }},
  
  "filter_page_info": {{
    "is_filter": false,
    "dropdown_count": 0,
    "has_search_button": false
  }},
  
  "analysis_warnings": []
}}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ EXAMPLE 1: LIST PAGE (공지사항) ⭐
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Query: "사물함 신청 방법"

{{
  "image_analysis_status": "success",
  
  "screenshot_description": "The screenshot shows a bulletin board page with a table containing 15+ rows. Each row has: 번호, 제목, 작성자, 날짜. I can see titles like '2025학년도 사물함 신청 안내', '장학금 신청', etc. At the bottom, there's pagination: [1] [2] [3] [다음].",
  
  "reasoning_process": {{
    "step1_visual_observation": "Table with 15+ similar rows, each with 번호-제목-날짜 structure. Pagination visible at bottom.",
    "step2_page_type_detection": "This is CLEARLY a list_page - repeating table rows (15+), pagination present",
    "step3_elements_identified": [
      "Table row 1: '2025학년도 사물함 신청 안내' at approximately (400, 200)",
      "Table row 2: '장학금 신청 안내' at (400, 230)"
    ],
    "step4_query_matching": "Row 1 directly mentions '사물함 신청' - exact match",
    "step5_delegation_decision": "MUST delegate to crawler - this is a list page with many items",
    "step6_confidence": "High (0.95) - clear list pattern",
    "step7_decision": "Delegate to crawler for batch analysis"
  }},
  
  "information_found": false,
  "confidence": 0.95,
  "page_type": "list_page",
  "summary": "Bulletin board with 15+ announcement items. Pagination present.",
  
  "visible_elements": [
    {{
      "type": "table_row",
      "text": "2025학년도 사물함 신청 안내",
      "coordinates": {{"x": 400, "y": 200}},
      "description": "First row in table, bold text, date: 2025.03.01"
    }},
    {{
      "type": "table_row",
      "text": "장학금 신청 안내",
      "coordinates": {{"x": 400, "y": 230}},
      "description": "Second row, date: 2025.02.28"
    }}
  ],
  
  "recommended_action": {{
    "should_click": false,
    "delegate_to": "crawler",
    "element_index": null,
    "element_text": null,
    "action_type": null,
    "coordinates": null,
    "confidence": 0.95,
    "reasoning": "This is a list_page with 15+ items. Should delegate to crawler for batch analysis and relevance ranking. Crawler will analyze all items and find the most relevant one.",
    "is_fallback": false
  }},
  
  "list_page_info": {{
    "is_list": true,
    "item_count_estimated": 15,
    "has_pagination": true
  }}
}}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ EXAMPLE 2: FILTER PAGE (SAP 강좌 조회) ⭐
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Query: "IT대학 개설강좌"

{{
  "image_analysis_status": "success",
  
  "screenshot_description": "The screenshot shows a filter interface with 4 dropdown selects at the top: '학년도' (set to 2025학년도), '학기' (1학기), '학부전공별' tab selected, 'IT대학' dropdown. Below is a '조회' (Search) button. The bottom area shows an empty table waiting for results. URL contains 'sap/bc/webdynpro'.",
  
  "reasoning_process": {{
    "step1_visual_observation": "4 dropdown selects visible, '조회' button, empty result table, URL has 'sap'",
    "step2_page_type_detection": "This is CLEARLY a filter_page - multiple dropdowns (4), search button, empty results, SAP URL",
    "step3_elements_identified": [
      "Dropdown '학년도' at (150, 40)",
      "Dropdown '학기' at (300, 40)",
      "Dropdown 'IT대학' at (450, 40)",
      "Button '조회' at (600, 40)"
    ],
    "step4_query_matching": "IT대학 dropdown matches query",
    "step5_delegation_decision": "MUST delegate to filter_based_page_handler - this is a filter page",
    "step6_confidence": "Very High (0.95) - obvious filter interface",
    "step7_decision": "Delegate to filter_based_page_handler"
  }},
  
  "information_found": false,
  "confidence": 0.95,
  "page_type": "filter_page",
  "summary": "SAP course search page with filters. Needs filter manipulation.",
  
  "visible_elements": [
    {{
      "type": "dropdown",
      "text": "학년도: 2025학년도",
      "coordinates": {{"x": 150, "y": 40}},
      "description": "First dropdown select"
    }},
    {{
      "type": "dropdown",
      "text": "IT대학",
      "coordinates": {{"x": 450, "y": 40}},
      "description": "College selection dropdown"
    }},
    {{
      "type": "button",
      "text": "조회",
      "coordinates": {{"x": 600, "y": 40}},
      "description": "Search/query button"
    }}
  ],
  
  "recommended_action": {{
    "should_click": false,
    "delegate_to": "filter_based_page_handler",
    "element_index": null,
    "element_text": null,
    "action_type": null,
    "coordinates": null,
    "confidence": 0.95,
    "reasoning": "This is a filter_page (SAP system) with 4 dropdowns and a search button. Should delegate to filter_based_page_handler which will manipulate filters and collect results.",
    "is_fallback": false
  }},
  
  "filter_page_info": {{
    "is_filter": true,
    "dropdown_count": 4,
    "has_search_button": true
  }}
}}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ EXAMPLE 3: MAIN PAGE (일반 메뉴 클릭)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Query: "사물함 신청 방법"

{{
  "image_analysis_status": "success",
  
  "screenshot_description": "The screenshot shows a university website header. Top navigation bar contains 5 items from left to right: '학사안내', '정보광장' (with dropdown indicator ▼), '학생지원', '입학안내', '취업정보'. The '정보광장' menu has a small downward arrow suggesting a dropdown.",
  
  "reasoning_process": {{
    "step1_visual_observation": "Navigation bar at top. '정보광장' menu visible with dropdown icon at approximately x=250, y=40",
    "step2_page_type_detection": "This is a main_page - homepage layout with navigation menu",
    "step3_elements_identified": [
      "'정보광장' menu at (250, 40) with dropdown icon",
      "'학생지원' menu at (400, 40)"
    ],
    "step4_query_matching": "사물함 신청 information is typically in '정보광장' → '공지사항'",
    "step5_delegation_decision": "No delegation - provide navigation action",
    "step6_confidence": "High (0.85) - Menu clearly visible",
    "step7_decision": "Hover over '정보광장' then click '공지사항'"
  }},
  
  "information_found": false,
  "confidence": 0.85,
  "page_type": "main_page",
  "summary": "University homepage with navigation menu. Target element '정보광장' identified.",
  
  "visible_elements": [
    {{
      "type": "menu",
      "text": "정보광장",
      "coordinates": {{"x": 250, "y": 40}},
      "description": "Navigation menu item with dropdown indicator, blue text"
    }}
  ],
  
  "recommended_action": {{
    "should_click": true,
    "delegate_to": null,
    "element_index": 0,
    "element_text": "정보광장",
    "action_type": "hover",
    "coordinates": {{"x": 250, "y": 40}},
    "confidence": 0.85,
    "reasoning": "In the screenshot, '정보광장' menu is visible at position (250, 40) with a dropdown indicator. This menu typically contains '공지사항' where locker application information is posted.",
    "requires_submenu_selection": true,
    "visible_submenus": [
      {{"text": "공지사항", "coordinates": {{"x": 250, "y": 70}}}},
      {{"text": "FAQ", "coordinates": {{"x": 250, "y": 100}}}}
    ],
    "recommended_submenu_index": 0
  }}
}}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
❌ EXAMPLE: FORBIDDEN RESPONSE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{{
  "summary": "현재 페이지에서 스크린샷을 확인할 수 없어, 실제 어떤 요소들이 있는지 구체적으로 볼 수는 없습니다..."
}}

↑ NEVER output responses like this! If you truly cannot see the image, output:

{{
  "image_analysis_status": "failed",
  "analysis_warnings": ["Screenshot image not accessible"]
}}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 FINAL REMINDER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. **Look at the screenshot image**
2. **Detect page type accurately** ⭐
   - list_page → delegate to crawler
   - filter_page → delegate to filter_based_page_handler
3. **Describe what you SEE**
4. **Identify elements by their visual appearance**
5. **Provide exact coordinates**
6. **Base reasoning on visual evidence**

**CRITICAL PAGE TYPE RULES:**
- 3+ repeating items in list/table → **list_page**
- 2+ dropdowns + search button → **filter_page**
- URL contains "sap" → likely **filter_page**

**DO NOT:**
- Give generic advice
- Say you cannot see the image (unless truly impossible)
- Make up elements not in the screenshot
- Miss obvious list or filter patterns

**NOW: Analyze the screenshot and output JSON only.**
"""
    
    return prompt