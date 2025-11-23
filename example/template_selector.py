"""
프롬프트 템플릿 테스트 및 선택 도구
다양한 프롬프트 템플릿을 미리보고 비교할 수 있습니다.
"""

import os
import sys

# 상위 디렉토리를 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from prompt_templates import PromptTemplates, PromptConfig


def display_template_list():
    """사용 가능한 템플릿 목록 표시"""
    print("\n" + "="*70)
    print("🎯 사용 가능한 프롬프트 템플릿 목록")
    print("="*70)
    
    templates = PromptTemplates.list_templates()
    
    for idx, (name, description) in enumerate(templates.items(), 1):
        print(f"\n{idx}. {name.upper()}")
        print(f"   📝 {description}")
    
    print("\n" + "="*70)


def preview_template(template_name: str):
    """템플릿 미리보기"""
    print("\n" + "="*70)
    print(f"📄 '{template_name}' 템플릿 미리보기")
    print("="*70)
    
    try:
        template_content = PromptTemplates.get_template(template_name)
        print(template_content)
        print("\n" + "="*70)
    except Exception as e:
        print(f"❌ 오류: {e}")


def compare_templates():
    """여러 템플릿 비교"""
    print("\n" + "="*70)
    print("🔍 템플릿 비교 모드")
    print("="*70)
    
    templates_to_compare = input("\n비교할 템플릿을 입력하세요 (쉼표로 구분, 예: default,leadership): ")
    template_names = [t.strip() for t in templates_to_compare.split(",")]
    
    for template_name in template_names:
        print("\n" + "-"*70)
        print(f"📌 {template_name.upper()}")
        print("-"*70)
        
        try:
            template_content = PromptTemplates.get_template(template_name)
            # 첫 300자만 표시
            preview = template_content[:300] + "..." if len(template_content) > 300 else template_content
            print(preview)
        except Exception as e:
            print(f"❌ 오류: {e}")


def test_custom_prompt():
    """사용자 정의 프롬프트 테스트"""
    print("\n" + "="*70)
    print("✏️  사용자 정의 프롬프트 작성")
    print("="*70)
    
    print("\n작성하고 싶은 프롬프트를 입력하세요 (여러 줄 입력 가능, 빈 줄 입력 시 종료):")
    print("(예: 참여자별 고객 중심 사고를 1-10점으로 평가)")
    
    lines = []
    while True:
        line = input()
        if not line:
            break
        lines.append(line)
    
    custom_prompt = "\n".join(lines)
    
    if custom_prompt:
        try:
            validated = PromptTemplates.create_custom_template(custom_prompt)
            print("\n✅ 유효한 프롬프트입니다!")
            print("\n작성하신 프롬프트:")
            print("-"*70)
            print(validated)
            print("-"*70)
            
            save = input("\n이 프롬프트를 파일로 저장하시겠습니까? (y/n): ")
            if save.lower() == 'y':
                filename = input("파일 이름을 입력하세요 (예: my_prompt.txt): ")
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(validated)
                print(f"✅ '{filename}'에 저장되었습니다!")
        except ValueError as e:
            print(f"❌ {e}")
    else:
        print("⚠️  프롬프트가 입력되지 않았습니다.")


def show_usage_examples():
    """사용 예제 표시"""
    print("\n" + "="*70)
    print("💡 프롬프트 템플릿 사용 예제")
    print("="*70)
    
    examples = [
        {
            "scenario": "일반 팀 회의 분석",
            "template": "default",
            "code": """
analyzer = MeetingPerformanceAnalyzer(
    mongodb_uri="mongodb://localhost:27017/",
    database_name="company_db",
    collection_name="meeting_transcripts",
    gemini_api_key=API_KEY,
    prompt_template="default"
)
results = analyzer.analyze_multiple_meetings()
"""
        },
        {
            "scenario": "리더십 평가",
            "template": "leadership",
            "code": """
analyzer = MeetingPerformanceAnalyzer(
    ...,
    prompt_template="leadership"
)
# 최근 3개월 임원 회의 분석
filters = {'date': {'$gte': datetime.now() - timedelta(days=90)}}
results = analyzer.analyze_multiple_meetings(filters)
"""
        },
        {
            "scenario": "커스텀 지시사항 추가",
            "template": "default",
            "code": """
analyzer = MeetingPerformanceAnalyzer(..., prompt_template="default")
results = analyzer.analyze_multiple_meetings(
    custom_instructions=\"\"\"
    특히 다음을 중점 평가:
    - 데이터 기반 의사결정
    - 고객 관점의 제안
    \"\"\"
)
"""
        },
    ]
    
    for idx, example in enumerate(examples, 1):
        print(f"\n📌 예제 {idx}: {example['scenario']}")
        print(f"   사용 템플릿: {example['template']}")
        print(f"   코드:")
        print(example['code'])
        print("-"*70)


