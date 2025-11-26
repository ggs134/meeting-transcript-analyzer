# 회의 Transcript 업무 정리 시스템

MongoDB에 저장된 회의 녹취록(transcript)을 AI로 분석하여 **내 업무를 정리**하고, **동료의 역할을 파악**하며, **다음 할 일을 명확히** 하는 실무자용 도구입니다.

## 🎯 이 도구의 목적

**평가가 아닌 실무 정리 도구**

- ✅ **내 성과 파악**: 내가 회의에서 뭘 했는지, 뭘 해야 하는지
- ✅ **팀 협업 이해**: 동료들이 각자 무엇을 하는지, 누구에게 뭘 물어봐야 하는지
- ✅ **업무 방향 명확화**: 다음에 뭘 해야 하는지, 언제까지 해야 하는지

## 🌟 주요 기능

### 12가지 실용적인 프롬프트 템플릿

#### 개별 분석 템플릿 (8개)
| 템플릿 | 용도 | 언제 사용 |
|--------|------|-----------|
| **default** ⭐ | 전체 업무 정리 | 일반 팀 회의 후 |
| **my_summary** | 내 성과 정리 | 내가 뭘 했는지 확인 |
| **team_collaboration** | 팀원 역할 파악 | 누구에게 뭘 물어볼지 |
| **action_items** | 액션 아이템 추적 | 누가 뭘 언제까지 |
| **knowledge_base** | 지식 정리 | 공유된 정보 저장 |
| **decision_log** | 결정 추적 | 왜 이렇게 결정했는지 |
| **quick_recap** | 빠른 요약 | 5분 안에 파악 |
| **meeting_context** | 회의 맥락 | 논의 흐름 이해 |

#### 종합 분석 템플릿 (4개)
| 템플릿 | 용도 | 언제 사용 |
|--------|------|-----------|
| **comprehensive_review** | 장기 성과 리뷰 | 여러 회의에 걸친 성장 평가 |
| **project_milestone** | 프로젝트 진척 추적 | 프로젝트 기여도 및 마일스톤 추적 |
| **soft_skills_growth** | 소프트 스킬 평가 | 커뮤니케이션 및 리더십 성장 분석 |
| **performance_ranking** | 성과 순위 | MVP 및 개선 필요 대상 식별 |

## 🚀 빠른 시작

### 1. 설치

```bash
# 패키지 설치
pip install -r requirements.txt

# 환경 변수 설정
cp .env.example .env
# .env 파일에 Gemini API 키 입력
```

### 2. 샘플 데이터로 테스트

```bash
# 샘플 회의 transcript 삽입
python example/insert_sample_data.py

# 분석 실행
python meeting_performance_analyzer.py
```

### 3. 팀 전체 성과표 생성 (50개 회의 일괄 분석) 🆕

```bash
# 모든 회의를 분석하여 팀 성과표 생성
python team_report/generate_team_report.py
```

**생성되는 파일:**
- `team_performance_report.txt` - 전체 리포트 (콘솔 출력 포함)
- `team_performance.json` - JSON 데이터 (프로그래밍 활용)
- `team_performance.csv` - CSV 파일 (Excel에서 바로 열기)
- `team_performance.xlsx` - Excel 파일 (차트 포함)

👉 [팀 성과표 생성 상세 가이드](team_report/TEAM_REPORT_GUIDE.md)

### 4. 다양한 템플릿으로 일괄 분석하기

`utils/run_analysis.py` 스크립트를 사용하여 여러 템플릿(협업, 액션 아이템, 지식 베이스 등)으로 회의를 한 번에 분석할 수 있습니다.

```bash
python utils/run_analysis.py
```

이 스크립트는 다음 템플릿들을 순차적으로 실행하여 분석 결과를 출력합니다:
- `team_collaboration` (팀 협업)
- `action_items` (액션 아이템)
- `knowledge_base` (지식 베이스)
- `decision_log` (결정 로그)
- `quick_recap` (빠른 요약)
- `meeting_context` (회의 맥락)

### 5. 내 회의 분석하기

