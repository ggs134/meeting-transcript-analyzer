#!/bin/bash

# 하루 전날 일간 보고서 생성 스크립트
# 사용법: ./scripts/run_yesterday_daily_report.sh

# 프로젝트 루트 디렉토리로 이동 (스크립트가 scripts/ 안에 있으므로 상위 디렉토리)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SCRIPT_DIR"

# 하루 전날 날짜 계산 (YYYY-MM-DD 형식)
# macOS/Linux 호환
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    YESTERDAY=$(date -v-1d +%Y-%m-%d)
else
    # Linux
    YESTERDAY=$(date -d "yesterday" +%Y-%m-%d)
fi

echo "=========================================="
echo "📅 Yesterday Daily Report Generator"
echo "=========================================="
echo "Target Date: $YESTERDAY"
echo ""

# Python 스크립트 실행
python utils/run_monthly_daily_reports.py --date "$YESTERDAY" --database "gemini" --collection "recordings_daily"

# 실행 결과 확인
if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Daily report for $YESTERDAY completed successfully!"
else
    echo ""
    echo "❌ Failed to generate daily report for $YESTERDAY"
    exit 1
fi