def recommend_template():
    """상황에 맞는 템플릿 추천"""
    print("\n" + "="*70)
    print("🎯 템플릿 추천 도구")
    print("="*70)
    
    print("\n어떤 상황인가요?")
    print("1. 일반 업무 회의")
    print("2. 리더 선발 / 승진 심사")
    print("3. 혁신 프로젝트 / 브레인스토밍")
    print("4. 팀 빌딩 / 협업 분석")
    print("5. 성과 평가 / 연말 평가")
    print("6. 빠른 리뷰 / 일일 미팅")
    print("7. 중요 전략 회의")
    
    choice = input("\n선택하세요 (1-7): ")
    
    recommendations = {
        "1": ("default", "일반적인 업무 회의에는 기본 템플릿이 적합합니다."),
        "2": ("leadership + detailed", "리더십 템플릿과 상세 분석을 조합하면 좋습니다."),
        "3": ("innovation", "혁신 중심 템플릿이 창의성을 잘 평가합니다."),
        "4": ("communication", "소통 중심 템플릿이 협업 능력을 분석합니다."),
        "5": ("performance + detailed", "성과 템플릿과 상세 분석을 권장합니다."),
        "6": ("brief", "간결 요약 템플릿으로 빠르게 확인하세요."),
        "7": ("detailed", "상세 분석 템플릿으로 모든 측면을 파악하세요."),
    }
    
    if choice in recommendations:
        template, reason = recommendations[choice]
        print(f"\n✅ 추천 템플릿: {template}")
        print(f"   이유: {reason}")
        
        print(f"\n사용 예시:")
        print(f"analyzer = MeetingPerformanceAnalyzer(..., prompt_template='{template.split('+')[0].strip()}')")
    else:
        print("\n⚠️  올바른 번호를 선택해주세요.")


def interactive_mode():
    """대화형 모드"""
    while True:
        print("\n" + "="*70)
        print("🎯 프롬프트 템플릿 도구")
        print("="*70)
        print("\n1. 템플릿 목록 보기")
        print("2. 템플릿 미리보기")
        print("3. 템플릿 비교")
        print("4. 커스텀 프롬프트 작성")
        print("5. 사용 예제 보기")
        print("6. 템플릿 추천 받기")
        print("7. 종료")
        
        choice = input("\n선택하세요 (1-7): ")
        
        if choice == "1":
            display_template_list()
        elif choice == "2":
            template_name = input("\n미리볼 템플릿 이름을 입력하세요: ")
            preview_template(template_name)
        elif choice == "3":
            compare_templates()
        elif choice == "4":
            test_custom_prompt()
        elif choice == "5":
            show_usage_examples()
        elif choice == "6":
            recommend_template()
        elif choice == "7":
            print("\n👋 프로그램을 종료합니다.")
            break
        else:
            print("\n⚠️  올바른 번호를 선택해주세요.")
        
        input("\n계속하려면 Enter를 누르세요...")


if __name__ == "__main__":
    print("="*70)
    print("🎯 프롬프트 템플릿 테스트 도구에 오신 것을 환영합니다!")
    print("="*70)
    print("\n이 도구로 다양한 프롬프트 템플릿을 탐색하고 선택할 수 있습니다.")
    
    interactive_mode()