```python
from meeting_performance_analyzer import MeetingPerformanceAnalyzer

# 내 성과 정리
analyzer = MeetingPerformanceAnalyzer(
    gemini_api_key="YOUR_API_KEY",
    database_name="company_db",
    collection_name="meeting_transcripts",
    mongodb_host="localhost",
    mongodb_port=27017,
    prompt_template="my_summary",  # 내 할 일 파악
    template_version="1.0",  # 특정 버전 사용 (선택사항)
    model_name="gemini-2.0-flash"  # 모델 선택 (선택사항)
)

# 오늘 회의 분석
from datetime import datetime
results = analyzer.analyze_multiple_meetings({
    'date': datetime.now().date()
})

# 결과 확인
for result in results:
    analysis = result['analysis']
    print(f"템플릿: {analysis['template_used']}")
    print(f"버전: {analysis['template_version']}")
    print(f"모델: {analysis['model_used']}")
    print(f"분석: {analysis['analysis']}")
```

## 📊 분석 결과 구조

`analyze_meetings()` 또는 `analyze_multiple_meetings()` 메서드는 다음과 같은 구조의 결과를 반환합니다:

```python
{
    "meeting_id": "507f1f77bcf86cd799439011",  # MongoDB ObjectId (문자열)
    "meeting_title": "주간 팀 회의",            # 회의 제목
    "meeting_date": "2025-11-17",              # 회의 날짜
    "participants": ["김민수", "이영희", "박철수"],  # 참여자 목록 (최상위 유지 - 편의성)
    "analysis": {                               # 분석 결과 (모든 메타데이터 포함)
        "status": "success",                    # 분석 상태 ("success" 또는 "error")
        "analysis": "AI가 생성한 분석 텍스트...",  # 실제 분석 내용
        "participant_stats": {                  # 참여자별 통계
            "김민수": {
                "speak_count": 15,              # 발언 횟수
                "total_words": 234,             # 총 단어 수
                "timestamps": ["00:01:23", ...],  # 발언 시간대 리스트
                "statements": ["발언 내용1", ...]   # 발언 내용 리스트
            },
            ...
        },
        "total_statements": 45,                 # 전체 발언 수
        "template_used": "default",             # 사용된 템플릿 이름
        "template_version": "1.0",              # 사용된 템플릿 버전 (custom이면 None)
        "model_used": "gemini-2.0-flash",       # 사용된 AI 모델
        "timestamp": "2025-11-17T10:30:00"      # 분석 실행 시간
    }
}
```

**중요한 점:**
- 모든 분석 관련 메타데이터(`template_used`, `template_version`, `model_used`, `participant_stats`, `total_statements`)는 `analysis` 딕셔너리 안에만 저장됩니다.
- `participants` 목록만 최상위 레벨에 유지되어 빠른 접근이 가능합니다.
- `status`가 `"error"`인 경우, `analysis` 대신 `error` 필드에 오류 메시지가 포함됩니다.

### 5. 이미 가져온 데이터 분석하기

```python
# MongoDB에서 데이터를 먼저 가져온 경우
meetings = analyzer.fetch_meeting_records({'date': today})

# 가져온 데이터를 직접 분석
results = analyzer.analyze_meetings(meetings)
```

## 💡 실전 사용 예시

### 시나리오 1: 회의 후 내 할 일 확인

```python
# 회의 직후
analyzer = MeetingPerformanceAnalyzer(..., prompt_template="my_summary")
my_tasks = analyzer.analyze_multiple_meetings({'date': today})

# → 내가 맡은 일, 마감일, 준비할 것 파악
```

### 시나리오 2: 팀원 역할 파악 (신규 입사자)

```python
# 최근 한 달 회의 분석
analyzer = MeetingPerformanceAnalyzer(..., prompt_template="team_collaboration")
team_info = analyzer.analyze_multiple_meetings({
    'date': {'$gte': last_month}
})

# → 누가 무엇을 담당하는지
# → 누구에게 무엇을 물어봐야 하는지
```

### 시나리오 3: 업무 관리

```python
# 주간 회의들 분석
analyzer = MeetingPerformanceAnalyzer(..., prompt_template="action_items")
all_tasks = analyzer.analyze_multiple_meetings({
    'date': {'$gte': this_week}
})

# → 캘린더나 Trello에 정리
# → 마감일 관리
```

### 시나리오 4: 못 간 회의 빠르게 캐치업

