import json
import os
import sys

# 상위 디렉토리를 sys.path에 추가하여 모듈 임포트 가능하게 함
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from dotenv import load_dotenv
from meeting_performance_analyzer import MeetingPerformanceAnalyzer

# .env 파일에서 환경 변수 로드 (상위 디렉토리)
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(dotenv_path=env_path)

def get_analyzer(
        gemini_api_key: str = None,
        database_name: str = None,
        collection_name: str = None,
        mongodb_host: str = None,
        mongodb_port: int = None,
        mongodb_username: str = None,
        mongodb_password: str = None,
        mongodb_auth_database: str = None,
        mongodb_uri: str = None,
        prompt_template: str = "default",
        template_version: str = None,
        custom_prompt: str = None,
        model_name: str = None
    ):
    """
    MeetingPerformanceAnalyzer 인스턴스 생성
    
    Args:
        gemini_api_key: Gemini API 키 (없으면 환경 변수에서 읽음)
        database_name: 데이터베이스 이름 (없으면 환경 변수에서 읽음)
        collection_name: 컬렉션 이름 (없으면 환경 변수에서 읽음)
        mongodb_host: MongoDB 호스트 (없으면 환경 변수에서 읽음)
        mongodb_port: MongoDB 포트 (없으면 환경 변수에서 읽음)
        mongodb_username: MongoDB 사용자명 (없으면 환경 변수에서 읽음)
        mongodb_password: MongoDB 비밀번호 (없으면 환경 변수에서 읽음)
        mongodb_auth_database: 인증 데이터베이스 (없으면 환경 변수에서 읽음)
        mongodb_uri: MongoDB URI (직접 지정 시 위 파라미터보다 우선)
        prompt_template: 프롬프트 템플릿 이름
        template_version: 템플릿 버전 (None이면 최신 버전, "latest"도 가능)
        custom_prompt: 사용자 정의 프롬프트
        model_name: Gemini 모델 이름 (없으면 환경변수 GEMINI_MODEL 또는 기본값 사용)
        
    Returns:
        MeetingPerformanceAnalyzer 인스턴스
    """
    # Gemini API 키
    if gemini_api_key is None:
        gemini_api_key = os.getenv('GEMINI_API_KEY')
        if not gemini_api_key:
            raise ValueError("GEMINI_API_KEY 환경 변수를 설정하거나 인자로 전달해주세요.")
    
    # 데이터베이스 이름
    if database_name is None:
        database_name = os.getenv('DATABASE_NAME', 'company_db')
    
    # 컬렉션 이름
    if collection_name is None:
        collection_name = os.getenv('COLLECTION_NAME', 'meeting_transcripts')
    
    # MongoDB 연결 파라미터 (URI가 없을 때만 사용)
    if mongodb_uri is None:
        if mongodb_host is None:
            mongodb_host = os.getenv('MONGODB_HOST', 'localhost')
        
        if mongodb_port is None:
            mongodb_port = int(os.getenv('MONGODB_PORT', '27017'))
        
        if mongodb_username is None:
            mongodb_username = os.getenv('MONGODB_USERNAME')
        
        if mongodb_password is None:
            mongodb_password = os.getenv('MONGODB_PASSWORD')
        
        if mongodb_auth_database is None:
            mongodb_auth_database = os.getenv('MONGODB_AUTH_DATABASE')
    else:
        # URI가 직접 제공된 경우 환경 변수에서 읽기
        mongodb_uri = os.getenv('MONGODB_URI', mongodb_uri)
    
    # 모델 이름 (환경변수에서 읽기)
    if model_name is None:
        model_name = os.getenv('GEMINI_MODEL')
    
    # MeetingPerformanceAnalyzer 생성
    analyzer = MeetingPerformanceAnalyzer(
        gemini_api_key=gemini_api_key,
        database_name=database_name,
        collection_name=collection_name,
        model_name=model_name,
        mongodb_host=mongodb_host,
        mongodb_port=mongodb_port,
        mongodb_username=mongodb_username,
        mongodb_password=mongodb_password,
        mongodb_auth_database=mongodb_auth_database,
        mongodb_uri=mongodb_uri,
        prompt_template=prompt_template,
        template_version=template_version,
        custom_prompt=custom_prompt
    )
    return analyzer


