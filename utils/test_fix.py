
import os
import sys
from datetime import datetime

# Add parent directory to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.run_analysis import get_latest_latest_analyzed, build_analyzer

def test_fix():
    print("Testing the fix...")
    try:
        latest_analyzed = get_latest_latest_analyzed()
        
        if latest_analyzed:
            meeting_date = latest_analyzed.get("meeting_date")
            print(f"Latest meeting_date: {meeting_date} (type: {type(meeting_date)})")
            # Convert to datetime if it's a string
            if isinstance(meeting_date, str):
                from dateutil import parser
                meeting_date = parser.parse(meeting_date)
                print(f"Converted to: {meeting_date} (type: {type(meeting_date)})")
        else:
            meeting_date = datetime(2000, 1, 1)
            print("No analyzed meetings, using default date")
        
        now = datetime.now()
        query = {
            "date": {
                "$gt": meeting_date,
                "$lte": now
            }
        }
        
        print(f"Query: {query}")
        
        analyzer = build_analyzer("team_collaboration")
        meetings = analyzer.fetch_meeting_records(query)
        print(f"Fetched {len(meetings)} meetings")
        
        if meetings:
            print(f"Analyzing {len(meetings)} meetings...")
            results = analyzer.analyze_meetings(meetings[:1])  # Just test with 1
            print(f"Got {len(results)} results")
            if results:
                print("SUCCESS! analyze_meetings returned results")
            else:
                print("FAIL! analyze_meetings returned empty list")
        else:
            print("No meetings found to analyze")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_fix()
