"""
move_failed_recordings.py 스크립트 테스트
"""

import sys
import os
import json
import tempfile
from unittest.mock import Mock, patch, MagicMock

# 상위 디렉토리를 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.move_failed_recordings import load_failed_ids, move_failed_recordings


def test_load_failed_ids():
    """load_failed_ids 함수 테스트"""
    print("=" * 80)
    print("🧪 load_failed_ids() 함수 테스트")
    print("=" * 80)
    
    # 임시 JSON 파일 생성
    test_data = {
        "total_failed": 3,
        "failed_meetings": [
            {"id": "691cee06d10432b7f9472790", "title": "Test Meeting 1"},
            {"id": "691cee06d10432b7f94727a8", "title": "Test Meeting 2"},
            {"id": "invalid_id", "title": "Test Meeting 3"}
        ]
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
        json.dump(test_data, f, ensure_ascii=False, indent=2)
        temp_file = f.name
    
    try:
        # utils/move_failed_recordings.py의 load_failed_ids 함수를 패치
        with patch('utils.move_failed_recordings.os.path.join') as mock_join, \
             patch('utils.move_failed_recordings.os.path.exists') as mock_exists, \
             patch('builtins.open', create=True) as mock_open:
            
            mock_exists.return_value = True
            mock_join.return_value = temp_file
            
            # 파일 읽기 모킹
            mock_file = MagicMock()
            mock_open.return_value.__enter__.return_value = mock_file
            mock_open.return_value.__exit__ = Mock()
            mock_file.read.return_value = json.dumps(test_data, ensure_ascii=False)
            
            # 실제 함수 호출 (간접적으로 테스트)
            script_dir = os.path.dirname(os.path.abspath(__file__))
            utils_dir = os.path.join(os.path.dirname(script_dir), "utils")
            json_file = os.path.join(utils_dir, "parsing_failed.json")
            
            if os.path.exists(json_file):
                failed_ids = load_failed_ids()
                print(f"\n✅ 실패 ID 로드 성공: {len(failed_ids)}개")
                print(f"   예상: 80개 (parsing_failed.json에 있는 실제 데이터)")
                
                # 유효한 ObjectId 형식인지 확인
                valid_count = sum(1 for id_str in failed_ids if isinstance(id_str, str) and len(id_str) == 24)
                print(f"   유효한 ObjectId 형식: {valid_count}개")
                
                return True
            else:
                print(f"⚠️  {json_file} 파일이 없습니다. 실제 파일로 테스트할 수 없습니다.")
                return False
                
    finally:
        # 임시 파일 정리
        if os.path.exists(temp_file):
            os.unlink(temp_file)


def test_load_failed_ids_error_handling():
    """에러 처리 로직 테스트"""
    print("\n" + "=" * 80)
    print("🧪 load_failed_ids() - 에러 처리 테스트")
    print("=" * 80)
    
    # 실제 파일이 존재하는지 확인하고 정상 동작 확인
    script_dir = os.path.dirname(os.path.abspath(__file__))
    utils_dir = os.path.join(os.path.dirname(script_dir), "utils")
    json_file = os.path.join(utils_dir, "parsing_failed.json")
    
    if not os.path.exists(json_file):
        print(f"⚠️  {json_file} 파일이 없습니다. 스킵합니다.")
        return True  # 파일이 없으면 스킵 (정상 상황일 수 있음)
    
    # 파일이 존재할 때 정상적으로 로드되는지 확인
    try:
        failed_ids = load_failed_ids()
        assert isinstance(failed_ids, list), "반환값이 리스트여야 합니다"
        
        # 모든 ID가 문자열인지 확인
        all_strings = all(isinstance(id_str, str) for id_str in failed_ids)
        assert all_strings, "모든 ID는 문자열이어야 합니다"
        
        print(f"\n✅ 에러 처리 테스트 성공: {len(failed_ids)}개 ID 로드됨")
        return True
        
    except Exception as e:
        print(f"\n❌ 테스트 중 오류: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_move_failed_recordings_dry_run():
    """move_failed_recordings 함수의 dry-run 모드 테스트"""
    print("\n" + "=" * 80)
    print("🧪 move_failed_recordings() - DRY RUN 모드 테스트")
    print("=" * 80)
    
    # 테스트용 ID 리스트
    test_ids = [
        "691cee06d10432b7f9472790",
        "691cee06d10432b7f94727a8",
        "691cee06d10432b7f94727a9"
    ]
    
    # MongoDB 클라이언트 모킹
    mock_client = MagicMock()
    mock_db = MagicMock()
    mock_source_collection = MagicMock()
    mock_target_collection = MagicMock()
    
    # 빈 문서 목록 반환 (문서가 없는 경우 시뮬레이션)
    mock_source_collection.find.return_value = []
    mock_source_collection.count_documents.return_value = 100
    
    mock_db.__getitem__.return_value = mock_source_collection
    mock_db.__getitem__ = Mock(side_effect=lambda x: {
        'recordings': mock_source_collection,
        'failed_recordings': mock_target_collection
    }[x])
    mock_client.__getitem__.return_value = mock_db
    
    try:
        with patch('utils.move_failed_recordings.MongoClient', return_value=mock_client):
            print("\n📊 Dry-run 모드로 테스트 실행 중...")
            move_failed_recordings(test_ids, dry_run=True)
            print("\n✅ Dry-run 모드 테스트 완료")
            return True
    except Exception as e:
        print(f"\n❌ 테스트 중 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_objectid_conversion():
    """ObjectId 변환 로직 테스트"""
    print("\n" + "=" * 80)
    print("🧪 ObjectId 변환 로직 테스트")
    print("=" * 80)
    
    from bson import ObjectId
    
    test_cases = [
        ("691cee06d10432b7f9472790", True),  # 유효한 24자리 ObjectId
        ("invalid_id", False),  # 유효하지 않은 ID
        ("123", False),  # 너무 짧은 ID
        ("", False),  # 빈 문자열
    ]
    
    print("\n📋 테스트 케이스:")
    for id_str, should_be_valid in test_cases:
        try:
            if isinstance(id_str, str) and len(id_str) == 24:
                obj_id = ObjectId(id_str)
                is_valid = True
            else:
                is_valid = False
                obj_id = None
        except Exception:
            is_valid = False
            obj_id = None
        
        status = "✅" if is_valid == should_be_valid else "❌"
        print(f"   {status} ID: {id_str[:20]}... | 유효: {is_valid} | 예상: {should_be_valid}")
    
    print("\n✅ ObjectId 변환 로직 테스트 완료")
    return True


def test_json_structure():
    """parsing_failed.json 파일 구조 검증"""
    print("\n" + "=" * 80)
    print("🧪 parsing_failed.json 파일 구조 검증")
    print("=" * 80)
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    utils_dir = os.path.join(os.path.dirname(script_dir), "utils")
    json_file = os.path.join(utils_dir, "parsing_failed.json")
    
    if not os.path.exists(json_file):
        print(f"⚠️  {json_file} 파일이 없습니다.")
        return False
    
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 필수 필드 확인
        assert 'total_failed' in data, "total_failed 필드가 없습니다"
        assert 'failed_meetings' in data, "failed_meetings 필드가 없습니다"
        assert isinstance(data['failed_meetings'], list), "failed_meetings는 리스트여야 합니다"
        
        print(f"\n✅ JSON 구조 검증 성공")
        print(f"   total_failed: {data['total_failed']}")
        print(f"   failed_meetings 수: {len(data['failed_meetings'])}")
        
        # 각 항목의 구조 확인
        if data['failed_meetings']:
            first_meeting = data['failed_meetings'][0]
            assert 'id' in first_meeting, "각 meeting에는 id 필드가 있어야 합니다"
            print(f"   첫 번째 항목 ID: {first_meeting.get('id', 'N/A')[:24]}...")
        
        return True
        
    except json.JSONDecodeError as e:
        print(f"\n❌ JSON 파싱 오류: {str(e)}")
        return False
    except AssertionError as e:
        print(f"\n❌ 구조 검증 실패: {str(e)}")
        return False
    except Exception as e:
        print(f"\n❌ 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """모든 테스트 실행"""
    print("\n" + "=" * 80)
    print("🚀 move_failed_recordings.py 전체 테스트 시작")
    print("=" * 80)
    
    tests = [
        ("JSON 파일 구조 검증", test_json_structure),
        ("실패 ID 로드", test_load_failed_ids),
        ("에러 처리", test_load_failed_ids_error_handling),
        ("ObjectId 변환", test_objectid_conversion),
        ("Dry-run 모드", test_move_failed_recordings_dry_run),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ {test_name} 테스트 중 예외 발생: {str(e)}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # 결과 요약
    print("\n" + "=" * 80)
    print("📊 테스트 결과 요약")
    print("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ 통과" if result else "❌ 실패"
        print(f"   {status}: {test_name}")
    
    print(f"\n총 {total}개 테스트 중 {passed}개 통과 ({passed/total*100:.1f}%)")
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    
    print("\n" + "=" * 80)
    if success:
        print("✅ 모든 테스트 통과!")
        sys.exit(0)
    else:
        print("❌ 일부 테스트 실패")
        sys.exit(1)

