# 템플릿 버전 관리 가이드

## 개요

템플릿의 특정 버전을 사용하여 분석할 수 있습니다. `prompt_templates.json` 파일에 여러 버전이 있을 때 특정 버전을 선택할 수 있습니다.

## 주요 기능

- ✅ 템플릿 버전 관리 (`prompt_templates.json`에서 관리)
- ✅ 특정 버전 지정 (`template_version` 파라미터)
- ✅ 최신 버전 자동 사용 (기본값)
- ✅ 분석 결과에 사용된 버전 정보 포함 (`template_version` 필드)

## 사용 방법

### 1. Analyzer 초기화 시 버전 지정

```python
from meeting_performance_analyzer import MeetingPerformanceAnalyzer

# 특정 버전(예: "1.0")을 사용하는 analyzer 생성
analyzer = MeetingPerformanceAnalyzer(
    gemini_api_key="your-api-key",
    database_name="company_db",
    collection_name="meeting_transcripts",
    mongodb_host="localhost",
    mongodb_port=27017,
    prompt_template="default",
    template_version="1.0"  # 특정 버전 지정
)

# 최신 버전 사용 (기본값)
analyzer_latest = MeetingPerformanceAnalyzer(
    gemini_api_key="your-api-key",
    database_name="company_db",
    collection_name="meeting_transcripts",
    mongodb_host="localhost",
    mongodb_port=27017,
    prompt_template="default"
    # template_version을 지정하지 않으면 최신 버전 사용
)

# "latest" 문자열로도 최신 버전 지정 가능
analyzer_latest2 = MeetingPerformanceAnalyzer(
    gemini_api_key="your-api-key",
    database_name="company_db",
    collection_name="meeting_transcripts",
    prompt_template="default",
    template_version="latest"  # 최신 버전 명시적 지정
)
```

### 2. 사용 가능한 버전 확인

```python
from prompt_templates import get_template_version

# 특정 템플릿의 최신 버전 확인
latest_version = get_template_version("default")
print(f"최신 버전: {latest_version}")
# 출력: "1.0" (예시)

# 특정 버전이 존재하는지 확인
version_10 = get_template_version("default", "1.0")
if version_10:
    print("버전 1.0 존재")
```

### 3. 특정 버전의 템플릿 내용 확인

```python
from prompt_templates import PromptTemplates

# 버전 1.0의 템플릿 내용 가져오기
template_v1 = PromptTemplates.get_template("default", version="1.0")

# 최신 버전의 템플릿 내용 가져오기
template_latest = PromptTemplates.get_template("default")
```

### 4. 분석 결과에서 버전 정보 확인

```python
results = analyzer.analyze_multiple_meetings()

for result in results:
    analysis = result['analysis']
    print(f"템플릿: {analysis['template_used']}")
    print(f"버전: {analysis['template_version']}")
    print(f"모델: {analysis['model_used']}")
    print(f"분석: {analysis['analysis']}")
```

### 📊 분석 결과 구조

버전 정보를 포함한 전체 분석 결과 구조:

```python
{
    "meeting_id": "507f1f77bcf86cd799439011",
    "meeting_title": "주간 팀 회의",
    "meeting_date": "2025-11-17",
    "participants": ["김민수", "이영희", "박철수"],
    "analysis": {
        "status": "success",
        "analysis": "AI 분석 결과...",
        "participant_stats": {...},      # 참여자별 통계
        "total_statements": 45,          # 전체 발언 수
        "template_used": "default",      # 사용된 템플릿
        "template_version": "1.0",       # 사용된 템플릿 버전 (중요!)
        "model_used": "gemini-2.0-flash", # AI 모델
        "timestamp": "2025-11-17T10:30:00"
    }
}
```

**버전 정보 확인:**
- `analysis['template_version']`: 사용된 템플릿 버전 (예: "1.0", "2.0")
- `analysis['template_used']`: 사용된 템플릿 이름 (예: "default", "my_summary")
- 커스텀 프롬프트를 사용한 경우 `template_version`은 `None`으로 기록됩니다.

## JSON 파일 구조

템플릿 JSON 파일에서 여러 버전을 정의할 수 있습니다:

```json
{
  "templates": {
    "default": {
      "1.0": {
        "content": "...",
        "description": "버전 1.0",
        "is_latest": false
      },
      "2.0": {
        "content": "...",
        "description": "버전 2.0 (개선됨)",
        "is_latest": true
      }
    }
  }
}
```

- `is_latest: true`인 버전이 최신 버전으로 간주됩니다
- `template_version`을 지정하지 않으면 `is_latest: true`인 버전이 사용됩니다

## 예시 시나리오

### 시나리오 1: 이전 버전과 비교 분석

```python
# 같은 데이터를 가져옴
meetings = analyzer.fetch_meeting_records()

# 버전 1.0으로 분석
analyzer_v1 = MeetingPerformanceAnalyzer(
    gemini_api_key="your-api-key",
    database_name="company_db",
    collection_name="meeting_transcripts",
    prompt_template="default",
    template_version="1.0"
)
results_v1 = analyzer_v1.analyze_meetings(meetings)

# 최신 버전으로 분석
analyzer_latest = MeetingPerformanceAnalyzer(
    gemini_api_key="your-api-key",
    database_name="company_db",
    collection_name="meeting_transcripts",
    prompt_template="default"
)
results_latest = analyzer_latest.analyze_meetings(meetings)

# 결과 비교
for v1, latest in zip(results_v1, results_latest):
    print(f"버전 1.0: {v1['analysis']['template_version']}")
    print(f"최신 버전: {latest['analysis']['template_version']}")
```

### 시나리오 2: 특정 버전의 템플릿 정보 확인

```python
from prompt_templates import get_template_version, PromptTemplates

# 템플릿의 최신 버전 확인
latest_version = get_template_version("default")
print(f"최신 버전: {latest_version}")

# 특정 버전 확인
version_10 = get_template_version("default", "1.0")
if version_10:
    print(f"버전 1.0 존재: {version_10}")

# 템플릿 내용 확인
template_content = PromptTemplates.get_template("default", version="1.0")
print(f"템플릿 내용: {template_content[:100]}...")
```

## 주의사항

1. **버전이 존재하지 않는 경우**: 지정한 버전이 없으면 최신 버전이 자동으로 사용됩니다.

2. **JSON 파일 수정 후**: JSON 파일을 수정한 후에는 Python 프로세스를 재시작해야 변경사항이 반영됩니다.

3. **버전 형식**: 버전은 문자열로 지정합니다 (예: `"1.0"`, `"2.0"`).

4. **최신 버전 우선**: `template_version=None`이거나 지정하지 않으면 `is_latest: true`인 버전이 사용됩니다.

