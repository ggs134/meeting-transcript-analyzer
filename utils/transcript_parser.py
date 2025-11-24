"""
MongoDB Transcript 파싱 대화형 인터페이스
사용자 입력을 받아서 핵심 기능을 호출하는 대화형 프로그램
"""

import os
import sys
import json
from datetime import datetime
from dotenv import load_dotenv

# 상위 디렉토리를 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from meeting_performance_analyzer import MeetingPerformanceAnalyzer
from prompt_templates import PromptTemplates
from transcript_parser_core import (
    get_all_participants,
    test_all_transcripts,
    test_with_filters,
    convert_objectid
)

# .env 파일에서 환경 변수 로드
load_dotenv()


def build_filters(analyzer=None):
    """
    대화형으로 필터 조건을 구성
    
    Args:
        analyzer: MeetingPerformanceAnalyzer 인스턴스 (참여자 목록 가져오기용, 선택사항)
    
    Returns:
        (filters, post_filters) 튜플 또는 (None, None) (취소 시)
    """
    filters = {}
    post_filters = {}  # 파싱 후 필터링할 조건들
    
    print("\n" + "="*80)
    print("🔍 필터 옵션 선택")
    print("="*80)
    print("\n다음 필터 옵션 중 선택하세요 (여러 개 선택 가능, 쉼표로 구분):")
    print("1. 날짜 범위 필터")
    print("2. 제목 키워드 필터")
    print("3. 특정 참여자 포함 필터")
    print("4. Transcript 길이 필터")
    print("5. 참여자 수 필터 (파싱 후)")
    print("0. 필터 없이 진행 (모든 회의)")
    print("b. 뒤로 가기 (필터 선택 취소)")
    
    try:
        choices = input("\n선택하세요 (예: 1,3,5 또는 0, b): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        choices = "0"
        print("\n기본값(0)을 사용합니다.")
    
    if not choices or choices == "0":
        print("\n✅ 필터 없이 모든 회의를 분석합니다.")
        return filters, post_filters
    
    if choices == "b" or choices == "back":
        print("\n⏪ 필터 선택을 취소하고 이전 단계로 돌아갑니다.")
        return None, None
    
    choice_list = [c.strip() for c in choices.split(',')]
    
    # 'b'가 포함되어 있으면 제거
    if 'b' in choice_list or 'back' in choice_list:
        choice_list = [c for c in choice_list if c not in ['b', 'back']]
        if not choice_list:
            print("\n⏪ 필터 선택을 취소하고 이전 단계로 돌아갑니다.")
            return None, None
    
    # 1. 날짜 범위 필터
    if '1' in choice_list:
        print("\n📅 날짜 범위 필터")
        print("   옵션:")
        print("   a. 최근 N일")
        print("   b. 특정 기간 (시작일 ~ 종료일)")
        print("   c. 이번 주")
        print("   d. 이번 달")
        print("   e. 올해")
        print("   x. 취소")
        
        try:
            date_choice = input("   선택 (a/b/c/d/e/x): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            date_choice = "a"
        
        if date_choice == "x" or date_choice == "cancel":
            print("   ⏪ 날짜 필터 선택을 취소했습니다.")
        else:
            from datetime import timedelta
            
            if date_choice == 'a':
                try:
                    days = int(input("   최근 며칠? (기본값: 30): ").strip() or "30")
                except (ValueError, EOFError, KeyboardInterrupt):
                    days = 30
                filters['date'] = {'$gte': datetime.now() - timedelta(days=days)}
                print(f"   ✅ 최근 {days}일 회의 필터 적용")
            
            elif date_choice == 'b':
                try:
                    start_str = input("   시작일 (YYYY-MM-DD): ").strip()
                    end_str = input("   종료일 (YYYY-MM-DD): ").strip()
                    if start_str:
                        start_date = datetime.strptime(start_str, '%Y-%m-%d')
                        filters['date'] = {'$gte': start_date}
                    if end_str:
                        end_date = datetime.strptime(end_str, '%Y-%m-%d')
                        if 'date' in filters:
                            filters['date']['$lte'] = end_date
                        else:
                            filters['date'] = {'$lte': end_date}
                    print(f"   ✅ 날짜 범위 필터 적용: {start_str} ~ {end_str}")
                except (ValueError, EOFError, KeyboardInterrupt) as e:
                    print(f"   ⚠️  날짜 형식 오류: {e}")
            
            elif date_choice == 'c':  # 이번 주
                today = datetime.now()
                week_start = today - timedelta(days=today.weekday())
                filters['date'] = {'$gte': week_start}
                print(f"   ✅ 이번 주 필터 적용")
            
            elif date_choice == 'd':  # 이번 달
                today = datetime.now()
                month_start = datetime(today.year, today.month, 1)
                filters['date'] = {'$gte': month_start}
                print(f"   ✅ 이번 달 필터 적용")
            
            elif date_choice == 'e':  # 올해
                today = datetime.now()
                year_start = datetime(today.year, 1, 1)
                filters['date'] = {'$gte': year_start}
                print(f"   ✅ 올해 필터 적용")
    
    # 2. 제목 키워드 필터
    if '2' in choice_list:
        try:
            keyword = input("\n📝 제목 키워드 (부분 일치, x로 취소): ").strip()
            if keyword and keyword.lower() not in ['x', 'cancel']:
                # title 또는 name 필드에 키워드가 포함된 경우
                title_filter = {
                    '$or': [
                        {'title': {'$regex': keyword, '$options': 'i'}},
                        {'name': {'$regex': keyword, '$options': 'i'}}
                    ]
                }
                # 기존 필터와 AND로 결합
                if filters:
                    # $and가 이미 있으면 배열에 추가, 없으면 새로 생성
                    if '$and' in filters:
                        filters['$and'].append(title_filter)
                    else:
                        # 기존 필터를 $and로 감싸고 title_filter 추가
                        filters = {'$and': [filters, title_filter]}
                else:
                    filters = title_filter
                print(f"   ✅ 제목 키워드 필터 적용: '{keyword}'")
            elif keyword.lower() in ['x', 'cancel']:
                print("   ⏪ 제목 키워드 필터 선택을 취소했습니다.")
        except (EOFError, KeyboardInterrupt):
            pass
    
    # 3. 특정 참여자 포함 필터
    if '3' in choice_list:
        try:
            if analyzer:
                # 참여자 목록 가져오기
                participants_list = get_all_participants(analyzer)
                
                if not participants_list:
                    print("\n   ⚠️  참여자 목록을 가져올 수 없습니다. 이름을 직접 입력하세요.")
                    participant = input("   👤 참여자 이름 (정확히 일치): ").strip()
                    if participant:
                        post_filters['participants'] = participant
                        print(f"   ✅ 참여자 필터 적용: '{participant}'")
                        print("   ⚠️  참여자는 파싱 후 필터링됩니다.")
                else:
                    print(f"\n👤 참여자 목록 ({len(participants_list)}명):")
                    for i, p in enumerate(participants_list, 1):
                        print(f"   {i:3d}. {p}")
                    
                    try:
                        choice_input = input("\n   선택하세요 (번호, 여러 개 선택 가능: 1,3,5 또는 Enter로 직접 입력, x로 취소): ").strip()
                    except (EOFError, KeyboardInterrupt):
                        choice_input = ""
                    
                    if choice_input and choice_input.lower() in ['x', 'cancel']:
                        print("   ⏪ 참여자 필터 선택을 취소했습니다.")
                    elif choice_input:
                        # 번호로 선택
                        try:
                            selected_indices = [int(x.strip()) - 1 for x in choice_input.split(',')]
                            selected_participants = [participants_list[i] for i in selected_indices if 0 <= i < len(participants_list)]
                            
                            if selected_participants:
                                if len(selected_participants) == 1:
                                    post_filters['participants'] = selected_participants[0]
                                    print(f"   ✅ 참여자 필터 적용: '{selected_participants[0]}'")
                                else:
                                    # 여러 명 선택 시 첫 번째만 사용 (또는 OR 조건으로 확장 가능)
                                    post_filters['participants'] = selected_participants[0]
                                    print(f"   ✅ 참여자 필터 적용: '{selected_participants[0]}' (첫 번째 선택)")
                                    print(f"   ℹ️  여러 명 선택 시 첫 번째 참여자만 필터로 사용됩니다.")
                                print("   ⚠️  참여자는 파싱 후 필터링됩니다.")
                            else:
                                print("   ⚠️  유효한 선택이 없습니다.")
                        except (ValueError, IndexError):
                            # 번호가 아니면 직접 입력으로 처리
                            participant = choice_input
                            post_filters['participants'] = participant
                            print(f"   ✅ 참여자 필터 적용: '{participant}'")
                            print("   ⚠️  참여자는 파싱 후 필터링됩니다.")
                    else:
                        # 직접 입력
                        participant = input("   👤 참여자 이름 (정확히 일치, x로 취소): ").strip()
                        if participant and participant.lower() not in ['x', 'cancel']:
                            post_filters['participants'] = participant
                            print(f"   ✅ 참여자 필터 적용: '{participant}'")
                            print("   ⚠️  참여자는 파싱 후 필터링됩니다.")
                        elif participant.lower() in ['x', 'cancel']:
                            print("   ⏪ 참여자 필터 선택을 취소했습니다.")
            else:
                # analyzer가 없으면 직접 입력
                participant = input("\n👤 참여자 이름 (정확히 일치, x로 취소): ").strip()
                if participant and participant.lower() not in ['x', 'cancel']:
                    post_filters['participants'] = participant
                    print(f"   ✅ 참여자 필터 적용: '{participant}'")
                    print("   ⚠️  참여자는 파싱 후 필터링됩니다.")
                elif participant.lower() in ['x', 'cancel']:
                    print("   ⏪ 참여자 필터 선택을 취소했습니다.")
        except (EOFError, KeyboardInterrupt):
            pass
    
    # 4. Transcript 길이 필터
    if '4' in choice_list:
        try:
            min_length = input("\n📏 최소 Transcript 길이 (문자 수, 기본값: 0, x로 취소): ").strip()
            if min_length and min_length.lower() in ['x', 'cancel']:
                print("   ⏪ Transcript 길이 필터 선택을 취소했습니다.")
            else:
                max_length = input("   최대 Transcript 길이 (문자 수, 기본값: 무제한): ").strip()
                
                if min_length or max_length:
                    # 간단한 방법: content 또는 transcript 필드로 필터링
                    # MongoDB aggregation을 사용하지 않고 파싱 후 필터링
                    if min_length:
                        post_filters['min_transcript_length'] = int(min_length)
                    if max_length:
                        post_filters['max_transcript_length'] = int(max_length)
                    print(f"   ✅ Transcript 길이 필터 적용 (파싱 후): {min_length or 0} ~ {max_length or '무제한'}자")
        except (ValueError, EOFError, KeyboardInterrupt):
            pass
    
    # 5. 참여자 수 필터 (파싱 후 필터링)
    if '5' in choice_list:
        try:
            min_participants = input("\n👥 최소 참여자 수 (기본값: 0, x로 취소): ").strip()
            if min_participants and min_participants.lower() in ['x', 'cancel']:
                print("   ⏪ 참여자 수 필터 선택을 취소했습니다.")
            else:
                max_participants = input("   최대 참여자 수 (기본값: 무제한, x로 취소): ").strip()
                
                if max_participants and max_participants.lower() in ['x', 'cancel']:
                    print("   ⏪ 참여자 수 필터 선택을 취소했습니다.")
                elif min_participants or max_participants:
                    post_filters['min_participants'] = int(min_participants) if min_participants else 0
                    post_filters['max_participants'] = int(max_participants) if max_participants else None
                    print(f"   ✅ 참여자 수 필터 적용 (파싱 후): {min_participants or 0} ~ {max_participants or '무제한'}명")
        except (ValueError, EOFError, KeyboardInterrupt):
            pass
    
    return filters, post_filters



def _select_individual_meeting(analyzer):
    """
    페이지네이션을 사용하여 개별 회의 선택
    
    Args:
        analyzer: MeetingPerformanceAnalyzer 인스턴스
        
    Returns:
        선택된 회의 문서 또는 None (취소 시)
    """
    # 모든 회의 가져오기 (최신순)
    all_meetings = list(analyzer.collection.find())
    
    # Sort by date or createdTime (support both schemas)
    all_meetings.sort(key=lambda m: m.get('date') or m.get('createdTime') or '', reverse=True)
    
    if not all_meetings:
        print("❌ 회의 데이터가 없습니다.")
        return None
    
    page_size = 5
    current_page = 0
    total_pages = (len(all_meetings) + page_size - 1) // page_size
    
    while True:
        # 현재 페이지의 회의 목록
        start_idx = current_page * page_size
        end_idx = min(start_idx + page_size, len(all_meetings))
        page_meetings = all_meetings[start_idx:end_idx]
        
        # 페이지 표시
        print("\n" + "="*80)
        print(f"📋 회의 목록 (페이지 {current_page + 1}/{total_pages})")
        print("="*80)
        
        for i, meeting in enumerate(page_meetings, 1):
            global_idx = start_idx + i
            # Support both Google Drive schema (name/content/createdTime) and standard schema (title/transcript/date)
            title = meeting.get('title') or meeting.get('name', 'Untitled')
            date = meeting.get('date') or meeting.get('createdTime', 'Unknown Date')
            if hasattr(date, 'strftime'):
                date = date.strftime('%Y-%m-%d %H:%M')
            
            # Participants: try to get from field or extract from transcript/content
            participants = meeting.get('participants', [])
            if not participants:
                # Try to extract from transcript
                import re
                transcript = meeting.get('transcript') or meeting.get('content', '')
                if transcript:
                    # Quick extraction of unique speakers (simplified)
                    speaker_pattern = r'\[[\d:]+\]\s*([^:]+):'
                    matches = re.findall(speaker_pattern, transcript[:5000])  # First 5000 chars
                    participants = list(dict.fromkeys(matches))  # Preserve order, remove duplicates
            
            participants_str = ', '.join(participants[:3]) if participants else '참여자 정보 없음'
            if len(participants) > 3:
                participants_str += f' (+{len(participants) - 3}명)'
            
            print(f"{global_idx}. {title}")
            print(f"   📅 {date}")
            print(f"   👥 {participants_str}")
            print()
        
        # 네비게이션 옵션
        print("-" * 80)
        nav_options = []
        if current_page > 0:
            nav_options.append("p (이전 페이지)")
        if current_page < total_pages - 1:
            nav_options.append("n (다음 페이지)")
        nav_options.append("숫자 (회의 선택)")
        nav_options.append("0 (취소)")
        
        print("옵션: " + " | ".join(nav_options))
        
        try:
            choice = input("\n선택: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            return None
        
        if choice == '0':
            return None
        elif choice == 'n' and current_page < total_pages - 1:
            current_page += 1
        elif choice == 'p' and current_page > 0:
            current_page -= 1
        elif choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(all_meetings):
                selected = all_meetings[idx]
                title = selected.get('title', 'Untitled')
                print(f"\n✅ 선택된 회의: {title}")
                return selected
            else:
                print(f"⚠️  잘못된 번호입니다. 1~{len(all_meetings)} 사이의 숫자를 입력하세요.")
        else:
            print("⚠️  잘못된 입력입니다.")


def _get_analyzer():
    """
    환경 변수에서 설정을 읽어 MeetingPerformanceAnalyzer 인스턴스 생성
    
    Returns:
        MeetingPerformanceAnalyzer 인스턴스
    """
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY 환경 변수가 설정되지 않았습니다.")
    
    DATABASE_NAME = os.getenv('DATABASE_NAME', 'company_db')
    COLLECTION_NAME = os.getenv('COLLECTION_NAME', 'meeting_transcripts')
    
    MONGODB_HOST = os.getenv('MONGODB_HOST', 'localhost')
    MONGODB_PORT = int(os.getenv('MONGODB_PORT', '27017'))
    MONGODB_USERNAME = os.getenv('MONGODB_USERNAME')
    MONGODB_PASSWORD = os.getenv('MONGODB_PASSWORD')
    MONGODB_AUTH_DATABASE = os.getenv('MONGODB_AUTH_DATABASE')
    MONGODB_URI = os.getenv('MONGODB_URI')
    
    return MeetingPerformanceAnalyzer(
        gemini_api_key=GEMINI_API_KEY,
        database_name=DATABASE_NAME,
        collection_name=COLLECTION_NAME,
        mongodb_host=MONGODB_HOST,
        mongodb_port=MONGODB_PORT,
        mongodb_username=MONGODB_USERNAME,
        mongodb_password=MONGODB_PASSWORD,
        mongodb_auth_database=MONGODB_AUTH_DATABASE,
        mongodb_uri=MONGODB_URI
    )


def _save_parsed_results(result, output_dir=None):
    """
    파싱 결과를 JSON 파일로 저장
    
    Args:
        result: test_all_transcripts 또는 test_with_filters의 결과
        output_dir: 출력 파일을 저장할 디렉토리 (None이면 현재 스크립트 디렉토리)
    """
    if output_dir is None:
        output_dir = os.getcwd()
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(output_dir, f"parsed_transcripts_{timestamp}.json")
    
    # 필터 정보가 있는지 확인 (test_with_filters 결과인지)
    if 'filters' in result:
        output_data = {
            "generated_at": datetime.now().isoformat(),
            "filters_applied": {
                "mongodb_filters": result.get('filters'),
                "post_filters": result.get('post_filters')
            },
            "summary": result['summary'],
            "parsed_meetings": result['parsed_meetings']
        }
    else:
        output_data = {
            "generated_at": datetime.now().isoformat(),
            "summary": result['summary'],
            "parsed_meetings": result['parsed_meetings']
        }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"\n💾 파싱 결과를 '{output_file}' 파일에 저장했습니다.")
    print(f"   총 {len(result['parsed_meetings'])}개의 회의 파싱 결과가 저장되었습니다.")


def _save_original_meetings(result, output_dir=None):
    """
    원본 쿼리 결과를 JSON 파일로 저장
    
    Args:
        result: test_all_transcripts 또는 test_with_filters의 결과
        output_dir: 출력 파일을 저장할 디렉토리 (None이면 현재 스크립트 디렉토리)
    """
    if output_dir is None:
        output_dir = os.getcwd()
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(output_dir, f"original_meetings_{timestamp}.json")
    
    # 필터 정보가 있는지 확인 (test_with_filters 결과인지)
    if 'filters' in result:
        output_data = {
            "generated_at": datetime.now().isoformat(),
            "filters_applied": {
                "mongodb_filters": result.get('filters'),
                "post_filters": result.get('post_filters')
            },
            "total_meetings": len(result['meetings']),
            "original_meetings": [convert_objectid(meeting) for meeting in result['meetings']]
        }
    else:
        output_data = {
            "generated_at": datetime.now().isoformat(),
            "total_meetings": len(result['meetings']),
            "original_meetings": [convert_objectid(meeting) for meeting in result['meetings']]
        }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"\n💾 원본 쿼리 결과를 '{output_file}' 파일에 저장했습니다.")
    print(f"   총 {len(result['meetings'])}개의 원본 회의 데이터가 저장되었습니다.")


def _ask_save_option(prompt):
    """
    저장 여부를 물어보는 헬퍼 함수
    
    Args:
        prompt: 물어볼 메시지
        
    Returns:
        bool: 저장할지 여부
    """
    try:
        choice = input(f"\n{prompt} (y/n, 기본값: n): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        choice = 'n'
        print("\n기본값(n)을 사용합니다.")
    
    return choice == 'y' or choice == 'yes'


def _interactive_analysis(analyzer, parsed_result, skip_mode_selection=False):
    """
    파싱된 결과에 대해 대화형으로 분석 수행
    
    Args:
        analyzer: MeetingPerformanceAnalyzer 인스턴스
        parsed_result: 파싱 결과 딕셔너리
        skip_mode_selection: True이면 개별 분석 모드로 바로 진행 (개별 회의 선택 시)
    """
    # 파싱된 회의가 없으면 종료
    if not parsed_result or not parsed_result.get('parsed_meetings'):
        return

    parsed_meetings = parsed_result['parsed_meetings']
    meeting_count = len(parsed_meetings)
    
    print("\n" + "="*80)
    print("🤖 AI 성과 분석 (선택 사항)")
    print("="*80)
    print(f"파싱된 {meeting_count}개의 회의에 대해 AI 분석을 실행할 수 있습니다.")
    
    if not _ask_save_option("AI 분석을 실행하시겠습니까?"):
        return

    # 개별 회의 선택 모드이거나 회의가 1개인 경우 모드 선택 스킵
    if skip_mode_selection or meeting_count == 1:
        mode = "1"  # 개별 분석 모드로 고정
        if skip_mode_selection:
            print("\n📊 개별 회의 분석 모드로 진행합니다.")
    else:
        while True:
            print("\n📊 분석 모드 선택:")
            print("1. 개별 회의 분석 (각 회의별로 분석 리포트 생성)")
            print("2. 종합 분석 (모든 회의를 합쳐서 하나의 리포트 생성)")
            print("0. 취소")
            
            try:
                mode = input("\n선택 (1/2/0): ").strip()
            except (EOFError, KeyboardInterrupt):
                mode = "0"
            
            if mode == "0":
                print("분석을 취소합니다.")
                return
            
            if mode not in ["1", "2"]:
                print("잘못된 선택입니다.")
                continue
            
            break
            
    # 템플릿 선택 루프
    while True:
        # 템플릿 선택
        print("\n📝 프롬프트 템플릿 선택:")
        all_templates = PromptTemplates.list_templates()
        
        # 분석 모드에 따른 템플릿 필터링
        aggregated_templates = ['comprehensive_review', 'project_milestone', 'soft_skills_growth', 'my_summary']
        
        if mode == "1": # 개별 분석
            # 종합 분석용 템플릿 제외
            filtered_templates = {k: v for k, v in all_templates.items() if k not in aggregated_templates}
        else: # 종합 분석
            # 종합 분석용 템플릿만 포함
            filtered_templates = {k: v for k, v in all_templates.items() if k in aggregated_templates}
            
        template_names = sorted(filtered_templates.keys())
        
        if not template_names:
            print("⚠️  사용 가능한 템플릿이 없습니다.")
            continue
        
        for i, name in enumerate(template_names, 1):
            desc = filtered_templates[name]
            # 설명이 너무 길면 자르기
            if len(desc) > 50:
                desc = desc[:47] + "..."
            print(f"{i}. {name:<20} : {desc}")
            
        print("0. 취소")
        
        try:
            template_idx = input(f"\n선택 (1~{len(template_names)}): ").strip()
        except (EOFError, KeyboardInterrupt):
            template_idx = "0"
            
        if template_idx == "0":
            continue
            
        try:
            idx = int(template_idx) - 1
            if 0 <= idx < len(template_names):
                selected_template = template_names[idx]
            else:
                print("잘못된 번호입니다.")
                continue
        except ValueError:
            print("숫자를 입력해주세요.")
            continue
            
        print(f"\n✅ 선택된 템플릿: {selected_template}")
        
        # 버전 선택
        available_versions = PromptTemplates.list_versions(selected_template)
        selected_version = None
        
        if available_versions:
            print(f"\n📅 프롬프트 버전 선택 (기본값: latest):")
            # 최신 버전 확인
            latest_ver = None
            # PromptTemplates.list_versions는 정렬된 리스트를 반환함
            # 하지만 latest 정보는 list_templates나 직접 확인해야 함
            # 여기서는 간단히 목록만 보여주고 선택하게 함
            
            for v in available_versions:
                print(f"   - {v}")
            
            ver_choice = input("버전 입력 (엔터치면 latest 사용): ").strip()
            if ver_choice:
                if ver_choice in available_versions:
                    selected_version = ver_choice
                    print(f"✅ 선택된 버전: {selected_version}")
                else:
                    print(f"⚠️  존재하지 않는 버전입니다. 최신 버전(latest)을 사용합니다.")
            else:
                print("✅ 최신 버전(latest)을 사용합니다.")
        
        
        # my_summary 템플릿인 경우 사용자 이름 물어보기
        user_name_instruction = ""
        if selected_template == "my_summary":
            # 참여자 목록 추출
            all_participants = set()
            if mode == "1": # 개별 분석 (모든 회의)
                for m in parsed_meetings:
                    all_participants.update(m.get('participants', []))
            elif mode == "2": # 종합 분석 (필터링된 회의)
                # parsed_meetings는 이미 필터링된 목록임 (test_with_filters의 결과가 parsed_meetings라면)
                # 하지만 여기서 parsed_meetings는 test_all_transcripts의 결과일 수도 있고 test_with_filters의 결과일 수도 있음
                # _interactive_analysis의 인자 parsed_result 구조를 확인해야 함
                # parsed_result['parsed_meetings']가 리스트임
                for m in parsed_meetings:
                    all_participants.update(m.get('participants', []))
            
            sorted_participants = sorted(list(all_participants))
            
            if sorted_participants:
                print("\n👤 회의록에서 본인의 이름을 선택해주세요:")
                for i, p in enumerate(sorted_participants, 1):
                    print(f"{i}. {p}")
                print(f"{len(sorted_participants) + 1}. 직접 입력")
                
                try:
                    p_choice = input(f"선택 (1~{len(sorted_participants) + 1}): ").strip()
                    p_idx = int(p_choice) - 1
                    if 0 <= p_idx < len(sorted_participants):
                        user_name = sorted_participants[p_idx]
                    else:
                        user_name = input("이름 입력: ").strip()
                except ValueError:
                    user_name = input("이름 입력: ").strip()
            else:
                print("\n👤 회의록에서 본인의 이름(또는 식별자)은 무엇인가요?")
                user_name = input("입력: ").strip()

            if user_name:
                user_name_instruction = f"\n\n[User Identification]\nThe user requesting this summary is identified as '{user_name}' in the transcript. Please focus on this person's contributions and tasks when referring to 'I' or 'me'."
                print(f"✅ 사용자 식별자가 설정되었습니다: '{user_name}'")
        
        # 추가 요청사항 입력
        print("\n📝 추가 요청사항이 있으신가요? (없으면 엔터)")
        custom_instructions = input("입력: ").strip()
        
        # 사용자 이름 지시사항과 추가 요청사항 합치기
        full_instructions = custom_instructions
        if user_name_instruction:
            full_instructions += user_name_instruction
            
        if full_instructions:
            print(f"✅ 추가 요청사항이 반영됩니다.")
        
        # 분석 실행
        try:
            if mode == "1":
                # 개별 분석
                print(f"\n🚀 {meeting_count}개의 회의를 개별적으로 분석합니다...")
                
                analysis_results = []
                
                for i, meeting in enumerate(parsed_meetings, 1):
                    title = meeting.get('title', 'Untitled')
                    print(f"\n[{i}/{meeting_count}] '{title}' 분석 중...")
                    
                    # 포맷팅된 텍스트 생성 (재사용)
                    # 주의: meeting_performance_analyzer의 내부 로직을 일부 재구현해야 함
                    # 여기서는 간단히 analyzer.analyze_participant_performance 호출
                    
                    # 필요한 데이터 재구성
                    stats = meeting.get('participant_stats', {})
                    parsed_transcript = meeting.get('parsed_transcript', [])
                    
                    # 포맷팅
                    formatted_text = analyzer.format_transcript_for_analysis(
                        meeting, parsed_transcript, stats
                    )
                    
                    # 분석 호출
                    result = analyzer.analyze_participant_performance(
                        formatted_text, stats, template_override=selected_template,
                        custom_instructions=full_instructions,
                        version=selected_version
                    )
                    
                    if result['status'] == 'success':
                        print("\n" + "-"*40)
                        print(f"📄 분석 결과 ({title})")
                        print("-" * 40)
                        print(result['analysis'])
                        print("-" * 40)
                        
                        # 결과 저장용 데이터 수집
                        analysis_results.append({
                            'title': title,
                            'date': meeting.get('date', 'Unknown'),
                            'template': selected_template,
                            'analysis': result['analysis']
                        })
                    else:
                        print(f"❌ 분석 실패: {result.get('error')}")
                
                # 일괄 저장 옵션
                if analysis_results:
                    if _ask_save_option(f"총 {len(analysis_results)}개의 분석 결과를 파일로 저장하시겠습니까?"):
                        saved_count = 0
                        # Output 디렉토리 생성
                        output_dir = os.path.join(os.getcwd(), "output")
                        os.makedirs(output_dir, exist_ok=True)
                        
                        for res in analysis_results:
                            try:
                                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                                safe_title = "".join([c for c in res['title'] if c.isalnum() or c in (' ', '-', '_')]).strip().replace(' ', '_')
                                filename = os.path.join(output_dir, f"analysis_{safe_title}_{timestamp}.md")
                                with open(filename, 'w', encoding='utf-8') as f:
                                    f.write(f"# Analysis Result: {res['title']}\n\n")
                                    f.write(f"Date: {res['date']}\n")
                                    f.write(f"Template: {res['template']}\n\n")
                                    f.write(res['analysis'])
                                print(f"✅ 파일 저장 완료: {filename}")
                                saved_count += 1
                            except Exception as e:
                                print(f"❌ '{res['title']}' 저장 실패: {e}")
                        print(f"\n💾 총 {saved_count}개의 파일이 저장되었습니다.")
                        
            elif mode == "2":
                # 종합 분석
                # 원본 회의 데이터가 필요함 (parsed_result['meetings']에 있음)
                original_meetings = parsed_result.get('meetings', [])
                if not original_meetings:
                    print("❌ 원본 회의 데이터를 찾을 수 없어 종합 분석을 수행할 수 없습니다.")
                    continue
                    
                # 필터링된 회의만 추출 (parsed_meetings에 있는 ID와 일치하는 것만)
                target_ids = set(m['id'] for m in parsed_meetings)
                target_meetings = [m for m in original_meetings if str(m.get('_id', '')) in target_ids]
                
                if not target_meetings:
                    print("❌ 분석 대상 회의를 찾을 수 없습니다.")
                    continue
                
                result = analyzer.analyze_aggregated_meetings(
                    target_meetings, 
                    template_name=selected_template,
                    custom_instructions=full_instructions,
                    version=selected_version
                )
                
                if result and result['status'] == 'success':
                    print("\n" + "="*60)
                    print(f"📊 종합 분석 결과 ({len(target_meetings)}개 회의)")
                    print("=" * 60)
                    print(result['analysis'])
                    print("=" * 60)
                    
                    # 결과 저장 옵션
                    if _ask_save_option("종합 분석 결과를 파일로 저장하시겠습니까?"):
                        try:
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        
                            # Output 디렉토리 생성
                            output_dir = os.path.join(os.getcwd(), "output")
                            os.makedirs(output_dir, exist_ok=True)
                            
                            filename = os.path.join(output_dir, f"aggregated_analysis_{selected_template}_{timestamp}.md")
                            with open(filename, 'w', encoding='utf-8') as f:
                                f.write(f"# Aggregated Analysis Result\n\n")
                                f.write(f"Date Range: {result.get('date_range', {}).get('start')} ~ {result.get('date_range', {}).get('end')}\n")
                                f.write(f"Meeting Count: {result.get('meeting_count')}\n")
                                f.write(f"Template: {selected_template}\n\n")
                                
                                # 회의 목록 추가
                                f.write("## Analyzed Meetings\n\n")
                                f.write("| Date | Title | Participants |\n")
                                f.write("|---|---|---|\n")
                                for m in target_meetings:
                                    date = m.get('date', 'Unknown')
                                    if hasattr(date, 'strftime'):
                                        date = date.strftime('%Y-%m-%d')
                                    title = m.get('title', 'Untitled')
                                    participants = ", ".join(m.get('participants', []))
                                    f.write(f"| {date} | {title} | {participants} |\n")
                                f.write("\n")
                                
                                f.write(result['analysis'])
                            print(f"✅ 파일 저장 완료: {filename}")
                        except Exception as e:
                            print(f"❌ 파일 저장 실패: {e}")
                else:
                    error_msg = result.get('error') if result else "Unknown error"
                    print(f"❌ 종합 분석 실패: {error_msg}")
            
            # 분석 후 종료 (또는 계속 하시겠습니까? 물어볼 수도 있음)
            if not _ask_save_option("다른 분석을 계속 하시겠습니까?"):
                break
                
        except Exception as e:
            print(f"❌ 오류 발생: {str(e)}")
            import traceback
            traceback.print_exc()


def main():
    """
    메인 함수 - 대화형 인터페이스
    """
    print("🚀 MongoDB Transcript 파싱 및 분석 유틸리티")
    
    # 분석기 초기화
    print(f"\n🔌 MongoDB 연결 중...")
    try:
        analyzer = _get_analyzer()
        print(f"   Database: {analyzer.db.name}")
        print(f"   Collection: {analyzer.collection.name}")
    except Exception as e:
        print(f"❌ 오류 발생: {str(e)}")
        return

    while True:
        print("\n" + "="*50)
        print("분석 옵션을 선택하세요:")
        print("  1️⃣  모든 회의 transcript 분석")
        print("  2️⃣  필터를 사용한 분석 (날짜, 제목, 참여자 등)")
        print("  3️⃣  개별 회의 선택")
        print("  0️⃣  종료")
        print("="*50)
        
        try:
            choice = input("\n선택 (1, 2, 3, 0): ").strip()
        except (EOFError, KeyboardInterrupt):
            choice = '0'
        
        if choice == '0':
            print("\n프로그램을 종료합니다.")
            break
            
        if choice not in ['1', '2', '3']:
            print("잘못된 선택입니다. 다시 선택해주세요.")
            continue
    

    
        try:
            if choice == '2':
                # 필터 구성
                filters, post_filters = build_filters(analyzer)
                
                # 필터 선택이 취소된 경우
                if filters is None and post_filters is None:
                    print("\n⏪ 필터 선택이 취소되었습니다. 메인 메뉴로 돌아갑니다.")
                    continue
                
                # Output 디렉토리 설정
                output_dir = os.path.join(os.getcwd(), "output")
                os.makedirs(output_dir, exist_ok=True)
                
                # 필터를 사용한 분석
                result = test_with_filters(
                    analyzer=analyzer,
                    filters=filters,
                    post_filters=post_filters,
                    output_dir=output_dir
                )
            elif choice == '3':
                # 개별 회의 선택
                selected_meeting = _select_individual_meeting(analyzer)
                
                if selected_meeting is None:
                    print("\n⏪ 회의 선택이 취소되었습니다. 메인 메뉴로 돌아갑니다.")
                    continue
                
                # 선택된 회의를 파싱
                # Support both Google Drive schema (content) and standard schema (transcript)
                transcript = selected_meeting.get('transcript') or selected_meeting.get('content', '')
                if not transcript:
                    print("❌ 선택된 회의에 transcript가 없습니다.")
                    continue
                
                print(f"\n🔄 회의 파싱 중...")
                parsed_transcript = analyzer.parse_transcript(transcript)
                
                if not parsed_transcript:
                    print("❌ 파싱 실패: transcript를 파싱할 수 없습니다.")
                    continue
                
                # 참여자 통계 계산
                participant_stats = analyzer.extract_participant_stats(parsed_transcript)
                
                # 파싱 결과 구성 (support both schemas)
                parsed_meeting = {
                    'id': str(selected_meeting.get('_id', '')),
                    'title': selected_meeting.get('title') or selected_meeting.get('name', 'Untitled'),
                    'date': selected_meeting.get('date') or selected_meeting.get('createdTime', 'Unknown'),
                    'participants': list(participant_stats.keys()),
                    'parsed_transcript': parsed_transcript,
                    'participant_stats': participant_stats
                }
                
                result = {
                    'meetings': [selected_meeting],
                    'parsed_meetings': [parsed_meeting],
                    'total_count': 1,
                    'parsed_count': 1,
                    'failed_count': 0
                }
                
                # 대화형 분석 실행 (개별 회의이므로 모드 선택 스킵)
                _interactive_analysis(analyzer, result, skip_mode_selection=True)
                
                # 저장 옵션은 스킵 (개별 회의는 저장 불필요)
                print("\n✅ 분석 완료!")
                
            else:
                # Output 디렉토리 설정
                output_dir = os.path.join(os.getcwd(), "output")
                os.makedirs(output_dir, exist_ok=True)
                
                # 모든 회의 분석
                result = test_all_transcripts(analyzer=analyzer, output_dir=output_dir)
            
            # 파싱 결과에 대해 대화형 분석 실행
            if result and result.get('parsed_meetings'):
                _interactive_analysis(analyzer, result)
            
            # 파싱 완료 후 저장 여부 물어보기
            if result and result.get('parsed_meetings'):
                if _ask_save_option("💾 파싱 결과를 JSON 파일로 저장하시겠습니까?"):
                    _save_parsed_results(result, output_dir=output_dir)
            
            if result and result.get('meetings'):
                if _ask_save_option("💾 원본 쿼리 결과(원본 회의 데이터)를 JSON 파일로 저장하시겠습니까?"):
                    _save_original_meetings(result, output_dir=output_dir)
            
            print("\n✅ 테스트 완료!")
            
        except Exception as e:
            print(f"\n❌ 오류 발생: {str(e)}")
            import traceback
            traceback.print_exc()
        
    analyzer.close()


if __name__ == "__main__":
    # .env 파일 확인
    env_file = ".env"
    if not os.path.exists(env_file):
        print(f"⚠️  경고: {env_file} 파일을 찾을 수 없습니다.")
        print(f"   {env_file}.example을 참고하여 {env_file} 파일을 생성해주세요.")
    
    # 환경 변수 확인
    if not os.getenv('GEMINI_API_KEY'):
        print("\n⚠️  경고: GEMINI_API_KEY 환경 변수가 설정되지 않았습니다.")
        print("   .env 파일에 다음을 추가해주세요:")
        print("   GEMINI_API_KEY=your-gemini-api-key-here")
    else:
        main()
