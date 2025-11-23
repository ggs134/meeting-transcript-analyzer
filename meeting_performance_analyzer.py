"""
MongoDB 회의 Transcript를 읽어 Gemini API로 참여자 성과를 분석하는 스크립트
Transcript 형식: [타임스탬프] 발언자: 발언내용
"""

import os
import re
from datetime import datetime
from pymongo import MongoClient
import google.generativeai as genai
from typing import List, Dict, Any, Optional, Union
from collections import defaultdict
from prompt_templates import PromptTemplates, PromptConfig, get_template_version



class MeetingPerformanceAnalyzer:
    def __init__(self, 
                 gemini_api_key: str,
                 database_name: str, 
                 collection_name: str,
                 model_name: str = None,
                 mongodb_host: str = None,
                 mongodb_port: int = 27017,
                 mongodb_username: str = None,
                 mongodb_password: str = None,
                 mongodb_auth_database: str = None,
                 mongodb_uri: str = None,
                 prompt_template: str = "default", 
                 template_version: str = None,
                 custom_prompt: str = None
                 ):
        """
        회의 Transcript 성과 분석기 초기화
        
        Args:
            gemini_api_key: Gemini API 키
            database_name: 데이터베이스 이름
            collection_name: transcript가 저장된 컬렉션 이름
            model_name: Gemini 모델 이름 (없으면 환경변수 GEMINI_MODEL 또는 기본값 사용)
            mongodb_host: MongoDB 호스트 (기본값: localhost)
            mongodb_port: MongoDB 포트 (기본값: 27017)
            mongodb_username: MongoDB 사용자명 (선택)
            mongodb_password: MongoDB 비밀번호 (선택)
            mongodb_auth_database: 인증에 사용할 데이터베이스 (선택, username이 있으면 필수)
            mongodb_uri: MongoDB 연결 URI (직접 지정 시 위 파라미터보다 우선)
            prompt_template: 사용할 프롬프트 템플릿 이름 (기본값: "default")
            template_version: 템플릿 버전 (None이면 최신 버전 사용)
            custom_prompt: 사용자 정의 프롬프트 (선택)
        """
        # MongoDB 연결 URI 생성
        if mongodb_uri:
            # URI가 직접 제공된 경우 사용
            connection_uri = mongodb_uri
        else:
            # 개별 파라미터로 URI 생성
            if mongodb_host is None:
                mongodb_host = os.getenv('MONGODB_HOST', 'localhost')
            
            if mongodb_username and mongodb_password:
                # 인증 정보가 있는 경우
                if mongodb_auth_database is None:
                    mongodb_auth_database = os.getenv('MONGODB_AUTH_DATABASE', 'admin')
                
                # URL 인코딩 (특수문자 처리)
                from urllib.parse import quote_plus
                encoded_username = quote_plus(mongodb_username)
                encoded_password = quote_plus(mongodb_password)
                
                # URI 생성: authSource만 지정하고 데이터베이스는 연결 후 선택
                # 특수문자(! 등)가 비밀번호에 포함될 수 있으므로 URL 인코딩 필수
                connection_uri = f"mongodb://{encoded_username}:{encoded_password}@{mongodb_host}:{mongodb_port}/?authSource={mongodb_auth_database}"
            else:
                # 인증 정보가 없는 경우
                connection_uri = f"mongodb://{mongodb_host}:{mongodb_port}/"
        
        # MongoDB 연결
        self.client = MongoClient(connection_uri)
        self.db = self.client[database_name]
        self.collection = self.db[collection_name]
        
        # Gemini API 설정
        genai.configure(api_key=gemini_api_key)
        
        # 모델 이름 설정 (환경변수 또는 파라미터 또는 기본값)
        if model_name is None:
            model_name = os.getenv('GEMINI_MODEL', 'gemini-2.0-flash')
        self.model_name = model_name
        self.model = genai.GenerativeModel(model_name)
        
        # 프롬프트 설정
        self.prompt_config = PromptConfig(
            default_template=prompt_template,
            custom_template=custom_prompt,
            default_version=template_version  # 지정된 버전 사용 (None이면 최신 버전)
        )
        
    def _extract_transcript_section(self, content: str) -> str:
        """
        content에서 Transcript 섹션만 추출
        
        Args:
            content: 전체 content 텍스트
            
        Returns:
            Transcript 섹션만 포함된 텍스트
        """
        # \r\n을 \n으로 정규화
        content = content.replace('\r\n', '\n').replace('\r', '\n')
        
        # "📖 Transcript", "📖 스크립트" 또는 "Transcript" 섹션 찾기
        transcript_markers = [
            r'📖\s*스크립트',
            r'📖\s*Transcript',
            r'스크립트',
            r'Transcript',
            r'TRANSCRIPT',
        ]
        
        for marker in transcript_markers:
            # 마커 이후의 모든 내용 추출 (문자열 끝까지)
            pattern = rf'{marker}.*$'
            match = re.search(pattern, content, re.DOTALL | re.IGNORECASE | re.MULTILINE)
            if match:
                transcript_section = match.group(0)
                # 마커와 날짜/제목 라인 제거
                # 예: "📖 Transcript\nNov 17, 2025\nSYB call - Transcript\n00:00:00"
                lines = transcript_section.split('\n')
                # 마커가 포함된 줄 찾기
                start_idx = 0
                for i, line in enumerate(lines):
                    if re.search(marker, line, re.IGNORECASE):
                        start_idx = i + 1
                        # 다음 줄이 날짜 형식이면 건너뛰기
                        if i + 1 < len(lines):
                            next_line = lines[i + 1].strip()
                            # 영어 날짜 형식 (예: "Nov 17, 2025")
                            if re.match(r'[A-Z][a-z]{2}\s+\d{1,2},\s+\d{4}', next_line):
                                start_idx = i + 2
                            # 한국어 날짜 형식 (예: "2025년 7월 9일")
                            elif re.match(r'\d{4}년\s+\d{1,2}월\s+\d{1,2}일', next_line):
                                start_idx = i + 2
                        # 그 다음 줄이 제목 형식이면 건너뛰기
                        if start_idx < len(lines):
                            title_line = lines[start_idx]
                            if ' - Transcript' in title_line or ' - 스크립트' in title_line:
                                start_idx += 1
                        break
                
                transcript_section = '\n'.join(lines[start_idx:])
                return transcript_section.strip()
        
        # 마커를 찾지 못하면 전체 content 반환
        return content
    
    def _normalize_document(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """
        Google Drive 스키마를 회의 분석 형식으로 정규화
        MongoDB 데이터를 수정하지 않고 메모리에서만 변환
        
        Args:
            doc: MongoDB 문서
            
        Returns:
            정규화된 문서
        """
        # 이미 정규화된 형식인지 확인 (title과 transcript가 모두 있으면 정규화됨)
        if 'title' in doc and 'transcript' in doc and doc.get('transcript'):
            return doc
        
        # Google Drive 스키마 형식인 경우 변환
        normalized = doc.copy()
        
        # title 변환: title이 없으면 name 사용
        if 'title' not in normalized:
            normalized['title'] = normalized.get('name', 'Untitled Meeting')
        
        # transcript 변환: transcript가 없으면 content에서 Transcript 섹션만 추출
        if 'transcript' not in normalized or not normalized.get('transcript'):
            content = normalized.get('content', '')
            if content:
                # content에서 Transcript 섹션만 추출
                normalized['transcript'] = self._extract_transcript_section(content)
            else:
                normalized['transcript'] = ''
        
        # date 변환: date가 없으면 createdTime 사용
        if 'date' not in normalized or normalized.get('date') is None:
            created_time = normalized.get('createdTime')
            if created_time:
                try:
                    if isinstance(created_time, str):
                        # ISO 8601 형식 파싱
                        # 예: "2025-11-17T10:17:47.962Z"
                        time_str = created_time
                        
                        # Z를 +00:00로 변환
                        if time_str.endswith('Z'):
                            time_str = time_str[:-1] + '+00:00'
                        
                        # 밀리초 제거 (있는 경우)
                        # 2025-11-17T10:17:47.962+00:00 -> 2025-11-17T10:17:47+00:00
                        if '.' in time_str:
                            # .962+00:00 또는 .962Z 같은 형식
                            dot_idx = time_str.index('.')
                            # + 또는 - 또는 Z 찾기
                            tz_start = len(time_str)
                            for char in ['+', '-', 'Z']:
                                idx = time_str.find(char, dot_idx)
                                if idx != -1 and idx < tz_start:
                                    tz_start = idx
                            
                            # 밀리초 부분 제거
                            time_str = time_str[:dot_idx] + time_str[tz_start:]
                            # Z가 남아있으면 +00:00로 변환
                            if time_str.endswith('Z'):
                                time_str = time_str[:-1] + '+00:00'
                        
                        dt = datetime.fromisoformat(time_str)
                        normalized['date'] = dt
                    elif isinstance(created_time, datetime):
                        normalized['date'] = created_time
                except Exception as e:
                    print(f"⚠️  날짜 변환 오류: {e}, 입력값: {created_time}")
                    normalized['date'] = datetime.now()
        
        # participants 자동 추출 (없는 경우)
        if 'participants' not in normalized or not normalized.get('participants'):
            transcript = normalized.get('transcript', '')
            if transcript:
                participants = self._extract_participants_from_transcript(transcript)
                if participants:
                    normalized['participants'] = participants
        
        return normalized
    
    def _is_valid_participant(self, speaker: str) -> bool:
        """
        발언자가 유효한 참여자인지 확인
        
        Args:
            speaker: 발언자 이름
            
        Returns:
            유효한 참여자면 True
        """
        speaker = speaker.strip()
        if not speaker:
            return False
        
        # BOM 문자 제거
        if speaker.startswith('\ufeff'):
            speaker = speaker[1:].strip()
        if not speaker:
            return False
        
        # 필터링할 패턴들
        invalid_patterns = [
            r'^Transcription\s+ended',
            r'^Transcription\s+ended\s+after',
            r'^Session\s+ended',
            r'^Session\s+ended\s+after',
            r'Meeting\s+ended\s+after',  # "Meeting ended after 00", "Meeting ended after 01" 등
            r'^This\s+editable\s+transcript',
            r'^You\s+should\s+review',
            r'^Please\s+provide\s+feedback',
            r'^Get\s+tips',
            r'^\*',  # "* "로 시작하는 것 (요약 항목)
            r'^Ooo',  # "Ooo"로 시작하는 것 (파일명 등)
            r'^첨부파일',  # "첨부파일"로 시작하는 것
            r'^초대됨',  # "초대됨"으로 시작하는 것
            r'^Gemini가',  # "Gemini가"로 시작하는 것
            r'^수정 가능한',  # "수정 가능한"으로 시작하는 것
            r'^\d{4}년',  # "2025년" 같은 날짜 형식
            r'^\d{2}:\d{2}:\d{2}$',  # 타임스탬프만 있는 것 (정확히 일치)
            r'^\d{2}:\d{2}$',  # 타임스탬프만 있는 것 (정확히 일치)
            r'^후 스크립트',  # "후 스크립트"로 시작하는 것
            r'^\d+$',  # 숫자만 있는 것 (예: "00")
            r'^Attachments',  # "Attachments Project TRH" 등
            r'^Project\s+TRH$',  # "Project TRH" (정확히 일치)
            r'\'s\s+Presentation$',  # "Jake Jang's Presentation" 등
            r'님의\s+발표$',  # "Theo Lee님의 발표" 등
            r'^[﻿\ufeff]',  # BOM 문자로 시작하는 것
        ]
        
        for pattern in invalid_patterns:
            if re.search(pattern, speaker, re.IGNORECASE):
                return False
        
        return True
    
    def _normalize_participant_name(self, name: str) -> str:
        """
        참여자 이름을 정규화 (동일 인물의 다른 표기법 통합)
        
        Args:
            name: 원본 참여자 이름
            
        Returns:
            정규화된 참여자 이름
        """
        if not name:
            return name
        
        name = name.strip()
        
        # 이름 매핑 딕셔너리 (별칭/변형 → 표준 이름)
        name_mapping = {
            # Nam 관련 변형들
            "Nam": "Nam Pham",
            "Nam Phạm Tiến": "Nam Pham",
            "Nam Tiến": "Nam Pham",
            
            # Chiko Nakamura 관련 변형들
            "Nakamura Chiko": "Chiko Nakamura",
            
            # 기타 일반적인 정규화
            # 대괄호와 그 안의 내용 제거 (예: "이낙준[ 정보보호대학원박사과정수료연구(재학) / 정보보호학과 ]" → "이낙준")
            # 하지만 이건 정규식으로 처리하는 게 나을 수도 있음
        }
        
        # 매핑에 있으면 표준 이름으로 변환
        if name in name_mapping:
            return name_mapping[name]
        
        # 대괄호와 그 안의 내용 제거 (예: "이낙준[ ... ]" → "이낙준")
        # 단, 대괄호가 없으면 그대로 반환
        bracket_match = re.match(r'^([^\[\]]+)\[.*?\]$', name)
        if bracket_match:
            normalized = bracket_match.group(1).strip()
            # 정규화된 이름도 매핑에 있는지 확인
            if normalized in name_mapping:
                return name_mapping[normalized]
            return normalized
        
        # 공백 정규화 (여러 공백을 하나로)
        normalized = re.sub(r'\s+', ' ', name).strip()
        
        # 정규화된 이름도 매핑에 있는지 확인
        if normalized in name_mapping:
            return name_mapping[normalized]
        
        return normalized
    
    def _extract_participants_from_transcript(self, transcript: str) -> List[str]:
        """
        Transcript에서 참여자 자동 추출
        
        Args:
            transcript: 회의 녹취록
            
        Returns:
            참여자 이름 리스트
        """
        # parse_transcript를 사용하여 파싱 후 참여자 추출
        parsed = self.parse_transcript(transcript)
        participants = set()
        
        for entry in parsed:
            speaker = entry.get('speaker', '').strip()
            if speaker and self._is_valid_participant(speaker):
                participants.add(speaker)
        
        return sorted(list(participants))
        
    def fetch_meeting_records(self, filters: Dict[str, Any] = None) -> List[Dict]:
        """
        MongoDB에서 회의 transcript 데이터 가져오기
        Google Drive 스키마 형식도 자동으로 처리
        
        Args:
            filters: MongoDB 쿼리 필터 (예: {'date': {'$gte': start_date}})
                     'date' 필터는 자동으로 'createdTime' 필드에도 적용됨
            
        Returns:
            회의 transcript 문서 리스트 (정규화됨)
        """
        # date 필터를 별도로 저장 (정규화 후 재적용용)
        date_filter = None
        mongo_filters = {}
        
        if filters:
            mongo_filters = filters.copy()
            date_filter = None
            
            # date 필터 찾기 (직접 있거나 $and 배열 안에 있을 수 있음)
            if 'date' in mongo_filters:
                date_filter = mongo_filters.pop('date')
            elif '$and' in mongo_filters:
                # $and 배열에서 date 필터 찾기
                found_index = None
                for i, condition in enumerate(mongo_filters['$and']):
                    if isinstance(condition, dict) and 'date' in condition:
                        date_filter = condition.pop('date')
                        # 빈 딕셔너리가 되면 나중에 제거하기 위해 인덱스 저장
                        if not condition:
                            found_index = i
                        # date 필터를 찾았으므로 break
                        break
                
                # 빈 딕셔너리 제거 (인덱스가 저장된 경우)
                if found_index is not None:
                    mongo_filters['$and'].pop(found_index)
            
            if date_filter:
                # date 필터를 createdTime 필드에도 적용
                # createdTime은 문자열일 수 있으므로 datetime을 ISO 문자열로 변환
                created_time_filter = {}
                if isinstance(date_filter, dict):
                    for op, value in date_filter.items():
                        if isinstance(value, datetime):
                            # datetime을 ISO 8601 문자열로 변환
                            created_time_filter[op] = value.isoformat() + 'Z'
                        else:
                            created_time_filter[op] = value
                else:
                    if isinstance(date_filter, datetime):
                        created_time_filter = date_filter.isoformat() + 'Z'
                    else:
                        created_time_filter = date_filter
                
                # date 또는 createdTime 필드 중 하나라도 조건을 만족하면 선택
                date_or_filter = {
                    '$or': [
                        {'date': date_filter},
                        {'createdTime': created_time_filter}
                    ]
                }
                
                # $and가 이미 있으면 배열에 추가, 없으면 새로 생성
                if '$and' in mongo_filters:
                    # 빈 $and 배열 정리
                    mongo_filters['$and'] = [c for c in mongo_filters['$and'] if c]
                    if mongo_filters['$and']:
                        mongo_filters['$and'].append(date_or_filter)
                    else:
                        mongo_filters = date_or_filter
                elif mongo_filters:
                    # 다른 필터가 있으면 $and로 결합
                    mongo_filters = {'$and': [mongo_filters, date_or_filter]}
                else:
                    mongo_filters = date_or_filter
        
        meetings = list(self.collection.find(mongo_filters))
        
        # 각 문서를 정규화 (Google Drive 스키마인 경우 변환)
        normalized_meetings = [self._normalize_document(meeting) for meeting in meetings]
        
        # 정규화 후 날짜 필터를 다시 적용 (정규화된 date 필드 기준)
        if date_filter:
            from datetime import timezone
            filtered_meetings = []
            for meeting in normalized_meetings:
                meeting_date = meeting.get('date')
                if meeting_date and isinstance(meeting_date, datetime):
                    # datetime 객체 비교 (타임존 처리)
                    if isinstance(date_filter, dict):
                        should_include = True
                        for op, filter_date in date_filter.items():
                            # 타임존 일치 처리
                            if isinstance(filter_date, datetime):
                                # meeting_date가 타임존이 있으면 filter_date도 타임존 추가
                                if meeting_date.tzinfo is not None and filter_date.tzinfo is None:
                                    filter_date = filter_date.replace(tzinfo=timezone.utc)
                                elif meeting_date.tzinfo is None and filter_date.tzinfo is not None:
                                    # meeting_date에 타임존이 없으면 filter_date에서 제거
                                    filter_date = filter_date.replace(tzinfo=None)
                                
                                if op == '$gte':
                                    should_include = should_include and (meeting_date >= filter_date)
                                elif op == '$lte':
                                    should_include = should_include and (meeting_date <= filter_date)
                                elif op == '$gt':
                                    should_include = should_include and (meeting_date > filter_date)
                                elif op == '$lt':
                                    should_include = should_include and (meeting_date < filter_date)
                            
                        if should_include:
                            filtered_meetings.append(meeting)
                    else:
                        # 단일 값 비교
                        filter_date = date_filter
                        if isinstance(filter_date, datetime):
                            if meeting_date.tzinfo is not None and filter_date.tzinfo is None:
                                filter_date = filter_date.replace(tzinfo=timezone.utc)
                            elif meeting_date.tzinfo is None and filter_date.tzinfo is not None:
                                filter_date = filter_date.replace(tzinfo=None)
                            if meeting_date >= filter_date:
                                filtered_meetings.append(meeting)
                        else:
                            filtered_meetings.append(meeting)
                else:
                    # 날짜가 없으면 제외하지 않음 (원본 필터 결과 유지)
                    filtered_meetings.append(meeting)
            normalized_meetings = filtered_meetings
        
        print(f"📚 {len(normalized_meetings)}개의 회의 transcript를 가져왔습니다.")
        return normalized_meetings
    
    def parse_transcript(self, transcript: str) -> List[Dict[str, str]]:
        """
        Transcript를 파싱하여 구조화된 데이터로 변환
        
        지원하는 형식:
        1. [00:01:23] 김민수: 내용
        2. 00:01:23 김민수: 내용
        3. 00:00:00
            김민수: 내용 (타임스탬프가 별도 줄)
        
        Args:
            transcript: 원본 transcript 텍스트
            
        Returns:
            파싱된 발언 리스트 [{"timestamp": "00:01:23", "speaker": "김민수", "text": "..."}]
        """
        parsed_lines = []
        lines = transcript.split('\n')
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # 빈 줄 건너뛰기
            if not line:
                i += 1
                continue
                
            # 형식 1, 2: 한 줄에 타임스탬프와 발언자가 모두 있는 경우
            patterns_single_line = [
                r'\[(\d{2}:\d{2}:\d{2})\]\s*([^:]+):\s*(.+)',  # [00:01:23] 김민수: 내용
                r'\[(\d{2}:\d{2})\]\s*([^:]+):\s*(.+)',        # [01:23] 김민수: 내용
                r'^(\d{2}:\d{2}:\d{2})\s+([^:]+):\s*(.+)',     # 00:01:23 김민수: 내용
                r'^(\d{2}:\d{2})\s+([^:]+):\s*(.+)',           # 01:23 김민수: 내용
            ]
            
            matched = False
            for pattern in patterns_single_line:
                match = re.match(pattern, line)
                if match:
                    timestamp, speaker, text = match.groups()
                    speaker = speaker.strip()
                    # 유효한 참여자인지 확인
                    if self._is_valid_participant(speaker):
                        # 참여자 이름 정규화
                        normalized_speaker = self._normalize_participant_name(speaker)
                        parsed_lines.append({
                            "timestamp": timestamp.strip(),
                            "speaker": normalized_speaker,
                            "text": text.strip()
                        })
                    matched = True
                    break
            
            if matched:
                i += 1
                continue
            
            # 형식 3: 타임스탬프가 별도 줄에 있는 경우
            # 예: 00:00:00\n \nJeff Chung: Hello Jamie.
            timestamp_pattern = r'^(\d{2}:\d{2}:\d{2})$|^(\d{2}:\d{2})$'
            timestamp_match = re.match(timestamp_pattern, line)
            
            if timestamp_match:
                timestamp = timestamp_match.group(1) or timestamp_match.group(2)
                # 다음 줄들 확인 (빈 줄이나 공백만 있는 줄 건너뛰기)
                i += 1
                while i < len(lines) and (not lines[i].strip() or lines[i].strip() == ' '):
                    i += 1
                
                # 발언자와 내용 찾기
                if i < len(lines):
                    speaker_line = lines[i].strip()
                    # 발언자: 내용 형식
                    speaker_match = re.match(r'^([^:]+):\s*(.+)', speaker_line)
                    if speaker_match:
                        speaker = speaker_match.group(1).strip()
                        text = speaker_match.group(2).strip()
                        
                        # 유효한 참여자인지 확인
                        if not self._is_valid_participant(speaker):
                            i += 1
                            continue
                        
                        # 참여자 이름 정규화
                        normalized_speaker = self._normalize_participant_name(speaker)
                        
                        # 다음 줄들도 같은 발언자의 연속 발언인지 확인
                        i += 1
                        while i < len(lines):
                            next_line = lines[i].strip()
                            # 타임스탬프나 새로운 발언자가 나오면 중단
                            if re.match(timestamp_pattern, next_line) or re.match(r'^[^:]+:\s*', next_line):
                                break
                            # 빈 줄이면 중단
                            if not next_line:
                                break
                            # 연속 발언으로 처리
                            text += ' ' + next_line
                            i += 1
                        
                        parsed_lines.append({
                            "timestamp": timestamp.strip(),
                            "speaker": normalized_speaker.strip(),
                            "text": text.strip()
                        })
                        continue
            
            # 형식 4: 발언자: 내용만 있는 경우 (타임스탬프 없음)
            speaker_only_match = re.match(r'^([^:]+):\s*(.+)', line)
            if speaker_only_match:
                speaker = speaker_only_match.group(1).strip()
                text = speaker_only_match.group(2).strip()
                
                # 타임스탬프 패턴인지 먼저 확인 (예: "00:00:00", "00:01:23")
                if re.match(r'^\d{2}:\d{2}(:\d{2})?$', speaker):
                    i += 1
                    continue
                
                # 유효한 참여자인지 확인
                if not self._is_valid_participant(speaker):
                    i += 1
                    continue
                
                # 참여자 이름 정규화
                normalized_speaker = self._normalize_participant_name(speaker)
                
                # 이전 발언과 같은 발언자인지 확인 (타임스탬프 없이 연속 발언)
                # 정규화된 이름으로 비교
                if parsed_lines and parsed_lines[-1]['speaker'] == normalized_speaker:
                    parsed_lines[-1]['text'] += ' ' + text
                else:
                    # 타임스탬프 없으면 마지막 타임스탬프 사용 또는 "00:00:00" 사용
                    last_timestamp = parsed_lines[-1]['timestamp'] if parsed_lines else "00:00:00"
                    parsed_lines.append({
                        "timestamp": last_timestamp,
                        "speaker": normalized_speaker,
                        "text": text.strip()
                    })
            
            i += 1
        
        return parsed_lines
    
    def extract_participant_stats(self, parsed_transcript: List[Dict[str, str]]) -> Dict[str, Dict]:
        """
        Transcript에서 참여자별 통계 추출
        
        Args:
            parsed_transcript: 파싱된 transcript
            
        Returns:
            참여자별 통계 딕셔너리
        """
        stats = defaultdict(lambda: {
            "speak_count": 0,
            "total_words": 0,
            "timestamps": [],
            "statements": []
        })
        
        for entry in parsed_transcript:
            speaker = entry["speaker"]
            text = entry["text"]
            timestamp = entry["timestamp"]
            
            stats[speaker]["speak_count"] += 1
            stats[speaker]["total_words"] += len(text.split())
            stats[speaker]["timestamps"].append(timestamp)
            stats[speaker]["statements"].append(text)
        
        return dict(stats)
    
    def format_transcript_for_analysis(self, meeting: Dict, parsed_transcript: List[Dict], stats: Dict) -> str:
        """
        Transcript와 통계를 분석을 위한 텍스트 형식으로 변환
        
        Args:
            meeting: 회의 문서
            parsed_transcript: 파싱된 transcript
            stats: 참여자별 통계
            
        Returns:
            포맷된 텍스트
        """
        # 참여자 목록
        participants = list(stats.keys())
        
        formatted_text = f"""
=== 회의 정보 ===
제목: {meeting.get('title', 'N/A')}
날짜: {meeting.get('date', 'N/A')}
참여자: {', '.join(participants)}

=== 참여자별 발언 통계 ===
"""
        for speaker, stat in stats.items():
            formatted_text += f"""
{speaker}:
  - 발언 횟수: {stat['speak_count']}회
  - 총 발언 단어 수: {stat['total_words']}개
  - 발언 시간대: {stat['timestamps'][0]} ~ {stat['timestamps'][-1]}
"""
        
        formatted_text += "\n=== 전체 대화 내용 ===\n"
        for entry in parsed_transcript:
            formatted_text += f"[{entry['timestamp']}] {entry['speaker']}: {entry['text']}\n"
        
        return formatted_text
    
    def analyze_participant_performance(self, formatted_text: str, stats: Dict, 
                                       template_override: str = None,
                                       custom_instructions: str = "") -> Dict[str, Any]:
        """
        Gemini API를 사용하여 참여자들의 성과 분석
        
        Args:
            formatted_text: 포맷된 transcript 텍스트
            stats: 참여자별 통계
            template_override: 이번 분석에만 사용할 템플릿 (선택)
            custom_instructions: 추가 지시사항 (선택)
            
        Returns:
            분석 결과 딕셔너리
        """
        participants = list(stats.keys())
        
        # 실제 사용될 템플릿과 버전 정보 미리 가져오기
        # 커스텀 프롬프트가 있으면 "custom"으로 기록하고 버전은 None
        if self.prompt_config.custom_template:
            template_name = "custom"
            template_version = None
        else:
            template_name = template_override or self.prompt_config.default_template
            # "latest" 문자열 처리
            if self.prompt_config.default_version == "latest":
                template_version = get_template_version(template_name)
            else:
                template_version = self.prompt_config.default_version or get_template_version(template_name)
        
        # 프롬프트 생성
        prompt = self.prompt_config.get_prompt(
            formatted_text,
            participants,
            template_override,
            None,  # version_override는 None (이미 default_version에 설정됨)
            custom_instructions
        )
        
        try:
            # 사용 중인 모델, 템플릿, 버전 정보 출력
            print("🤖 Gemini API로 성과 분석 중...")
            print(f"   모델: {self.model_name}")
            print(f"   템플릿: {template_name}")
            print(f"   버전: {template_version if template_version else 'latest'}")
            if template_override:
                print(f"   (템플릿 오버라이드: {template_override})")
            response = self.model.generate_content(prompt)
            
            # 응답 텍스트 추출
            analysis_text = response.text
            
            result = {
                "status": "success",
                "analysis": analysis_text,
                "participant_stats": stats,
                "template_used": template_name,
                "template_version": template_version,
                "model_used": self.model_name,
                "timestamp": datetime.now().isoformat()
            }
            
            return result
            
        except Exception as e:
            print(f"❌ 분석 중 오류 발생: {str(e)}")
            
            return {
                "status": "error",
                "error": str(e),
                "template_used": template_name,
                "template_version": template_version,
                "model_used": self.model_name,
                "timestamp": datetime.now().isoformat()
            }
    
    def _analyze_single_meeting(self, meeting: Dict, idx: int, total: int,
                                 template_override: str = None,
                                custom_instructions: str = "") -> Dict:
        """
        단일 회의 분석 (내부 메서드)
        
        Args:
            meeting: 회의 문서
            idx: 현재 인덱스 (1부터 시작)
            total: 전체 회의 수
            template_override: 이번 분석에만 사용할 템플릿 (선택)
            custom_instructions: 추가 지시사항 (선택)
            
        Returns:
            분석 결과 딕셔너리 또는 None (분석 실패 시)
        """
        # ... (기존 코드와 동일)
        # 이 메서드는 analyze_meetings에서 호출됨
        pass  # 실제 구현은 analyze_meetings 내부에 있음 (여기서는 생략)

    def analyze_aggregated_meetings(self, meetings: List[Dict], template_name: str = "comprehensive_review", 
                                   custom_instructions: str = "") -> Dict[str, Any]:
        """
        여러 회의를 하나의 텍스트로 합쳐서 종합 분석 (Multi-Meeting Aggregation)
        
        Args:
            meetings: 회의 문서 리스트
            template_name: 사용할 템플릿 이름 (기본값: "comprehensive_review")
            custom_instructions: 추가 지시사항
            
        Returns:
            종합 분석 결과
        """
        if not meetings:
            print("❌ 분석할 회의가 없습니다.")
            return None
            
        print(f"🔄 {len(meetings)}개의 회의를 종합 분석합니다...")
        
        # 1. 텍스트 합치기
        aggregated_transcript = ""
        all_participants = set()
        
        # 날짜순 정렬
        sorted_meetings = sorted(meetings, key=lambda x: x.get('date', datetime.min))
        
        for meeting in sorted_meetings:
            title = meeting.get('title', 'Untitled')
            date = meeting.get('date', 'Unknown Date')
            if isinstance(date, datetime):
                date = date.strftime('%Y-%m-%d')
                
            transcript = meeting.get('transcript', '')
            
            # 참여자 수집
            if 'participants' in meeting:
                all_participants.update(meeting['participants'])
            else:
                # transcript에서 추출 시도
                extracted = self._extract_participants_from_transcript(transcript)
                all_participants.update(extracted)
                
            aggregated_transcript += f"\n\n=== Meeting: {title} ({date}) ===\n\n"
            aggregated_transcript += transcript
            
        # 2. 프롬프트 생성
        participants_list = sorted(list(all_participants))
        
        # 템플릿 버전 확인
        template_version = get_template_version(template_name)
        
        # 프롬프트 설정 업데이트 (일시적)
        original_template = self.prompt_config.default_template
        self.prompt_config.default_template = template_name
        
        try:
            prompt = self.prompt_config.get_prompt(
                aggregated_transcript,
                participants_list,
                template_name,
                None,
                custom_instructions
            )
            
            # 3. 분석 요청
            print(f"🤖 Gemini API로 종합 분석 중... (템플릿: {template_name})")
            response = self.model.generate_content(prompt)
            
            result = {
                "status": "success",
                "analysis": response.text,
                "meeting_count": len(meetings),
                "meeting_titles": [m.get('title') for m in sorted_meetings],
                "date_range": {
                    "start": sorted_meetings[0].get('date'),
                    "end": sorted_meetings[-1].get('date')
                },
                "participants": participants_list,
                "template_used": template_name,
                "template_version": template_version,
                "model_used": self.model_name,
                "timestamp": datetime.now().isoformat()
            }
            
            return result
            
        except Exception as e:
            print(f"❌ 종합 분석 중 오류 발생: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }
        finally:
            # 프롬프트 설정 복구
            self.prompt_config.default_template = original_template
        print(f"\n{'='*60}")
        print(f"📋 회의 {idx}/{total} 분석 중: {meeting.get('title', 'N/A')}")
        print(f"{'='*60}")
        
        # Transcript 가져오기
        transcript = meeting.get('transcript', '')
        
        if not transcript:
            print("⚠️  Transcript가 없습니다. 다음 회의로 넘어갑니다.")
            return None
        
        # Transcript 파싱
        print("📝 Transcript 파싱 중...")
        parsed_transcript = self.parse_transcript(transcript)
        
        if not parsed_transcript:
            print("⚠️  Transcript 파싱 실패. 형식을 확인해주세요.")
            return None
        
        print(f"✓ {len(parsed_transcript)}개의 발언을 파싱했습니다.")
        
        # 참여자별 통계 추출
        stats = self.extract_participant_stats(parsed_transcript)
        participants = list(stats.keys())
        
        print(f"✓ 참여자 {len(participants)}명: {', '.join(participants)}")
        
        # 분석용 텍스트 포맷팅
        formatted_text = self.format_transcript_for_analysis(meeting, parsed_transcript, stats)
        
        # 성과 분석
        analysis_result = self.analyze_participant_performance(
            formatted_text, 
            stats,
            template_override,
            custom_instructions
        )
        
        # total_statements를 analysis_result에 추가
        analysis_result['total_statements'] = len(parsed_transcript)
        
        # 결과 저장
        # analysis_result에 이미 template_used, template_version, model_used, participant_stats, total_statements가 포함되어 있으므로 중복 저장하지 않음
        result = {
            "meeting_id": str(meeting.get('_id', '')),
            "meeting_title": meeting.get('title', 'N/A'),
            "meeting_date": meeting.get('date', 'N/A'),
            "participants": participants,  # 참여자 목록은 최상위에 유지 (편의성)
            "analysis": analysis_result
        }
        
        print("✅ 분석 완료!")
        return result
    
    def analyze_multiple_meetings(self, filters: Dict[str, Any] = None,
                                 template_override: str = None,
                                 custom_instructions: str = "") -> List[Dict]:
        """
        MongoDB 쿼리를 이용하여 여러 회의 transcript를 한번에 분석
        
        Args:
            filters: MongoDB 쿼리 필터
            template_override: 이번 분석에만 사용할 템플릿 (선택)
            custom_instructions: 추가 지시사항 (선택)
            
        Returns:
            각 회의별 분석 결과 리스트
        """
        meetings = self.fetch_meeting_records(filters)
        return self.analyze_meetings(meetings, template_override, custom_instructions)
    
    def analyze_meetings(self, meetings: Union[List[Dict], Dict],
                        template_override: str = None,
                        custom_instructions: str = "") -> List[Dict]:
        """
        이미 fetch된 회의 데이터를 분석
        
        Args:
            meetings: 이미 fetch된 회의 문서 리스트 또는 단일 회의 문서
            template_override: 이번 분석에만 사용할 템플릿 (선택)
            custom_instructions: 추가 지시사항 (선택)
            
        Returns:
            각 회의별 분석 결과 리스트 (단일 meeting인 경우에도 리스트로 반환)
        """
        # 단일 meeting 객체인 경우 리스트로 변환
        if isinstance(meetings, dict):
            meetings = [meetings]
        
        results = []
        
        for idx, meeting in enumerate(meetings, 1):
            result = self._analyze_single_meeting(
                meeting, idx, len(meetings),
                template_override,
                custom_instructions
            )
            
            if result:
                results.append(result)
        
        return results
    
    def save_analysis_to_mongodb(self, analysis_results: List[Dict], 
                                 output_collection_name: str = "meeting_analysis",
                                 output_database_name: str = None):
        """
        분석 결과를 MongoDB에 저장
        
        Args:
            analysis_results: 분석 결과 리스트
            output_collection_name: 결과를 저장할 컬렉션 이름 (기본값: "meeting_analysis")
            output_database_name: 결과를 저장할 데이터베이스 이름 (기본값: None, 초기화 시 지정한 데이터베이스 사용)
        """
        # 데이터베이스 선택 (지정되지 않으면 초기화 시 지정한 데이터베이스 사용)
        if output_database_name:
            output_db = self.client[output_database_name]
        else:
            output_db = self.db
        
        output_collection = output_db[output_collection_name]
        
        if analysis_results:
            result = output_collection.insert_many(analysis_results)
            db_name = output_database_name or self.db.name
            print(f"\n💾 {len(result.inserted_ids)}개의 분석 결과를 '{db_name}.{output_collection_name}' 컬렉션에 저장했습니다.")
        else:
            print("\n⚠️  저장할 분석 결과가 없습니다.")
    
    def print_analysis_summary(self, analysis_results: List[Dict]):
        """
        분석 결과 요약 출력
        
        Args:
            analysis_results: 분석 결과 리스트
        """
        print("\n" + "="*80)
        print("📊 분석 결과 요약")
        print("="*80)
        
        for result in analysis_results:
            print(f"\n회의: {result['meeting_title']}")
            print(f"날짜: {result['meeting_date']}")
            analysis = result.get('analysis', {})
            print(f"총 발언 수: {analysis.get('total_statements', 'N/A')}개")
            print(f"참여자: {', '.join(result['participants'])}")
            
            print(f"\n참여자별 통계:")
            analysis = result.get('analysis', {})
            participant_stats = analysis.get('participant_stats', {})
            for speaker, stats in participant_stats.items():
                print(f"  {speaker}: {stats['speak_count']}회 발언, {stats['total_words']}단어")
            
            print(f"\n성과 분석:")
            print(analysis.get('analysis', 'N/A'))
            print("-" * 80)
    
    def close(self):
        """MongoDB 연결 종료"""
        self.client.close()
        print("\n🔒 MongoDB 연결을 종료했습니다.")


def main():
    """
    메인 실행 함수
    """
    # 환경 변수에서 설정 읽기
    MONGODB_HOST = os.getenv('MONGODB_HOST', 'localhost')
    MONGODB_PORT = int(os.getenv('MONGODB_PORT', '27017'))
    MONGODB_USERNAME = os.getenv('MONGODB_USERNAME')
    MONGODB_PASSWORD = os.getenv('MONGODB_PASSWORD')
    MONGODB_AUTH_DATABASE = os.getenv('MONGODB_AUTH_DATABASE')
    MONGODB_URI = os.getenv('MONGODB_URI')  # URI가 직접 제공되면 우선 사용
    
    DATABASE_NAME = os.getenv('DATABASE_NAME', 'company_db')
    COLLECTION_NAME = os.getenv('COLLECTION_NAME', 'meeting_transcripts')
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', 'your-gemini-api-key-here')
    
    print("🚀 회의 Transcript 성과 분석 시작")
    print(f"Database: {DATABASE_NAME}")
    print(f"Collection: {COLLECTION_NAME}")
    if MONGODB_URI:
        print(f"MongoDB URI: {MONGODB_URI[:20]}...")  # 보안을 위해 일부만 표시
    else:
        print(f"MongoDB Host: {MONGODB_HOST}:{MONGODB_PORT}")
        if MONGODB_USERNAME:
            print(f"MongoDB User: {MONGODB_USERNAME}")
            print(f"Auth Database: {MONGODB_AUTH_DATABASE or 'admin'}")
    
    # 분석기 초기화
    analyzer = MeetingPerformanceAnalyzer(
        database_name=DATABASE_NAME,
        collection_name=COLLECTION_NAME,
        gemini_api_key=GEMINI_API_KEY,
        mongodb_host=MONGODB_HOST,
        mongodb_port=MONGODB_PORT,
        mongodb_username=MONGODB_USERNAME,
        mongodb_password=MONGODB_PASSWORD,
        mongodb_auth_database=MONGODB_AUTH_DATABASE,
        mongodb_uri=MONGODB_URI
    )
    
    try:
        # 필터 설정 (예: 최근 30일 회의만 분석)
        # from datetime import datetime, timedelta
        # filters = {
        #     'date': {'$gte': datetime.now() - timedelta(days=30)}
        # }
        
        # 모든 transcript 분석
        filters = {}
        
        # 분석 실행
        analysis_results = analyzer.analyze_multiple_meetings(filters)
        
        # 결과 출력
        analyzer.print_analysis_summary(analysis_results)
        
        # MongoDB에 결과 저장
        analyzer.save_analysis_to_mongodb(analysis_results)
        
    except Exception as e:
        print(f"❌ 오류 발생: {str(e)}")
    
    finally:
        # 연결 종료
        analyzer.close()


if __name__ == "__main__":
    main()
