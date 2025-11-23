# 프롬프트 템플릿 사용 가이드 (실무자 관점)

## 🎯 이 도구의 목적

이 시스템은 **회의 참여자**가:
- ✅ 내 성과와 기여를 정리하기 위해
- ✅ 동료들이 무엇을 하는지 파악하기 위해
- ✅ 향후 업무 방향을 명확히 하기 위해

사용하는 도구입니다. **평가가 아닌 실무 정리 도구**입니다.

---

## 📋 프롬프트 템플릿 목록

### 1. **default** ⭐ (기본 업무 정리)

**언제 사용:**
- 일반적인 팀 회의 후
- 전체적인 업무 현황 파악
- 누가 무엇을 하는지 정리

**얻을 수 있는 것:**
- 각자의 아이디어와 제안
- 업무 조율 내용 (누가 누구에게 뭘 요청했는지)
- 업무 보고 (완료한 것, 할 것)
- 상대적 기여도 (발언량 기준)

**사용 예시:**
```python
# 주간 팀 회의 후 전체 정리
analyzer = MeetingPerformanceAnalyzer(..., prompt_template="default")
results = analyzer.analyze_multiple_meetings()
```

---

### 2. **my_summary** (내 성과 정리)

**언제 사용:**
- 내가 뭘 했는지 정리하고 싶을 때
- 내 할 일을 명확히 하고 싶을 때
- 자기 업무 리뷰

**얻을 수 있는 것:**
- 내가 제안한 것
- 내가 맡은 일과 마감일
- 내가 완료 보고한 것
- 내가 다음에 할 것
- 내 발언 비중

**실사용 케이스:**
```
"이번 주 회의에서 내가 한 게 뭐였지?"
"내가 다음 회의까지 뭘 준비해야 하지?"
"내 기여가 충분했나?"
```

**사용 예시:**
```python
# 내 성과만 집중 정리
analyzer = MeetingPerformanceAnalyzer(
    gemini_api_key="your-api-key",
    database_name="company_db",
    collection_name="meeting_transcripts",
    prompt_template="my_summary"
)
results = analyzer.analyze_multiple_meetings()

# 결과 확인
for result in results:
    analysis = result['analysis']
    print(f"템플릿: {analysis['template_used']}")
    print(f"버전: {analysis['template_version']}")
    print(f"분석: {analysis['analysis']}")
```

### 📊 분석 결과 구조

각 템플릿을 사용한 분석 결과는 다음과 같은 구조를 가집니다:

```python
{
    "meeting_id": "507f1f77bcf86cd799439011",
    "meeting_title": "주간 팀 회의",
    "meeting_date": "2025-11-17",
    "participants": ["김민수", "이영희", "박철수"],  # 참여자 목록 (최상위)
    "analysis": {  # 모든 분석 메타데이터 포함
        "status": "success",
        "analysis": "AI가 생성한 분석 텍스트...",
        "participant_stats": {...},      # 참여자별 통계
        "total_statements": 45,          # 전체 발언 수
        "template_used": "my_summary",   # 사용된 템플릿
        "template_version": "1.0",       # 템플릿 버전
        "model_used": "gemini-2.0-flash", # AI 모델
        "timestamp": "2025-11-17T10:30:00"
    }
}
```

**중요:** 모든 분석 관련 메타데이터는 `analysis` 딕셔너리 안에만 저장됩니다.

---

### 3. **team_collaboration** (팀 협업 파악)

**언제 사용:**
- 팀원들이 각자 무엇을 하는지 파악
- 누구에게 무엇을 물어봐야 하는지 알고 싶을 때
- 협업 구조 이해

**얻을 수 있는 것:**
- 각 팀원의 현재 역할
- 누가 무엇을 제공할 수 있는지
- 누가 무엇이 필요한지
- 협업 관계 맵
- 누구에게 언제 연락할지

**실사용 케이스:**
```
"이 문제는 누구에게 물어봐야 하지?"
"김팀장님은 지금 뭘 하고 계시지?"
"이 일은 누구랑 협업해야 하지?"
```

**사용 예시:**
```python
# 팀 구조 파악용
analyzer = MeetingPerformanceAnalyzer(..., prompt_template="team_collaboration")
results = analyzer.analyze_multiple_meetings()
```

