"""
빠른 시작 예제 - example_transcript.json 파일을 사용한 분석 데모

###### 로깅 하는법 #####
# # 세션 시작
# script quick_start_output.log

# # 프로그램 실행 (여러 번 입력 가능)
# python quick_start_examples.py

# # 세션 종료
# exit

"""

import json
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# 상위 디렉토리를 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from meeting_performance_analyzer import MeetingPerformanceAnalyzer

# .env 파일에서 환경 변수 로드
load_dotenv()


def get_analyzer(gemini_api_key: str = None):
    """
    분석기 인스턴스 생성 (MongoDB 연결 없이)
    
    Args:
        gemini_api_key: Gemini API 키
        
    Returns:
        MeetingPerformanceAnalyzer 인스턴스
    """
    if gemini_api_key is None:
        gemini_api_key = os.getenv('GEMINI_API_KEY')
        if not gemini_api_key:
            raise ValueError("GEMINI_API_KEY 환경 변수를 설정하거나 인자로 전달해주세요.")
    
    try:
        # MongoDB 연결 없이도 작동하도록 더미 값 사용
        analyzer = MeetingPerformanceAnalyzer(
            gemini_api_key=gemini_api_key,
            database_name="dummy",
            collection_name="dummy",
            mongodb_host="localhost",
            mongodb_port=27017
        )
        return analyzer
    except Exception as e:
        # MongoDB 연결 실패해도 계속 진행
        print(f"⚠️  MongoDB 연결 시도 실패 (무시됨): {e}")
        print("   MongoDB 없이도 분석 기능은 사용 가능합니다.")
        
        # MongoDB 없이도 작동하도록 임시 객체 생성
        import google.generativeai as genai
        from prompt_templates import PromptConfig
        
        genai.configure(api_key=gemini_api_key)
        model_name = os.getenv('GEMINI_MODEL', 'gemini-2.0-flash')
        
        class TempAnalyzer:
            def __init__(self):
                self.model = genai.GenerativeModel(model_name)
                self.model_name = model_name
                self.prompt_config = PromptConfig(default_template="default")
                # MeetingPerformanceAnalyzer의 메서드를 직접 사용하기 위한 임시 인스턴스
                # 실제 MongoDB 연결 없이 메서드만 사용
                self._temp_analyzer = None
            
            def _get_temp_analyzer(self):
                """필요할 때만 임시 analyzer 인스턴스 생성"""
                if self._temp_analyzer is None:
                    # MongoDB 연결 없이 메서드만 사용하기 위해
                    # 실제 인스턴스는 만들지 않고 클래스 메서드를 직접 호출
                    from meeting_performance_analyzer import MeetingPerformanceAnalyzer
                    # 더미 인스턴스 생성 (MongoDB 연결 시도하지만 실패해도 무시)
                    try:
                        self._temp_analyzer = MeetingPerformanceAnalyzer(
                            gemini_api_key=os.getenv('GEMINI_API_KEY', ''),
                            database_name="dummy",
                            collection_name="dummy",
                            mongodb_host="localhost",
                            mongodb_port=27017
                        )
                    except:
                        # MongoDB 연결 실패해도 메서드는 사용 가능
                        pass
                return self._temp_analyzer
            
            def _normalize_document(self, doc):
                """문서 정규화 - MeetingPerformanceAnalyzer 메서드 사용"""
                temp = self._get_temp_analyzer()
                if temp:
                    try:
                        return temp._normalize_document(doc)
                    except:
                        pass
                # MongoDB 연결 실패 시 직접 구현
                normalized = doc.copy()
                if 'title' not in normalized:
                    normalized['title'] = normalized.get('name', 'Untitled Meeting')
                if 'transcript' not in normalized or not normalized.get('transcript'):
                    content = normalized.get('content', '')
                    if content:
                        # 📖 Transcript 섹션 추출
                        import re
                        content = content.replace('\r\n', '\n').replace('\r', '\n')
                        transcript_markers = [r'📖\s*Transcript', r'Transcript', r'TRANSCRIPT']
                        for marker in transcript_markers:
                            pattern = rf'{marker}.*$'
                            match = re.search(pattern, content, re.DOTALL | re.IGNORECASE | re.MULTILINE)
                            if match:
                                transcript_section = match.group(0)
                                lines = transcript_section.split('\n')
                                start_idx = 0
                                for i, line in enumerate(lines):
                                    if re.search(marker, line, re.IGNORECASE):
                                        start_idx = i + 1
                                        if i + 1 < len(lines) and re.match(r'[A-Z][a-z]{2}\s+\d{1,2},\s+\d{4}', lines[i + 1].strip()):
                                            start_idx = i + 2
                                        if start_idx < len(lines) and ' - Transcript' in lines[start_idx]:
                                            start_idx += 1
                                        break
                                normalized['transcript'] = '\n'.join(lines[start_idx:]).strip()
                                break
                        if 'transcript' not in normalized:
                            normalized['transcript'] = content
                    else:
                        normalized['transcript'] = ''
                if 'date' not in normalized or normalized.get('date') is None:
                    from datetime import datetime
                    created_time = normalized.get('createdTime')
                    if created_time:
                        try:
                            if isinstance(created_time, str):
                                time_str = created_time
                                if time_str.endswith('Z'):
                                    time_str = time_str[:-1] + '+00:00'
                                if '.' in time_str:
                                    dot_idx = time_str.index('.')
                                    tz_start = len(time_str)
                                    for char in ['+', '-', 'Z']:
                                        idx = time_str.find(char, dot_idx)
                                        if idx != -1 and idx < tz_start:
                                            tz_start = idx
                                    time_str = time_str[:dot_idx] + time_str[tz_start:]
                                    if time_str.endswith('Z'):
                                        time_str = time_str[:-1] + '+00:00'
                                normalized['date'] = datetime.fromisoformat(time_str)
                            else:
                                normalized['date'] = created_time
                        except:
                            normalized['date'] = datetime.now()
                if 'participants' not in normalized or not normalized.get('participants'):
                    transcript = normalized.get('transcript', '')
                    if transcript:
                        participants = self._extract_participants_simple(transcript)
                        if participants:
                            normalized['participants'] = participants
                return normalized
            
            def _extract_participants_simple(self, transcript):
                """간단한 참여자 추출"""
                import re
                participants = set()
                # [타임스탬프] 발언자: 형식 찾기
                pattern = r'\[?\d{2}:\d{2}:\d{2}\]?\s+([^:]+):'
                matches = re.findall(pattern, transcript)
                for match in matches:
                    speaker = match.strip()
                    if speaker and not any(x in speaker.lower() for x in ['transcription', 'session', 'ended']):
                        participants.add(speaker)
                return sorted(list(participants))
            
            def parse_transcript(self, transcript):
                """Transcript 파싱 - MeetingPerformanceAnalyzer 메서드 사용"""
                temp = self._get_temp_analyzer()
                if temp:
                    try:
                        return temp.parse_transcript(transcript)
                    except:
                        pass
                # 간단한 파싱 구현
                import re
                parsed = []
                lines = transcript.split('\n')
                i = 0
                while i < len(lines):
                    line = lines[i].strip()
                    if not line:
                        i += 1
                        continue
                    # [00:01:23] 발언자: 내용 형식
                    patterns = [
                        r'\[(\d{2}:\d{2}:\d{2})\]\s*([^:]+):\s*(.+)',
                        r'\[(\d{2}:\d{2})\]\s*([^:]+):\s*(.+)',
                        r'^(\d{2}:\d{2}:\d{2})\s+([^:]+):\s*(.+)',
                        r'^(\d{2}:\d{2})\s+([^:]+):\s*(.+)',
                    ]
                    matched = False
                    for pattern in patterns:
                        match = re.match(pattern, line)
                        if match:
                            timestamp, speaker, text = match.groups()
                            speaker = speaker.strip()
                            if speaker and not any(x in speaker.lower() for x in ['transcription', 'session', 'ended']):
                                parsed.append({
                                    "timestamp": timestamp.strip(),
                                    "speaker": speaker,
                                    "text": text.strip()
                                })
                            matched = True
                            break
                    if not matched:
                        # 타임스탬프만 있는 줄 처리
                        timestamp_match = re.match(r'^(\d{2}:\d{2}:\d{2})$|^(\d{2}:\d{2})$', line)
                        if timestamp_match:
                            timestamp = timestamp_match.group(1) or timestamp_match.group(2)
                            i += 1
                            while i < len(lines) and (not lines[i].strip() or lines[i].strip() == ' '):
                                i += 1
                            if i < len(lines):
                                speaker_line = lines[i].strip()
                                speaker_match = re.match(r'^([^:]+):\s*(.+)', speaker_line)
                                if speaker_match:
                                    speaker = speaker_match.group(1).strip()
                                    text = speaker_match.group(2).strip()
                                    if speaker and not any(x in speaker.lower() for x in ['transcription', 'session', 'ended']):
                                        parsed.append({
                                            "timestamp": timestamp.strip(),
                                            "speaker": speaker,
                                            "text": text.strip()
                                        })
                    i += 1
                return parsed
            
            def extract_participant_stats(self, parsed_transcript):
                """참여자 통계 추출"""
                from collections import defaultdict
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
            
            def format_transcript_for_analysis(self, meeting, parsed_transcript, stats):
                """분석용 텍스트 포맷팅"""
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
            
            def analyze_participant_performance(self, formatted_text, stats, template_override, custom_instructions):
                """성과 분석"""
                participants = list(stats.keys())
                prompt = self.prompt_config.get_prompt(
                    formatted_text,
                    participants,
                    template_override,
                    None,  # version_override
                    custom_instructions
                )
                try:
                    response = self.model.generate_content(prompt)
                    template_name = template_override or self.prompt_config.default_template
                    from prompt_templates import get_template_version
                    template_version = get_template_version(template_name)
                    
                    return {
                        "status": "success",
                        "analysis": response.text,
                        "participant_stats": stats,
                        "template_used": template_name,
                        "template_version": template_version,
                        "model_used": self.model_name,
                        "timestamp": datetime.now().isoformat()
                    }
                except Exception as e:
                    return {
                        "status": "error",
                        "error": str(e),
                        "template_used": template_override or "default",
                        "template_version": None,
                        "model_used": self.model_name,
                        "timestamp": datetime.now().isoformat()
                    }
        
        return TempAnalyzer()


