"""
회의 Transcript 분석을 위한 프롬프트 템플릿 관리 모듈
템플릿은 JSON 파일에서 직접 로드됩니다.
"""

import json
import os
from typing import Dict, List, Optional


# 전역 템플릿 캐시: {템플릿명: {version: {content, description, ...}}}
# 모든 버전을 저장하여 특정 버전 선택 가능
_templates_cache: Dict[str, Dict[str, Dict]] = {}
# 최신 버전 캐시: {템플릿명: 버전번호}
_latest_versions: Dict[str, str] = {}


def _load_templates_from_json(json_path: str = None) -> bool:
    """
    JSON 파일에서 템플릿을 로드하여 캐시에 저장
    
    Args:
        json_path: JSON 파일 경로 (None이면 기본 경로 사용)
        
    Returns:
        성공 여부
    """
    global _templates_cache, _latest_versions
    
    if json_path is None:
        # 현재 파일과 같은 디렉토리의 prompt_templates.json 사용
        current_dir = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(current_dir, "prompt_templates.json")
    
    try:
        if not os.path.exists(json_path):
            print(f"⚠️  템플릿 JSON 파일을 찾을 수 없습니다: {json_path}")
            return False
        
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        templates_data = data.get("templates", {})
        _templates_cache = {}
        _latest_versions = {}
        
        for template_name, versions in templates_data.items():
            # 모든 버전을 저장
            _templates_cache[template_name] = {}
            
            latest_version = None
            
            for version, template_info in versions.items():
                # 각 버전 정보 저장
                _templates_cache[template_name][version] = {
                    "content": template_info.get("content", ""),
                    "description": template_info.get("description", ""),
                    "created_at": template_info.get("created_at", ""),
                    "author": template_info.get("author", "system")
                }
                
                # is_latest=True인 버전 찾기
                if template_info.get("is_latest", False):
                    latest_version = version
            
            # 최신 버전이 없으면 첫 번째 버전 사용
            if latest_version is None and versions:
                latest_version = list(versions.keys())[0]
            
            if latest_version:
                _latest_versions[template_name] = latest_version
        
        print(f"✅ 템플릿 로드 완료: {len(_templates_cache)}개 템플릿")
        return True
        
    except json.JSONDecodeError as e:
        print(f"❌ JSON 파일 파싱 오류: {e}")
        return False
    except Exception as e:
        print(f"❌ 템플릿 로드 오류: {e}")
        return False


def _get_default_template() -> str:
    """기본 템플릿 반환 (폴백용)"""
    return """회의록을 바탕으로 참여자별로 다음의 내용을 추출하고 정리해.

**각 참여자가 무엇을 했는지, 무엇을 할 것인지 정리하는 것이 목표야.**

1. 아이디어
2. 업무 조율
3. 업무 보고
4. 양적 기여도
"""


# 템플릿 초기화
_load_templates_from_json()


