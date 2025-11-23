"""
MongoDB 컬렉션에서 meeting_id 중복을 찾아 하나만 남기고 나머지를 다른 컬렉션으로 이동
"""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv
from pymongo import MongoClient
from collections import defaultdict

# 상위 디렉토리를 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# .env 파일에서 환경 변수 로드
load_dotenv()


def get_mongodb_client():
    """
    환경 변수에서 MongoDB 설정을 읽어 클라이언트 생성
    
    Returns:
        MongoClient 인스턴스
    """
    MONGODB_HOST = os.getenv('MONGODB_HOST', 'localhost')
    MONGODB_PORT = int(os.getenv('MONGODB_PORT', '27017'))
    MONGODB_USERNAME = os.getenv('MONGODB_USERNAME')
    MONGODB_PASSWORD = os.getenv('MONGODB_PASSWORD')
    MONGODB_AUTH_DATABASE = os.getenv('MONGODB_AUTH_DATABASE')
    MONGODB_URI = os.getenv('MONGODB_URI')
    
    # URI 생성
    if MONGODB_URI:
        connection_uri = MONGODB_URI
    else:
        if MONGODB_USERNAME and MONGODB_PASSWORD:
            from urllib.parse import quote_plus
            encoded_username = quote_plus(MONGODB_USERNAME)
            encoded_password = quote_plus(MONGODB_PASSWORD)
            auth_db = MONGODB_AUTH_DATABASE or 'admin'
            connection_uri = f"mongodb://{encoded_username}:{encoded_password}@{MONGODB_HOST}:{MONGODB_PORT}/?authSource={auth_db}"
        else:
            connection_uri = f"mongodb://{MONGODB_HOST}:{MONGODB_PORT}/"
    
    return MongoClient(connection_uri)


def find_duplicates(collection, meeting_id_field='meeting_id'):
    """
    컬렉션에서 meeting_id 중복을 찾기
    
    Args:
        collection: MongoDB 컬렉션
        meeting_id_field: meeting_id 필드 이름 (기본값: 'meeting_id')
        
    Returns:
        dict: {meeting_id: [document_ids]} 형태의 중복 정보
    """
    print(f"\n🔍 '{meeting_id_field}' 필드로 중복을 찾는 중...")
    
    # 먼저 컬렉션 통계 확인
    total_count = collection.count_documents({})
    field_exists_count = collection.count_documents({meeting_id_field: {'$exists': True, '$ne': None}})
    
    print(f"   📊 컬렉션 통계:")
    print(f"      - 전체 문서 수: {total_count}개")
    print(f"      - '{meeting_id_field}' 필드가 있는 문서: {field_exists_count}개")
    
    if field_exists_count == 0:
        print(f"\n   ⚠️  '{meeting_id_field}' 필드가 있는 문서가 없습니다.")
        print(f"   💡 샘플 문서의 필드명을 확인합니다...")
        
        # 샘플 문서 확인
        sample = collection.find_one()
        if sample:
            print(f"   📋 샘플 문서의 필드:")
            for key in list(sample.keys())[:10]:  # 처음 10개 필드만
                value = sample[key]
                if isinstance(value, str):
                    value_preview = value[:50] + "..." if len(value) > 50 else value
                else:
                    value_preview = str(value)[:50]
                print(f"      - {key}: {value_preview}")
            
            # 가능한 ID 필드 제안
            possible_id_fields = ['id', 'driveId', '_id', 'meeting_id', 'meetingId']
            found_fields = [f for f in possible_id_fields if f in sample]
            if found_fields:
                print(f"\n   💡 발견된 ID 관련 필드: {', '.join(found_fields)}")
                print(f"   💡 '{meeting_id_field}' 대신 위 필드 중 하나를 사용해보세요.")
        
        return {}
    
    # meeting_id별로 그룹화
    pipeline = [
        {
            '$match': {
                meeting_id_field: {'$exists': True, '$ne': None}
            }
        },
        {
            '$group': {
                '_id': f'${meeting_id_field}',
                'documents': {'$push': '$_id'},
                'count': {'$sum': 1}
            }
        },
        {
            '$match': {
                'count': {'$gt': 1}  # 중복만 찾기
            }
        }
    ]
    
    duplicates = {}
    try:
        cursor = collection.aggregate(pipeline)
        
        for item in cursor:
            meeting_id = item['_id']
            document_ids = item['documents']
            duplicates[meeting_id] = document_ids
            print(f"   ✓ {meeting_id}: {len(document_ids)}개 중복 발견")
    except Exception as e:
        print(f"   ❌ Aggregation 오류: {e}")
        print(f"   💡 필드명이 올바른지 확인해주세요.")
        return {}
    
    return duplicates