def list_json_files():
    """
    현재 디렉토리에서 JSON 파일 목록 반환
    
    Returns:
        JSON 파일 경로 리스트
    """
    json_files = []
    for file in os.listdir('.'):
        if file.endswith('.json') and os.path.isfile(file):
            json_files.append(file)
    return sorted(json_files)


def select_json_file():
    """
    사용자가 JSON 파일을 선택할 수 있도록 함
    
    Returns:
        선택된 JSON 파일 경로 또는 None
    """
    json_files = list_json_files()
    
    if not json_files:
        print("⚠️  현재 디렉토리에 JSON 파일이 없습니다.")
        return None
    
    print("\n📂 사용 가능한 JSON 파일:")
    for i, file in enumerate(json_files, 1):
        print(f"  {i}. {file}")
    
    print("\n" + "-"*60)
    try:
        choice = input(f"사용할 파일 번호를 선택하세요 (1-{len(json_files)}, Enter로 기본값 사용): ").strip()
        
        if not choice:
            # 기본값 사용
            if "example_transcript.json" in json_files:
                return "example_transcript.json"
            else:
                return json_files[0]
        
        choice_num = int(choice)
        
        if choice_num < 1 or choice_num > len(json_files):
            print(f"⚠️  잘못된 번호입니다. 1-{len(json_files)} 사이의 숫자를 입력해주세요.")
            return None
        
        selected_file = json_files[choice_num - 1]
        print(f"\n✅ 선택된 파일: {selected_file}")
        return selected_file
        
    except ValueError:
        print("⚠️  숫자를 입력해주세요.")
        return None
    except KeyboardInterrupt:
        print("\n\n취소되었습니다.")
        return None