---

### 4. **action_items** (액션 아이템 추적)

**언제 사용:**
- 누가 뭘 해야 하는지 명확히 하고 싶을 때
- 마감일 관리
- 업무 의존성 파악

**얻을 수 있는 것:**
- 담당자별 액션 아이템 목록
- 각 일의 마감일과 우선순위
- 선행 조건 (다른 사람 기다려야 하는지)
- 협업 필요 사항
- 산출물과 전달 대상
- 전체 타임라인

**실사용 케이스:**
```
"다음 주까지 뭘 해야 하지?"
"이 일 시작하려면 뭐가 필요하지?"
"누구 일이 끝나야 내가 시작할 수 있지?"
```

**사용 예시:**
```python
# 업무 관리용
analyzer = MeetingPerformanceAnalyzer(..., prompt_template="action_items")
results = analyzer.analyze_multiple_meetings()

# 캘린더나 Trello와 연동 가능
```

---

### 5. **knowledge_base** (지식 정리)

**언제 사용:**
- 회의에서 공유된 정보 정리
- 나중에 참고할 지식 저장
- 팀 지식베이스 구축

**얻을 수 있는 것:**
- 공유된 전문 지식
- 인사이트와 발견
- 언급된 리소스 (문서, 링크, 도구)
- 배경 설명
- 배운 점

**실사용 케이스:**
```
"저번에 누가 말했던 그 도구 뭐였지?"
"그 문제 해결한 사례가 뭐였지?"
"참고할 자료가 뭐가 있었지?"
```

**사용 예시:**
```python
# 지식 아카이빙용
analyzer = MeetingPerformanceAnalyzer(..., prompt_template="knowledge_base")
results = analyzer.analyze_multiple_meetings()

# Notion이나 Confluence에 저장
```

---

### 6. **decision_log** (결정 추적)

**언제 사용:**
- 왜 이렇게 결정했는지 기록
- 결정 배경 이해
- 나중에 돌아볼 때

**얻을 수 있는 것:**
- 결정 사항과 배경
- 누가 어떤 근거를 제시했는지
- 고려된 대안들
- 각자의 의견과 우려사항
- 재검토 시점

**실사용 케이스:**
```
"왜 A안이 아니라 B안을 선택했지?"
"그때 무슨 근거로 결정했지?"
"다른 옵션은 뭐가 있었지?"
```

**사용 예시:**
```python
# 의사결정 기록용
analyzer = MeetingPerformanceAnalyzer(..., prompt_template="decision_log")
results = analyzer.analyze_multiple_meetings()

# ADR(Architecture Decision Record) 스타일로 저장
```

---

### 7. **quick_recap** (빠른 요약)

**언제 사용:**
- 5분 안에 회의 내용 파악
- 참석 못한 회의 빠르게 캐치업
- 일일 스탠드업

**얻을 수 있는 것:**
- 참여자별 한 줄 요약
- 주요 결정 사항
- 다음 액션 목록
- 주의사항

**실사용 케이스:**
```
"회의 못 갔는데 무슨 얘기 나왔어?"
"오늘 회의 핵심만 알려줘"
```

**사용 예시:**
```python
# 빠른 확인용
analyzer = MeetingPerformanceAnalyzer(..., prompt_template="quick_recap")
results = analyzer.analyze_multiple_meetings()

# Slack으로 자동 전송
```

---

### 8. **meeting_context** (회의 맥락)

**언제 사용:**
- 회의가 어떻게 흘러갔는지 이해
- 논의 과정 파악
- 의사결정 과정 복기

**얻을 수 있는 것:**
- 회의 흐름 (초반/중반/후반)
- 누가 어떤 방식으로 기여했는지
- 논의 방향 전환점
- 갈등이나 합의 과정

**실사용 케이스:**
```
"왜 갑자기 그 주제로 넘어갔지?"
"논의가 어떻게 진행됐지?"
```

---

## 🎯 상황별 템플릿 추천

