"""
parsing_failed.json 파일에 있는 ID를 이용하여
shared.recordings 컬렉션의 실패한 회의 데이터를 shared.failed_recordings로 이동하는 스크립트
"""

import os
import sys
import json
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv

# 프로젝트 루트를 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# .env 파일에서 환경 변수 로드
load_dotenv()


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


def move_failed_recordings(failed_ids, dry_run=True):
    """
    실패한 회의 데이터를 shared.recordings에서 shared.failed_recordings로 이동
    
    Args:
        failed_ids: 이동할 회의 ID 리스트
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
        
        if dry_run:
            print(f"\n📋 DRY RUN 결과:")
            print(f"   - 이동할 문서 수: {found_count}개")
            print(f"   - 대상 컬렉션: shared.failed_recordings")
            print(f"\n💡 실제 이동을 수행하려면 dry_run=False로 실행하세요.")
        else:
            # 실제 이동 수행
            print(f"\n🔄 문서 이동 중...")
            
            # 대상 컬렉션에 문서 삽입
            if found_count > 0:
                result = target_collection.insert_many(documents)
                print(f"✅ {len(result.inserted_ids)}개의 문서를 shared.failed_recordings에 삽입했습니다.")
                
                # 소스 컬렉션에서 문서 삭제
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
    
    # parsing_failed.json에서 ID 로드
    failed_ids = load_failed_ids()
    
    if not failed_ids:
        print("\n⚠️  이동할 ID가 없습니다.")
        return
    
    # 사용자 확인
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
    move_failed_recordings(failed_ids, dry_run=dry_run)


if __name__ == "__main__":
    # .env 파일 확인
    env_file = ".env"
    if not os.path.exists(env_file):
        print(f"⚠️  경고: {env_file} 파일을 찾을 수 없습니다.")
        print(f"   {env_file}.example을 참고하여 {env_file} 파일을 생성해주세요.")
    
    main()