def load_json_file(json_file_path: str = "example_transcript.json"):
    """
    JSON 파일 로드
    
    Args:
        json_file_path: JSON 파일 경로
        
    Returns:
        로드된 문서 딕셔너리
    """
    if not os.path.exists(json_file_path):
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {json_file_path}")
    
    print(f"📂 파일 읽는 중: {json_file_path}")
    with open(json_file_path, 'r', encoding='utf-8') as f:
        doc = json.load(f)
    
    print(f"✅ 파일 로드 완료")
    print(f"   제목: {doc.get('name', 'N/A')}")
    print(f"   날짜: {doc.get('createdTime', 'N/A')}")
    
    return doc


def example_1_basic_analysis(json_file: str = None):
    """예제 1: 기본 분석 - JSON 파일 전체 분석"""
    print("="*60)
    print("예제 1: 기본 분석")
    print("="*60)
    
    # JSON 파일 선택 (지정되지 않은 경우)
    if json_file is None:
        json_file = select_json_file()
        if json_file is None:
            return
    
    # JSON 파일 로드
    doc = load_json_file(json_file)
    
    # 분석기 생성
    analyzer = get_analyzer()
    
    # 문서 정규화
    normalized_doc = analyzer._normalize_document(doc)
    
    print(f"\n📝 정규화된 문서:")
    print(f"   제목: {normalized_doc.get('title', 'N/A')}")
    print(f"   날짜: {normalized_doc.get('date', 'N/A')}")
    print(f"   참여자: {normalized_doc.get('participants', [])}")
    
    # Transcript 파싱
    transcript = normalized_doc.get('transcript', '')
    if not transcript:
        print("⚠️  Transcript가 없습니다.")
        return
    
    print(f"\n📊 Transcript 길이: {len(transcript)} 문자")
    print("\n📝 Transcript 파싱 중...")
    parsed_transcript = analyzer.parse_transcript(transcript)
    
    if not parsed_transcript:
        print("⚠️  Transcript 파싱 실패.")
        return
    
    print(f"✓ {len(parsed_transcript)}개의 발언을 파싱했습니다.")
    
    # 참여자별 통계
    stats = analyzer.extract_participant_stats(parsed_transcript)
    participants = list(stats.keys())
    print(f"✓ 참여자 {len(participants)}명: {', '.join(participants)}")
    
    # 분석용 텍스트 포맷팅
    formatted_text = analyzer.format_transcript_for_analysis(normalized_doc, parsed_transcript, stats)
    
    # 성과 분석
    print("\n🤖 Gemini API로 성과 분석 중...")
    analysis_result = analyzer.analyze_participant_performance(
        formatted_text,
        stats,
        template_override=None,
        custom_instructions=""
    )
    
    if analysis_result['status'] == 'success':
        print("\n" + "="*80)
        print("📊 분석 결과")
        print("="*80)
        print(f"\n회의: {normalized_doc.get('title', 'N/A')}")
        print(f"날짜: {normalized_doc.get('date', 'N/A')}")
        print(f"총 발언 수: {len(parsed_transcript)}개")
        print(f"참여자: {', '.join(participants)}")
        
        print(f"\n참여자별 통계:")
        for speaker, stat in stats.items():
            print(f"  {speaker}: {stat['speak_count']}회 발언, {stat['total_words']}단어")
        
        print(f"\n성과 분석:")
        print(analysis_result['analysis'])
        print("-" * 80)
    else:
        print(f"❌ 분석 실패: {analysis_result.get('error', 'Unknown error')}")