```python
# 빠른 요약
analyzer = MeetingPerformanceAnalyzer(..., prompt_template="quick_recap")
summary = analyzer.analyze_multiple_meetings({'title': '전략 회의'})

# → 5분 안에 핵심 파악
```

## 📋 템플릿 상세 설명

### 1. **default** - 기본 업무 정리

누가 무엇을 했고, 무엇을 할 것인지 전체 정리

**출력:**
- 아이디어 (제안, 개선, 문제식별)
- 업무 조율 (할일 부여, 범위, 일정)
- 업무 보고 (완료, 계획)
- 양적 기여도 (100점 기준)

### 2. **my_summary** - 내 성과 정리

회의에서 내가 한 것과 할 것 정리

**출력:**
- 내가 제안한 것
- 내가 맡은 일 (마감일, 우선순위)
- 내가 완료 보고한 것
- 다음에 할 것
- 내 발언 비중

**활용:** 개인 업무 리뷰, 자기 점검

### 3. **team_collaboration** - 팀 협업 구조

각 팀원의 역할과 협업 포인트

**출력:**
- 각 사람의 현재 역할
- 제공할 수 있는 것
- 필요로 하는 것
- 협업 관계
- 누구에게 언제 연락할지

**활용:** 신규 입사자, 크로스 팀 협업

### 4. **action_items** - 액션 아이템 관리

누가 무엇을 언제까지 해야 하는지

**출력:**
- 담당자별 액션 아이템
- 마감일과 우선순위
- 선행 조건 (누구 기다려야 하나)
- 협업 필요 사항
- 산출물과 전달 대상

**활용:** 업무 관리, 일정 관리

### 5. **knowledge_base** - 지식 아카이빙

회의에서 공유된 정보와 인사이트

**출력:**
- 공유된 전문 지식
- 인사이트
- 리소스 (문서, 링크, 도구)
- 배운 점

**활용:** 팀 위키, Notion 정리

### 6. **decision_log** - 결정 기록

무엇을 왜 결정했는지

**출력:**
- 결정 사항
- 결정 배경과 근거
- 주요 기여자
- 고려된 대안
- 재검토 시점

**활용:** ADR(Architecture Decision Record), 회고

### 7. **quick_recap** - 빠른 요약

5분 안에 회의 파악

**출력:**
- 참여자별 한 줄 요약
- 주요 결정 사항
- 다음 액션
- 주의사항

**활용:** 일일 미팅, 빠른 공유

### 8. **meeting_context** - 회의 맥락

논의가 어떻게 흘러갔는지

**출력:**
- 회의 흐름 (초반/중반/후반)
- 논의 기여 방식
- 전환점
- 합의 과정

**활용:** 의사결정 과정 복기

### 9. **comprehensive_review** - 종합 리뷰 (종합 분석)

여러 회의에 걸친 장기 성과 및 성장 분석

**출력:**
- 일관된 기여
- 주요 성과
- 리더십
- 성장 영역
- 팀 진화

**활용:** 성과 리뷰, 팀 회고

### 10. **project_milestone** - 프로젝트 마일스톤 (종합 분석)

여러 회의에 걸친 프로젝트 진척 및 기여도 분석

**출력:**
- 프로젝트 기여도
- 현재 책임
- 협업
- 진척 속도
- 품질 영향

**활용:** 프로젝트 상태 보고, 스프린트 리뷰

### 11. **soft_skills_growth** - 소프트 스킬 성장 (종합 분석)

시간에 따른 커뮤니케이션 스타일 및 리더십 발전

**출력:**
- 커뮤니케이션 스타일
- 협업 능력
- 리더십
- 문제 해결
- 성장 궤적

**활용:** 전문성 개발, 팀 역학 분석

### 12. **performance_ranking** - 성과 순위 (종합 분석)

여러 회의에 걸친 최고 및 최저 성과자 식별

**출력:**
- MVP (최고 성과자)
- 개선 필요 (최저 성과자)
- 전체 순위
- 격차 분석

**활용:** 성과 리뷰, 팀 성과 평가

## 🎯 상황별 사용 가이드

### 회의 직후

```python
# 1. 빠른 요약
quick = analyze("quick_recap")

# 2. 내 할 일
my_tasks = analyze("my_summary")

# 3. 액션 아이템
actions = analyze("action_items")
```

### 주간 정기 회의

