"""
parsing_failed.json 파일에 있는 ID를 이용하여
또는 MongoDB에서 직접 실패한 회의를 찾아서
shared.recordings 컬렉션의 실패한 회의 데이터를 shared.failed_recordings로 이동하는 스크립트
"""

import os
import sys
import json
import re
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv

# 프로젝트 루트를 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# .env 파일에서 환경 변수 로드
load_dotenv()


def is_failed_transcript(transcript_text):
    """
    Transcript가 실패한 회의인지 판단
    
    Args:
        transcript_text: Transcript 내용 문자열
    
    Returns:
        (is_failed, failure_reason) 튜플
    """
    if not transcript_text:
        return True, "Transcript가 없습니다"
    
    transcript = transcript_text.strip()
    transcript_lower = transcript.lower()
    
    # 실제 발언 패턴이 있는지 확인 (나중에 사용)
    import re
    # 패턴 1: [00:00:00] 발언자: 내용
    speaker_pattern1 = re.compile(r'\[\d{2}:\d{2}:\d{2}\]\s+[가-힣a-zA-Z\s]{2,}:\s+', re.MULTILINE)
    # 패턴 2: [00:00] 발언자: 내용
    speaker_pattern2 = re.compile(r'\[\d{2}:\d{2}\]\s+[가-힣a-zA-Z\s]{2,}:\s+', re.MULTILINE)
    # 패턴 3: 00:00:00\n\n발언자: 내용 (대괄호 없는 형식)
    speaker_pattern3 = re.compile(r'\d{2}:\d{2}:\d{2}\s*\n\s*\n\s*[A-Za-z가-힣]+\s+[A-Za-z가-힣]+:', re.MULTILINE)
    # 패턴 4: 00:00:00\n발언자: 내용 (한 줄 건너뛰기)
    speaker_pattern4 = re.compile(r'\d{2}:\d{2}:\d{2}\s*\n\s*[A-Za-z가-힣]+\s+[A-Za-z가-힣]+:', re.MULTILINE)
    # 패턴 5: 발언자: 내용 (타임스탬프 근처에 있는 경우)
    # 타임스탬프 다음에 나오는 발언 패턴
    speaker_pattern5 = re.compile(r'\d{2}:\d{2}:\d{2}.*?[A-Za-z가-힣]+\s+[A-Za-z가-힣]+:\s+', re.MULTILINE | re.DOTALL)
    
    has_speaker_statements = bool(
        speaker_pattern1.search(transcript) or 
        speaker_pattern2.search(transcript) or
        speaker_pattern3.search(transcript) or
        speaker_pattern4.search(transcript) or
        speaker_pattern5.search(transcript)
    )
    
    # 모든 실패 조건을 동등하게 체크 (OR 조건)
    failure_reasons = []
    
    # Summary가 생성되었는지 확인 (정상 문서 판단 기준)
    has_summary = (
        'Summary' in transcript and 
        'summary wasn\'t produced' not in transcript_lower and
        '요약이 생성되지 않았' not in transcript
    )
    
    # Transcription ended after 시간 추출 (초 단위)
    transcription_duration_seconds = None
    transcription_match = re.search(r'transcription ended after (\d{2}):(\d{2}):(\d{2})', transcript_lower)
    if transcription_match:
        hours = int(transcription_match.group(1))
        minutes = int(transcription_match.group(2))
        seconds = int(transcription_match.group(3))
        transcription_duration_seconds = hours * 3600 + minutes * 60 + seconds
    
    # 1. "A summary wasn't produced" 또는 "요약이 생성되지 않았습니다" 메시지가 있는 경우
    # 실제 발언이 없거나, 발언이 있어도 매우 짧은 경우만 실패
    if ("a summary wasn't produced" in transcript_lower or 
        "summary wasn't produced" in transcript_lower or
        "요약이 생성되지 않았습니다" in transcript or
        "요약이 생성되지 않았" in transcript):
        # 실제 발언이 없거나, Transcription이 5분 미만이면 실패
        if not has_speaker_statements:
            failure_reasons.append("요약이 생성되지 않음 (A summary wasn't produced)")
        elif transcription_duration_seconds and transcription_duration_seconds < 300:  # 5분 미만
            failure_reasons.append("요약이 생성되지 않음 (A summary wasn't produced)")
    
    # 2. "wasn't enough conversation" 또는 "충분하지 않" 메시지가 있는 경우
    if ("wasn't enough conversation" in transcript_lower or 
        "wasn't enough conversation in a supported language" in transcript_lower or
        "대화가 요약을 생성하기에 충분하지 않" in transcript or
        "요약을 생성하기에 충분하지 않" in transcript or
        "충분하지 않" in transcript):
        if not has_speaker_statements:
            failure_reasons.append("충분한 대화 내용이 없음 (실제 내용 없음)")
    
    # 3. "Transcription ended after" 메시지가 있고 실제 발언이 없는 경우
    if 'transcription ended after' in transcript_lower and not has_speaker_statements:
        failure_reasons.append("Transcription ended 메시지만 있음 (실제 내용 없음)")
    
    # 4. "Transcription ended after" 메시지가 있고 매우 짧은 시간(5분 미만)인 경우
    # 단, Summary가 생성되어 있으면 정상 문서로 판단
    if (transcription_duration_seconds and 
        transcription_duration_seconds < 300 and 
        not has_summary and 
        not has_speaker_statements):  # 5분 미만 + Summary 없음 + 발언 없음
        failure_reasons.append("Transcription ended 메시지만 있음 (실제 내용 없음)")
    
    # 5. "후 스크립트 작성이 종료되었습니다" 메시지가 있는 경우
    if '후 스크립트 작성이 종료되었습니다' in transcript:
        # 실제 발언이 없거나, 실제 발언이 있어도 길이가 짧으면 실패
        if not has_speaker_statements:
            failure_reasons.append("후 스크립트 작성 종료 메시지만 있음 (실제 내용 없음)")
        elif len(transcript) < 300:
            failure_reasons.append("후 스크립트 작성 종료 메시지만 있음 (실제 내용 없음)")
    
    # 6. Transcript가 너무 짧은 경우
    if len(transcript) < 200:
        failure_reasons.append(f"Transcript가 너무 짧음 ({len(transcript)}자)")
    
    # 7. 타임스탬프/발언자 구분자 없음
    if not any(char in transcript for char in [':', '[', ']']):
        failure_reasons.append("타임스탬프/발언자 구분자 없음")
    
    # 어떤 조건이라도 만족하면 실패
    if failure_reasons:
        # 첫 번째 발견된 실패 이유 반환 (모두 동등하므로 어떤 것이든 상관없음)
        return True, failure_reasons[0]
    
    return False, None