def example_2_transcript_parsing(json_file: str = None):
    """예제 2: Transcript 파싱 테스트"""
    print("\n" + "="*60)
    print("예제 2: Transcript 파싱 기능 테스트")
    print("="*60)
    
    # JSON 파일 선택 (지정되지 않은 경우)
    if json_file is None:
        json_file = select_json_file()
        if json_file is None:
            return
    
    # JSON 파일 로드
    doc = load_json_file(json_file)
    
    # 분석기 생성
    analyzer = get_analyzer()
    
    # 문서 정규화
    normalized_doc = analyzer._normalize_document(doc)
    transcript = normalized_doc.get('transcript', '')
    
    if not transcript:
        print("⚠️  Transcript가 없습니다.")
        return
    
    # Transcript 파싱
    parsed = analyzer.parse_transcript(transcript)
    
    print(f"\n✅ {len(parsed)}개의 발언을 파싱했습니다.")
    
    # 통계 추출
    stats = analyzer.extract_participant_stats(parsed)
    participants = list(stats.keys())
    
    # 참여자 목록 출력
    print(f"\n👥 참여자: {len(participants)}명")
    print(f"   {', '.join(participants)}")
    
    print("\n📋 파싱 결과 (처음 10개):")
    for i, entry in enumerate(parsed[:10], 1):
        print(f"  {i}. [{entry['timestamp']}] {entry['speaker']}: {entry['text'][:60]}...")
    
    if len(parsed) > 10:
        print(f"  ... 외 {len(parsed) - 10}개")
    
    print("\n📊 참여자별 통계:")
    for speaker, stat in stats.items():
        print(f"  {speaker}:")
        print(f"    - 발언 횟수: {stat['speak_count']}회")
        print(f"    - 총 단어 수: {stat['total_words']}개")