```python
# 전체 정리
analyzer = MeetingPerformanceAnalyzer(..., prompt_template="default")
weekly = analyzer.analyze_multiple_meetings()
```

### 중요한 전략 회의

```python
# 1. 전체 정리
overall = analyze("default")

# 2. 결정 사항 기록
decisions = analyze("decision_log")

# 3. 지식 저장
knowledge = analyze("knowledge_base")
```

## 🔧 고급 기능

### 템플릿 버전 관리

```python
# 특정 버전 사용
analyzer = MeetingPerformanceAnalyzer(
    ...,
    prompt_template="default",
    template_version="1.0"  # 특정 버전 지정
)

# 최신 버전 사용 (기본값)
analyzer = MeetingPerformanceAnalyzer(
    ...,
    prompt_template="default"
    # template_version을 지정하지 않으면 최신 버전 사용
)

# 사용 가능한 버전 확인
from prompt_templates import get_template_version
latest_version = get_template_version("default")
print(f"최신 버전: {latest_version}")
```

👉 [템플릿 버전 사용 가이드](VERSION_USAGE_EXAMPLE.md)

### 참여자 이름 정규화

동일 인물의 다른 표기법을 하나로 통합하여 분석의 정확도를 높입니다.

**자동 정규화 항목:**
- 대괄호 제거: `"이낙준[ 정보보호대학원박사과정수료연구(재학) / 정보보호학과 ]"` → `"이낙준"`
- 공백 정규화: 여러 공백을 하나로 통합
- 이름 매핑: 별칭/변형을 표준 이름으로 통합

**정규화 설정 방법:**

`meeting_performance_analyzer.py` 파일의 `_normalize_participant_name()` 메서드에서 `name_mapping` 딕셔너리를 수정하세요:

```python
def _normalize_participant_name(self, name: str) -> str:
    # ... (기존 코드) ...
    
    # 이름 매핑 딕셔너리 (별칭/변형 → 표준 이름)
    name_mapping = {
        # Nam 관련 변형들
        "Nam": "Nam Pham",
        "Nam Phạm Tiến": "Nam Pham",
        "Nam Tiến": "Nam Pham",
        
        # Chiko Nakamura 관련 변형들
        "Nakamura Chiko": "Chiko Nakamura",
        
        # 여기에 추가 매핑을 넣으세요
        # "별칭": "표준 이름",
        # "Kevin": "Kevin Jeong",  # 예시
    }
    
    # ... (나머지 코드) ...
```

**예시: 추가 매핑**

```python
name_mapping = {
    # 기존 매핑
    "Nam": "Nam Pham",
    "Nam Phạm Tiến": "Nam Pham",
    "Nakamura Chiko": "Chiko Nakamura",
    
    # 새로운 매핑 추가
    "Kevin": "Kevin Jeong",           # "Kevin"만 표기된 경우
    "Jake": "Jake Jang",              # "Jake"만 표기된 경우
    "Harvey": "Harvey Jo",            # "Harvey"만 표기된 경우
    "James Bello": "James Bello",     # 이미 표준이면 그대로 유지
}
```

**정규화 확인:**

`utils/transcript_parser.py` 스크립트를 실행하여 정규화가 제대로 적용되었는지 확인할 수 있습니다:

```bash
python utils/transcript_parser.py
```

출력된 "전체 참여자 목록"에서 동일 인물의 다른 표기가 하나로 통합되었는지 확인하세요.

**주의사항:**
- 매핑은 대소문자를 구분합니다. `"kevin"`과 `"Kevin"`은 별도로 매핑해야 합니다.
- 대괄호 제거는 자동으로 처리되므로 매핑에 추가할 필요가 없습니다.
- 공백 정규화도 자동으로 처리됩니다.

### 여러 템플릿 조합

```python
# 같은 회의를 여러 관점으로 분석
meetings = analyzer.fetch_meeting_records({'title': '중요한_회의'})

# 빠른 요약
analyzer_quick = MeetingPerformanceAnalyzer(..., prompt_template="quick_recap")
quick_results = analyzer_quick.analyze_meetings(meetings)

# 내 성과
analyzer_mine = MeetingPerformanceAnalyzer(..., prompt_template="my_summary")
my_results = analyzer_mine.analyze_meetings(meetings)

# 액션 아이템
analyzer_actions = MeetingPerformanceAnalyzer(..., prompt_template="action_items")
action_results = analyzer_actions.analyze_meetings(meetings)
```