| 상황 | 추천 템플릿 | 이유 |
|------|-------------|------|
| 회의 직후 내 할 일 확인 | `my_summary` | 빠르게 내 액션 파악 |
| 업무 분담 확인 | `action_items` | 누가 뭘 언제까지 |
| 팀원 역할 파악 | `team_collaboration` | 협업 구조 이해 |
| 지식 저장 | `knowledge_base` | 나중에 찾아볼 정보 |
| 결정 기록 | `decision_log` | 왜 이렇게 했는지 |
| 일일 미팅 | `quick_recap` | 핵심만 빠르게 |
| 전체 정리 | `default` | 균형잡힌 정리 |

---

## 💡 실전 활용 예시

### 시나리오 1: 주간 팀 회의 후

```python
# 같은 데이터를 가져옴
analyzer = MeetingPerformanceAnalyzer(
    gemini_api_key="your-api-key",
    database_name="company_db",
    collection_name="meeting_transcripts"
)
meetings = analyzer.fetch_meeting_records({'date': today})

# 1. 전체 정리
analyzer_default = MeetingPerformanceAnalyzer(..., prompt_template="default")
overall = analyzer_default.analyze_meetings(meetings)

# 2. 내 할 일 확인
analyzer_mine = MeetingPerformanceAnalyzer(..., prompt_template="my_summary")
my_tasks = analyzer_mine.analyze_meetings(meetings)

# 3. 액션 아이템 추출
analyzer_actions = MeetingPerformanceAnalyzer(..., prompt_template="action_items")
actions = analyzer_actions.analyze_meetings(meetings)

# → Notion에 정리하거나 이메일로 전송
```

### 시나리오 2: 신규 입사자

```python
# 최근 회의들을 team_collaboration으로 분석
analyzer = MeetingPerformanceAnalyzer(
    gemini_api_key="your-api-key",
    database_name="company_db",
    collection_name="meeting_transcripts",
    prompt_template="team_collaboration"
)
team_structure = analyzer.analyze_multiple_meetings(
    filters={'date': {'$gte': last_month}}
)

# → 팀 구조와 각자 역할 파악
# → 누구에게 무엇을 물어봐야 하는지 이해
```

### 시나리오 3: 프로젝트 회고

```python
# 프로젝트 기간 동안의 모든 회의 분석
analyzer = MeetingPerformanceAnalyzer(
    gemini_api_key="your-api-key",
    database_name="company_db",
    collection_name="meeting_transcripts",
    prompt_template="decision_log"
)
decisions = analyzer.analyze_multiple_meetings(
    filters={'project': 'ProjectX', 'date': {'$gte': project_start}}
)

# → 어떤 결정들이 있었는지
# → 왜 그렇게 결정했는지 복기
```

---

## 🔧 조합 사용하기

여러 템플릿을 연속으로 사용하여 다각도 분석:

```python
meeting_id = "중요한_회의_ID"

# 1. 빠른 요약
quick = analyze(meeting_id, "quick_recap")

# 2. 내 성과 확인
mine = analyze(meeting_id, "my_summary")

# 3. 액션 아이템 추출
actions = analyze(meeting_id, "action_items")

# 4. 지식 저장
knowledge = analyze(meeting_id, "knowledge_base")

# → 한 회의를 완벽히 정리
```

---

## 📝 커스터마이징

### 내 업무에 맞게 조정

```python
custom_prompt = """
회의록을 바탕으로 각 참여자별로:

1. 고객 관련 논의 내용
2. 기술적 이슈
3. 예산 관련 언급
4. 다음 마일스톤

정리해줘.
"""

analyzer = MeetingPerformanceAnalyzer(
    gemini_api_key="your-api-key",
    database_name="company_db",
    collection_name="meeting_transcripts",
    custom_prompt=custom_prompt
)
```

### 추가 지시사항

```python
results = analyzer.analyze_multiple_meetings(
    filters={'date': today},
    custom_instructions="""
    특히 다음 사항을 집중:
    - 고객 피드백 언급
    - 기술 부채 논의
    - 일정 변경 사항
    """
)
```

### 템플릿 버전 지정

```python
# 특정 버전 사용
analyzer = MeetingPerformanceAnalyzer(
    ...,
    prompt_template="default",
    template_version="1.0"  # 특정 버전 지정
)

# 분석 결과에 버전 정보 포함
results = analyzer.analyze_multiple_meetings()
for result in results:
    print(f"사용된 버전: {result['analysis']['template_version']}")
```

