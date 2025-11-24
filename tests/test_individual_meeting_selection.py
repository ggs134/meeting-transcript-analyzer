"""
개별 회의 선택 기능 테스트
"""

import sys
import os

# 상위 디렉토리를 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from meeting_performance_analyzer import MeetingPerformanceAnalyzer

# .env 파일 로드
load_dotenv()


def test_individual_meeting_selection():
    """개별 회의 선택 및 파싱 테스트"""
    print("=" * 80)
    print("🧪 개별 회의 선택 기능 테스트")
    print("=" * 80)
    
    # 분석기 초기화
    print("\n🔌 MongoDB 연결 중...")
    try:
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
        
        analyzer = MeetingPerformanceAnalyzer(
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
        
        print(f"   Database: {analyzer.db.name}")
        print(f"   Collection: {analyzer.collection.name}")
    except Exception as e:
        print(f"❌ 연결 실패: {str(e)}")
        return False
    
    # 회의 목록 가져오기
    print("\n📋 회의 목록 가져오는 중...")
    all_meetings = list(analyzer.collection.find())
    
    if not all_meetings:
        print("❌ 회의 데이터가 없습니다.")
        return False
    
    # Sort by date or createdTime (support both schemas)
    all_meetings.sort(key=lambda m: m.get('date') or m.get('createdTime') or '', reverse=True)
    
    print(f"✅ 총 {len(all_meetings)}개의 회의를 찾았습니다.")
    
    # 첫 번째 회의 선택하여 테스트
    print("\n🎯 첫 번째 회의로 테스트 진행...")
    selected_meeting = all_meetings[0]
    
    # 회의 정보 표시
    title = selected_meeting.get('title') or selected_meeting.get('name', 'Untitled')
    date = selected_meeting.get('date') or selected_meeting.get('createdTime', 'Unknown Date')
    if hasattr(date, 'strftime'):
        date = date.strftime('%Y-%m-%d %H:%M')
    
    print(f"\n선택된 회의:")
    print(f"  제목: {title}")
    print(f"  날짜: {date}")
    
    # Transcript 가져오기
    transcript = selected_meeting.get('transcript') or selected_meeting.get('content', '')
    if not transcript:
        print("❌ 선택된 회의에 transcript가 없습니다.")
        return False
    
    print(f"  Transcript 길이: {len(transcript)} 문자")
    
    # 파싱 테스트
    print("\n🔄 회의 파싱 중...")
    try:
        parsed_transcript = analyzer.parse_transcript(transcript)
        
        if not parsed_transcript:
            print("❌ 파싱 실패: 발언이 추출되지 않았습니다.")
            return False
        
        print(f"✅ 파싱 성공: {len(parsed_transcript)}개의 발언 추출")
        
        # 참여자 통계 계산
        print("\n📊 참여자 통계 계산 중...")
        participant_stats = analyzer.extract_participant_stats(parsed_transcript)
        
        print(f"✅ 참여자 통계 계산 완료: {len(participant_stats)}명의 참여자")
        
        # 참여자 정보 표시
        print("\n👥 참여자 목록:")
        for participant, stats in participant_stats.items():
            print(f"  - {participant}: {stats.get('total_statements', 0)}개 발언")
        
        # 파싱 결과 구성
        parsed_meeting = {
            'id': str(selected_meeting.get('_id', '')),
            'title': title,
            'date': date,
            'participants': list(participant_stats.keys()),
            'parsed_transcript': parsed_transcript,
            'participant_stats': participant_stats
        }
        
        print("\n✅ 파싱 결과 구성 완료")
        print(f"  회의 ID: {parsed_meeting['id'][:24]}...")
        print(f"  참여자 수: {len(parsed_meeting['participants'])}")
        print(f"  발언 수: {len(parsed_meeting['parsed_transcript'])}")
        
        return True
        
    except Exception as e:
        print(f"❌ 파싱 중 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        analyzer.close()


if __name__ == "__main__":
    print("\n" + "=" * 80)
    success = test_individual_meeting_selection()
    print("\n" + "=" * 80)
    
    if success:
        print("✅ 테스트 성공!")
        sys.exit(0)
    else:
        print("❌ 테스트 실패!")
        sys.exit(1)