def deduplicate_meetings(
    source_database_name,
    source_collection_name,
    target_database_name=None,
    target_collection_name=None,
    meeting_id_field='meeting_id',
    keep_strategy='first',  # 'first', 'last', 'newest', 'oldest'
    dry_run=True
):
    """
    meeting_id 중복을 제거하고 중복 문서를 다른 컬렉션으로 이동
    
    Args:
        source_database_name: 소스 데이터베이스 이름
        source_collection_name: 소스 컬렉션 이름
        target_database_name: 대상 데이터베이스 이름 (None이면 소스와 동일)
        target_collection_name: 대상 컬렉션 이름 (None이면 'duplicates_YYYYMMDD' 형식)
        meeting_id_field: meeting_id 필드 이름
        keep_strategy: 유지할 문서 선택 전략 ('first', 'last', 'newest', 'oldest')
        dry_run: True면 실제 이동 없이 시뮬레이션만 수행
        
    Returns:
        dict: 처리 결과 통계
    """
    client = get_mongodb_client()
    
    try:
        # 데이터베이스 및 컬렉션 가져오기
        source_db = client[source_database_name]
        source_collection = source_db[source_collection_name]
        
        if target_database_name is None:
            target_database_name = source_database_name
        target_db = client[target_database_name]
        
        if target_collection_name is None:
            timestamp = datetime.now().strftime("%Y%m%d")
            target_collection_name = f"duplicates_{timestamp}"
        target_collection = target_db[target_collection_name]
        
        print("="*80)
        print("🔄 Meeting ID 중복 제거 및 이동")
        print("="*80)
        print(f"\n소스: {source_database_name}.{source_collection_name}")
        print(f"대상: {target_database_name}.{target_collection_name}")
        print(f"전략: {keep_strategy} (첫 번째/마지막/최신/최旧 문서 유지)")
        print(f"모드: {'🔍 DRY RUN (시뮬레이션)' if dry_run else '💾 실제 실행'}")
        
        # 중복 찾기
        duplicates = find_duplicates(source_collection, meeting_id_field)
        
        if not duplicates:
            print("\n✅ 중복된 meeting_id가 없습니다.")
            return {
                'total_duplicates': 0,
                'total_documents_to_move': 0,
                'moved_documents': 0
            }
        
        print(f"\n📊 총 {len(duplicates)}개의 중복된 meeting_id를 발견했습니다.")
        
        # 각 중복 그룹 처리
        total_to_move = 0
        documents_to_move = []
        documents_to_keep = []
        
        for meeting_id, doc_ids in duplicates.items():
            # 문서들 가져오기
            docs = list(source_collection.find({'_id': {'$in': doc_ids}}))
            
            if not docs:
                continue
            
            # 유지할 문서 선택
            if keep_strategy == 'first':
                keep_doc = docs[0]
                move_docs = docs[1:]
            elif keep_strategy == 'last':
                keep_doc = docs[-1]
                move_docs = docs[:-1]
            elif keep_strategy == 'newest':
                # date 또는 createdTime 필드 기준으로 최신 선택
                keep_doc = max(docs, key=lambda d: _get_date(d) or datetime.min)
                move_docs = [d for d in docs if d['_id'] != keep_doc['_id']]
            elif keep_strategy == 'oldest':
                # date 또는 createdTime 필드 기준으로 최旧 선택
                keep_doc = min(docs, key=lambda d: _get_date(d) or datetime.max)
                move_docs = [d for d in docs if d['_id'] != keep_doc['_id']]
            else:
                # 기본값: 첫 번째
                keep_doc = docs[0]
                move_docs = docs[1:]
            
            documents_to_keep.append(keep_doc['_id'])
            documents_to_move.extend(move_docs)
            total_to_move += len(move_docs)
            
            # 제목 가져오기 (meeting_title, title, name 순서로 확인)
            def get_title(doc):
                return doc.get('meeting_title') or doc.get('title') or doc.get('name') or 'N/A'
            
            keep_title = get_title(keep_doc)
            if len(keep_title) > 50:
                keep_title = keep_title[:50] + "..."
            
            print(f"\n   meeting_id: {meeting_id}")
            print(f"      유지: {keep_doc['_id']} (제목: {keep_title})")
            print(f"      이동: {len(move_docs)}개 문서")
            for move_doc in move_docs:
                move_title = get_title(move_doc)
                if len(move_title) > 50:
                    move_title = move_title[:50] + "..."
                print(f"         - {move_doc['_id']} (제목: {move_title})")
        
        print(f"\n📋 요약:")
        print(f"   - 중복된 meeting_id: {len(duplicates)}개")
        print(f"   - 유지할 문서: {len(documents_to_keep)}개")
        print(f"   - 이동할 문서: {total_to_move}개")
        
        if not dry_run:
            # 사용자 확인
            try:
                confirm = input(f"\n⚠️  {total_to_move}개의 문서를 이동하시겠습니까? (yes/no, 기본값: no): ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                confirm = 'no'
                print("\n기본값(no)을 사용합니다.")
            
            if confirm != 'yes':
                print("\n⏪ 작업이 취소되었습니다.")
                return {
                    'total_duplicates': len(duplicates),
                    'total_documents_to_move': total_to_move,
                    'moved_documents': 0,
                    'cancelled': True
                }
            
            # 대상 컬렉션에 문서 삽입
            print(f"\n💾 {target_database_name}.{target_collection_name}에 문서 이동 중...")
            if documents_to_move:
                result = target_collection.insert_many(documents_to_move)
                print(f"   ✓ {len(result.inserted_ids)}개 문서 이동 완료")
            
            # 소스 컬렉션에서 문서 삭제
            print(f"\n🗑️  {source_database_name}.{source_collection_name}에서 중복 문서 삭제 중...")
            delete_result = source_collection.delete_many({'_id': {'$in': [d['_id'] for d in documents_to_move]}})
            print(f"   ✓ {delete_result.deleted_count}개 문서 삭제 완료")
            
            print(f"\n✅ 작업 완료!")
            print(f"   - 이동된 문서: {len(documents_to_move)}개")
            print(f"   - 유지된 문서: {len(documents_to_keep)}개")
            
            return {
                'total_duplicates': len(duplicates),
                'total_documents_to_move': total_to_move,
                'moved_documents': len(documents_to_move),
                'kept_documents': len(documents_to_keep)
            }
        else:
            print(f"\n🔍 DRY RUN 모드: 실제로는 이동하지 않았습니다.")
            return {
                'total_duplicates': len(duplicates),
                'total_documents_to_move': total_to_move,
                'moved_documents': 0,
                'dry_run': True
            }
    
    finally:
        client.close()


def _get_date(doc):
    """
    문서에서 날짜를 추출 (date 또는 createdTime 필드)
    
    Args:
        doc: MongoDB 문서
        
    Returns:
        datetime 객체 또는 None
    """
    # date 필드 확인
    if 'date' in doc and doc['date']:
        if isinstance(doc['date'], datetime):
            return doc['date']
        elif isinstance(doc['date'], str):
            try:
                return datetime.fromisoformat(doc['date'].replace('Z', '+00:00'))
            except:
                pass
    
    # createdTime 필드 확인
    if 'createdTime' in doc and doc['createdTime']:
        if isinstance(doc['createdTime'], datetime):
            return doc['createdTime']
        elif isinstance(doc['createdTime'], str):
            try:
                return datetime.fromisoformat(doc['createdTime'].replace('Z', '+00:00'))
            except:
                pass
    
    return None


def main():
    """
    대화형 메인 함수
    """
    print("🚀 MongoDB Meeting ID 중복 제거 및 이동 유틸리티")
    print("="*80)
    
    # 환경 변수에서 기본값 읽기
    default_database = os.getenv('DATABASE_NAME', 'company_db')
    default_collection = os.getenv('COLLECTION_NAME', 'meeting_transcripts')
    
    # 소스 정보 입력
    print("\n📥 소스 컬렉션 정보:")
    try:
        source_db = input(f"   데이터베이스 이름 (기본값: {default_database}): ").strip() or default_database
        source_collection = input(f"   컬렉션 이름 (기본값: {default_collection}): ").strip() or default_collection
        meeting_id_field = input("   meeting_id 필드 이름 (기본값: meeting_id): ").strip() or 'meeting_id'
    except (EOFError, KeyboardInterrupt):
        print("\n⏪ 작업이 취소되었습니다.")
        return
    
    # 대상 정보 입력
    print("\n📤 대상 컬렉션 정보:")
    try:
        target_db_input = input(f"   데이터베이스 이름 (기본값: {source_db}, Enter로 동일): ").strip()
        target_db = target_db_input if target_db_input else source_db
        
        timestamp = datetime.now().strftime("%Y%m%d")
        default_target_collection = f"duplicates_{timestamp}"
        target_collection_input = input(f"   컬렉션 이름 (기본값: {default_target_collection}): ").strip()
        target_collection = target_collection_input if target_collection_input else default_target_collection
    except (EOFError, KeyboardInterrupt):
        print("\n⏪ 작업이 취소되었습니다.")
        return
    
    # 전략 선택
    print("\n📋 유지할 문서 선택 전략:")
    print("   1. first - 첫 번째 문서 유지")
    print("   2. last - 마지막 문서 유지")
    print("   3. newest - 가장 최신 문서 유지 (date/createdTime 기준)")
    print("   4. oldest - 가장 오래된 문서 유지 (date/createdTime 기준)")
    try:
        strategy_choice = input("   선택 (1-4, 기본값: 1): ").strip() or '1'
        strategy_map = {'1': 'first', '2': 'last', '3': 'newest', '4': 'oldest'}
        keep_strategy = strategy_map.get(strategy_choice, 'first')
    except (EOFError, KeyboardInterrupt):
        keep_strategy = 'first'
        print("\n기본값(first)을 사용합니다.")
    
    # Dry run 여부
    print("\n🔍 실행 모드:")
    try:
        dry_run_choice = input("   Dry run 모드로 실행하시겠습니까? (y/n, 기본값: y): ").strip().lower() or 'y'
        dry_run = dry_run_choice == 'y'
    except (EOFError, KeyboardInterrupt):
        dry_run = True
        print("\n기본값(y)을 사용합니다.")
    
    # 실행
    result = deduplicate_meetings(
        source_database_name=source_db,
        source_collection_name=source_collection,
        target_database_name=target_db if target_db != source_db else None,
        target_collection_name=target_collection,
        meeting_id_field=meeting_id_field,
        keep_strategy=keep_strategy,
        dry_run=dry_run
    )
    
    print(f"\n📊 최종 결과:")
    print(f"   - 중복된 meeting_id: {result.get('total_duplicates', 0)}개")
    print(f"   - 이동할 문서: {result.get('total_documents_to_move', 0)}개")
    if not dry_run:
        print(f"   - 실제 이동된 문서: {result.get('moved_documents', 0)}개")


if __name__ == "__main__":
    # .env 파일 확인
    env_file = ".env"
    if not os.path.exists(env_file):
        print(f"⚠️  경고: {env_file} 파일을 찾을 수 없습니다.")
        print(f"   {env_file}.example을 참고하여 {env_file} 파일을 생성해주세요.")
    
    main()

