"""
월간 일간 보고서 배치 생성 스크립트
특정 월의 모든 평일(월-금)에 대해 일간 보고서를 생성하고 MongoDB에 저장합니다.
"""

import json
import os
import sys
from datetime import datetime, timedelta
from calendar import monthrange

# 상위 디렉토리를 sys.path에 추가하여 모듈 임포트 가능하게 함
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from meeting_performance_analyzer import MeetingPerformanceAnalyzer
from utils.run_analysis import get_analyzer
from utils.run_daily_analysis import (
    get_target_date,
    fetch_meetings_for_date,
    generate_daily_report,
    save_daily_report,
    save_daily_report_to_file
)

# .env 파일에서 환경 변수 로드 (상위 디렉토리)
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(dotenv_path=env_path)


def get_weekdays_in_month(year: int, month: int):
    """
    특정 월의 모든 평일(월-금) 날짜 리스트를 반환합니다.
    주말(토요일=5, 일요일=6)은 제외됩니다.
    
    Args:
        year: 연도
        month: 월 (1-12)
        
    Returns:
        평일 날짜 리스트 (datetime 객체)
    """
    weekdays = []
    # 해당 월의 첫 날과 마지막 날
    first_day = datetime(year, month, 1)
    last_day_num = monthrange(year, month)[1]
    last_day = datetime(year, month, last_day_num)
    
    # 첫 날부터 마지막 날까지 반복
    current_date = first_day
    while current_date <= last_day:
        # 월요일(0)부터 금요일(4)까지만 포함 (주말 제외)
        if current_date.weekday() < 5:  # 0=Monday, 4=Friday, 5=Saturday, 6=Sunday
            weekdays.append(current_date.replace(hour=0, minute=0, second=0, microsecond=0))
        current_date += timedelta(days=1)
    
    return weekdays


def is_weekday(date: datetime) -> bool:
    """
    주어진 날짜가 평일인지 확인합니다.
    
    Args:
        date: 확인할 날짜
        
    Returns:
        평일이면 True, 주말이면 False
    """
    return date.weekday() < 5  # 0-4: 월-금, 5-6: 토-일


def fetch_meetings_for_date_with_saturday(analyzer: MeetingPerformanceAnalyzer, target_date: datetime):
    """
    특정 날짜의 회의들을 가져옵니다.
    월요일인 경우 이전 토요일도 포함합니다.
    
    Args:
        analyzer: MeetingPerformanceAnalyzer 인스턴스
        target_date: 분석 대상 날짜
        
    Returns:
        해당 날짜(및 월요일인 경우 토요일)의 회의 리스트
    """
    # 월요일인 경우 토요일부터 포함
    if target_date.weekday() == 0:  # 0 = Monday
        # 이전 토요일 (2일 전)
        start_date = target_date - timedelta(days=2)
    else:
        start_date = target_date
    
    # 시작 날짜의 시작 시간
    start_datetime = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
    # 대상 날짜의 끝 시간
    end_datetime = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    # 날짜 필터 쿼리
    query = {
        "date": {
            "$gte": start_datetime,
            "$lte": end_datetime
        }
    }
    
    meetings = analyzer.fetch_meeting_records(query)
    return meetings


