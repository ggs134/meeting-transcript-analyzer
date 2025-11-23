"""
팀 성과 리포트 빠른 예제
다양한 시나리오별 사용법 데모
"""

import os
from datetime import datetime, timedelta
import sys
from pathlib import Path

# 상위 디렉토리를 경로에 추가
sys.path.insert(0, str(Path(__file__).parent.parent))

from generate_team_report import TeamPerformanceReport
from meeting_performance_analyzer import MeetingPerformanceAnalyzer


def example_1_all_meetings():
    """예제 1: 모든 회의 분석"""
    print("\n" + "="*70)
    print("예제 1: 모든 회의 분석하여 팀 성과표 생성")
    print("="*70)
    
    analyzer = MeetingPerformanceAnalyzer(
        mongodb_uri=os.getenv('MONGODB_URI', 'mongodb://localhost:27017/'),
        database_name=os.getenv('DATABASE_NAME', 'company_db'),
        collection_name=os.getenv('COLLECTION_NAME', 'meeting_transcripts'),
        gemini_api_key=os.getenv('GEMINI_API_KEY'),
        prompt_template="default"
    )
    
    report = TeamPerformanceReport(analyzer)
    
    # 모든 회의 분석
    report.analyze_multiple_meetings()
    
    # 리포트 출력
    print(report.generate_summary_report())
    
    # 파일 저장
    report.save_full_report("example1_all_meetings.txt")
    report.export_to_csv("example1_all_meetings.csv")
    
    analyzer.close()


def example_2_recent_3_months():
    """예제 2: 최근 3개월 회의만 분석"""
    print("\n" + "="*70)
    print("예제 2: 최근 3개월 회의만 분석")
    print("="*70)
    
    analyzer = MeetingPerformanceAnalyzer(
        mongodb_uri=os.getenv('MONGODB_URI', 'mongodb://localhost:27017/'),
        database_name=os.getenv('DATABASE_NAME', 'company_db'),
        collection_name=os.getenv('COLLECTION_NAME', 'meeting_transcripts'),
        gemini_api_key=os.getenv('GEMINI_API_KEY'),
        prompt_template="default"
    )
    
    report = TeamPerformanceReport(analyzer)
    
    # 최근 3개월 필터
    three_months_ago = datetime.now() - timedelta(days=90)
    filters = {
        'date': {'$gte': three_months_ago}
    }
    
    report.analyze_multiple_meetings(filters)
    
    print(report.generate_detailed_table())
    
    # 파일 저장
    report.save_full_report("example2_recent_3months.txt")
    report.export_to_json("example2_recent_3months.json")
    
    analyzer.close()


def example_3_specific_project():
    """예제 3: 특정 프로젝트 회의만 분석"""
    print("\n" + "="*70)
    print("예제 3: 특정 프로젝트의 회의만 분석")
    print("="*70)
    
    analyzer = MeetingPerformanceAnalyzer(
        mongodb_uri=os.getenv('MONGODB_URI', 'mongodb://localhost:27017/'),
        database_name=os.getenv('DATABASE_NAME', 'company_db'),
        collection_name=os.getenv('COLLECTION_NAME', 'meeting_transcripts'),
        gemini_api_key=os.getenv('GEMINI_API_KEY'),
        prompt_template="default"
    )
    
    report = TeamPerformanceReport(analyzer)
    
    # 특정 프로젝트만
    filters = {
        'project': 'ProjectAlpha'
    }
    
    report.analyze_multiple_meetings(filters)
    
    print(report.generate_summary_report())
    
    # 모든 형식으로 저장
    report.save_full_report("example3_project_alpha.txt")
    report.export_to_json("example3_project_alpha.json")
    report.export_to_csv("example3_project_alpha.csv")
    report.export_to_excel("example3_project_alpha.xlsx")
    
    analyzer.close()


def example_4_custom_date_range():
    """예제 4: 특정 날짜 범위 분석"""
    print("\n" + "="*70)
    print("예제 4: 2024년 10월~11월 회의 분석")
    print("="*70)
    
    analyzer = MeetingPerformanceAnalyzer(
        mongodb_uri=os.getenv('MONGODB_URI', 'mongodb://localhost:27017/'),
        database_name=os.getenv('DATABASE_NAME', 'company_db'),
        collection_name=os.getenv('COLLECTION_NAME', 'meeting_transcripts'),
        gemini_api_key=os.getenv('GEMINI_API_KEY'),
        prompt_template="default"
    )
    
    report = TeamPerformanceReport(analyzer)
    
    # 특정 날짜 범위
    filters = {
        'date': {
            '$gte': datetime(2024, 10, 1),
            '$lte': datetime(2024, 11, 30)
        }
    }
    
    report.analyze_multiple_meetings(filters)
    
    print(report.generate_detailed_table())
    
    report.save_full_report("example4_oct_nov_2024.txt")
    
    analyzer.close()


