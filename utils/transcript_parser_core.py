"""
MongoDB Transcript 파싱 핵심 기능 모듈
다른 프로그램에서 import하여 사용할 수 있는 비대화형 기능들
"""

import os
import json
from datetime import datetime
from collections import defaultdict


def convert_objectid(obj):
    """
    MongoDB ObjectId를 문자열로 변환하기 위한 헬퍼 함수
    
    Args:
        obj: 변환할 객체
        
    Returns:
        변환된 객체
    """
    if isinstance(obj, dict):
        return {k: convert_objectid(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_objectid(item) for item in obj]
    elif hasattr(obj, '__str__') and 'ObjectId' in str(type(obj)):
        return str(obj)
    elif isinstance(obj, datetime):
        return obj.isoformat()
    else:
        return obj


def get_all_participants(analyzer):
    """
    MongoDB에서 모든 참여자 목록을 가져옴 (효율적인 방법)
    
    Args:
        analyzer: MeetingPerformanceAnalyzer 인스턴스
        
    Returns:
        정렬된 참여자 목록
    """
    print("\n📋 참여자 목록을 가져오는 중...")
    all_participants = set()
    
    try:
        # 방법 1: MongoDB aggregation을 사용하여 participants 필드가 있는 문서에서만 추출
        # 이 방법이 훨씬 빠름 (전체 문서를 가져오지 않고 참여자만 추출)
        pipeline = [
            {
                '$match': {
                    '$or': [
                        {'participants': {'$exists': True, '$ne': None, '$ne': []}},
                        {'transcript': {'$exists': True, '$ne': None, '$ne': ''}},
                        {'content': {'$exists': True, '$ne': None, '$ne': ''}}
                    ]
                }
            },
            {
                '$project': {
                    'participants': 1,
                    'transcript': 1,
                    'content': 1
                }
            }
        ]
        
        # aggregation으로 필요한 필드만 가져오기
        cursor = analyzer.collection.aggregate(pipeline)
        docs_with_participants = 0
        docs_needing_parsing = 0
        
        for doc in cursor:
            # participants 필드가 이미 있으면 사용
            if 'participants' in doc and doc.get('participants'):
                participants_list = doc.get('participants', [])
                if isinstance(participants_list, list):
                    for p in participants_list:
                        if p and isinstance(p, str):
                            # 정규화된 이름으로 추가
                            normalized = analyzer._normalize_participant_name(p.strip())
                            if normalized and analyzer._is_valid_participant(normalized):
                                all_participants.add(normalized)
                    docs_with_participants += 1
                    continue
            
            # participants 필드가 없으면 transcript 파싱
            transcript = doc.get('transcript') or doc.get('content', '')
            if transcript:
                try:
                    # 정규화된 문서로 변환 (transcript 추출)
                    normalized_doc = analyzer._normalize_document(doc)
                    transcript_text = normalized_doc.get('transcript', '')
                    if transcript_text:
                        parsed = analyzer.parse_transcript(transcript_text)
                        for entry in parsed:
                            speaker = entry.get('speaker', '').strip()
                            if speaker and analyzer._is_valid_participant(speaker):
                                # 정규화된 이름으로 추가
                                normalized = analyzer._normalize_participant_name(speaker)
                                if normalized:
                                    all_participants.add(normalized)
                        docs_needing_parsing += 1
                except:
                    pass
        
        if docs_with_participants > 0 or docs_needing_parsing > 0:
            print(f"   ✓ {docs_with_participants}개 문서에서 participants 필드 사용")
            if docs_needing_parsing > 0:
                print(f"   ✓ {docs_needing_parsing}개 문서에서 transcript 파싱")
    
    except Exception as e:
        print(f"   ⚠️  Aggregation 실패: {e}")
        print("   대체 방법으로 시도 중...")
        
        # 대체 방법: 기존 방식 (전체 문서 가져오기)
        meetings = analyzer.fetch_meeting_records({})
        
        for meeting in meetings:
            # participants 필드가 이미 있으면 사용
            if 'participants' in meeting and meeting.get('participants'):
                participants_list = meeting.get('participants', [])
                if isinstance(participants_list, list):
                    for p in participants_list:
                        if p and isinstance(p, str):
                            normalized = analyzer._normalize_participant_name(p.strip())
                            if normalized and analyzer._is_valid_participant(normalized):
                                all_participants.add(normalized)
                continue
            
            # participants 필드가 없으면 transcript 파싱
            transcript = meeting.get('transcript', '')
            if transcript:
                try:
                    parsed = analyzer.parse_transcript(transcript)
                    for entry in parsed:
                        speaker = entry.get('speaker', '').strip()
                        if speaker and analyzer._is_valid_participant(speaker):
                            normalized = analyzer._normalize_participant_name(speaker)
                            if normalized:
                                all_participants.add(normalized)
                except:
                    pass
    
    return sorted(list(all_participants))


def test_all_transcripts(analyzer, output_dir=None):
    """
    MongoDB에서 모든 transcript를 가져와 파싱 테스트
    
    Args:
        analyzer: MeetingPerformanceAnalyzer 인스턴스
        output_dir: 출력 파일을 저장할 디렉토리 (None이면 현재 스크립트 디렉토리)
        
    Returns:
        dict: {
            'parsed_meetings': [...],
            'failed_meetings': [...],
            'meetings': [...],  # 원본 회의 데이터
            'summary': {...}
        }
    """
    print("="*80)
    print("📊 MongoDB Transcript 파싱 테스트")
    print("="*80)
    
    # 모든 transcript 가져오기
    print(f"\n📚 MongoDB에서 transcript 가져오는 중...")
    meetings = analyzer.fetch_meeting_records()
    
    if not meetings:
        print("⚠️  가져온 transcript가 없습니다.")
        return {
            'parsed_meetings': [],
            'failed_meetings': [],
            'summary': {
                'total_meetings': 0,
                'success_count': 0,
                'fail_count': 0
            }
        }
    
    print(f"\n✅ 총 {len(meetings)}개의 transcript를 가져왔습니다.")
    print("\n" + "="*80)
    print("📝 파싱 테스트 시작")
    print("="*80)
    
    # 통계 변수
    total_meetings = len(meetings)
    success_count = 0
    fail_count = 0
    total_statements = 0
    total_participants = set()
    participant_count_by_meeting = []
    failed_meetings = []
    parsed_meetings = []
    
    # 각 transcript 파싱 테스트
    for idx, meeting in enumerate(meetings, 1):
        meeting_id = str(meeting.get('_id', ''))
        meeting_title = meeting.get('title', 'N/A')
        meeting_date = meeting.get('date', 'N/A')
        
        print(f"\n[{idx}/{total_meetings}] {meeting_title}")
        print(f"   ID: {meeting_id[:24]}...")
        print(f"   날짜: {meeting_date}")
        
        # Transcript 가져오기
        transcript = meeting.get('transcript', '')
        
        if not transcript:
            print("   ⚠️  Transcript가 없습니다.")
            fail_count += 1
            failed_meetings.append({
                "id": meeting_id,
                "title": meeting_title,
                "date": str(meeting_date) if meeting_date != 'N/A' else None,
                "failure_reason": "Transcript가 없습니다"
            })
            continue
        
        print(f"   📄 Transcript 길이: {len(transcript)} 문자")
        
        # Transcript 파싱
        try:
            parsed_transcript = analyzer.parse_transcript(transcript)
            
            if not parsed_transcript:
                print("   ❌ 파싱 실패: 발언이 추출되지 않았습니다.")
                fail_count += 1
                # 실패 이유 분석
                failure_reason = "발언이 추출되지 않았습니다"
                transcript_lower = transcript.lower()
                if 'transcription ended after' in transcript_lower:
                    failure_reason = "Transcription ended 메시지만 있음 (실제 내용 없음)"
                elif '후 스크립트 작성이 종료되었습니다' in transcript:
                    failure_reason = "후 스크립트 작성 종료 메시지만 있음 (실제 내용 없음)"
                elif len(transcript.strip()) < 200:
                    failure_reason = f"Transcript가 너무 짧음 ({len(transcript)}자)"
                elif not any(char in transcript for char in [':', '[', ']']):
                    failure_reason = "타임스탬프/발언자 구분자 없음"
                
                failed_meetings.append({
                    "id": meeting_id,
                    "title": meeting_title,
                    "date": str(meeting_date) if meeting_date != 'N/A' else None,
                    "failure_reason": failure_reason,
                    "transcript_length": len(transcript)
                })
                continue
            
            # 통계 추출
            stats = analyzer.extract_participant_stats(parsed_transcript)
            participants = list(stats.keys())
            
            # 통계 업데이트
            success_count += 1
            total_statements += len(parsed_transcript)
            total_participants.update(participants)
            participant_count_by_meeting.append(len(participants))
            
            # 파싱 결과 저장
            parsed_meetings.append({
                "id": meeting_id,
                "title": meeting_title,
                "date": str(meeting_date) if meeting_date != 'N/A' else None,
                "participants": participants,
                "total_statements": len(parsed_transcript),
                "participant_stats": {k: {
                    "speak_count": v["speak_count"],
                    "total_words": v["total_words"]
                } for k, v in stats.items()},
                "parsed_transcript": parsed_transcript
            })
            
            # 결과 출력
            print(f"   ✅ 파싱 성공!")
            print(f"      - 발언 수: {len(parsed_transcript)}개")
            print(f"      - 참여자: {len(participants)}명 ({', '.join(participants)})")
            
            # 참여자별 통계 (간단히)
            for speaker, stat in stats.items():
                print(f"         • {speaker}: {stat['speak_count']}회 발언, {stat['total_words']}단어")
            
        except Exception as e:
            print(f"   ❌ 파싱 오류: {str(e)}")
            fail_count += 1
            failed_meetings.append({
                "id": meeting_id,
                "title": meeting_title,
                "date": str(meeting_date) if meeting_date != 'N/A' else None,
                "failure_reason": f"파싱 오류: {str(e)}",
                "transcript_length": len(transcript) if transcript else 0
            })
            continue
    
    # 실패한 회의 정보를 JSON 파일로 저장
    if failed_meetings:
        if output_dir is None:
            output_dir = os.path.dirname(os.path.abspath(__file__))
        output_file = os.path.join(output_dir, "parsing_failed.json")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                "total_failed": len(failed_meetings),
                "generated_at": datetime.now().isoformat(),
                "failed_meetings": failed_meetings
            }, f, ensure_ascii=False, indent=2)
        print(f"\n💾 실패한 회의 정보를 '{output_file}' 파일에 저장했습니다.")
        print(f"   총 {len(failed_meetings)}개의 실패 케이스가 기록되었습니다.")
    
    # 전체 통계 출력
    print("\n" + "="*80)
    print("📊 파싱 테스트 결과 요약")
    print("="*80)
    print(f"\n총 회의 수: {total_meetings}개")
    print(f"✅ 성공: {success_count}개")
    print(f"❌ 실패: {fail_count}개")
    if total_meetings > 0:
        print(f"성공률: {(success_count/total_meetings*100):.1f}%")
    
    if success_count > 0:
        print(f"\n📈 통계:")
        print(f"   - 총 발언 수: {total_statements:,}개")
        print(f"   - 평균 발언 수/회의: {total_statements/success_count:.1f}개")
        print(f"   - 고유 참여자 수: {len(total_participants)}명")
        if participant_count_by_meeting:
            avg_participants = sum(participant_count_by_meeting) / len(participant_count_by_meeting)
            print(f"   - 평균 참여자 수/회의: {avg_participants:.1f}명")
            print(f"   - 최소 참여자 수: {min(participant_count_by_meeting)}명")
            print(f"   - 최대 참여자 수: {max(participant_count_by_meeting)}명")
        
        print(f"\n👥 전체 참여자 목록 ({len(total_participants)}명):")
        for i, participant in enumerate(sorted(total_participants), 1):
            print(f"   {i}. {participant}")
    
    return {
        'parsed_meetings': parsed_meetings,
        'failed_meetings': failed_meetings,
        'meetings': meetings,  # 원본 회의 데이터
        'summary': {
            'total_meetings': total_meetings,
            'success_count': success_count,
            'fail_count': fail_count,
            'total_statements': total_statements,
            'unique_participants': len(total_participants),
            'participants_list': sorted(list(total_participants))
        }
    }