def find_failed_recordings_from_db(dry_run=True):
    """
    MongoDB에서 직접 실패한 회의를 찾아서 읽어옴
    
    Args:
        dry_run: True이면 실제 이동하지 않고 정보만 표시
    
    Returns:
        실패한 회의 문서 리스트
    """
    # MongoDB 연결 설정
    MONGODB_HOST = os.getenv('MONGODB_HOST', 'localhost')
    MONGODB_PORT = int(os.getenv('MONGODB_PORT', '27017'))
    MONGODB_USERNAME = os.getenv('MONGODB_USERNAME')
    MONGODB_PASSWORD = os.getenv('MONGODB_PASSWORD')
    MONGODB_AUTH_DATABASE = os.getenv('MONGODB_AUTH_DATABASE')
    MONGODB_URI = os.getenv('MONGODB_URI')
    
    # MongoDB URI 생성
    if MONGODB_URI:
        connection_uri = MONGODB_URI
    else:
        if MONGODB_USERNAME and MONGODB_PASSWORD:
            from urllib.parse import quote_plus
            encoded_username = quote_plus(MONGODB_USERNAME)
            encoded_password = quote_plus(MONGODB_PASSWORD)
            if MONGODB_AUTH_DATABASE is None:
                MONGODB_AUTH_DATABASE = os.getenv('MONGODB_AUTH_DATABASE', 'admin')
            connection_uri = f"mongodb://{encoded_username}:{encoded_password}@{MONGODB_HOST}:{MONGODB_PORT}/?authSource={MONGODB_AUTH_DATABASE}"
        else:
            connection_uri = f"mongodb://{MONGODB_HOST}:{MONGODB_PORT}/"
    
    # MongoDB 연결
    print(f"\n🔌 MongoDB 연결 중...")
    client = MongoClient(connection_uri)
    
    try:
        db = client['shared']
        source_collection = db['recordings']
        
        print(f"   소스 컬렉션: shared.recordings")
        print(f"\n📊 실패한 회의를 검색 중...")
        
        # 모든 문서 가져오기 (또는 배치로 처리)
        total_count = source_collection.count_documents({})
        print(f"   전체 문서 수: {total_count}개")
        
        failed_documents = []
        checked_count = 0
        failure_reason_stats = {}  # 실패 이유별 통계
        
        # 배치로 문서 읽기
        batch_size = 100
        for skip in range(0, total_count, batch_size):
            documents = list(source_collection.find({}).skip(skip).limit(batch_size))
            
            for doc in documents:
                checked_count += 1
                
                # progress 표시
                if checked_count % 50 == 0:
                    print(f"   검사 중... {checked_count}/{total_count} ({checked_count*100//total_count}%)")
                
                # transcript/content 필드 가져오기
                transcript = doc.get('transcript') or doc.get('content', '')
                
                # 실패 여부 확인
                is_failed, failure_reason = is_failed_transcript(transcript)
                
                if is_failed:
                    failed_documents.append({
                        'document': doc,
                        'failure_reason': failure_reason
                    })
                    # 실패 이유별 통계
                    if failure_reason not in failure_reason_stats:
                        failure_reason_stats[failure_reason] = 0
                    failure_reason_stats[failure_reason] += 1
        
        print(f"\n✅ 검색 완료!")
        print(f"   검사한 문서 수: {checked_count}개")
        print(f"   실패한 회의 수: {len(failed_documents)}개")
        
        # 실패 이유별 통계 출력
        if failure_reason_stats:
            print(f"\n📊 실패 이유별 통계:")
            for reason, count in sorted(failure_reason_stats.items(), key=lambda x: x[1], reverse=True):
                print(f"   {count}개: {reason}")
        
        if failed_documents:
            print(f"\n📋 실패한 회의 상세 목록:")
            print("=" * 80)
            
            for i, item in enumerate(failed_documents, 1):
                doc = item['document']
                meeting_id = str(doc.get('_id', ''))
                title = doc.get('title') or doc.get('name', 'Untitled')
                date = doc.get('date') or doc.get('createdTime', 'N/A')
                reason = item['failure_reason']
                
                # 날짜 포맷팅
                if hasattr(date, 'strftime'):
                    date_str = date.strftime('%Y-%m-%d %H:%M:%S')
                elif isinstance(date, str):
                    date_str = date[:19] if len(date) >= 19 else date
                else:
                    date_str = str(date)
                
                # Transcript 정보
                transcript = doc.get('transcript') or doc.get('content', '')
                transcript_length = len(transcript) if transcript else 0
                
                print(f"\n{i}. 문서 ID: {meeting_id}")
                print(f"   제목: {title}")
                print(f"   날짜: {date_str}")
                print(f"   Transcript 길이: {transcript_length}자")
                print(f"   실패 이유: {reason}")
                
                # Transcript 미리보기 (처음 200자)
                if transcript:
                    preview = transcript[:200].replace('\n', ' ').strip()
                    if len(transcript) > 200:
                        preview += "..."
                    print(f"   Transcript 미리보기: {preview}")
                
                if i < len(failed_documents):
                    print("-" * 80)
            
            print("=" * 80)
        
        # 문서와 실패 정보를 함께 반환할 수 있도록 리스트 반환
        # (실패 정보는 별도로 전달할 예정)
        return failed_documents  # {'document': doc, 'failure_reason': reason} 형태로 반환
        
    except Exception as e:
        print(f"\n❌ 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()
        return []
    
    finally:
        client.close()
        print("\n🔒 MongoDB 연결을 종료했습니다.")


def load_failed_ids():
    """
    parsing_failed.json 파일에서 실패한 회의 ID 목록을 로드
    
    Returns:
        실패한 회의 ID 리스트
    """
    # parsing_failed.json은 utils 디렉토리에 있음
    script_dir = os.path.dirname(os.path.abspath(__file__))
    json_file = os.path.join(script_dir, "parsing_failed.json")
    
    if not os.path.exists(json_file):
        print(f"❌ 파일을 찾을 수 없습니다: {json_file}")
        return []
    
    print(f"📂 {json_file} 파일 읽는 중...")
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    failed_meetings = data.get('failed_meetings', [])
    failed_ids = [meeting.get('id') for meeting in failed_meetings if meeting.get('id')]
    
    print(f"✅ {len(failed_ids)}개의 실패한 회의 ID를 로드했습니다.")
    return failed_ids


def move_failed_recordings(failed_ids=None, failed_documents=None, failure_info=None, dry_run=True):
    """
    실패한 회의 데이터를 shared.recordings에서 shared.failed_recordings로 이동
    
    Args:
        failed_ids: 이동할 회의 ID 리스트 (선택사항)
        failed_documents: 이동할 회의 문서 리스트 (선택사항, ID보다 우선)
        failure_info: 문서별 실패 정보 딕셔너리 {doc_id: failure_reason} (선택사항)
        dry_run: True이면 실제 이동하지 않고 시뮬레이션만 수행
    """
    # MongoDB 연결 설정
    MONGODB_HOST = os.getenv('MONGODB_HOST', 'localhost')
    MONGODB_PORT = int(os.getenv('MONGODB_PORT', '27017'))
    MONGODB_USERNAME = os.getenv('MONGODB_USERNAME')
    MONGODB_PASSWORD = os.getenv('MONGODB_PASSWORD')
    MONGODB_AUTH_DATABASE = os.getenv('MONGODB_AUTH_DATABASE')
    MONGODB_URI = os.getenv('MONGODB_URI')
    
    # MongoDB URI 생성
    if MONGODB_URI:
        connection_uri = MONGODB_URI
    else:
        if MONGODB_USERNAME and MONGODB_PASSWORD:
            from urllib.parse import quote_plus
            encoded_username = quote_plus(MONGODB_USERNAME)
            encoded_password = quote_plus(MONGODB_PASSWORD)
            if MONGODB_AUTH_DATABASE is None:
                MONGODB_AUTH_DATABASE = os.getenv('MONGODB_AUTH_DATABASE', 'admin')
            connection_uri = f"mongodb://{encoded_username}:{encoded_password}@{MONGODB_HOST}:{MONGODB_PORT}/?authSource={MONGODB_AUTH_DATABASE}"
        else:
            connection_uri = f"mongodb://{MONGODB_HOST}:{MONGODB_PORT}/"
    
    # MongoDB 연결
    print(f"\n🔌 MongoDB 연결 중...")
    client = MongoClient(connection_uri)
    
    try:
        db = client['shared']
        source_collection = db['recordings']
        target_collection = db['failed_recordings']
        
        print(f"   소스 컬렉션: shared.recordings")
        print(f"   대상 컬렉션: shared.failed_recordings")
        
        if dry_run:
            print(f"\n⚠️  DRY RUN 모드: 실제 이동하지 않고 시뮬레이션만 수행합니다.")
        else:
            print(f"\n⚠️  실제 이동 모드: 데이터가 실제로 이동됩니다!")
        
        # query 초기화 (나중에 사용)
        query = None
        
        # 문서가 직접 제공된 경우
        if failed_documents:
            documents = failed_documents
            found_count = len(documents)
            print(f"\n📊 {found_count}개의 문서를 처리합니다.")
            
            if found_count == 0:
                print("\n⚠️  이동할 문서가 없습니다.")
                return
            
            # 삭제용 query 준비
            doc_ids = [doc['_id'] for doc in documents]
            query = {'_id': {'$in': doc_ids}}
            
            # failure_info가 제공되지 않은 경우 빈 딕셔너리로 초기화
            if failure_info is None:
                failure_info = {}
        
        # ID 리스트가 제공된 경우
        elif failed_ids:
            # ObjectId로 변환 (문자열 ID를 ObjectId로)
            object_ids = []
            invalid_ids = []
            
            for id_str in failed_ids:
                try:
                    # ObjectId로 변환 시도
                    if isinstance(id_str, str) and len(id_str) == 24:
                        object_ids.append(ObjectId(id_str))
                    else:
                        invalid_ids.append(id_str)
                except Exception as e:
                    invalid_ids.append(id_str)
            
            if invalid_ids:
                print(f"\n⚠️  {len(invalid_ids)}개의 유효하지 않은 ID를 건너뜁니다.")
                for invalid_id in invalid_ids[:5]:  # 처음 5개만 표시
                    print(f"   - {invalid_id}")
                if len(invalid_ids) > 5:
                    print(f"   ... 외 {len(invalid_ids) - 5}개")
            
            if not object_ids:
                print("\n❌ 이동할 유효한 ID가 없습니다.")
                return
            
            print(f"\n📊 {len(object_ids)}개의 문서를 찾는 중...")
            
            # 소스 컬렉션에서 문서 찾기
            query = {'_id': {'$in': object_ids}}
            documents = list(source_collection.find(query))
            
            found_count = len(documents)
            print(f"✅ {found_count}개의 문서를 찾았습니다.")
            
            if found_count == 0:
                print("\n⚠️  찾은 문서가 없습니다. ID가 올바른지 확인해주세요.")
                return
            
            # 찾지 못한 ID 확인
            found_ids = {str(doc['_id']) for doc in documents}
            not_found_ids = [str(oid) for oid in object_ids if str(oid) not in found_ids]
            
            if not_found_ids:
                print(f"\n⚠️  {len(not_found_ids)}개의 문서를 찾지 못했습니다:")
                for missing_id in not_found_ids[:5]:
                    print(f"   - {missing_id}")
                if len(not_found_ids) > 5:
                    print(f"   ... 외 {len(not_found_ids) - 5}개")
        
        else:
            print("\n❌ 이동할 ID나 문서가 제공되지 않았습니다.")
            return
        
        if dry_run:
            print(f"\n📋 DRY RUN 결과:")
            print(f"   - 이동할 문서 수: {found_count}개")
            print(f"   - 대상 컬렉션: shared.failed_recordings")
            
            # 문서 정보 상세 출력
            if documents:
                print(f"\n📋 이동할 문서 상세 정보:")
                print("=" * 80)
                
                for i, doc in enumerate(documents, 1):
                    doc_id = str(doc.get('_id', ''))
                    title = doc.get('title') or doc.get('name', 'Untitled')
                    date = doc.get('date') or doc.get('createdTime', 'N/A')
                    
                    # 날짜 포맷팅
                    if hasattr(date, 'strftime'):
                        date_str = date.strftime('%Y-%m-%d %H:%M:%S')
                    elif isinstance(date, str):
                        date_str = date[:19] if len(date) >= 19 else date
                    else:
                        date_str = str(date)
                    
                    # Transcript 정보
                    transcript = doc.get('transcript') or doc.get('content', '')
                    transcript_length = len(transcript) if transcript else 0
                    
                    # 실패 이유 확인 (이미 알려진 경우 또는 다시 확인)
                    failure_reason = None
                    if failure_info and doc_id in failure_info:
                        failure_reason = failure_info[doc_id]
                    elif transcript:
                        is_failed, reason = is_failed_transcript(transcript)
                        if is_failed:
                            failure_reason = reason
                    
                    print(f"\n{i}. 문서 ID: {doc_id}")
                    print(f"   제목: {title}")
                    print(f"   날짜: {date_str}")
                    print(f"   Transcript 길이: {transcript_length}자")
                    
                    if failure_reason:
                        print(f"   실패 이유: {failure_reason}")
                    
                    # Transcript 미리보기 (처음 200자)
                    if transcript:
                        preview = transcript[:200].replace('\n', ' ').strip()
                        if len(transcript) > 200:
                            preview += "..."
                        print(f"   Transcript 미리보기: {preview}")
                    
                    # 기타 필드
                    if i < len(documents):
                        print("-" * 80)
                
                print("=" * 80)
            
            print(f"\n💡 실제 이동을 수행하려면 dry_run=False로 실행하세요.")
        else:
            # 실제 이동 수행
            print(f"\n🔄 문서 이동 중...")
            
            # 대상 컬렉션에 문서 삽입
            if found_count > 0:
                result = target_collection.insert_many(documents)
                print(f"✅ {len(result.inserted_ids)}개의 문서를 shared.failed_recordings에 삽입했습니다.")
                
                # 소스 컬렉션에서 문서 삭제 (query는 이미 위에서 정의됨)
                delete_result = source_collection.delete_many(query)
                print(f"✅ {delete_result.deleted_count}개의 문서를 shared.recordings에서 삭제했습니다.")
                
                print(f"\n✅ 이동 완료!")
                print(f"   - 이동된 문서 수: {delete_result.deleted_count}개")
                print(f"   - 소스 컬렉션 (shared.recordings)에 남은 문서 수: {source_collection.count_documents({})}개")
                print(f"   - 대상 컬렉션 (shared.failed_recordings)의 문서 수: {target_collection.count_documents({})}개")
            else:
                print("⚠️  이동할 문서가 없습니다.")
        
    except Exception as e:
        print(f"\n❌ 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        client.close()
        print("\n🔒 MongoDB 연결을 종료했습니다.")


def main():
    """
    메인 함수
    """
    print("="*80)
    print("📦 실패한 회의 데이터 이동 스크립트")
    print("="*80)
    
    # 모드 선택
    print("\n모드를 선택하세요:")
    print("  1. parsing_failed.json 파일에서 ID 읽기")
    print("  2. MongoDB에서 직접 실패한 회의 찾기")
    
    try:
        mode = input("\n모드 선택 (1 또는 2, 기본값: 2): ").strip()
        if not mode:
            mode = '2'
    except (EOFError, KeyboardInterrupt):
        mode = '2'
        print("\n기본값(2)을 사용합니다.")
    
    failed_ids = None
    failed_documents = None
    
    if mode == '1':
        # parsing_failed.json에서 ID 로드
        failed_ids = load_failed_ids()
        
        if not failed_ids:
            print("\n⚠️  이동할 ID가 없습니다.")
            return
        
        print(f"\n⚠️  주의: {len(failed_ids)}개의 문서를 shared.recordings에서 shared.failed_recordings로 이동합니다.")
        print("   이 작업은 되돌릴 수 없습니다!")
        
        try:
            choice = input("\n계속하시겠습니까? (dry-run: d, 실제 이동: y, 취소: n, 기본값: d): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            choice = 'd'
            print("\n기본값(dry-run)을 사용합니다.")
        
        if choice == 'y' or choice == 'yes':
            dry_run = False
            print("\n⚠️  실제 이동 모드로 실행합니다!")
        elif choice == 'n' or choice == 'no':
            print("\n취소되었습니다.")
            return
        else:
            dry_run = True
            print("\nDRY RUN 모드로 실행합니다.")
        
        # 이동 수행
        move_failed_recordings(failed_ids=failed_ids, dry_run=dry_run)
    
    else:  # mode == '2'
        print("\n📊 MongoDB에서 직접 실패한 회의를 검색합니다...")
        
        # MongoDB에서 직접 실패한 회의 찾기
        failed_items = find_failed_recordings_from_db(dry_run=True)
        
        if not failed_items:
            print("\n⚠️  실패한 회의를 찾지 못했습니다.")
            return
        
        print(f"\n✅ 찾은 실패한 회의: {len(failed_items)}개")
        
        # 실행 모드 선택
        print("\n실행 모드를 선택하세요:")
        print("  d. DRY RUN (시뮬레이션만, 기본값)")
        print("  y. 실제 이동 (데이터가 실제로 이동됩니다)")
        print("  n. 취소")
        
        try:
            choice = input("\n모드 선택 (d/y/n, 기본값: d): ").strip().lower()
            if not choice:
                choice = 'd'
        except (EOFError, KeyboardInterrupt):
            choice = 'd'
            print("\n기본값(dry-run)을 사용합니다.")
        
        if choice == 'n' or choice == 'no':
            print("\n취소되었습니다.")
            return
        elif choice == 'y' or choice == 'yes':
            dry_run = False
            print(f"\n⚠️  실제 이동 모드로 실행합니다!")
            print(f"   {len(failed_items)}개의 문서가 실제로 이동됩니다!")
        else:
            dry_run = True
            print("\n📋 DRY RUN 모드로 실행합니다.")
        
        # 실패 정보 딕셔너리 생성
        failure_info = {}
        documents_list = []
        for item in failed_items:
            doc = item['document']
            doc_id = str(doc.get('_id', ''))
            failure_info[doc_id] = item['failure_reason']
            documents_list.append(doc)
        
        # 이동 수행 (dry-run 또는 실제 이동)
        move_failed_recordings(failed_documents=documents_list, failure_info=failure_info, dry_run=dry_run)


if __name__ == "__main__":
    # .env 파일 확인
    env_file = ".env"
    if not os.path.exists(env_file):
        print(f"⚠️  경고: {env_file} 파일을 찾을 수 없습니다.")
        print(f"   {env_file}.example을 참고하여 {env_file} 파일을 생성해주세요.")
    
    main()