def example_3_participant_focus(json_file: str = None):
    """예제 3: 특정 참여자 집중 분석"""
    print("\n" + "="*60)
    print("예제 3: 특정 참여자 집중 분석")
    print("="*60)
    
    # JSON 파일 선택 (지정되지 않은 경우)
    if json_file is None:
        json_file = select_json_file()
        if json_file is None:
            return
    
    # JSON 파일 로드
    doc = load_json_file(json_file)
    
    # 분석기 생성
    analyzer = get_analyzer()
    
    # 문서 정규화
    normalized_doc = analyzer._normalize_document(doc)
    transcript = normalized_doc.get('transcript', '')
    
    if not transcript:
        print("⚠️  Transcript가 없습니다.")
        return
    
    # Transcript 파싱
    parsed = analyzer.parse_transcript(transcript)
    stats = analyzer.extract_participant_stats(parsed)
    
    if not stats:
        print("⚠️  참여자 정보를 찾을 수 없습니다.")
        return
    
    # 참여자 목록 표시
    participants = list(stats.keys())
    print(f"\n👥 참여자 목록:")
    for i, participant in enumerate(participants, 1):
        participant_stats = stats[participant]
        print(f"  {i}. {participant} ({participant_stats['speak_count']}회 발언, {participant_stats['total_words']}단어)")
    
    # 사용자 선택
    print("\n" + "-"*60)
    try:
        choice = input(f"분석할 참여자 번호를 선택하세요 (1-{len(participants)}): ").strip()
        choice_num = int(choice)
        
        if choice_num < 1 or choice_num > len(participants):
            print(f"⚠️  잘못된 번호입니다. 1-{len(participants)} 사이의 숫자를 입력해주세요.")
            return
        
        speaker_name = participants[choice_num - 1]
    except ValueError:
        print("⚠️  숫자를 입력해주세요.")
        return
    except KeyboardInterrupt:
        print("\n\n취소되었습니다.")
        return
    
    speaker_stats = stats[speaker_name]
    
    print(f"\n🎯 선택된 참여자: {speaker_name}")
    print(f"   발언 횟수: {speaker_stats['speak_count']}회")
    print(f"   총 단어 수: {speaker_stats['total_words']}개")
    print(f"   평균 단어 수: {speaker_stats['total_words'] / speaker_stats['speak_count']:.1f}단어/발언")
    
    # 해당 참여자의 모든 발언 추출
    speaker_utterances = [entry for entry in parsed if entry['speaker'] == speaker_name]
    
    # 통계 요약
    print(f"\n📊 {speaker_name}님의 발언 통계:")
    print(f"   - 총 발언 수: {len(speaker_utterances)}개")
    if speaker_utterances:
        print(f"   - 첫 발언: {speaker_utterances[0]['timestamp']}")
        print(f"   - 마지막 발언: {speaker_utterances[-1]['timestamp']}")