### 커스텀 지시사항 추가

```python
results = analyzer.analyze_multiple_meetings(
    filters={'date': today},
    custom_instructions="""
    특히 다음을 집중:
    - 고객 피드백
    - 기술 부채
    - 일정 변경
    """
)
```

### 완전 커스텀 프롬프트

```python
my_prompt = """
참여자별로:
1. 고객 관련 논의
2. 기술적 이슈
3. 예산 언급
정리해줘
"""

analyzer = MeetingPerformanceAnalyzer(..., custom_prompt=my_prompt)
```

### 모델 선택

```python
# 환경변수로 설정
# .env 파일에: GEMINI_MODEL=gemini-2.0-flash

# 또는 코드에서 직접 지정
analyzer = MeetingPerformanceAnalyzer(
    ...,
    model_name="gemini-2.0-flash"  # 또는 "gemini-1.5-pro" 등
)
```

## 📊 지원 Transcript 형식

```
✅ [00:01:23] 김민수: 발언 내용
✅ [01:23] 이지은: 발언 내용
✅ 00:01:23 박준호: 발언 내용
✅ 01:23 최서연: 발언 내용
```

## 🎯 실무 활용 팁

### Notion과 연동

```python
# 분석 후 Notion에 자동 정리
results = analyzer.analyze_multiple_meetings()
for result in results:
    notion_api.create_page(
        title=result['meeting_title'],
        content=result['analysis']['analysis']
    )
```

### Slack으로 공유

```python
# 빠른 요약을 Slack에 자동 전송
analyzer = MeetingPerformanceAnalyzer(..., prompt_template="quick_recap")
summary = analyzer.analyze_multiple_meetings({'date': today})
slack_api.post_message(channel='#team', text=summary)
```

### 캘린더 연동

```python
# 액션 아이템을 캘린더에 추가
analyzer = MeetingPerformanceAnalyzer(..., prompt_template="action_items")
tasks = analyzer.analyze_multiple_meetings()
# 파싱 후 Google Calendar API로 일정 생성
```

## 📚 추가 문서

- [프롬프트 템플릿 상세 가이드](PROMPT_GUIDE.md) - 각 템플릿 설명 및 사용법
- [템플릿 버전 사용 가이드](VERSION_USAGE_EXAMPLE.md) - 특정 버전 템플릿 사용 방법
- [스키마 가이드](SCHEMA_GUIDE.md) - Google Drive 스키마 자동 변환
- [팀 성과표 생성 가이드](team_report/TEAM_REPORT_GUIDE.md) - 50개 회의 일괄 분석 방법
- [빠른 시작 예제](example/quick_start_examples.py) - 다양한 사용 예제 코드
- [템플릿 선택 도구](example/template_selector.py) - 대화형 템플릿 탐색
- [JSON 파일 분석 예제](example/analyze_json_file.py) - MongoDB 없이 JSON 파일 직접 분석

## ⚠️ 주의사항

- **Gemini API**: 무료 플랜은 월 60회 제한, 유료 플랜은 사용량에 따라 과금
- **토큰 제한**: 매우 긴 transcript는 토큰 제한 고려 필요 (약 30,000 토큰)
- **API 키 보안**: 절대 공개 금지, `.env` 파일을 `.gitignore`에 추가
- **MongoDB 연결**: 인증 정보는 환경변수로 관리 권장

## 💬 자주 묻는 질문

**Q: 어떤 템플릿을 사용해야 하나요?**
A: 
- 회의 직후 → `my_summary` + `action_items`
- 일반 회의 → `default`
- 빠른 확인 → `quick_recap`
- 팀 파악 → `team_collaboration`

**Q: 결과를 어떻게 활용하나요?**
A:
- Notion/Confluence에 정리
- Slack으로 팀 공유
- Trello/Jira에 액션 아이템 생성
- 개인 업무 노트 작성

**Q: 평가 용도로 사용할 수 있나요?**
A: 이 도구는 평가가 아닌 **실무 정리** 목적입니다. 각자가 자신의 업무를 파악하고 팀 협업을 원활히 하기 위한 도구입니다.

