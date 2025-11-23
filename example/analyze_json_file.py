"""
JSON 파일에서 회의록을 직접 읽어서 분석하는 스크립트
MongoDB 없이 파일을 직접 분석
"""

import json
import os
import sys
from datetime import datetime

# 상위 디렉토리를 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from meeting_performance_analyzer import MeetingPerformanceAnalyzer


def analyze_json_file(json_file_path: str, gemini_api_key: str = None):
    """
    JSON 파일에서 회의록을 읽어서 분석
    
    Args:
        json_file_path: 분석할 JSON 파일 경로
        gemini_api_key: Gemini API 키 (없으면 환경 변수에서 읽음)
    """
    # API 키 설정
    if gemini_api_key is None:
        gemini_api_key = os.getenv('GEMINI_API_KEY')
        if not gemini_api_key:
            raise ValueError("GEMINI_API_KEY 환경 변수를 설정하거나 인자로 전달해주세요.")
    
    # JSON 파일 읽기
    print(f"📂 파일 읽는 중: {json_file_path}")
    with open(json_file_path, 'r', encoding='utf-8') as f:
        doc = json.load(f)
    
    print(f"✅ 파일 로드 완료")
    print(f"   제목: {doc.get('name', 'N/A')}")
    print(f"   날짜: {doc.get('createdTime', 'N/A')}")
    
    # 분석기 생성 (MongoDB 연결 없이 작동하도록 수정)
    # 실제로는 MongoDB를 사용하지 않고 메모리에서만 처리
    try:
        analyzer = MeetingPerformanceAnalyzer(
            mongodb_uri="mongodb://localhost:27017/",  # 사용하지 않음
            database_name="dummy",
            collection_name="dummy",
            gemini_api_key=gemini_api_key
        )
    except Exception as e:
        # MongoDB 연결 실패해도 계속 진행 (실제로 사용하지 않으므로)
        print(f"⚠️  MongoDB 연결 시도 실패 (무시됨): {e}")
        # MongoDB 없이도 작동하도록 임시 객체 생성
        import google.generativeai as genai
        from prompt_templates import PromptConfig
        
        genai.configure(api_key=gemini_api_key)
        
        # 분석기와 유사한 구조의 임시 객체 생성
        class TempAnalyzer:
            def __init__(self):
                self.model = genai.GenerativeModel('gemini-2.0-flash')
                self.prompt_config = PromptConfig(default_template="default")
            
            def _normalize_document(self, doc):
                from meeting_performance_analyzer import MeetingPerformanceAnalyzer
                # 정적 메서드처럼 사용
                temp = MeetingPerformanceAnalyzer.__new__(MeetingPerformanceAnalyzer)
                temp.prompt_config = self.prompt_config
                return temp._normalize_document(doc)
            
            def parse_transcript(self, transcript):
                from meeting_performance_analyzer import MeetingPerformanceAnalyzer
                temp = MeetingPerformanceAnalyzer.__new__(MeetingPerformanceAnalyzer)
                return temp.parse_transcript(transcript)
            
            def extract_participant_stats(self, parsed_transcript):
                from meeting_performance_analyzer import MeetingPerformanceAnalyzer
                temp = MeetingPerformanceAnalyzer.__new__(MeetingPerformanceAnalyzer)
                return temp.extract_participant_stats(parsed_transcript)
            
            def format_transcript_for_analysis(self, meeting, parsed_transcript, stats):
                from meeting_performance_analyzer import MeetingPerformanceAnalyzer
                temp = MeetingPerformanceAnalyzer.__new__(MeetingPerformanceAnalyzer)
                return temp.format_transcript_for_analysis(meeting, parsed_transcript, stats)
            
            def analyze_participant_performance(self, formatted_text, stats, template_override, custom_instructions):
                prompt = self.prompt_config.get_prompt(
                    formatted_text,
                    list(stats.keys()),
                    template_override,
                    custom_instructions
                )
                try:
                    response = self.model.generate_content(prompt)
                    return {
                        "status": "success",
                        "analysis": response.text,
                        "participant_stats": stats,
                        "template_used": template_override or "default",
                        "timestamp": datetime.now().isoformat()
                    }
                except Exception as e:
                    return {
                        "status": "error",
                        "error": str(e),
                        "timestamp": datetime.now().isoformat()
                    }
        
        analyzer = TempAnalyzer()
    
    # 문서 정규화 (Google Drive 스키마 → 회의 분석 형식)
    normalized_doc = analyzer._normalize_document(doc)
    
    print(f"\n📝 정규화된 문서:")
    print(f"   제목: {normalized_doc.get('title', 'N/A')}")
    print(f"   날짜: {normalized_doc.get('date', 'N/A')}")
    print(f"   참여자: {normalized_doc.get('participants', [])}")
    
    # Transcript 가져오기
    transcript = normalized_doc.get('transcript', '')
    if not transcript:
        print("⚠️  Transcript가 없습니다.")
        return
    
    print(f"\n📊 Transcript 길이: {len(transcript)} 문자")
    
    # Transcript 파싱
    print("\n📝 Transcript 파싱 중...")
    parsed_transcript = analyzer.parse_transcript(transcript)
    
    if not parsed_transcript:
        print("⚠️  Transcript 파싱 실패. 형식을 확인해주세요.")
        return
    
    print(f"✓ {len(parsed_transcript)}개의 발언을 파싱했습니다.")
    
    # 참여자별 통계 추출
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
    
    # 결과를 파일로 저장
    output_file = json_file_path.replace('.json', '_analysis.txt')
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("="*80 + "\n")
        f.write("회의록 분석 결과\n")
        f.write("="*80 + "\n\n")
        f.write(f"회의: {normalized_doc.get('title', 'N/A')}\n")
        f.write(f"날짜: {normalized_doc.get('date', 'N/A')}\n")
        f.write(f"총 발언 수: {len(parsed_transcript)}개\n")
        f.write(f"참여자: {', '.join(participants)}\n\n")
        f.write("참여자별 통계:\n")
        for speaker, stat in stats.items():
            f.write(f"  {speaker}: {stat['speak_count']}회 발언, {stat['total_words']}단어\n")
        f.write("\n성과 분석:\n")
        f.write(analysis_result.get('analysis', ''))
        f.write("\n" + "="*80 + "\n")
    
    print(f"\n💾 분석 결과 저장: {output_file}")


def main():
    """메인 함수"""
    import sys
    
    if len(sys.argv) < 2:
        print("사용법: python analyze_json_file.py <json_file_path> [gemini_api_key]")
        print("\n예시:")
        print("  python analyze_json_file.py example_transcript.json")
        print("  python analyze_json_file.py example_transcript.json YOUR_API_KEY")
        sys.exit(1)
    
    json_file = sys.argv[1]
    api_key = sys.argv[2] if len(sys.argv) > 2 else None
    
    if not os.path.exists(json_file):
        print(f"❌ 파일을 찾을 수 없습니다: {json_file}")
        sys.exit(1)
    
    try:
        analyze_json_file(json_file, api_key)
    except Exception as e:
        print(f"❌ 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