def example_4_custom_template(json_file: str = None):
    """예제 4: 커스텀 템플릿 사용"""
    print("\n" + "="*60)
    print("예제 4: 커스텀 프롬프트 템플릿 사용")
    print("="*60)
    
    # 사용 가능한 템플릿 목록 표시
    from prompt_templates import PromptTemplates
    
    templates = PromptTemplates.list_templates()
    template_names = list(templates.keys())
    
    print("\n📋 사용 가능한 템플릿:")
    for i, (name, description) in enumerate(templates.items(), 1):
        print(f"  {i}. {name.upper()}")
        print(f"     {description}")
    
    # 템플릿 선택
    print("\n" + "-"*60)
    try:
        choice = input(f"사용할 템플릿 번호를 선택하세요 (1-{len(template_names)}): ").strip()
        choice_num = int(choice)
        
        if choice_num < 1 or choice_num > len(template_names):
            print(f"⚠️  잘못된 번호입니다. 1-{len(template_names)} 사이의 숫자를 입력해주세요.")
            return
        
        selected_template = template_names[choice_num - 1]
        print(f"\n✅ 선택된 템플릿: {selected_template.upper()}")
        print(f"   {templates[selected_template]}")
    except ValueError:
        print("⚠️  숫자를 입력해주세요.")
        return
    except KeyboardInterrupt:
        print("\n\n취소되었습니다.")
        return
    
    # JSON 파일 선택 (지정되지 않은 경우)
    if json_file is None:
        json_file = select_json_file()
        if json_file is None:
            return
    
    # JSON 파일 로드
    doc = load_json_file(json_file)
    
    # 분석기 생성
    analyzer = get_analyzer()
    
    # 문서 정규화
    normalized_doc = analyzer._normalize_document(doc)
    transcript = normalized_doc.get('transcript', '')
    
    if not transcript:
        print("⚠️  Transcript가 없습니다.")
        return
    
    # Transcript 파싱
    parsed_transcript = analyzer.parse_transcript(transcript)
    stats = analyzer.extract_participant_stats(parsed_transcript)
    participants = list(stats.keys())
    
    # MY_SUMMARY 템플릿인 경우 참여자 선택
    custom_instructions = ""
    if selected_template == "my_summary":
        print("\n" + "-"*60)
        print("👤 '내 성과 정리' 템플릿을 사용합니다.")
        print("   분석할 참여자(나)를 선택해주세요:")
        print()
        for i, participant in enumerate(participants, 1):
            participant_stats = stats[participant]
            print(f"  {i}. {participant} ({participant_stats['speak_count']}회 발언, {participant_stats['total_words']}단어)")
        
        try:
            participant_choice = input(f"\n참여자 번호를 선택하세요 (1-{len(participants)}): ").strip()
            participant_num = int(participant_choice)
            
            if participant_num < 1 or participant_num > len(participants):
                print(f"⚠️  잘못된 번호입니다. 1-{len(participants)} 사이의 숫자를 입력해주세요.")
                return
            
            selected_participant = participants[participant_num - 1]
            print(f"\n✅ 선택된 참여자: {selected_participant}")
            
            # 기본 지시사항 설정
            base_instruction = f"이 분석은 '{selected_participant}'의 관점에서 수행됩니다. '{selected_participant}'를 '나' 또는 '내가'로 지칭하며, 이 사람의 기여와 할 일을 중심으로 상세히 분석해주세요."
            
            # 추가 지시사항 입력 (선택사항)
            print("\n" + "-"*60)
            additional_instructions = input("추가 지시사항을 입력하세요 (선택사항, Enter로 건너뛰기): ").strip()
            
            if additional_instructions:
                custom_instructions = f"{base_instruction} 추가로: {additional_instructions}"
            else:
                custom_instructions = base_instruction
        except ValueError:
            print("⚠️  숫자를 입력해주세요.")
            return
        except KeyboardInterrupt:
            print("\n\n취소되었습니다.")
            return
    else:
        # 다른 템플릿인 경우 추가 지시사항 입력 (선택사항)
        print("\n" + "-"*60)
        custom_instructions = input("추가 지시사항을 입력하세요 (선택사항, Enter로 건너뛰기): ").strip()
    
    # 분석용 텍스트 포맷팅
    formatted_text = analyzer.format_transcript_for_analysis(normalized_doc, parsed_transcript, stats)
    
    # 선택한 템플릿으로 분석
    print(f"\n🤖 '{selected_template}' 템플릿으로 분석 중...")
    if custom_instructions:
        print(f"   추가 지시사항: {custom_instructions[:100]}...")
    
    analysis_result = analyzer.analyze_participant_performance(
        formatted_text,
        stats,
        template_override=selected_template,
        custom_instructions=custom_instructions
    )
    
    if analysis_result['status'] == 'success':
        print("\n" + "="*80)
        print("📊 분석 결과")
        print("="*80)
        print(f"사용된 템플릿: {selected_template.upper()}")
        if custom_instructions:
            print(f"추가 지시사항: {custom_instructions}")
        print("-"*80)
        print(analysis_result['analysis'])
        print("="*80)
    else:
        print(f"❌ 분석 실패: {analysis_result.get('error', 'Unknown error')}")