def build_analyzer(template_name: str = "default", template_version: str = "latest"):
    #Gemini API 키
    GEMENI_API_KEY=os.getenv("GEMINI_API_KEY")
    GEMINI_MODEL=os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    #MongoDB Connection Info
    MONGODB_HOST = os.getenv("MONGODB_HOST")
    MONGODB_PORT = int(os.getenv("MONGODB_PORT", 27017))
    MONGODB_USERNAME = os.getenv("MONGODB_USERNAME")
    MONGODB_PASSWORD = os.getenv("MONGODB_PASSWORD")
    MONGODB_AUTH_DATABASE=os.getenv("MONGODB_AUTH_DATABASE")

    #Target Database and Collection
    DATABASE_NAME = os.getenv("DATABASE_NAME")
    COLLECTION_NAME = os.getenv("COLLECTION_NAME")

    #Prompt Template (파라미터로 받은 template_name 사용)
    # 가능한 값: ["default", "my_summary", "team_collaboration", "action_items", "knowledge_base", "decision_log"]
    # template_version: ["latest", "v1", "v2", "v3"]
    # CUSTOM_PROMPT = None


    #Get Analyzer
    analyzer = get_analyzer(
        gemini_api_key=GEMENI_API_KEY,
        model_name=GEMINI_MODEL,
        database_name=DATABASE_NAME,
        collection_name=COLLECTION_NAME,
        mongodb_host=MONGODB_HOST,
        mongodb_port=MONGODB_PORT,
        mongodb_username=MONGODB_USERNAME,
        mongodb_password=MONGODB_PASSWORD,
        mongodb_auth_database=MONGODB_AUTH_DATABASE,
        prompt_template=template_name,  # 파라미터로 받은 template_name 사용
        template_version=template_version,  # 파라미터로 받은 template_version 사용
        # custom_prompt=CUSTOM_PROMPT
    )
    return analyzer

def main():
    # template_keys = ["default", "team_collaboration", "action_items", "knowledge_base", "decision_log"]
    template_keys = ["team_collaboration", "action_items", "knowledge_base", "decision_log", "quick_recap", "meeting_context", "performance_ranking"]
    #my_summary is missing

    template_analyzers = {}

    for template_key in template_keys:
        template_analyzers[template_key] = build_analyzer(template_key, "latest")

    #all types of analyzer
    # default_analyzer = template_analyzers["default"]
    
    #get all meetings
    query = {}
    # meetings = default_analyzer.fetch_meeting_records(query)

    for template_key, analyzer in template_analyzers.items():
        meetings = analyzer.fetch_meeting_records(query)
        analyzed_list = analyzer.analyze_meetings(meetings)
        print(analyzed_list)
        # analyzer.save_analysis_to_mongodb(
        #     analyzed_list,
        #     output_collection_name="recordings",
        #     output_database_name="gemini"
        # )

    # default_analyzer = template_analyzers["default"]
    
    # query = {"created_by": "Jamie"}
    # results = default_analyzer.fetch_meeting_records(query)
    # default_analyzed = default_analyzer.analyze_meetings(results[0])
    # default_analyzer.save_analysis_to_mongodb(
    #     default_analyzed,
    #     output_collection_name="recordings",
    #     output_database_name="gemini"
    # )
    
    # # 분석 결과 확인
    # if default_analyzed:
    #     first_result = default_analyzed[0]
    #     analysis = first_result.get('analysis', {})
    #     print(f"\n✅ 분석 완료: {len(default_analyzed)}개 회의")
    #     print(f"\n첫 번째 회의 결과:")
    #     print(f"  - meeting_title: {first_result.get('meeting_title')}")
    #     print(f"  - template_used: {analysis.get('template_used')}")
    #     print(f"  - template_version: {analysis.get('template_version')}")
    #     print(f"  - model_used: {analysis.get('model_used')}")

    # return default_analyzed


if __name__ == "__main__":
    # results = main()
    main()