"""
일간 업무 보고서 생성 스크립트
특정 날짜의 회의록들을 분석하여 각 팀원의 일간 업무 보고서를 생성합니다.
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# 상위 디렉토리를 sys.path에 추가하여 모듈 임포트 가능하게 함
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from meeting_performance_analyzer import MeetingPerformanceAnalyzer
from utils.run_analysis import get_analyzer

# .env 파일에서 환경 변수 로드 (상위 디렉토리)
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(dotenv_path=env_path)


def get_target_date(date_str: str = None):
    """
    분석 대상 날짜를 반환합니다.
    
    Args:
        date_str: 날짜 문자열 (YYYY-MM-DD 형식). None이면 오늘 날짜 사용
        
    Returns:
        datetime 객체
    """
    if date_str:
        try:
            return datetime.strptime(date_str, '%Y-%m-%d')
        except ValueError:
            print(f"❌ 잘못된 날짜 형식: {date_str}. YYYY-MM-DD 형식을 사용해주세요.")
            sys.exit(1)
    else:
        return datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)


def fetch_meetings_for_date(analyzer: MeetingPerformanceAnalyzer, target_date: datetime):
    """
    특정 날짜의 회의들을 가져옵니다.
    
    Args:
        analyzer: MeetingPerformanceAnalyzer 인스턴스
        target_date: 분석 대상 날짜
        
    Returns:
        해당 날짜의 회의 리스트
    
    Note:
        - `date` 필드가 있는 경우: date 필드로 필터링
        - `createdTime` 필드만 있는 경우 (Google Drive 스키마): 
          fetch_meeting_records가 자동으로 createdTime 필드에도 동일한 필터를 적용합니다.
          createdTime은 ISO 8601 문자열 형식이지만, ISO 형식은 사전식 정렬이 시간 순서와 일치하므로
          문자열 비교로도 정확하게 날짜 범위 필터링이 가능합니다.
    """
    # 해당 날짜의 시작과 끝 시간
    start_datetime = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_datetime = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    # 날짜 필터 쿼리
    # fetch_meeting_records가 자동으로 'date' 필터를 'createdTime' 필드에도 적용합니다.
    # 따라서 Google Drive 스키마(createdTime 사용)와 일반 스키마(date 사용) 모두 지원됩니다.
    query = {
        "date": {
            "$gte": start_datetime,
            "$lte": end_datetime
        }
    }
    
    meetings = analyzer.fetch_meeting_records(query)
    return meetings


def generate_daily_report(analyzer: MeetingPerformanceAnalyzer, meetings: list, target_date: datetime):
    """
    일간 보고서를 생성합니다.
    
    Args:
        analyzer: MeetingPerformanceAnalyzer 인스턴스
        meetings: 분석할 회의 리스트
        target_date: 분석 대상 날짜
        
    Returns:
        분석 결과 리스트 (각 결과에 원본 미팅 정보 추가됨)
    """
    if not meetings:
        print(f"⚠️  {target_date.strftime('%Y-%m-%d')} 날짜에 해당하는 회의가 없습니다.")
        return []
    
    print(f"\n📊 {target_date.strftime('%Y-%m-%d')} 일간 보고서 생성 중...")
    print(f"   분석 대상 회의: {len(meetings)}개")
    
    # 원본 미팅 데이터 수집 (각 회의의 정보를 리스트로 저장)
    target_meetings_info = []
    for meeting in meetings:
        # _id 필드 사용 (MongoDB ObjectId)
        meeting_id = meeting.get('_id', '')
        if isinstance(meeting_id, dict):
            # {"$oid": "..."} 형식
            meeting_id = str(meeting_id.get('$oid', ''))
        elif meeting_id:
            # ObjectId 객체이거나 문자열
            meeting_id = str(meeting_id)
        else:
            # _id가 없으면 id 필드 사용 (fallback)
            meeting_id = meeting.get('id', '')
        
        target_meetings_info.append({
            'meeting_id': meeting_id,
            'meeting_title': meeting.get('title', meeting.get('name', 'N/A')),
            'created_time': meeting.get('createdTime', meeting.get('date', 'N/A'))
        })
    
    # daily_report 템플릿을 사용하여 분석
    # daily_report는 여러 회의를 한번에 분석해야 하므로 analyze_aggregated_meetings 사용
    aggregated_result = analyzer.analyze_aggregated_meetings(
        meetings,
        template_name="daily_report",
        custom_instructions=f"분석 대상 날짜: {target_date.strftime('%Y-%m-%d')}",
        version="latest"  # 최신 버전 사용 (JSON 형식)
    )
    
    # analyze_aggregated_meetings는 단일 결과를 반환하므로 리스트로 변환
    if aggregated_result:
        analyzed_results = [aggregated_result]
    else:
        analyzed_results = []
    
    # 각 분석 결과에 모든 원본 미팅 정보를 리스트로 추가
    for result in analyzed_results:
        result['target_meetings'] = target_meetings_info
        result['target_date'] = target_date.strftime('%Y-%m-%d')
        # 원본 분석 텍스트 보존 (JSON 파싱 실패 시 사용)
        original_analysis_text = result.get('analysis', '')
        
        # structured_analysis가 있고 실제 데이터가 있는 경우 analysis로 이동하고 중복 제거
        if 'structured_analysis' in result and result['structured_analysis']:
            structured = result['structured_analysis']
            # 빈 구조가 아닌지 확인 (summary나 participants에 실제 데이터가 있는지)
            has_data = (
                (structured.get('summary', {}) and 
                 (structured['summary'].get('overview') or 
                  (structured['summary'].get('topics') and len(structured['summary']['topics']) > 0) or
                  (structured['summary'].get('key_decisions') and len(structured['summary']['key_decisions']) > 0) or
                  (structured['summary'].get('major_achievements') and len(structured['summary']['major_achievements']) > 0) or
                  (structured['summary'].get('common_issues') and len(structured['summary']['common_issues']) > 0))) or
                (structured.get('participants') and len(structured['participants']) > 0)
            )
            if has_data:
                # JSON 형식의 경우 structured_analysis를 analysis로 복사하고 중복 제거
                result['analysis'] = result['structured_analysis']
                
                # participants_analysis를 participants로 이름 변경 (하위 호환성)
                if 'participants_analysis' in result['analysis']:
                    # participants_analysis를 participants로 이름 변경
                    result['analysis']['participants'] = result['analysis'].pop('participants_analysis')
                
                # 최상위 participants의 speak_count, word_count를 analysis.participants에 병합
                if 'participants' in result and 'analysis' in result and isinstance(result['analysis'], dict):
                    top_level_participants = result['participants']  # 최상위 participants (통계 정보 포함)
                    analysis_participants = result['analysis'].get('participants', [])
                    
                    # 이름 기준으로 매칭하여 speak_count, word_count 추가 및 speaking_percentage 재계산
                    top_level_dict = {p.get('name'): p for p in top_level_participants}
                    
                    # 전체 word_count 합계 계산 (비중 계산용) - top_level_participants 기준
                    total_word_count = sum(p.get('word_count', 0) for p in top_level_participants)
                    
                    # 중복 제거를 위해 이미 처리한 참여자 이름 추적
                    processed_names = set()
                    unique_participants = []
                    
                    for participant in analysis_participants:
                        participant_name = participant.get('name', '')
                        
                        # 중복 제거: 같은 이름이 이미 처리되었으면 건너뜀
                        if participant_name in processed_names:
                            continue
                        
                        if participant_name in top_level_dict:
                            # speak_count, word_count 추가
                            participant['speak_count'] = top_level_dict[participant_name].get('speak_count', 0)
                            participant['word_count'] = top_level_dict[participant_name].get('word_count', 0)
                            
                            # 실제 계산된 speaking_time 사용 (타임스탬프 기반)
                            top_level_participant = top_level_dict[participant_name]
                            if 'speaking_time' in top_level_participant:
                                participant['speaking_time'] = top_level_participant['speaking_time']
                            if 'speaking_time_seconds' in top_level_participant:
                                participant['speaking_time_seconds'] = top_level_participant['speaking_time_seconds']
                            
                            # word_count를 기반으로 speaking_percentage 재계산 (정확한 비중)
                            word_count = participant['word_count']
                            if total_word_count > 0:
                                participant['speaking_percentage'] = round((word_count / total_word_count) * 100, 1)
                            else:
                                participant['speaking_percentage'] = 0.0
                            
                            processed_names.add(participant_name)
                            unique_participants.append(participant)
                    
                    # 중복 제거된 participants로 교체
                    result['analysis']['participants'] = unique_participants
                    
                    # 실제 계산된 회의 시간 사용 (AI 생성 값 대신)
                    if 'total_meeting_time' in result:
                        # summary.overview.total_time을 실제 계산된 값으로 업데이트
                        if 'summary' in result['analysis'] and isinstance(result['analysis']['summary'], dict):
                            if 'overview' in result['analysis']['summary']:
                                result['analysis']['summary']['overview']['total_time'] = result['total_meeting_time']
                    
                    # 최상위 participants 필드 제거 (중복이므로)
                    del result['participants']
                
                # participants_formatted 필드 제거
                if 'participants_formatted' in result:
                    del result['participants_formatted']
                
                # structured_analysis는 중복이므로 제거
                del result['structured_analysis']
            else:
                # 데이터가 없으면 원본 analysis_text 유지하고 structured_analysis 제거
                result['analysis'] = original_analysis_text
                del result['structured_analysis']
        else:
            # structured_analysis가 없으면 원본 텍스트 유지
            result['analysis'] = original_analysis_text
    
    return analyzed_results


def _generate_markdown_content(analyzed_results: list, target_date: datetime) -> str:
    """
    분석 결과를 마크다운 형식의 문자열로 생성
    
    Args:
        analyzed_results: 분석 결과 리스트
        target_date: 분석 대상 날짜
        
    Returns:
        마크다운 형식의 문자열
    """
    from io import StringIO
    from datetime import datetime
    
    output = StringIO()
    analysis_time = datetime.now()
    
    output.write(f"# Daily Work Report - {target_date.strftime('%B %d, %Y')}\n\n")
    output.write(f"**Generated at**: {analysis_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    output.write("---\n\n")
    
    for result in analyzed_results:
        output.write(f"## Meeting Information\n\n")
        output.write(f"- **Target Date**: {target_date.strftime('%Y-%m-%d')}\n")
        output.write(f"- **Number of Meetings Analyzed**: {result.get('meeting_count', len(result.get('target_meetings', [])))}\n")
        
        # target_meetings 정보가 있으면 추가
        if 'target_meetings' in result and result['target_meetings']:
            output.write(f"\n### Analyzed Meetings List\n\n")
            for idx, target_meeting in enumerate(result['target_meetings'], 1):
                output.write(f"{idx}. **{target_meeting.get('meeting_title', 'N/A')}**\n")
                output.write(f"   - ID: `{target_meeting.get('meeting_id', 'N/A')}`\n")
                output.write(f"   - Created Time: {target_meeting.get('created_time', 'N/A')}\n")
        
        output.write("\n---\n\n")
        
        # JSON 형식의 분석 결과를 마크다운으로 변환
        analysis = result.get('analysis', {})
        if isinstance(analysis, dict) and 'summary' in analysis:
            # JSON 형식의 분석 데이터
            # 빈 구조가 아닌지 확인
            has_data = (
                (analysis.get('summary', {}) and 
                 (analysis['summary'].get('overview') or 
                  (analysis['summary'].get('topics') and len(analysis['summary']['topics']) > 0) or
                  (analysis['summary'].get('key_decisions') and len(analysis['summary']['key_decisions']) > 0) or
                  (analysis['summary'].get('major_achievements') and len(analysis['summary']['major_achievements']) > 0) or
                  (analysis['summary'].get('common_issues') and len(analysis['summary']['common_issues']) > 0))) or
                (analysis.get('participants') and len(analysis['participants']) > 0)
            )
            if has_data:
                _write_json_analysis_to_markdown(output, analysis)
            else:
                # 빈 구조면 원본 텍스트 확인
                analysis_data = result.get('analysis', {})
                if isinstance(analysis_data, dict):
                    original_text = analysis_data.get('full_analysis_text', analysis_data.get('_raw', ''))
                else:
                    original_text = str(analysis_data) if analysis_data else ''
                if isinstance(original_text, str) and original_text:
                    output.write("## Analysis Results\n\n")
                    output.write("⚠️ JSON parsing succeeded but the structure is empty. Showing original response:\n\n")
                    output.write("```json\n")
                    output.write(original_text)
                    output.write("\n```\n\n")
                else:
                    output.write("⚠️ No analysis results available.\n\n")
        else:
            # 기존 마크다운 형식 또는 문자열
            if isinstance(analysis, dict):
                analysis_text = analysis.get('analysis', '')
            else:
                analysis_text = str(analysis)
            if analysis_text:
                output.write(analysis_text)
                output.write("\n\n")
            else:
                output.write("⚠️ No analysis results available.\n\n")
    
    return output.getvalue()


def save_daily_report(analyzer: MeetingPerformanceAnalyzer, analyzed_results: list, 
                     target_date: datetime,
                     output_database_name: str = "gemini", 
                     output_collection_name: str = "daily_reports"):
    """
    일간 보고서를 MongoDB에 저장합니다.
    
    Args:
        analyzer: MeetingPerformanceAnalyzer 인스턴스
        analyzed_results: 분석 결과 리스트
        target_date: 분석 대상 날짜
        output_database_name: 저장할 데이터베이스 이름 (기본값: "gemini")
        output_collection_name: 저장할 컬렉션 이름 (기본값: "daily_reports")
    """
    if not analyzed_results:
        return
    
    # 마크다운 파일 내용 생성
    markdown_content = _generate_markdown_content(analyzed_results, target_date)
    
    # 각 결과에 마크다운 내용을 analysis 안에 full_analysis_text로 저장
    for result in analyzed_results:
        # analysis가 딕셔너리가 아니면 딕셔너리로 변환
        current_analysis = result.get('analysis', {})
        if not isinstance(current_analysis, dict):
            # 기존 analysis 값을 보존
            existing_analysis = current_analysis
            result['analysis'] = {}
            # 기존 값이 문자열이면 임시로 저장
            if isinstance(existing_analysis, str):
                result['analysis']['_raw'] = existing_analysis
            # 기존 값이 딕셔너리가 아니면 summary와 participants 구조로 변환
            # (JSON 파싱 실패한 경우)
        
        # analysis 딕셔너리에 full_analysis_text 추가
        if not isinstance(result.get('analysis'), dict):
            result['analysis'] = {}
        result['analysis']['full_analysis_text'] = markdown_content
    
    # MongoDB에 저장
    analyzer.save_analysis_to_mongodb(
        analyzed_results,
        output_collection_name=output_collection_name,
        output_database_name=output_database_name
    )
    
    print(f"✅ 일간 보고서가 MongoDB에 저장되었습니다.")
    print(f"   Database: {output_database_name}")
    print(f"   Collection: {output_collection_name}")


def _json_analysis_to_markdown_string(analysis_data: dict) -> str:
    """
    JSON 형식의 분석 결과를 마크다운 문자열로 변환
    
    Args:
        analysis_data: JSON 형식의 분석 데이터
        
    Returns:
        마크다운 형식의 문자열
    """
    from io import StringIO
    
    output = StringIO()
    _write_json_analysis_to_markdown(output, analysis_data)
    return output.getvalue()


def _write_json_analysis_to_markdown(file, analysis_data: dict):
    """
    JSON 형식의 분석 결과를 마크다운으로 변환하여 파일에 작성
    
    Args:
        file: 파일 객체
        analysis_data: JSON 형식의 분석 데이터
    """
    # Summary 섹션
    summary = analysis_data.get('summary', {})
    if summary:
        file.write("## Summary of Today's Meetings\n\n")
        
        # Overview
        overview = summary.get('overview', {})
        if overview:
            file.write("### Overall Meeting Overview\n\n")
            file.write(f"- Total Number of Meetings: {overview.get('meeting_count', 'N/A')}\n")
            file.write(f"- Total Meeting Time: {overview.get('total_time', 'N/A')}\n")
            main_topics = overview.get('main_topics', [])
            if main_topics:
                file.write(f"- Main Discussion Topics: {', '.join(main_topics)}\n")
            file.write("\n")
        
        # Topics
        topics = summary.get('topics', [])
        if topics:
            file.write("### Meeting Content by Topic\n\n")
            for topic in topics:
                topic_name = topic.get('topic', '')
                if topic_name:
                    file.write(f"#### {topic_name}\n\n")
                    related_meetings = topic.get('related_meetings', [])
                    if related_meetings:
                        file.write(f"- **Related Meetings**: {', '.join(related_meetings)}\n")
                    
                    key_discussions = topic.get('key_discussions', [])
                    if key_discussions:
                        file.write("- **Key Discussion Points**:\n")
                        for discussion in key_discussions:
                            file.write(f"  - {discussion}\n")
                    
                    key_decisions = topic.get('key_decisions', [])
                    if key_decisions:
                        file.write("- **Key Decisions**:\n")
                        for decision in key_decisions:
                            file.write(f"  - {decision}\n")
                    
                    progress = topic.get('progress', [])
                    if progress:
                        file.write("- **Progress**:\n")
                        for prog in progress:
                            file.write(f"  - {prog}\n")
                    
                    issues = topic.get('issues', [])
                    if issues:
                        file.write("- **Issues and Blockers**:\n")
                        for issue in issues:
                            file.write(f"  - {issue}\n")
                    
                    file.write("\n")
        
        # Key Decisions
        key_decisions = summary.get('key_decisions', [])
        if key_decisions:
            file.write("### Key Decisions (Overall Summary)\n\n")
            for decision in key_decisions:
                file.write(f"- {decision}\n")
            file.write("\n")
        
        # Major Achievements
        major_achievements = summary.get('major_achievements', [])
        if major_achievements:
            file.write("### Major Achievements and Progress (Overall Summary)\n\n")
            for achievement in major_achievements:
                file.write(f"- {achievement}\n")
            file.write("\n")
        
        # Common Issues
        common_issues = summary.get('common_issues', [])
        if common_issues:
            file.write("### Common Issues and Blockers (Overall Summary)\n\n")
            for issue in common_issues:
                file.write(f"- {issue}\n")
            file.write("\n")
        
        file.write("---\n\n")
    
    # Participants Analysis
    participants = analysis_data.get('participants', [])
    if participants:
        for participant in participants:
            name = participant.get('name', '')
            if name:
                file.write(f"## {name}\n\n")
                
                speaking_time = participant.get('speaking_time')
                speaking_percentage = participant.get('speaking_percentage')
                if speaking_time or speaking_percentage:
                    file.write("### Speaking Time\n\n")
                    if speaking_time and speaking_percentage:
                        file.write(f"- {speaking_time} ({speaking_percentage}% of total)\n")
                    elif speaking_time:
                        file.write(f"- {speaking_time}\n")
                    elif speaking_percentage:
                        file.write(f"- {speaking_percentage}% of total\n")
                    file.write("\n")
                
                key_activities = participant.get('key_activities', [])
                if key_activities:
                    file.write("### Today's Key Activities\n\n")
                    for activity in key_activities:
                        file.write(f"- {activity}\n")
                    file.write("\n")
                
                progress = participant.get('progress', [])
                if progress:
                    file.write("### Progress and Achievements\n\n")
                    for prog in progress:
                        file.write(f"- {prog}\n")
                    file.write("\n")
                
                issues = participant.get('issues', [])
                if issues:
                    file.write("### Issues and Blockers\n\n")
                    for issue in issues:
                        file.write(f"- {issue}\n")
                    file.write("\n")
                
                action_items = participant.get('action_items', [])
                if action_items:
                    file.write("### Next Action Items\n\n")
                    for item in action_items:
                        file.write(f"- [ ] {item}\n")
                    file.write("\n")
                
                collaboration = participant.get('collaboration', [])
                if collaboration:
                    file.write("### Collaboration Status\n\n")
                    for collab in collaboration:
                        file.write(f"- {collab}\n")
                    file.write("\n")
                
                file.write("---\n\n")


def save_daily_report_to_file(analyzed_results: list, target_date: datetime, output_dir: str = "output"):
    """
    일간 보고서를 파일로 저장합니다.
    
    Args:
        analyzed_results: 분석 결과 리스트
        target_date: 분석 대상 날짜
        output_dir: 출력 디렉토리
    """
    if not analyzed_results:
        return
    
    # 출력 디렉토리 생성
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # 분석 시간 가져오기
    analysis_time = datetime.now()
    analysis_time_str = analysis_time.strftime('%Y%m%d_%H%M%S')
    
    # 파일명 생성 (날짜 + 분석 시간 포함)
    date_str = target_date.strftime('%Y%m%d')
    md_filename = os.path.join(output_dir, f"daily_report_{date_str}_{analysis_time_str}.md")
    json_filename = os.path.join(output_dir, f"daily_report_{date_str}_{analysis_time_str}.json")
    
    # 마크다운 파일로 저장
    with open(md_filename, 'w', encoding='utf-8') as f:
        f.write(f"# Daily Work Report - {target_date.strftime('%B %d, %Y')}\n\n")
        f.write(f"**Generated at**: {analysis_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("---\n\n")
        
        for result in analyzed_results:
            f.write(f"## Meeting Information\n\n")
            f.write(f"- **Target Date**: {target_date.strftime('%Y-%m-%d')}\n")
            f.write(f"- **Number of Meetings Analyzed**: {result.get('meeting_count', len(result.get('target_meetings', [])))}\n")
            
            # target_meetings 정보가 있으면 추가
            if 'target_meetings' in result and result['target_meetings']:
                f.write(f"\n### Analyzed Meetings List\n\n")
                for idx, target_meeting in enumerate(result['target_meetings'], 1):
                    f.write(f"{idx}. **{target_meeting.get('meeting_title', 'N/A')}**\n")
                    f.write(f"   - ID: `{target_meeting.get('meeting_id', 'N/A')}`\n")
                    f.write(f"   - Created Time: {target_meeting.get('created_time', 'N/A')}\n")
            
            f.write("\n---\n\n")
            
            # JSON 형식의 분석 결과를 마크다운으로 변환
            analysis = result.get('analysis', {})
            if isinstance(analysis, dict) and 'summary' in analysis:
                # JSON 형식의 분석 데이터
                # 빈 구조가 아닌지 확인
                has_data = (
                    (analysis.get('summary', {}) and 
                     (analysis['summary'].get('overview') or 
                      (analysis['summary'].get('topics') and len(analysis['summary']['topics']) > 0) or
                      (analysis['summary'].get('key_decisions') and len(analysis['summary']['key_decisions']) > 0) or
                      (analysis['summary'].get('major_achievements') and len(analysis['summary']['major_achievements']) > 0) or
                      (analysis['summary'].get('common_issues') and len(analysis['summary']['common_issues']) > 0))) or
                    (analysis.get('participants') and len(analysis['participants']) > 0)
                )
                if has_data:
                    _write_json_analysis_to_markdown(f, analysis)
                else:
                    # 빈 구조면 원본 텍스트 확인
                    original_text = result.get('analysis', '')
                    if isinstance(original_text, str) and original_text:
                        f.write("## Analysis Results\n\n")
                        f.write("⚠️ JSON parsing succeeded but the structure is empty. Showing original response:\n\n")
                        f.write("```json\n")
                        f.write(original_text)
                        f.write("\n```\n\n")
                    else:
                        f.write("⚠️ No analysis results available.\n\n")
            else:
                # 기존 마크다운 형식 또는 문자열
                if isinstance(analysis, dict):
                    analysis_text = analysis.get('analysis', '')
                else:
                    analysis_text = str(analysis)
                if analysis_text:
                    f.write(analysis_text)
                    f.write("\n\n")
                else:
                    f.write("⚠️ No analysis results available.\n\n")
    
    # JSON 파일로 저장
    with open(json_filename, 'w', encoding='utf-8') as f:
        json.dump(analyzed_results, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"💾 일간 보고서 파일 저장 완료:")
    print(f"   - {md_filename}")
    print(f"   - {json_filename}")


def main(date_str: str = None):
    """
    메인 실행 함수
    
    Args:
        date_str: 분석 대상 날짜 (YYYY-MM-DD 형식). None이면 오늘 날짜 사용
    """
    print("\n" + "=" * 70)
    print("📅 일간 업무 보고서 생성기")
    print("=" * 70)
    
    # 분석 대상 날짜 결정
    target_date = get_target_date(date_str)
    print(f"\n📆 분석 대상 날짜: {target_date.strftime('%Y-%m-%d')}")
    
    try:
        # Analyzer 생성 (daily_report 템플릿 사용)
        analyzer = get_analyzer(
            prompt_template="daily_report",
            template_version="latest"  # 최신 버전 사용
        )
        
        # 해당 날짜의 회의들 가져오기
        meetings = fetch_meetings_for_date(analyzer, target_date)
        
        if not meetings:
            print(f"⚠️  {target_date.strftime('%Y-%m-%d')} 날짜에 해당하는 회의가 없습니다.")
            return
        
        print(f"✅ {len(meetings)}개의 회의를 찾았습니다.")
        
        # 회의 제목 출력
        print("\n📋 분석 대상 회의:")
        for i, meeting in enumerate(meetings, 1):
            meeting_title = meeting.get('title', meeting.get('name', 'N/A'))
            meeting_date = meeting.get('date', meeting.get('createdTime', 'N/A'))
            print(f"   {i}. {meeting_title} ({meeting_date})")
        
        # 일간 보고서 생성
        analyzed_results = generate_daily_report(analyzer, meetings, target_date)
        
        if not analyzed_results:
            print("⚠️  분석 결과가 없습니다.")
            return
        
        # MongoDB에 저장
        save_daily_report(analyzer, analyzed_results, target_date, output_database_name="test_database", output_collection_name="daily_reports")
        
        # 파일로 저장
        save_daily_report_to_file(analyzed_results, target_date)
        
        print("\n✅ 일간 보고서 생성 완료!")
        
    except Exception as e:
        print(f"\n❌ 오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        # 연결 종료
        if 'analyzer' in locals():
            analyzer.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='일간 업무 보고서 생성')
    parser.add_argument(
        '--date',
        type=str,
        help='분석 대상 날짜 (YYYY-MM-DD 형식). 지정하지 않으면 오늘 날짜 사용',
        default=None
    )
    
    args = parser.parse_args()
    main(args.date)