def main():
    """
    메인 함수 - 원하는 예제를 선택하여 실행
    """
    print("🚀 회의 Transcript 분석 예제 프로그램")
    print("\n사용 가능한 예제:")
    print("1. 기본 분석 - 전체 회의 분석")
    print("2. Transcript 파싱 테스트")
    print("3. 특정 참여자 집중 분석")
    print("4. 커스텀 템플릿 사용")
    
    choice = input("\n실행할 예제 번호를 입력하세요 (1-4, 또는 'all'): ")
    
    # 'all'인 경우 한 번만 파일 선택
    if choice.lower() == 'all':
        json_file = select_json_file()
        if json_file is None:
            return
        example_2_transcript_parsing(json_file)  # 먼저 파싱 테스트
        example_1_basic_analysis(json_file)
        example_3_participant_focus(json_file)
        example_4_custom_template(json_file)
    elif choice == '1':
        example_1_basic_analysis()
    elif choice == '2':
        example_2_transcript_parsing()
    elif choice == '3':
        example_3_participant_focus()
    elif choice == '4':
        example_4_custom_template()
    else:
        print("올바른 번호를 입력해주세요.")


if __name__ == "__main__":
    # .env 파일 확인
    env_file = ".env"
    if not os.path.exists(env_file):
        print(f"⚠️  경고: {env_file} 파일을 찾을 수 없습니다.")
        print(f"   {env_file}.example을 참고하여 {env_file} 파일을 생성해주세요.")
        print(f"   예: cp .env.example .env")
        print(f"   그리고 {env_file} 파일에 GEMINI_API_KEY를 설정해주세요.")
    
    # 환경 변수 확인
    if not os.getenv('GEMINI_API_KEY'):
        print("\n⚠️  경고: GEMINI_API_KEY 환경 변수가 설정되지 않았습니다.")
        print("   .env 파일에 다음을 추가해주세요:")
        print("   GEMINI_API_KEY=your-gemini-api-key-here")
    else:
        # JSON 파일 존재 확인
        json_files = list_json_files()
        if not json_files:
            print("\n⚠️  경고: 현재 디렉토리에 JSON 파일이 없습니다.")
            print("   분석할 JSON 파일을 현재 디렉토리에 추가해주세요.")
        else:
            main()
