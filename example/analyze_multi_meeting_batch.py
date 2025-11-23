"""
여러 회의를 한꺼번에 분석하여 종합적인 성과를 평가하는 예제 스크립트
"""

import os
import sys
from datetime import datetime, timedelta

# 상위 디렉토리를 sys.path에 추가
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from meeting_performance_analyzer import MeetingPerformanceAnalyzer
from dotenv import load_dotenv

# .env 로드
load_dotenv()

def main():
    # 1. Analyzer 초기화
    analyzer = MeetingPerformanceAnalyzer(
        gemini_api_key=os.getenv("GEMINI_API_KEY"),
        database_name=os.getenv("DATABASE_NAME", "company_db"),
        collection_name=os.getenv("COLLECTION_NAME", "meeting_transcripts"),
        mongodb_host=os.getenv("MONGODB_HOST", "localhost"),
        mongodb_port=int(os.getenv("MONGODB_PORT", 27017))
    )
    
    print("🔍 최근 회의를 검색합니다...")
    
    # 2. 분석할 회의 검색 (예: 최근 30일간의 회의)
    # 또는 특정 프로젝트 이름으로 검색: {'title': {'$regex': 'Project Alpha'}}
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    
    filters = {
        'date': {
            '$gte': start_date,
            '$lte': end_date
        }
    }
    
    meetings = analyzer.fetch_meeting_records(filters)
    
    if not meetings:
        print("❌ 분석할 회의가 없습니다.")
        return
        
    # 너무 많은 회의는 토큰 제한에 걸릴 수 있으므로 최근 5개만 선택
    if len(meetings) > 5:
        print(f"⚠️ 회의가 {len(meetings)}개로 너무 많습니다. 최근 5개만 분석합니다.")
        meetings = sorted(meetings, key=lambda x: x.get('date', datetime.min), reverse=True)[:5]
    
    print(f"\n📊 선택된 {len(meetings)}개의 회의를 종합 분석합니다.")
    for m in meetings:
        print(f"  - {m.get('title')} ({m.get('date')})")
        
    # 3. 종합 성과 리뷰 (comprehensive_review)
    print("\n\n" + "="*50)
    print("1️⃣ 종합 성과 리뷰 (Comprehensive Review)")
    print("="*50)
    
    result_review = analyzer.analyze_aggregated_meetings(
        meetings, 
        template_name="comprehensive_review"
    )
    
    if result_review and result_review['status'] == 'success':
        print(result_review['analysis'])
        
    # 4. 프로젝트 기여도 분석 (project_milestone)
    print("\n\n" + "="*50)
    print("2️⃣ 프로젝트 기여도 분석 (Project Milestone)")
    print("="*50)
    
    result_project = analyzer.analyze_aggregated_meetings(
        meetings, 
        template_name="project_milestone"
    )
    
    if result_project and result_project['status'] == 'success':
        print(result_project['analysis'])
        
    # 5. 소프트 스킬 성장 분석 (soft_skills_growth)
    print("\n\n" + "="*50)
    print("3️⃣ 소프트 스킬 성장 분석 (Soft Skills Growth)")
    print("="*50)
    
    result_soft = analyzer.analyze_aggregated_meetings(
        meetings, 
        template_name="soft_skills_growth"
    )
    
    if result_soft and result_soft['status'] == 'success':
        print(result_soft['analysis'])

if __name__ == "__main__":
    main()
