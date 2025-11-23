# Google Drive 스키마 지원 가이드

## 🎯 자동 스키마 변환

`MeetingPerformanceAnalyzer`는 Google Drive 스키마와 회의 분석 형식을 모두 자동으로 지원합니다.
MongoDB 데이터를 수정하지 않고 메모리에서 자동으로 변환합니다.

### 지원하는 스키마 형식

#### Google Drive 스키마 (자동 변환됨)
```json
{
  "name": "회의 파일명",
  "content": "회의 내용",
  "createdTime": "2024-11-21T10:00:00Z"
}
```

#### 회의 분석 형식 (그대로 사용)
```json
{
  "title": "회의 제목",
  "transcript": "파싱 가능한 녹취록",
  "date": "2024-11-21",
  "participants": ["참여자1", "참여자2"]
}
```

---

## 🚀 사용 방법

### 기본 사용 (자동 변환)

```python
from meeting_performance_analyzer import MeetingPerformanceAnalyzer

# Google Drive 스키마 컬렉션을 직접 사용 가능
analyzer = MeetingPerformanceAnalyzer(
    mongodb_uri="mongodb://localhost:27017/",
    database_name="company_db",
    collection_name="shared-recordings",  # Google Drive 컬렉션
    gemini_api_key="YOUR_API_KEY"
)

# 자동으로 변환되어 분석됨
results = analyzer.analyze_multiple_meetings()
```

**중요:** MongoDB 데이터는 수정되지 않습니다. 변환은 메모리에서만 수행됩니다.

### 📊 분석 결과 구조

스키마 변환 후 분석 결과는 다음과 같은 구조를 가집니다:

```python
{
    "meeting_id": "507f1f77bcf86cd799439011",
    "meeting_title": "회의 파일명",  # name → title 변환됨
    "meeting_date": "2025-11-17",    # createdTime → date 변환됨
    "participants": ["참여자1", "참여자2"],  # transcript에서 자동 추출
    "analysis": {
        "status": "success",
        "analysis": "AI 분석 결과...",
        "participant_stats": {...},      # 참여자별 통계
        "total_statements": 45,          # 전체 발언 수
        "template_used": "default",      # 사용된 템플릿
        "template_version": "1.0",       # 템플릿 버전
        "model_used": "gemini-2.0-flash", # AI 모델
        "timestamp": "2025-11-17T10:30:00"
    }
}
```

**중요:** 모든 분석 관련 메타데이터는 `analysis` 딕셔너리 안에만 저장됩니다.

---

### 필터 사용

```python
from datetime import datetime, timedelta

# 날짜 필터 (createdTime 또는 date 모두 지원)
filters = {
    'date': {'$gte': datetime.now() - timedelta(days=30)}
}

results = analyzer.analyze_multiple_meetings(filters)
```

---

## 🔧 필드 매핑 상세

### 자동 변환 규칙

| Google Drive 필드 | 변환 후 필드 | 변환 로직 |
|-------------------|-------------|----------|
| `name` | `title` | 그대로 복사 |
| `content` | `transcript` | 그대로 복사 |
| `createdTime` | `date` | ISO 8601 → datetime |
| - | `participants` | transcript에서 자동 추출 |

### 자동 추출 예시

**content (원본):**
```
[00:01:23] 김민수: 회의를 시작하겠습니다.
[00:01:30] 이지은: 네, 준비됐습니다.
[00:02:00] 박준호: 좋습니다.
```

**자동 추출:**
```python
participants = ["김민수", "이지은", "박준호"]
```

---

## 🎯 추천 워크플로우

### 시나리오 1: 자동 변환 사용 (권장)

```python
from meeting_performance_analyzer import MeetingPerformanceAnalyzer

# Google Drive 스키마 컬렉션을 직접 사용
analyzer = MeetingPerformanceAnalyzer(
    gemini_api_key="YOUR_API_KEY",
    database_name="company_db",
    collection_name="shared-recordings",  # Google Drive 컬렉션
    mongodb_host="localhost",
    mongodb_port=27017
)

# 자동으로 변환되어 분석됨
results = analyzer.analyze_multiple_meetings()
```

**중요:** MongoDB 데이터는 수정되지 않습니다. 모든 변환은 메모리에서만 수행됩니다.

---

## 📊 추가 필드 추천

분석을 더 잘하기 위해 다음 필드를 수동으로 추가하면 좋습니다:

```json
{
  "project": "ProjectAlpha",
  "team": "개발팀",
  "importance": "high",
  "duration": 60,
  "meeting_type": "sprint-planning"
}
```

**추가 방법:**

```python
from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017/")
db = client["company_db"]
coll = db["meeting_transcripts"]

# 특정 회의에 메타데이터 추가
coll.update_one(
    {"title": "Q4 전략 회의"},
    {"$set": {
        "project": "ProjectAlpha",
        "team": "경영진",
        "importance": "high"
    }}
)

# 또는 일괄 업데이트
coll.update_many(
    {"name": {"$regex": "ProjectAlpha"}},
    {"$set": {"project": "ProjectAlpha"}}
)
```

---

## ⚠️ 주의사항

### 1. 백업

```bash
# MongoDB 백업
mongodump --db company_db --collection shared-recordings
```

### 2. 인덱스 생성 (성능 향상)

```python
from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017/")
db = client["company_db"]
coll = db["meeting_transcripts"]

# 자주 사용하는 필드에 인덱스
coll.create_index("date")
coll.create_index("project")
coll.create_index("team")
coll.create_index([("date", -1)])  # 최신순
```

### 3. 데이터 검증

```python
# 변환 후 검증
from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017/")
db = client["company_db"]
coll = db["meeting_transcripts"]

# 필수 필드 확인
missing_title = coll.count_documents({"title": {"$exists": False}})
missing_date = coll.count_documents({"date": {"$exists": False}})
missing_transcript = coll.count_documents({"transcript": {"$exists": False}})

print(f"title 없음: {missing_title}개")
print(f"date 없음: {missing_date}개")
print(f"transcript 없음: {missing_transcript}개")
```

---

## 💡 FAQ

**Q: 기존 데이터가 손상될까요?**
A: 옵션 1(새 컬렉션 복사)을 사용하면 원본은 그대로 유지됩니다.

**Q: Google Drive와 동기화는?**
A: 새 데이터가 추가되면 다시 변환 스크립트를 실행하면 됩니다.

**Q: 참여자 자동 추출이 실패하면?**
A: 수동으로 추가하거나 transcript 형식을 맞춰주세요.

**Q: 변환 시간이 얼마나 걸리나요?**
A: 문서 100개당 약 1~2초. 50개면 1초 미만입니다.

---

## 🎯 요약

1. **분석기 생성**: Google Drive 스키마 컬렉션을 직접 지정
2. **자동 변환**: `MeetingPerformanceAnalyzer`가 자동으로 처리
3. **분석 실행**: `analyze_multiple_meetings()` 또는 `analyze_meetings()` 사용

**MongoDB 데이터는 수정되지 않습니다!** 모든 변환은 메모리에서만 수행됩니다.

## 📝 최신 기능

- ✅ Google Drive 스키마 자동 변환 (메모리에서만)
- ✅ Transcript 섹션 자동 추출
- ✅ 참여자 자동 추출 및 필터링
- ✅ 다양한 타임스탬프 형식 지원
- ✅ `analyze_meetings()`: 이미 가져온 데이터 직접 분석
- ✅ `analyze_multiple_meetings()`: MongoDB 쿼리로 분석

완료! 🎉
