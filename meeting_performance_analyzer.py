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

            # Thomas Shin 관련 변형들
            "Geonwoo Shin": "Thomas Shin",
            
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
    
    def _parse_daily_report_analysis(self, analysis_text: str, participants: List[str]) -> Dict[str, Any]:
        """
        daily_report 분석 텍스트를 구조화된 데이터로 파싱
        
        Args:
            analysis_text: 마크다운 형식의 분석 텍스트
            participants: 참여자 이름 리스트
            
        Returns:
            구조화된 분석 데이터 딕셔너리
        """
        import re
        
        result = {
            "summary": {},
            "participants": []
        }
        
        # 1. 하루의 회의 내용 요약 파싱
        summary_text = None
        # "## 하루의 회의 내용 요약" 또는 "## YYYY년 MM월 DD일 일간 업무 보고서" 형식 모두 지원
        # 첫 번째 ## 섹션을 찾되, 참여자 섹션(## 참여자명) 전까지의 내용을 가져옴
        summary_match = None
        
        # 먼저 "하루의 회의 내용 요약" 형식 시도
        # 참여자 섹션(## 참여자명) 또는 종합 비교(## 종합 비교) 전까지의 내용을 가져옴
        summary_match = re.search(r'## 하루의 회의 내용 요약\s*\n(.*?)(?=\n## [A-Z가-힣]|\n## 종합 비교|\Z)', analysis_text, re.DOTALL)
        
        # 없으면 날짜 형식 시도 (## YYYY년 MM월 DD일 일간 업무 보고서)
        if not summary_match:
            summary_match = re.search(r'## \d{4}년 \d{1,2}월 \d{1,2}일 일간 업무 보고서\s*\n(.*?)(?=\n## [A-Z가-힣]|\n## 종합 비교|\Z)', analysis_text, re.DOTALL)
        
        # 그래도 없으면 첫 번째 ## 섹션 전체를 가져옴
        # "전체 회의 개요"가 포함된 첫 번째 ## 섹션을 요약 섹션으로 간주
        if not summary_match:
            # 첫 번째 ## 섹션 찾기 (두 번째 ## 섹션 전까지)
            # 두 번째 ## 섹션은 참여자명(## NAME)이거나 종합 비교일 수 있음
            first_section_match = re.search(r'## [^\n]+\s*\n(.*?)(?=\n## [A-Z가-힣]|\n## 종합 비교|\Z)', analysis_text, re.DOTALL)
            if first_section_match:
                # "전체 회의 개요" 또는 "주제별 회의 내용 분류"가 포함되어 있으면 요약 섹션으로 간주
                section_content = first_section_match.group(0)
                if '전체 회의 개요' in section_content or '주제별 회의 내용 분류' in section_content:
                    summary_match = first_section_match
        
        if summary_match:
            summary_text = summary_match.group(1)
        else:
            # 파싱 실패 시 첫 번째 줄만 확인하여 디버깅
            first_lines = analysis_text.split('\n')[:5]
            print(f"⚠️  요약 섹션 파싱 실패. 첫 5줄: {first_lines}")
        
        if summary_text:
            # 전체 회의 개요
            overview_match = re.search(r'### 전체 회의 개요\s*\n(.*?)(?=\n### |\Z)', summary_text, re.DOTALL)
            if overview_match:
                overview_text = overview_match.group(1)
                result["summary"]["overview"] = {
                    "meeting_count": self._extract_value(overview_text, r'총 회의 수:\s*(\d+)'),
                    "total_time": self._extract_value(overview_text, r'총 회의 시간:\s*([^\n]+)'),
                    "main_topics": self._extract_list(overview_text, r'주요 논의 주제:\s*([^\n]+)')
                }
            
            # 주제별 회의 내용 분류 파싱
            topics_section_match = re.search(r'### 주제별 회의 내용 분류\s*\n(.*?)(?=\n### 핵심 결정사항|\n### 주요 성과|\n### 공통 이슈|\Z)', summary_text, re.DOTALL)
            if topics_section_match:
                topics_text = topics_section_match.group(1)
                # 각 주제별 섹션 파싱 (#### [주제명] 또는 #### 주제명 형식 모두 지원)
                # 먼저 대괄호가 있는 형식 시도
                topic_pattern = r'####\s*(?:\[([^\]]+)\]|([^\n]+))\s*\n(.*?)(?=\n####|\Z)'
                topic_matches = re.finditer(topic_pattern, topics_text, re.DOTALL)
                
                topics_list = []
                for topic_match in topic_matches:
                    # 대괄호가 있으면 group(1), 없으면 group(2) 사용
                    topic_name = topic_match.group(1) if topic_match.group(1) else topic_match.group(2)
                    topic_content = topic_match.group(3)
                    if topic_name:
                        topic_name = topic_name.strip()
                    
                    topic_data = {
                        "topic": topic_name,
                        "related_meetings": [],
                        "key_discussions": [],
                        "key_decisions": [],
                        "progress": [],
                        "issues": []
                    }
                    
                    # 관련 회의 추출
                    meetings_match = re.search(r'\*\*관련 회의\*\*:\s*([^\n]+)', topic_content)
                    if meetings_match:
                        meetings_str = meetings_match.group(1)
                        topic_data["related_meetings"] = [m.strip() for m in meetings_str.split(',')]
                    
                    # 주요 논의 내용 추출
                    discussions_match = re.search(r'\*\*주요 논의 내용\*\*:\s*\n(.*?)(?=\n\*\*|\Z)', topic_content, re.DOTALL)
                    if discussions_match:
                        discussions_text = discussions_match.group(1)
                        topic_data["key_discussions"] = self._extract_bullet_list(discussions_text)
                    
                    # 핵심 결정사항 추출
                    decisions_match = re.search(r'\*\*핵심 결정사항\*\*:\s*\n(.*?)(?=\n\*\*|\Z)', topic_content, re.DOTALL)
                    if decisions_match:
                        decisions_text = decisions_match.group(1)
                        topic_data["key_decisions"] = self._extract_bullet_list(decisions_text)
                    
                    # 진전 사항 추출
                    progress_match = re.search(r'\*\*진전 사항\*\*:\s*\n(.*?)(?=\n\*\*|\Z)', topic_content, re.DOTALL)
                    if progress_match:
                        progress_text = progress_match.group(1)
                        topic_data["progress"] = self._extract_bullet_list(progress_text)
                    
                    # 이슈 및 블로커 추출
                    issues_match = re.search(r'\*\*이슈 및 블로커\*\*:\s*\n(.*?)(?=\n\*\*|\Z)', topic_content, re.DOTALL)
                    if issues_match:
                        issues_text = issues_match.group(1)
                        topic_data["issues"] = self._extract_bullet_list(issues_text)
                    
                    topics_list.append(topic_data)
                
                result["summary"]["topics"] = topics_list
            
            # 핵심 결정사항 (전체 요약)
            decisions_match = re.search(r'### 핵심 결정사항 \(전체 요약\)\s*\n(.*?)(?=\n### |\Z)', summary_text, re.DOTALL)
            if not decisions_match:
                # 하위 호환성을 위해 괄호 없는 버전도 시도
                decisions_match = re.search(r'### 핵심 결정사항\s*\n(.*?)(?=\n### |\Z)', summary_text, re.DOTALL)
            if decisions_match:
                decisions_text = decisions_match.group(1)
                result["summary"]["key_decisions"] = self._extract_bullet_list(decisions_text)
            
            # 주요 성과 및 진전 (전체 요약)
            achievements_match = re.search(r'### 주요 성과 및 진전 \(전체 요약\)\s*\n(.*?)(?=\n### |\Z)', summary_text, re.DOTALL)
            if not achievements_match:
                # 하위 호환성을 위해 괄호 없는 버전도 시도
                achievements_match = re.search(r'### 주요 성과 및 진전\s*\n(.*?)(?=\n### |\Z)', summary_text, re.DOTALL)
            if achievements_match:
                achievements_text = achievements_match.group(1)
                result["summary"]["major_achievements"] = self._extract_bullet_list(achievements_text)
            
            # 공통 이슈 및 블로커 (전체 요약)
            issues_match = re.search(r'### 공통 이슈 및 블로커 \(전체 요약\)\s*\n(.*?)(?=\n### |\Z)', summary_text, re.DOTALL)
            if not issues_match:
                # 하위 호환성을 위해 괄호 없는 버전도 시도
                issues_match = re.search(r'### 공통 이슈 및 블로커\s*\n(.*?)(?=\n### |\Z)', summary_text, re.DOTALL)
            if issues_match:
                issues_text = issues_match.group(1)
                result["summary"]["common_issues"] = self._extract_bullet_list(issues_text)
        
        # 2. 각 참여자별 분석 파싱
        for participant in participants:
            # 참여자 섹션 찾기 (## 참여자명 형식)
            participant_pattern = rf'##\s+{re.escape(participant)}\s*\n(.*?)(?=\n##\s+[^#]|\n#\s+종합 비교|\Z)'
            participant_match = re.search(participant_pattern, analysis_text, re.DOTALL)
            
            if participant_match:
                participant_text = participant_match.group(1)
                participant_analysis = {
                    "name": participant,
                    "speaking_time": None,
                    "speaking_percentage": None,
                    "key_activities": [],
                    "progress": [],
                    "issues": [],
                    "action_items": [],
                    "collaboration": []
                }
                
                # 개인별 발언 시간
                speaking_time_match = re.search(r'### 개인별 발언 시간\s*\n-?\s*([^\n]+)', participant_text)
                if speaking_time_match:
                    time_text = speaking_time_match.group(1)
                    time_match = re.search(r'(\d+:\d+:\d+)\s*\(전체의\s*([\d.]+)%\)', time_text)
                    if time_match:
                        participant_analysis["speaking_time"] = time_match.group(1)
                        participant_analysis["speaking_percentage"] = float(time_match.group(2))
                
                # 오늘의 주요 활동
                activities_match = re.search(r'### 오늘의 주요 활동\s*\n(.*?)(?=\n### |\Z)', participant_text, re.DOTALL)
                if activities_match:
                    activities_text = activities_match.group(1)
                    participant_analysis["key_activities"] = self._extract_bullet_list(activities_text)
                
                # 진행 상황 및 성과
                progress_match = re.search(r'### 진행 상황 및 성과\s*\n(.*?)(?=\n### |\Z)', participant_text, re.DOTALL)
                if progress_match:
                    progress_text = progress_match.group(1)
                    participant_analysis["progress"] = self._extract_bullet_list(progress_text)
                
                # 이슈 및 블로커
                issues_match = re.search(r'### 이슈 및 블로커\s*\n(.*?)(?=\n### |\Z)', participant_text, re.DOTALL)
                if issues_match:
                    issues_text = issues_match.group(1)
                    participant_analysis["issues"] = self._extract_bullet_list(issues_text)
                
                # 다음 액션 아이템
                action_items_match = re.search(r'### 다음 액션 아이템\s*\n(.*?)(?=\n### |\Z)', participant_text, re.DOTALL)
                if action_items_match:
                    action_items_text = action_items_match.group(1)
                    participant_analysis["action_items"] = self._extract_checkbox_list(action_items_text)
                
                # 협업 현황
                collaboration_match = re.search(r'### 협업 현황\s*\n(.*?)(?=\n### |\Z)', participant_text, re.DOTALL)
                if collaboration_match:
                    collaboration_text = collaboration_match.group(1)
                    participant_analysis["collaboration"] = self._extract_bullet_list(collaboration_text)
                
                result["participants"].append(participant_analysis)
        
        return result
    
    def _parse_daily_report_json(self, analysis_text: str, participants: List[str]) -> Dict[str, Any]:
        """
        daily_report JSON 형식 분석 텍스트를 구조화된 데이터로 파싱
        
        Args:
            analysis_text: JSON 형식의 분석 텍스트
            participants: 참여자 이름 리스트
            
        Returns:
            구조화된 분석 데이터 딕셔너리
        """
        import json
        import re
        
        # JSON 추출 시도 (마크다운 코드 블록이나 다른 텍스트가 있을 수 있음)
        json_text = analysis_text.strip()
        
        # 코드 블록 제거 (```json ... ``` 또는 ``` ... ```)
        json_text = re.sub(r'```(?:json)?\s*\n?(.*?)\n?```', r'\1', json_text, flags=re.DOTALL)
        
        # JSON 객체 찾기 (중괄호로 시작하고 끝나는 부분)
        json_match = re.search(r'\{.*\}', json_text, re.DOTALL)
        if json_match:
            json_text = json_match.group(0)
        
        try:
            # JSON 파싱
            parsed_data = json.loads(json_text)
            
            # 스키마 검증 및 정규화
            result = {
                "summary": {},
                "participants": []
            }
            
            # summary 파싱
            if "summary" in parsed_data:
                summary = parsed_data["summary"]
                result["summary"] = {
                    "overview": summary.get("overview", {}),
                    "topics": summary.get("topics", []),
                    "key_decisions": summary.get("key_decisions", []),
                    "major_achievements": summary.get("major_achievements", []),
                    "common_issues": summary.get("common_issues", [])
                }
            
            # participants 파싱 (participants_analysis도 지원 - 하위 호환성)
            if "participants" in parsed_data:
                result["participants"] = parsed_data["participants"]
            elif "participants_analysis" in parsed_data:
                # 하위 호환성: participants_analysis도 지원
                result["participants"] = parsed_data["participants_analysis"]
            else:
                # participants가 없으면 빈 리스트 반환
                result["participants"] = []
            
            # 빈 구조인지 확인 (실제 데이터가 있는지 체크)
            has_data = (
                (result.get('summary', {}) and 
                 (result['summary'].get('overview', {}) or 
                  (result['summary'].get('topics') and len(result['summary']['topics']) > 0) or
                  (result['summary'].get('key_decisions') and len(result['summary']['key_decisions']) > 0) or
                  (result['summary'].get('major_achievements') and len(result['summary']['major_achievements']) > 0) or
                  (result['summary'].get('common_issues') and len(result['summary']['common_issues']) > 0))) or
                (result.get('participants') and len(result['participants']) > 0)
            )
            
            # 실제 데이터가 있으면 반환, 없으면 None 반환 (원본 텍스트 유지)
            if has_data:
                return result
            else:
                print(f"⚠️  JSON 파싱은 성공했지만 빈 구조입니다. 원본 텍스트를 유지합니다.")
                return None
            
        except json.JSONDecodeError as e:
            print(f"⚠️  JSON 파싱 실패: {str(e)}")
            print(f"   원본 텍스트 (처음 500자): {analysis_text[:500]}")
            # JSON 파싱 실패 시 None 반환 (원본 텍스트 유지)
            return None
    
    def _extract_value(self, text: str, pattern: str) -> Optional[str]:
        """정규식으로 값 추출"""
        match = re.search(pattern, text)
        return match.group(1) if match else None
    
    def _extract_list(self, text: str, pattern: str) -> List[str]:
        """정규식으로 리스트 추출 (쉼표로 구분)"""
        match = re.search(pattern, text)
        if match:
            items = [item.strip() for item in match.group(1).split(',')]
            return items
        return []
    
    def _extract_bullet_list(self, text: str) -> List[str]:
        """마크다운 불릿 리스트 추출"""
        items = []
        for line in text.split('\n'):
            line = line.strip()
            if line.startswith('- '):
                items.append(line[2:].strip())
            elif line.startswith('* '):
                items.append(line[2:].strip())
        return items
    
    def _extract_checkbox_list(self, text: str) -> List[str]:
        """마크다운 체크박스 리스트 추출"""
        items = []
        for line in text.split('\n'):
            line = line.strip()
            if line.startswith('- [ ]') or line.startswith('- [x]'):
                items.append(line[5:].strip())
        return items
    
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
        
    def fetch_meeting_records(self, filters: Dict[str, Any] = None, limit: int = 0, sort: List[tuple] = None) -> List[Dict]:
        """
        MongoDB에서 회의 transcript 데이터 가져오기
        Google Drive 스키마 형식도 자동으로 처리
        
        Args:
            filters: MongoDB 쿼리 필터 (예: {'date': {'$gte': start_date}})
                     'date' 필터는 자동으로 'createdTime' 필드에도 적용됨
            limit: 가져올 문서 최대 개수 (0이면 제한 없음)
            sort: 정렬 기준 (예: [('date', -1)])
            
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
        
        cursor = self.collection.find(mongo_filters)
        
        if sort:
            cursor = cursor.sort(sort)
            
        if limit > 0:
            cursor = cursor.limit(limit)
            
        meetings = list(cursor)
        
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
  - 발언 시간대: {f"{stat['timestamps'][0]} ~ {stat['timestamps'][-1]}" if stat.get('timestamps') else "N/A"}
"""
        
        formatted_text += "\n=== 전체 대화 내용 ===\n"
        for entry in parsed_transcript:
            formatted_text += f"[{entry['timestamp']}] {entry['speaker']}: {entry['text']}\n"
        
        return formatted_text
    
    def analyze_participant_performance(self, formatted_text: str, stats: Dict, 
                                       template_override: str = None,
                                       custom_instructions: str = "",
                                       version: str = None) -> Dict[str, Any]:
        """
        Gemini API를 사용하여 참여자들의 성과 분석
        
        Args:
            formatted_text: 포맷된 transcript 텍스트
            stats: 참여자별 통계
            template_override: 이번 분석에만 사용할 템플릿 (선택)
            custom_instructions: 추가 지시사항 (선택)
            version: 사용할 템플릿 버전 (None이면 최신 버전)
            
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
            
            # 버전 결정 로직:
            # 1. 인자로 전달된 version이 있으면 최우선 사용
            # 2. 없으면 config의 default_version 사용 ("latest"면 None으로 처리하여 최신 버전 사용)
            if version:
                template_version = version
            elif self.prompt_config.default_version == "latest":
                template_version = get_template_version(template_name)
            else:
                template_version = self.prompt_config.default_version or get_template_version(template_name)
        
        # 프롬프트 생성
        prompt = self.prompt_config.get_prompt(
            formatted_text,
            participants,
            template_override,
            version,  # 인자로 받은 버전을 전달 (None이면 config의 default_version 사용됨)
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

    def analyze_aggregated_meetings(self, meetings: List[Dict], template_name: str = "comprehensive_review", 
                                   custom_instructions: str = "",
                                   version: str = None) -> Dict[str, Any]:
        """
        여러 회의를 하나의 텍스트로 합쳐서 종합 분석 (Multi-Meeting Aggregation)
        
        Args:
            meetings: 회의 문서 리스트
            template_name: 사용할 템플릿 이름 (기본값: "comprehensive_review")
            custom_instructions: 추가 지시사항
            version: 사용할 템플릿 버전 (None이면 최신 버전)
            
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
        global_stats = defaultdict(lambda: {"speak_count": 0, "total_words": 0})
        
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
            
            # 통계 계산을 위해 파싱
            parsed_transcript = self.parse_transcript(transcript)
            meeting_stats = self.extract_participant_stats(parsed_transcript)
            
            for speaker, stats in meeting_stats.items():
                global_stats[speaker]["speak_count"] += stats["speak_count"]
                global_stats[speaker]["total_words"] += stats["total_words"]
                
            aggregated_transcript += f"\n\n=== Meeting: {title} ({date}) ===\n\n"
            aggregated_transcript += transcript
            
        # 2. 프롬프트 생성
        # 참여자별 통계 정보를 포함한 리스트 생성 (문자열 형식 - 프롬프트용)
        participants_list = []
        # 참여자별 통계 정보를 객체 배열로 생성 (구조화된 데이터용)
        participants_data = []
        total_words_all = sum(s["total_words"] for s in global_stats.values())
        
        sorted_participants = sorted(list(all_participants))
        for p in sorted_participants:
            stats = global_stats.get(p, {"speak_count": 0, "total_words": 0})
            words = stats["total_words"]
            ratio = (words / total_words_all * 100) if total_words_all > 0 else 0
            
            p_info = f"{p} (발언: {stats['speak_count']}회, 단어: {words}개, 비율: {ratio:.1f}%)"
            participants_list.append(p_info)
            
            # 구조화된 참여자 데이터 추가
            participants_data.append({
                "name": p,
                "speak_count": stats["speak_count"],
                "word_count": words,
                "percentage": round(ratio, 1)
            })
        
        # 템플릿 버전 확인
        if version:
            # "latest"인 경우 실제 버전 번호로 변환
            if version == "latest":
                template_version = get_template_version(template_name)
            else:
                template_version = version
        else:
            template_version = get_template_version(template_name)
        
        # 프롬프트 설정 업데이트 (일시적)
        original_template = self.prompt_config.default_template
        self.prompt_config.default_template = template_name
        
        # daily_report 등에서 사용할 날짜 정보 추출
        date_str = None
        if sorted_meetings:
            first_date = sorted_meetings[0].get('date')
            if isinstance(first_date, datetime):
                date_str = first_date.strftime('%Y-%m-%d')
            elif isinstance(first_date, str):
                date_str = first_date
        
        # custom_instructions에서 날짜 추출 시도 (예: "분석 대상 날짜: 2024-12-01")
        if not date_str and custom_instructions:
            import re
            date_match = re.search(r'분석 대상 날짜:\s*(\d{4}-\d{2}-\d{2})', custom_instructions)
            if date_match:
                date_str = date_match.group(1)
        
        # participants_list는 포맷된 문자열 리스트이므로, 순수 참여자 이름 리스트로 변환
        participants_names = sorted_participants if 'sorted_participants' in locals() else [p.split(' (')[0] for p in participants_list]
        
        # custom_instructions에 실제 회의 수 정보 추가 (daily_report 템플릿인 경우)
        enhanced_custom_instructions = custom_instructions
        if template_name == "daily_report":
            meeting_count_info = f"\n\n중요: 실제로 분석된 회의 수는 {len(meetings)}개입니다. '총 회의 수'를 작성할 때는 반드시 이 숫자를 사용하세요."
            enhanced_custom_instructions = (custom_instructions + meeting_count_info) if custom_instructions else meeting_count_info
        
        try:
            prompt = self.prompt_config.get_prompt(
                aggregated_transcript,
                participants_names,  # 순수 참여자 이름 리스트
                template_name,
                version,  # 인자로 받은 버전 사용
                enhanced_custom_instructions,  # 회의 수 정보가 추가된 custom_instructions 사용
                date=date_str,  # 분석 대상 날짜
                meetings_data=aggregated_transcript  # 회의록 데이터
            )
            
            # 3. 분석 요청
            print(f"🤖 Gemini API로 종합 분석 중... (템플릿: {template_name})")
            response = self.model.generate_content(prompt)
            
            # 분석 텍스트 파싱 (daily_report 템플릿인 경우)
            analysis_text = response.text
            structured_analysis = None
            if template_name == "daily_report":
                # 템플릿 버전 확인: 2.0 이상이면 JSON 형식, 그 이하는 마크다운 형식
                try:
                    version_num = float(template_version) if template_version else 0.0
                    if version_num >= 2.0:
                        # JSON 형식 파싱
                        structured_analysis = self._parse_daily_report_json(analysis_text, sorted_participants)
                    else:
                        # 마크다운 형식 파싱 (하위 호환성)
                        structured_analysis = self._parse_daily_report_analysis(analysis_text, sorted_participants)
                except (ValueError, AttributeError):
                    # 버전 파싱 실패 시 마크다운 형식으로 시도
                    structured_analysis = self._parse_daily_report_analysis(analysis_text, sorted_participants)
            
            result = {
                "status": "success",
                "analysis": analysis_text,  # 원본 텍스트 유지 (JSON 또는 마크다운)
                "meeting_count": len(meetings),
                "meeting_titles": [m.get('title') for m in sorted_meetings],
                "date_range": {
                    "start": sorted_meetings[0].get('date'),
                    "end": sorted_meetings[-1].get('date')
                },
                "participants": participants_data,  # 구조화된 객체 배열
                "participants_formatted": participants_list,  # 기존 문자열 형식 (하위 호환성)
                "template_used": template_name,
                "template_version": template_version,
                "model_used": self.model_name,
                "timestamp": datetime.now().isoformat()
            }
            
            # 구조화된 분석 결과가 있으면 추가
            if structured_analysis:
                result["structured_analysis"] = structured_analysis
            
            return result
            
        except Exception as e:
            print(f"❌ 종합 분석 중 오류 발생: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }
        finally:
            # 프롬프트 설정 복원
            self.prompt_config.default_template = original_template
    
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