# 기존 API와의 호환성을 위한 클래스
class PromptTemplates:
    """프롬프트 템플릿 관리 클래스"""
    
    @classmethod
    def get_template(cls, template_name: str = "default", version: Optional[str] = None) -> str:
        """
        템플릿 이름으로 프롬프트 가져오기
        
        Args:
            template_name: 템플릿 이름
            version: 버전 번호 (None이면 최신 버전 사용)
            
        Returns:
            프롬프트 템플릿 문자열
        """
        if template_name not in _templates_cache:
            return _get_default_template()
        
        # "latest" 문자열이면 최신 버전으로 처리
        if version == "latest":
            version = None
        
        # 버전이 지정되지 않으면 최신 버전 사용
        if version is None:
            version = _latest_versions.get(template_name)
            if version is None:
                # 최신 버전이 없으면 첫 번째 버전 사용
                versions = list(_templates_cache[template_name].keys())
                if versions:
                    version = versions[0]
                else:
                    return _get_default_template()

        # 지정된 버전이 있으면 사용
        if version in _templates_cache[template_name]:
            return _templates_cache[template_name][version]["content"]

        # 버전을 찾을 수 없으면 최신 버전 사용
        latest_version = _latest_versions.get(template_name)
        if latest_version and latest_version in _templates_cache[template_name]:
            return _templates_cache[template_name][latest_version]["content"]
        
        return _get_default_template()
    
    @classmethod
    def list_templates(cls) -> Dict[str, str]:
        """
        사용 가능한 모든 템플릿 목록과 설명 반환
        
        Returns:
            {템플릿명: 설명} 딕셔너리
        """
        result = {}
        for name, versions in _templates_cache.items():
            latest_version = _latest_versions.get(name)
            if latest_version and latest_version in versions:
                result[name] = versions[latest_version].get("description", "")
            elif versions:
                # 최신 버전이 없으면 첫 번째 버전의 설명 사용
                first_version = list(versions.keys())[0]
                result[name] = versions[first_version].get("description", "")
        return result
    
    @classmethod
    def list_versions(cls, template_name: str) -> List[str]:
        """
        템플릿의 사용 가능한 모든 버전 목록 반환
        
        Args:
            template_name: 템플릿 이름
            
        Returns:
            버전 번호 리스트
        """
        if template_name in _templates_cache:
            return sorted(_templates_cache[template_name].keys())
        return []
    
    @classmethod
    def build_prompt(cls, 
                    template_name: str,
                    formatted_text: str, 
                    participants: List[str],
                    custom_instructions: str = "",
                    version: Optional[str] = None,
                    date: Optional[str] = None,
                    meetings_data: Optional[str] = None) -> str:
        """
        최종 프롬프트 생성
        
        Args:
            template_name: 사용할 템플릿 이름
            formatted_text: 포맷된 transcript 텍스트
            participants: 참여자 목록
            custom_instructions: 추가 커스텀 지시사항 (선택)
            version: 템플릿 버전 (None이면 최신 버전)
            date: 분석 대상 날짜 (선택, daily_report 등에서 사용)
            meetings_data: 회의록 데이터 (선택, daily_report 등에서 사용)
            
        Returns:
            완성된 프롬프트
        """
        template = cls.get_template(template_name, version)
        
        # 프롬프트 변수 치환을 위한 기본값 설정
        # formatted_text를 meetings_data로 사용 (없으면 formatted_text 사용)
        meetings_data_value = meetings_data if meetings_data is not None else formatted_text
        participants_value = ', '.join(participants) if isinstance(participants, list) else str(participants)
        date_value = date if date is not None else "N/A"
        
        # 템플릿에 변수 치환 적용
        template = template.replace('{date}', date_value)
        template = template.replace('{meetings_data}', meetings_data_value)
        template = template.replace('{participants}', participants_value)
        
        prompt = f"""
다음은 회의 녹취록(transcript)입니다.

{formatted_text}

참여자 목록: {participants_value}

---

{template}

"""
        
        if custom_instructions:
            prompt += f"""
---
**추가 지시사항:**
{custom_instructions}
"""
        
        return prompt
    
    @classmethod
    def create_custom_template(cls, template_content: str) -> str:
        """
        사용자 정의 템플릿 생성
        
        Args:
            template_content: 사용자가 작성한 프롬프트 내용
            
        Returns:
            검증된 템플릿
        """
        # 기본 검증
        if not template_content or len(template_content.strip()) < 50:
            raise ValueError("템플릿 내용이 너무 짧습니다. 최소 50자 이상 작성해주세요.")
        
        return template_content