def example_5_extract_individual_data():
    """예제 5: 개인별 상세 데이터 추출"""
    print("\n" + "="*70)
    print("예제 5: 특정 팀원의 상세 데이터 추출")
    print("="*70)
    
    analyzer = MeetingPerformanceAnalyzer(
        mongodb_uri=os.getenv('MONGODB_URI', 'mongodb://localhost:27017/'),
        database_name=os.getenv('DATABASE_NAME', 'company_db'),
        collection_name=os.getenv('COLLECTION_NAME', 'meeting_transcripts'),
        gemini_api_key=os.getenv('GEMINI_API_KEY'),
        prompt_template="default"
    )
    
    report = TeamPerformanceReport(analyzer)
    
    # 분석
    report.analyze_multiple_meetings()
    
    # JSON으로 저장
    json_file = report.export_to_json("example5_team_data.json")
    
    # JSON에서 특정 인물 데이터 추출
    import json
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 특정 팀원 찾기 (예: 첫 번째 팀원)
    if data['participants']:
        first_person = list(data['participants'].keys())[0]
        person_data = data['participants'][first_person]
        
        print(f"\n📊 {first_person}님의 상세 데이터:")
        print(f"  참여 회의: {person_data['total_meetings']}회")
        print(f"  평균 기여도: {person_data['avg_contribution_score']:.1f}")
        print(f"  아이디어: {person_data['ideas_count']}개")
        print(f"  완료 업무: {person_data['completed_tasks_count']}건")
        
        if person_data['ideas']:
            print(f"\n  제안한 아이디어:")
            for i, idea in enumerate(person_data['ideas'][:3], 1):
                print(f"    {i}. {idea[:60]}...")
    
    analyzer.close()


def example_6_comparison():
    """예제 6: 기간별 비교 분석"""
    print("\n" + "="*70)
    print("예제 6: Q3 vs Q4 비교 분석")
    print("="*70)
    
    analyzer = MeetingPerformanceAnalyzer(
        mongodb_uri=os.getenv('MONGODB_URI', 'mongodb://localhost:27017/'),
        database_name=os.getenv('DATABASE_NAME', 'company_db'),
        collection_name=os.getenv('COLLECTION_NAME', 'meeting_transcripts'),
        gemini_api_key=os.getenv('GEMINI_API_KEY'),
        prompt_template="default"
    )
    
    # Q3 분석
    report_q3 = TeamPerformanceReport(analyzer)
    filters_q3 = {
        'date': {
            '$gte': datetime(2024, 7, 1),
            '$lte': datetime(2024, 9, 30)
        }
    }
    report_q3.analyze_multiple_meetings(filters_q3)
    report_q3.save_full_report("example6_q3_report.txt")
    
    # Q4 분석
    report_q4 = TeamPerformanceReport(analyzer)
    filters_q4 = {
        'date': {
            '$gte': datetime(2024, 10, 1),
            '$lte': datetime(2024, 12, 31)
        }
    }
    report_q4.analyze_multiple_meetings(filters_q4)
    report_q4.save_full_report("example6_q4_report.txt")
    
    print("\n✅ Q3와 Q4 리포트를 각각 생성했습니다.")
    print("   파일을 비교하여 성장/변화를 확인하세요!")
    
    analyzer.close()


def main():
    """메인 함수 - 원하는 예제 선택 실행"""
    print("🚀 팀 성과 리포트 예제 프로그램")
    print("\n사용 가능한 예제:")
    print("1. 모든 회의 분석")
    print("2. 최근 3개월 회의만")
    print("3. 특정 프로젝트만")
    print("4. 특정 날짜 범위")
    print("5. 개인별 상세 데이터")
    print("6. 기간별 비교 분석")
    print("all. 모든 예제 실행")
    
    choice = input("\n실행할 예제 번호를 입력하세요 (1-6, 또는 'all'): ")
    
    # API 키 확인
    if not os.getenv('GEMINI_API_KEY'):
        print("\n⚠️  경고: GEMINI_API_KEY 환경 변수가 설정되지 않았습니다.")
        print("   .env 파일을 생성하거나 환경 변수를 설정해주세요.")
        return
    
    try:
        if choice == '1':
            example_1_all_meetings()
        elif choice == '2':
            example_2_recent_3_months()
        elif choice == '3':
            example_3_specific_project()
        elif choice == '4':
            example_4_custom_date_range()
        elif choice == '5':
            example_5_extract_individual_data()
        elif choice == '6':
            example_6_comparison()
        elif choice.lower() == 'all':
            print("\n⚠️  모든 예제 실행은 시간이 오래 걸립니다.")
            confirm = input("계속하시겠습니까? (y/n): ")
            if confirm.lower() == 'y':
                example_1_all_meetings()
                example_2_recent_3_months()
                example_3_specific_project()
                example_4_custom_date_range()
                example_5_extract_individual_data()
                example_6_comparison()
        else:
            print("\n⚠️  올바른 번호를 입력해주세요.")
    except Exception as e:
        print(f"\n❌ 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