👉 [템플릿 버전 관리 상세 가이드](VERSION_USAGE_EXAMPLE.md)

---

## 🎯 핵심 원칙

1. **평가가 아닌 정리**: "얼마나 잘했나"가 아니라 "무엇을 했나"
2. **실무 중심**: 실제 업무에 바로 활용 가능한 정보
3. **협업 이해**: 팀원들과 더 잘 일하기 위한 도구
4. **방향 파악**: 다음에 무엇을 해야 하는지 명확히

---

## ❓ FAQ

**Q: 어떤 템플릿이 가장 유용한가요?**
A: 상황에 따라 다릅니다.
- 회의 직후: `my_summary` + `action_items`
- 정기 회의: `default`
- 빠른 확인: `quick_recap`

**Q: 여러 템플릿을 동시에 사용할 수 있나요?**
A: 한 번에 하나씩만 가능하지만, 같은 회의를 여러 템플릿으로 분석할 수 있습니다.

**Q: 결과를 어떻게 활용하나요?**
A: 
- Notion/Confluence에 정리
- Slack으로 팀 공유
- Trello/Jira에 액션 아이템 생성
- 개인 업무 노트 작성

---

## 🚀 빠른 시작

```python
# 가장 기본적인 사용법
from meeting_performance_analyzer import MeetingPerformanceAnalyzer

# 1. 분석기 생성
analyzer = MeetingPerformanceAnalyzer(
    gemini_api_key="YOUR_API_KEY",
    database_name="company_db",
    collection_name="meeting_transcripts",
    mongodb_host="localhost",
    mongodb_port=27017,
    prompt_template="my_summary",  # 내 성과 정리
    template_version="1.0",  # 특정 버전 사용 (선택사항)
    model_name="gemini-2.0-flash"  # 모델 선택 (선택사항)
)

# 2. 오늘 회의 분석
from datetime import datetime
results = analyzer.analyze_multiple_meetings({
    'date': datetime.now().date()
})

# 3. 결과 확인
for result in results:
    analysis = result['analysis']
    print(f"템플릿: {analysis['template_used']}")
    print(f"버전: {analysis['template_version']}")
    print(f"모델: {analysis['model_used']}")
    print(f"분석: {analysis['analysis']}")
```

### 이미 가져온 데이터 분석

```python
# MongoDB에서 데이터를 먼저 가져온 경우
meetings = analyzer.fetch_meeting_records({'date': today})

# 가져온 데이터를 직접 분석 (여러 템플릿으로 재사용 가능)
results = analyzer.analyze_meetings(meetings)
```

---

이제 회의를 더 효과적으로 정리하고 활용하세요! 🎯

---

## 7. 종합 성과 리뷰 (Comprehensive Review)

여러 회의를 종합하여 장기적인 성과와 성장을 분석합니다.

- **템플릿 키**: `comprehensive_review`
- **주요 분석 항목**:
  - 지속적 기여 (Consistent Contributions)
  - 주요 성과 (Key Achievements)
  - 리더십 및 주도성 (Leadership & Initiative)
  - 성장 영역 (Growth Areas)
  - 전체 팀 진화 (Overall Team Evolution)

## 8. 프로젝트 마일스톤 (Project Milestone)

프로젝트 진행 상황과 마일스톤 달성 여부를 중심으로 분석합니다.

- **템플릿 키**: `project_milestone`
- **주요 분석 항목**:
  - 문제 해결 (Problem Solving)
  - 블로커 제거 (Blocker Removal)
  - 일정 관리 (Schedule Management)
  - 품질 보증 (Quality Assurance)
  - 프로젝트 궤적 (Project Trajectory)

## 9. 소프트 스킬 성장 (Soft Skills Growth)

커뮤니케이션 스타일, 갈등 해결 등 정성적인 역량의 변화를 분석합니다.

- **템플릿 키**: `soft_skills_growth`
- **주요 분석 항목**:
  - 커뮤니케이션 스타일 (Communication Style)
  - 갈등 해결 (Conflict Resolution)
  - 영향력 및 팀워크 (Influence & Teamwork)
  - 태도 변화 (Attitude Shift)
  - 팀 문화 관찰 (Team Culture Observation)