class PromptConfig:
    """프롬프트 설정 관리 클래스"""
    
    def __init__(self, 
                 default_template: str = "default",
                 default_version: Optional[str] = None,
                 custom_template: str = None):
        """
        프롬프트 설정 초기화
        
        Args:
            default_template: 기본으로 사용할 템플릿 이름
            default_version: 기본으로 사용할 템플릿 버전 (None이면 최신 버전)
            custom_template: 사용자 정의 템플릿 (선택)
        """
        self.default_template = default_template
        self.default_version = default_version
        self.custom_template = custom_template
    
    def get_prompt(self, 
                   formatted_text: str, 
                   participants: List[str],
                   template_override: str = None,
                   version_override: Optional[str] = None,
                   custom_instructions: str = "",
                   date: Optional[str] = None,
                   meetings_data: Optional[str] = None) -> str:
        """
        설정에 따라 프롬프트 생성
        
        Args:
            formatted_text: 포맷된 transcript
            participants: 참여자 목록
            template_override: 이번에만 사용할 템플릿 (선택)
            version_override: 이번에만 사용할 버전 (선택, None이면 설정된 버전 또는 최신 버전)
            custom_instructions: 추가 지시사항 (선택)
            date: 분석 대상 날짜 (선택, daily_report 등에서 사용)
            meetings_data: 회의록 데이터 (선택, daily_report 등에서 사용)
            
        Returns:
            완성된 프롬프트
        """
        # 커스텀 템플릿이 있으면 우선 사용
        if self.custom_template:
            return PromptTemplates.build_prompt(
                "default",  # 더미
                formatted_text,
                participants,
                custom_instructions,
                None,
                date,
                meetings_data
            ).replace(PromptTemplates.get_template("default"), self.custom_template)
        
        # 템플릿 선택
        template_name = template_override or self.default_template
        # version_override가 있으면 사용, 없으면 설정된 버전, 그것도 없으면 최신 버전
        version = version_override or self.default_version
        # "latest" 문자열이면 None으로 변환하여 최신 버전 사용
        if version == "latest":
            version = None
        
        return PromptTemplates.build_prompt(
            template_name,
            formatted_text,
            participants,
            custom_instructions,
            version,
            date,
            meetings_data
        )
    
    def get_template_info(self) -> Dict:
        """현재 설정된 템플릿 정보 반환"""
        if self.custom_template:
            return {
                "template_name": "custom",
                "version": "custom",
                "is_custom": True
            }
        
        template_name = self.default_template
        version = self.default_version or _latest_versions.get(template_name)
        
        if template_name in _templates_cache and version:
            template_info = _templates_cache[template_name].get(version, {})
            return {
                "template_name": template_name,
                "version": version,
                "is_custom": False,
                "info": template_info
            }
        
        return {
            "template_name": template_name,
            "version": version or "unknown",
            "is_custom": False,
            "info": {}
        }


# 버전 정보를 가져오는 간단한 함수들
def get_template_version(template_name: str, version: Optional[str] = None) -> Optional[str]:
    """
    템플릿의 버전 번호 가져오기
    
    Args:
        template_name: 템플릿 이름
        version: 버전 번호 (None이면 최신 버전)
        
    Returns:
        버전 번호 또는 None
    """
    if template_name not in _templates_cache:
        return None
    
    if version is None:
        return _latest_versions.get(template_name)
    
    if version in _templates_cache[template_name]:
        return version
    
    return None


def list_templates() -> Dict[str, Dict]:
    """모든 템플릿 목록과 정보 반환 (최신 버전만)"""
    result = {}
    for name, versions in _templates_cache.items():
        latest_version = _latest_versions.get(name)
        if latest_version and latest_version in versions:
            result[name] = {
                "version": latest_version,
                **versions[latest_version]
            }
    return result


# 기존 코드 호환성을 위한 별칭
VersionedPromptTemplates = type('VersionedPromptTemplates', (), {
    'get_template': staticmethod(PromptTemplates.get_template),
    'get_template_version': staticmethod(get_template_version),
    'list_templates': staticmethod(lambda: {name: {"latest_version": _latest_versions.get(name, ""), "available_versions": list(versions.keys()), "description": versions.get(_latest_versions.get(name, ""), {}).get("description", "")} for name, versions in _templates_cache.items()}),
    'get_latest_version': staticmethod(lambda name: _latest_versions.get(name)),
    'get_template_info': lambda cls, name, version=None: _templates_cache.get(name, {}).get(version or _latest_versions.get(name, ""), {}) if name in _templates_cache else {},
    'list_versions': staticmethod(PromptTemplates.list_versions),
})


# 사용 예시 및 테스트
if __name__ == "__main__":
    print("=" * 60)
    print("사용 가능한 프롬프트 템플릿 목록")
    print("=" * 60)
    
    templates_info = list_templates()
    for name, info in templates_info.items():
        print(f"\n📌 {name}")
        print(f"   버전: {info.get('version', 'unknown')}")
        print(f"   설명: {info.get('description', '')}")
    
    print("\n\n" + "=" * 60)
    print("템플릿 미리보기 예시")
    print("=" * 60)
    
    # 기본 템플릿 미리보기
    print("\n[MY_SUMMARY 템플릿 (내 성과 정리용)]")
    print(PromptTemplates.get_template("my_summary")[:300] + "...")