**Q: 못 간 회의를 따라잡을 수 있나요?**
A: 네! `quick_recap` 템플릿으로 5분 안에 핵심 파악 가능합니다.

**Q: 50개 회의를 한번에 분석하려면?** 🆕
A: `team_report/generate_team_report.py`를 사용하세요! 자동으로 모든 회의를 분석하고 팀 전체 성과표를 생성합니다. [상세 가이드](team_report/TEAM_REPORT_GUIDE.md)

**Q: 분석 시간이 얼마나 걸리나요?**
A: 회의 1개당 30초~1분. 50개면 약 25~50분 소요됩니다.

**Q: 템플릿 버전은 어떻게 관리하나요?**
A: `prompt_templates.json` 파일에서 각 템플릿의 여러 버전을 관리할 수 있습니다. `template_version` 파라미터로 특정 버전을 지정하거나, 지정하지 않으면 최신 버전(`is_latest: true`)이 사용됩니다. [상세 가이드](VERSION_USAGE_EXAMPLE.md)

**Q: analyze_meetings와 analyze_multiple_meetings의 차이는?**
A: `analyze_multiple_meetings`는 MongoDB 쿼리를 사용하여 데이터를 가져온 후 분석합니다. `analyze_meetings`는 이미 가져온 데이터 리스트를 직접 분석합니다. 같은 데이터를 여러 템플릿으로 분석할 때 유용합니다.

## 🛠️ 개발자 가이드

### 새로운 프롬프트 템플릿 추가하기

시스템에 새로운 프롬프트 템플릿을 추가할 때는 다음 체크리스트를 따라 모든 파일을 업데이트하세요:

#### 1. 프롬프트 파일 생성
- [ ] **`prompt_md/kr/[TEMPLATE_NAME].md`** - 한국어 버전 프롬프트
- [ ] **`prompt_md/en/[TEMPLATE_NAME].md`** - 영어 버전 프롬프트

#### 2. 설정 파일 업데이트
- [ ] **`prompt_templates.json`** - 버전 1.0으로 템플릿 추가 및 `is_latest: true` 설정

#### 3. 문서 업데이트
- [ ] **`PROMPT_GUIDE.md`** - 템플릿 설명 및 주요 분석 항목 추가
- [ ] **`README.md`** - 템플릿 개수 업데이트 및 템플릿 테이블에 추가
- [ ] **`README_kr.md`** - 템플릿 개수 업데이트 및 템플릿 테이블에 추가 (한국어)

#### 4. 코드 업데이트 (해당되는 경우)
- [ ] **`utils/transcript_parser.py`** - `aggregated_templates` 리스트에 추가 (종합 분석 템플릿인 경우)
- [ ] **`utils/run_analysis.py`** - `template_keys` 리스트에 추가 (일괄 분석에 포함하려는 경우)

#### 5. 테스트
- [ ] 새 템플릿이 올바르게 작동하는지 확인하는 테스트 스크립트 작성
- [ ] 샘플 데이터로 테스트하여 출력이 예상과 일치하는지 확인

#### 예시: `performance_ranking` 템플릿 추가

```bash
# 1. 프롬프트 파일 생성
touch prompt_md/kr/PERFORMANCE_RANKING.md
touch prompt_md/en/PERFORMANCE_RANKING.md

# 2. prompt_templates.json 편집
# 버전 1.0으로 새 항목 추가

# 3. 문서 업데이트
# PROMPT_GUIDE.md, README.md, README_kr.md 편집

# 4. 코드 업데이트 (종합 분석 템플릿인 경우)
# utils/transcript_parser.py 편집
# utils/run_analysis.py 편집 (선택사항)

# 5. 테스트
python test_new_template.py

# 6. 커밋 및 푸시
git add .
git commit -m "feat: Add [template_name] prompt template"
git push
```

## 🎯 핵심 원칙

1. **평가 X, 정리 O**: "얼마나 잘했나"가 아니라 "무엇을 했나"
2. **실무 중심**: 실제 업무에 바로 활용
3. **협업 촉진**: 팀원들과 더 잘 일하기 위한 도구
4. **방향 명확화**: 다음에 무엇을 해야 하는지

## 📝 라이선스

MIT License

## 🤝 기여

버그 리포트나 기능 제안은 이슈로 등록해주세요.

---

**이제 회의를 더 효과적으로 활용하세요!** 🚀