def process_single_date(target_date: datetime,
                       output_database_name: str = "gemini",
                       output_collection_name: str = "recordings_daily",
                       save_to_file: bool = True):
    """
    특정 날짜에 대해 일간 보고서를 생성하고 저장합니다.
    월요일인 경우 이전 토요일도 포함합니다.
    
    Args:
        target_date: 분석 대상 날짜
        output_database_name: 저장할 데이터베이스 이름 (기본값: "gemini")
        output_collection_name: 저장할 컬렉션 이름 (기본값: "recordings_daily")
        save_to_file: 파일로도 저장할지 여부 (기본값: True)
    """
    date_str = target_date.strftime('%Y-%m-%d')
    
    # 주말 확인
    if not is_weekday(target_date):
        weekday_name = target_date.strftime('%A')
        print(f"⚠️  {date_str} ({weekday_name})는 주말입니다. 평일만 처리합니다.")
        return False
    
    # 월요일인 경우 토요일 포함 안내
    date_range_info = ""
    if target_date.weekday() == 0:  # Monday
        saturday_date = target_date - timedelta(days=2)
        date_range_info = f" (including Saturday {saturday_date.strftime('%Y-%m-%d')})"
    
    print(f"\n📅 Processing {date_str} ({target_date.strftime('%A')}){date_range_info}...")
    print("-" * 70)
    
    try:
        # Analyzer 생성 (daily_report 템플릿 사용)
        analyzer = get_analyzer(
            prompt_template="daily_report",
            template_version="latest"
        )
        
        # 해당 날짜의 회의들 가져오기 (월요일인 경우 토요일 포함)
        meetings = fetch_meetings_for_date_with_saturday(analyzer, target_date)
        
        if not meetings:
            print(f"⚠️  {date_str} 날짜에 해당하는 회의가 없습니다.")
            analyzer.close()
            return False
        
        print(f"✅ {len(meetings)}개의 회의를 찾았습니다.")
        
        # 일간 보고서 생성
        analyzed_results = generate_daily_report(analyzer, meetings, target_date)
        
        if not analyzed_results:
            print(f"⚠️  {date_str} 분석 결과가 없습니다.")
            analyzer.close()
            return False
        
        # MongoDB에 저장
        save_daily_report(
            analyzer, 
            analyzed_results, 
            target_date,
            output_database_name=output_database_name,
            output_collection_name=output_collection_name
        )
        
        # 파일로 저장 (선택사항)
        if save_to_file:
            save_daily_report_to_file(analyzed_results, target_date)
        
        print(f"✅ {date_str} 일간 보고서 생성 및 저장 완료!")
        analyzer.close()
        return True
        
    except Exception as e:
        print(f"❌ {date_str} 처리 중 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def process_monthly_daily_reports(year: int, month: int, 
                                  output_database_name: str = "gemini",
                                  output_collection_name: str = "recordings_daily",
                                  save_to_file: bool = True):
    """
    특정 월의 모든 평일에 대해 일간 보고서를 생성하고 저장합니다.
    
    Args:
        year: 연도
        month: 월 (1-12)
        output_database_name: 저장할 데이터베이스 이름 (기본값: "gemini")
        output_collection_name: 저장할 컬렉션 이름 (기본값: "recordings_daily")
        save_to_file: 파일로도 저장할지 여부 (기본값: True)
    """
    print("\n" + "=" * 70)
    print(f"📅 Monthly Daily Reports Generator - {year}년 {month}월")
    print("=" * 70)
    
    # 해당 월의 모든 평일 가져오기
    weekdays = get_weekdays_in_month(year, month)
    print(f"\n📆 총 {len(weekdays)}개의 평일이 있습니다.")
    
    if not weekdays:
        print("⚠️  처리할 평일이 없습니다.")
        return
    
    try:
        # Analyzer 생성 (daily_report 템플릿 사용)
        analyzer = get_analyzer(
            prompt_template="daily_report",
            template_version="latest"  # 최신 버전 사용
        )
        
        success_count = 0
        skip_count = 0
        error_count = 0
        
        # 각 평일에 대해 처리
        for idx, target_date in enumerate(weekdays, 1):
            date_str = target_date.strftime('%Y-%m-%d')
            
            # 월요일인 경우 토요일 포함 안내
            date_range_info = ""
            if target_date.weekday() == 0:  # Monday
                saturday_date = target_date - timedelta(days=2)
                date_range_info = f" (including Saturday {saturday_date.strftime('%Y-%m-%d')})"
            
            print(f"\n[{idx}/{len(weekdays)}] Processing {date_str} ({target_date.strftime('%A')}){date_range_info}...")
            print("-" * 70)
            
            try:
                # 해당 날짜의 회의들 가져오기 (월요일인 경우 토요일 포함)
                meetings = fetch_meetings_for_date_with_saturday(analyzer, target_date)
                
                if not meetings:
                    print(f"⚠️  {date_str}{date_range_info} 날짜에 해당하는 회의가 없습니다. 건너뜁니다.")
                    skip_count += 1
                    continue
                
                print(f"✅ {len(meetings)}개의 회의를 찾았습니다{date_range_info}.")
                
                # 일간 보고서 생성
                analyzed_results = generate_daily_report(analyzer, meetings, target_date)
                
                if not analyzed_results:
                    print(f"⚠️  {date_str} 분석 결과가 없습니다. 건너뜁니다.")
                    skip_count += 1
                    continue
                
                # MongoDB에 저장 (gemini.recordings_daily)
                save_daily_report(
                    analyzer, 
                    analyzed_results, 
                    target_date,
                    output_database_name=output_database_name,
                    output_collection_name=output_collection_name
                )
                
                # 파일로 저장 (선택사항)
                if save_to_file:
                    save_daily_report_to_file(analyzed_results, target_date)
                
                success_count += 1
                print(f"✅ {date_str} 일간 보고서 생성 및 저장 완료!")
                
            except Exception as e:
                error_count += 1
                print(f"❌ {date_str} 처리 중 오류 발생: {str(e)}")
                import traceback
                traceback.print_exc()
                continue
        
        # 최종 요약
        print("\n" + "=" * 70)
        print("📊 처리 완료 요약")
        print("=" * 70)
        print(f"✅ 성공: {success_count}개")
        print(f"⚠️  건너뜀 (회의 없음): {skip_count}개")
        print(f"❌ 오류: {error_count}개")
        print(f"📅 총 처리 대상: {len(weekdays)}개")
        print(f"💾 저장 위치: {output_database_name}.{output_collection_name}")
        
    except Exception as e:
        print(f"\n❌ 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        # 연결 종료
        if 'analyzer' in locals():
            analyzer.close()


def main():
    """
    메인 실행 함수
    """
    import argparse
    
    parser = argparse.ArgumentParser(description='일간 보고서 배치 생성 (특정 날짜 또는 월 전체)')
    parser.add_argument(
        '--date',
        type=str,
        help='특정 날짜 (YYYY-MM-DD 형식). 지정하면 해당 날짜만 처리. 지정하지 않으면 --year와 --month로 한 달 전체 처리',
        default=None
    )
    parser.add_argument(
        '--year',
        type=int,
        help='연도 (예: 2025). --date가 없을 때만 사용. 지정하지 않으면 현재 연도 사용',
        default=None
    )
    parser.add_argument(
        '--month',
        type=int,
        help='월 (1-12). --date가 없을 때만 사용. 지정하지 않으면 현재 월 사용',
        default=None
    )
    parser.add_argument(
        '--database',
        type=str,
        help='저장할 데이터베이스 이름 (기본값: gemini)',
        default='gemini'
    )
    parser.add_argument(
        '--collection',
        type=str,
        help='저장할 컬렉션 이름 (기본값: recordings_daily)',
        default='recordings_daily'
    )
    parser.add_argument(
        '--no-file',
        action='store_true',
        help='파일로 저장하지 않음 (MongoDB에만 저장)',
        default=False
    )
    
    args = parser.parse_args()
    
    # --date가 지정된 경우: 특정 날짜만 처리
    if args.date:
        try:
            target_date = datetime.strptime(args.date, '%Y-%m-%d')
            target_date = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        except ValueError:
            print("❌ 잘못된 날짜 형식입니다. YYYY-MM-DD 형식을 사용해주세요. (예: 2025-11-24)")
            sys.exit(1)
        
        print("\n" + "=" * 70)
        print(f"📅 Single Date Daily Report Generator - {target_date.strftime('%Y-%m-%d')}")
        print("=" * 70)
        
        success = process_single_date(
            target_date=target_date,
            output_database_name=args.database,
            output_collection_name=args.collection,
            save_to_file=not args.no_file
        )
        
        if success:
            print(f"\n✅ {args.date} 일간 보고서 처리 완료!")
        else:
            print(f"\n⚠️  {args.date} 일간 보고서 처리 실패 또는 건너뜀")
    
    # --date가 없고, year나 month가 지정된 경우: 한 달 전체 처리
    elif args.year or args.month:
        # 연도와 월 결정
        now = datetime.now()
        year = args.year if args.year else now.year
        month = args.month if args.month else now.month
        
        # 유효성 검사
        if month < 1 or month > 12:
            print("❌ 월은 1-12 사이의 값이어야 합니다.")
            sys.exit(1)
        
        if year < 2000 or year > 2100:
            print("❌ 연도는 2000-2100 사이의 값이어야 합니다.")
            sys.exit(1)
        
        # 배치 처리 실행
        process_monthly_daily_reports(
            year=year,
            month=month,
            output_database_name=args.database,
            output_collection_name=args.collection,
            save_to_file=not args.no_file
        )
    
    # date, year, month 모두 지정하지 않은 경우: 오늘 날짜 처리
    else:
        now = datetime.now()
        target_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        print("\n" + "=" * 70)
        print(f"📅 Daily Report Generator - Today ({target_date.strftime('%Y-%m-%d')})")
        print("=" * 70)
        
        success = process_single_date(
            target_date=target_date,
            output_database_name=args.database,
            output_collection_name=args.collection,
            save_to_file=not args.no_file
        )
        
        if success:
            print(f"\n✅ {target_date.strftime('%Y-%m-%d')} 일간 보고서 처리 완료!")
        else:
            print(f"\n⚠️  {target_date.strftime('%Y-%m-%d')} 일간 보고서 처리 실패 또는 건너뜀")


if __name__ == "__main__":
    main()