def test_with_filters(analyzer, filters, post_filters=None, output_dir=None):
    """
    필터를 사용하여 특정 조건의 transcript만 테스트
    
    Args:
        analyzer: MeetingPerformanceAnalyzer 인스턴스
        filters: MongoDB 쿼리 필터 딕셔너리
        post_filters: 파싱 후 필터링할 조건들 (선택사항)
        output_dir: 출력 파일을 저장할 디렉토리 (None이면 현재 스크립트 디렉토리)
        
    Returns:
        dict: {
            'parsed_meetings': [...],
            'failed_meetings': [...],
            'meetings': [...],  # 원본 회의 데이터
            'filters': {...},  # 적용된 필터
            'post_filters': {...},  # 적용된 post 필터
            'summary': {...}
        }
    """
    print("="*80)
    print("📊 MongoDB Transcript 파싱 테스트 (필터 적용)")
    print("="*80)
    
    if post_filters is None:
        post_filters = {}
    
    # 필터 요약 출력
    if filters or post_filters:
        print("\n" + "="*80)
        print("📋 적용된 필터 요약")
        print("="*80)
        if post_filters:
            print("\n파싱 후 필터:")
            for key, value in post_filters.items():
                print(f"   - {key}: {value}")
        if filters:
            print("\n✅ MongoDB 쿼리 필터가 적용되었습니다.")
    else:
        print("\n🔍 필터 없음: 모든 회의를 분석합니다.")
    
    # 필터링된 transcript 가져오기
    print(f"\n📚 MongoDB에서 transcript 가져오는 중...")
    meetings = analyzer.fetch_meeting_records(filters)
    
    if not meetings:
        print("⚠️  필터 조건에 맞는 transcript가 없습니다.")
        return {
            'parsed_meetings': [],
            'failed_meetings': [],
            'summary': {
                'total_meetings': 0,
                'success_count': 0,
                'fail_count': 0,
                'post_filtered_count': 0
            }
        }
    
    print(f"\n✅ 총 {len(meetings)}개의 transcript를 가져왔습니다.")
    print("\n" + "="*80)
    print("📝 파싱 테스트 시작")
    print("="*80)
    
    # 통계 변수
    total_meetings = len(meetings)
    success_count = 0
    fail_count = 0
    total_statements = 0
    total_participants = set()
    failed_meetings = []
    post_filtered_count = 0
    parsed_meetings = []
    
    for idx, meeting in enumerate(meetings, 1):
        meeting_id = str(meeting.get('_id', ''))
        meeting_title = meeting.get('title', 'N/A')
        meeting_date = meeting.get('date', 'N/A')
        
        print(f"\n[{idx}/{total_meetings}] {meeting_title}")
        print(f"   날짜: {meeting_date}")
        
        # Transcript 가져오기
        transcript = meeting.get('transcript', '')
        
        if not transcript:
            print("   ⚠️  Transcript가 없습니다.")
            fail_count += 1
            failed_meetings.append({
                "id": meeting_id,
                "title": meeting_title,
                "date": str(meeting_date) if meeting_date != 'N/A' else None,
                "failure_reason": "Transcript가 없습니다"
            })
            continue
        
        # Transcript 파싱
        try:
            parsed_transcript = analyzer.parse_transcript(transcript)
            
            if not parsed_transcript:
                print("   ❌ 파싱 실패: 발언이 추출되지 않았습니다.")
                fail_count += 1
                # 실패 이유 분석
                failure_reason = "발언이 추출되지 않았습니다"
                transcript_lower = transcript.lower()
                if 'transcription ended after' in transcript_lower:
                    failure_reason = "Transcription ended 메시지만 있음 (실제 내용 없음)"
                elif '후 스크립트 작성이 종료되었습니다' in transcript:
                    failure_reason = "후 스크립트 작성 종료 메시지만 있음 (실제 내용 없음)"
                elif len(transcript.strip()) < 200:
                    failure_reason = f"Transcript가 너무 짧음 ({len(transcript)}자)"
                elif not any(char in transcript for char in [':', '[', ']']):
                    failure_reason = "타임스탬프/발언자 구분자 없음"
                
                failed_meetings.append({
                    "id": meeting_id,
                    "title": meeting_title,
                    "date": str(meeting_date) if meeting_date != 'N/A' else None,
                    "failure_reason": failure_reason,
                    "transcript_length": len(transcript)
                })
                continue
            
            # 통계 추출
            stats = analyzer.extract_participant_stats(parsed_transcript)
            participants = list(stats.keys())
            
            # 파싱 후 필터링 적용
            should_include = True
            
            # Transcript 길이 필터
            if 'min_transcript_length' in post_filters:
                min_len = post_filters['min_transcript_length']
                if len(transcript) < min_len:
                    print(f"   ⏭️  필터링됨: Transcript 길이가 {min_len}자 미만입니다 ({len(transcript)}자).")
                    should_include = False
            
            if should_include and 'max_transcript_length' in post_filters:
                max_len = post_filters['max_transcript_length']
                if len(transcript) > max_len:
                    print(f"   ⏭️  필터링됨: Transcript 길이가 {max_len}자 초과입니다 ({len(transcript)}자).")
                    should_include = False
            
            # 참여자 필터 (특정 참여자 포함)
            if should_include and 'participants' in post_filters:
                required_participant = post_filters['participants']
                if required_participant not in participants:
                    print(f"   ⏭️  필터링됨: '{required_participant}' 참여자가 없습니다.")
                    should_include = False
            
            # 참여자 수 필터
            if should_include and 'min_participants' in post_filters:
                min_p = post_filters['min_participants']
                if len(participants) < min_p:
                    print(f"   ⏭️  필터링됨: 참여자 수가 {min_p}명 미만입니다 ({len(participants)}명).")
                    should_include = False
            
            if should_include and 'max_participants' in post_filters and post_filters['max_participants']:
                max_p = post_filters['max_participants']
                if len(participants) > max_p:
                    print(f"   ⏭️  필터링됨: 참여자 수가 {max_p}명 초과입니다 ({len(participants)}명).")
                    should_include = False
            
            if not should_include:
                post_filtered_count += 1
                continue
            
            # 통계 업데이트
            success_count += 1
            total_statements += len(parsed_transcript)
            total_participants.update(participants)
            
            # 파싱 결과 저장
            parsed_meetings.append({
                "id": meeting_id,
                "title": meeting_title,
                "date": str(meeting_date) if meeting_date != 'N/A' else None,
                "participants": participants,
                "total_statements": len(parsed_transcript),
                "participant_stats": {k: {
                    "speak_count": v["speak_count"],
                    "total_words": v["total_words"],
                    "timestamps": v.get("timestamps", [])
                } for k, v in stats.items()},
                "parsed_transcript": parsed_transcript
            })
            
            # 결과 출력
            print(f"   ✅ 파싱 성공: {len(parsed_transcript)}개 발언, {len(participants)}명 참여자")
            
        except Exception as e:
            print(f"   ❌ 파싱 오류: {str(e)}")
            fail_count += 1
            failed_meetings.append({
                "id": meeting_id,
                "title": meeting_title,
                "date": str(meeting_date) if meeting_date != 'N/A' else None,
                "failure_reason": f"파싱 오류: {str(e)}",
                "transcript_length": len(transcript) if transcript else 0
            })
            continue
    
    # 실패한 회의 정보를 JSON 파일로 저장
    if failed_meetings:
        if output_dir is None:
            output_dir = os.path.dirname(os.path.abspath(__file__))
        output_file = os.path.join(output_dir, "parsing_failed.json")
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                "total_failed": len(failed_meetings),
                "generated_at": datetime.now().isoformat(),
                "failed_meetings": failed_meetings
            }, f, ensure_ascii=False, indent=2)
        print(f"\n💾 실패한 회의 정보를 '{output_file}' 파일에 저장했습니다.")
        print(f"   총 {len(failed_meetings)}개의 실패 케이스가 기록되었습니다.")
    
    # 전체 통계 출력
    print("\n" + "="*80)
    print("📊 파싱 테스트 결과 요약")
    print("="*80)
    print(f"\n총 회의 수: {total_meetings}개")
    if post_filters and post_filtered_count > 0:
        print(f"⏭️  파싱 후 필터링으로 제외: {post_filtered_count}개")
    print(f"✅ 성공: {success_count}개")
    print(f"❌ 실패: {fail_count}개")
    
    if success_count > 0:
        print(f"\n📈 통계:")
        print(f"   - 총 발언 수: {total_statements:,}개")
        print(f"   - 고유 참여자 수: {len(total_participants)}명")
        
        # 전체 참여자 목록 출력
        if total_participants:
            print(f"\n👥 전체 참여자 목록 ({len(total_participants)}명):")
            for i, participant in enumerate(sorted(total_participants), 1):
                print(f"   {i}. {participant}")
    
    return {
        'parsed_meetings': parsed_meetings,
        'failed_meetings': failed_meetings,
        'meetings': meetings,  # 원본 회의 데이터
        'filters': filters,  # 적용된 필터
        'post_filters': post_filters,  # 적용된 post 필터
        'summary': {
            'total_meetings': total_meetings,
            'success_count': success_count,
            'fail_count': fail_count,
            'post_filtered_count': post_filtered_count,
            'total_statements': total_statements,
            'unique_participants': len(total_participants),
            'participants_list': sorted(list(total_participants))
        }
    }

