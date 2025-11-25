# Meeting Transcript Work Organizer System

A practical tool for practitioners to **organize work**, **understand colleagues' roles**, and **clarify next steps** by analyzing meeting transcripts stored in MongoDB using AI.

## 🎯 Purpose of this Tool

**A practical organization tool, not for evaluation**

- ✅ **Understand My Performance**: What I did in the meeting and what I need to do.
- ✅ **Understand Team Collaboration**: What colleagues are doing and who to ask.
- ✅ **Clarify Work Direction**: What to do next and by when.

## 🌟 Key Features

### 11 Practical Prompt Templates

#### Individual Analysis Templates (8)
| Template | Purpose | When to Use |
|----------|---------|-------------|
| **default** ⭐ | Overall work organization | After general team meetings |
| **my_summary** | My performance summary | To check what I did |
| **team_collaboration** | Understand team roles | To know who to ask what |
| **action_items** | Track action items | Who does what by when |
| **knowledge_base** | Organize knowledge | To save shared information |
| **decision_log** | Track decisions | Why was this decided |
| **quick_recap** | Quick summary | Understand in 5 minutes |
| **meeting_context** | Meeting context | Understand discussion flow |

#### Aggregated Analysis Templates (3)
| Template | Purpose | When to Use |
|----------|---------|-------------|
| **comprehensive_review** | Long-term performance review | Evaluate growth across multiple meetings |
| **project_milestone** | Project progress tracking | Track project contributions and milestones |
| **soft_skills_growth** | Soft skills assessment | Analyze communication and leadership growth |

## 🚀 Quick Start

### 1. Installation

```bash
# Install packages
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Enter your Gemini API Key in the .env file
```

### 2. Test with Sample Data

```bash
# Insert sample meeting transcript
python example/insert_sample_data.py

# Run analysis
python meeting_performance_analyzer.py
```

### 3. Generate Team Performance Report (Batch Analysis of 50 Meetings) 🆕

```bash
# Analyze all meetings and generate team report
python team_report/generate_team_report.py
```

**Generated Files:**
- `team_performance_report.txt` - Full report (includes console output)
- `team_performance.json` - JSON data (for programming use)
- `team_performance.csv` - CSV file (open directly in Excel)
- `team_performance.xlsx` - Excel file (includes charts)

👉 [Team Report Generation Guide](team_report/TEAM_REPORT_GUIDE.md)

### 5. Interactive Transcript Parser 🆕

Analyze meetings interactively with filters, template selection, and version control.

```bash
python utils/transcript_parser.py
```

**Features:**
- **3 Analysis Modes:**
  1. Analyze all meetings
  2. Filter-based analysis (date, title, participants)
  3. Individual meeting selection (with pagination)
- **Template Selection:** Choose from 11 templates
- **Version Selection:** Select specific template version or use latest
- **Custom Instructions:** Add specific analysis requirements
- **Participant Selection:** For `my_summary` template, select your name from extracted participants
- **Auto-save:** Results saved to `output/` directory

**Example Workflow:**
1. Select analysis mode (e.g., "3. Individual meeting selection")
2. Browse meetings with pagination (5 per page)
3. Select a meeting
4. Choose template (e.g., "my_summary")
5. Select version (default: latest)
6. View analysis results immediately

### 6. Batch Analysis with Various Templates

You can analyze meetings with multiple templates (collaboration, action items, knowledge base, etc.) at once using the `utils/run_analysis.py` script.

```bash
python utils/run_analysis.py
```

This script sequentially executes the following templates and outputs the analysis results:
- `team_collaboration`
- `action_items`
- `knowledge_base`
- `decision_log`
- `quick_recap`
- `meeting_context`

### 7. Analyze My Meetings

```python
from meeting_performance_analyzer import MeetingPerformanceAnalyzer

# Organize my performance
analyzer = MeetingPerformanceAnalyzer(
    gemini_api_key="YOUR_API_KEY",
    database_name="company_db",
    collection_name="meeting_transcripts",
    mongodb_host="localhost",
    mongodb_port=27017,
    prompt_template="my_summary",  # Identify my tasks
    template_version="1.0",  # Use specific version (optional)
    model_name="gemini-2.0-flash"  # Select model (optional)
)

# Analyze today's meetings
from datetime import datetime
results = analyzer.analyze_multiple_meetings({
    'date': datetime.now().date()
})

# Check results
for result in results:
    analysis = result['analysis']
    print(f"Template: {analysis['template_used']}")
    print(f"Version: {analysis['template_version']}")
    print(f"Model: {analysis['model_used']}")
    print(f"Analysis: {analysis['analysis']}")
```

## 📊 Analysis Result Structure

The `analyze_meetings()` or `analyze_multiple_meetings()` methods return results in the following structure:

```python
{
    "meeting_id": "507f1f77bcf86cd799439011",  # MongoDB ObjectId (string)
    "meeting_title": "Weekly Team Meeting",     # Meeting title
    "meeting_date": "2025-11-17",               # Meeting date
    "participants": ["Minsoo Kim", "Younghee Lee"],  # Participant list (kept at top level for convenience)
    "analysis": {                               # Analysis result (includes all metadata)
        "status": "success",                    # Analysis status ("success" or "error")
        "analysis": "AI generated analysis text...",  # Actual analysis content
        "participant_stats": {                  # Statistics per participant
            "Minsoo Kim": {
                "speak_count": 15,              # Speak count
                "total_words": 234,             # Total words
                "timestamps": ["00:01:23", ...],  # List of timestamps
                "statements": ["Statement 1", ...]   # List of statements
            },
            ...
        },
        "total_statements": 45,                 # Total statements
        "template_used": "default",             # Template name used
        "template_version": "1.0",              # Template version used (None if custom)
        "model_used": "gemini-2.0-flash",       # AI model used
        "timestamp": "2025-11-17T10:30:00"      # Analysis execution time
    }
}
```

**Important Notes:**
- All analysis-related metadata (`template_used`, `template_version`, `model_used`, `participant_stats`, `total_statements`) is stored only within the `analysis` dictionary.
- Only the `participants` list is kept at the top level for quick access.
- If `status` is `"error"`, an `error` field containing the error message is included instead of `analysis`.

### 5. Analyze Already Fetched Data

```python
# If data is already fetched from MongoDB
meetings = analyzer.fetch_meeting_records({'date': today})

# Analyze fetched data directly
results = analyzer.analyze_meetings(meetings)
```

## 💡 Usage Scenarios

### Scenario 1: Check My Tasks After Meeting

```python
# Immediately after meeting
analyzer = MeetingPerformanceAnalyzer(..., prompt_template="my_summary")
my_tasks = analyzer.analyze_multiple_meetings({'date': today})

# → Identify assigned tasks, deadlines, and preparations
```

### Scenario 2: Understand Team Roles (New Joiner)

```python
# Analyze meetings from the last month
analyzer = MeetingPerformanceAnalyzer(..., prompt_template="team_collaboration")
team_info = analyzer.analyze_multiple_meetings({
    'date': {'$gte': last_month}
})

# → Who is responsible for what
# → Who to ask about what
```

### Scenario 3: Task Management

```python
# Analyze weekly meetings
analyzer = MeetingPerformanceAnalyzer(..., prompt_template="action_items")
all_tasks = analyzer.analyze_multiple_meetings({
    'date': {'$gte': this_week}
})

# → Organize in Calendar or Trello
# → Manage deadlines
```

### Scenario 4: Quick Catch-up for Missed Meetings

```python
# Quick recap
analyzer = MeetingPerformanceAnalyzer(..., prompt_template="quick_recap")
summary = analyzer.analyze_multiple_meetings({'title': 'Strategy Meeting'})

# → Grasp key points in 5 minutes
```

## 📋 Template Details

### 1. **default** - Basic Work Organization
Organize who did what and what they will do.
**Output:** Ideas, Work Coordination, Work Reporting, Quantitative Contribution.

### 2. **my_summary** - My Performance Summary
Organize what I did and what I need to do.
**Output:** My proposals, My tasks, My reports, Next steps, Speaking proportion.
**Usage:** Personal work review, Self-check.

### 3. **team_collaboration** - Team Collaboration Structure
Roles of each team member and collaboration points.
**Output:** Current roles, What they provide, What they need, Collaboration relationships, Contact points.
**Usage:** New joiners, Cross-team collaboration.

### 4. **action_items** - Action Item Management
Who needs to do what by when.
**Output:** Action items per person, Deadlines & Priorities, Prerequisites, Collaboration needs, Deliverables.
**Usage:** Task management, Schedule management.

### 5. **knowledge_base** - Knowledge Archiving
Information and insights shared in the meeting.
**Output:** Expert knowledge, Insights, Resources, Key learnings.
**Usage:** Team Wiki, Notion organization.

### 6. **decision_log** - Decision Record
What was decided and why.
**Output:** Decisions, Background & Rationale, Key contributors, Alternatives, Review points.
**Usage:** ADR (Architecture Decision Record), Retrospectives.

### 7. **quick_recap** - Quick Summary
Understand the meeting in 5 minutes.
**Output:** One-line summary per participant, Key decisions, Next actions, Notes.
**Usage:** Daily meetings, Quick sharing.

### 8. **meeting_context** - Meeting Context
How the discussion flowed.
**Output:** Meeting flow (Start/Middle/End), Contribution style, Turning points, Consensus process.
**Usage:** Reviewing decision-making process.

### 9. **comprehensive_review** - Comprehensive Review (Aggregated)
Long-term performance and growth across multiple meetings.
**Output:** Consistent contributions, Key achievements, Leadership, Growth areas, Team evolution.
**Usage:** Performance reviews, Team retrospectives.

### 10. **project_milestone** - Project Milestone (Aggregated)
Project progress and contributions across multiple meetings.
**Output:** Project contributions, Current responsibilities, Collaboration, Progress velocity, Quality impact.
**Usage:** Project status reports, Sprint reviews.

### 11. **soft_skills_growth** - Soft Skills Growth (Aggregated)
Communication style and leadership development over time.
**Output:** Communication style, Collaboration skills, Leadership, Problem-solving, Growth trajectory.
**Usage:** Professional development, Team dynamics analysis.

## 🎯 Situational Usage Guide

### Immediately After Meeting
```python
quick = analyze("quick_recap")
my_tasks = analyze("my_summary")
actions = analyze("action_items")
```

### Weekly Regular Meeting
```python
analyzer = MeetingPerformanceAnalyzer(..., prompt_template="default")
weekly = analyzer.analyze_multiple_meetings()
```

### Important Strategy Meeting
```python
overall = analyze("default")
decisions = analyze("decision_log")
knowledge = analyze("knowledge_base")
```

## 🔧 Advanced Features

### Template Version Control

```python
# Use specific version
analyzer = MeetingPerformanceAnalyzer(
    ...,
    prompt_template="default",
    template_version="1.0"
)

# Use latest version (default)
analyzer = MeetingPerformanceAnalyzer(
    ...,
    prompt_template="default"
)

# Check available versions
from prompt_templates import get_template_version
latest_version = get_template_version("default")
```

👉 [Template Version Usage Guide](VERSION_USAGE_EXAMPLE.md)

### Date Precision (Version 1.1+)

All templates now calculate specific dates instead of using relative terms:

**Before (v1.0):**
- "Complete by next week"
- "Follow up tomorrow"

**After (v1.1):**
- "Complete by 2025-11-30"
- "Follow up on 2025-11-26"

This ensures clarity when reviewing past meeting notes.

### Multilingual Prompt Templates

Prompt templates are available in multiple languages:
- **Korean:** `prompt_md/kr/`
- **English:** `prompt_md/en/`

Templates are automatically loaded based on your configuration.

### Participant Name Normalization

Integrate different notations of the same person to improve analysis accuracy.

**Automatic Normalization:**
- Remove brackets: `"Kevin[Dev]"` → `"Kevin"`
- Normalize whitespace.
- Name mapping: Integrate aliases/variations.

**How to Configure:**
Modify the `name_mapping` dictionary in `_normalize_participant_name()` method in `meeting_performance_analyzer.py`.

### Combining Multiple Templates

```python
# Analyze same meeting from multiple perspectives
meetings = analyzer.fetch_meeting_records({'title': 'Important_Meeting'})

analyzer_quick = MeetingPerformanceAnalyzer(..., prompt_template="quick_recap")
quick_results = analyzer_quick.analyze_meetings(meetings)

analyzer_mine = MeetingPerformanceAnalyzer(..., prompt_template="my_summary")
my_results = analyzer_mine.analyze_meetings(meetings)
```

### Custom Instructions

```python
results = analyzer.analyze_multiple_meetings(
    filters={'date': today},
    custom_instructions="Focus on customer feedback and technical debt."
)
```

### Model Selection

```python
# Set via environment variable
# GEMINI_MODEL=gemini-2.0-flash

# Or directly in code
analyzer = MeetingPerformanceAnalyzer(
    ...,
    model_name="gemini-2.0-flash"
)
```

## 📊 Supported Transcript Format

```
✅ [00:01:23] Minsoo Kim: Statement content
✅ [01:23] Jieun Lee: Statement content
✅ 00:01:23 Junho Park: Statement content
```

## 🎯 Practical Tips

### Notion Integration
```python
# Automatically organize in Notion after analysis
results = analyzer.analyze_multiple_meetings()
for result in results:
    notion_api.create_page(
        title=result['meeting_title'],
        content=result['analysis']['analysis']
    )
```

### Slack Sharing
```python
# Automatically send quick recap to Slack
analyzer = MeetingPerformanceAnalyzer(..., prompt_template="quick_recap")
summary = analyzer.analyze_multiple_meetings({'date': today})
slack_api.post_message(channel='#team', text=summary)
```

## 📚 Additional Documentation

- [Prompt Template Guide](PROMPT_GUIDE.md)
- [Template Version Usage Guide](VERSION_USAGE_EXAMPLE.md)
- [Schema Guide](SCHEMA_GUIDE.md)
- [Team Report Guide](team_report/TEAM_REPORT_GUIDE.md)
- [Quick Start Examples](example/quick_start_examples.py)
- [Template Selector](example/template_selector.py)
- [JSON File Analysis](example/analyze_json_file.py)

## ⚠️ Precautions

- **Gemini API**: Free plan has limits; paid plan charges by usage.
- **Token Limit**: Consider token limits for very long transcripts.
- **API Key Security**: Never expose your API key.
- **MongoDB Connection**: Use environment variables for credentials.

## 💬 FAQ

**Q: Which template should I use?**
A:
- After meeting → `my_summary` + `action_items`
- General meeting → `default`
- Quick check → `quick_recap`
- Team understanding → `team_collaboration`

**Q: How can I use the results?**
A: Organize in Notion/Confluence, share on Slack, create tasks in Trello/Jira, or write personal work notes.

**Q: Can I use this for evaluation?**
A: This tool is for **practical organization**, not evaluation. It helps individuals understand their work and facilitate team collaboration.

**Q: Can I catch up on missed meetings?**
A: Yes! Use the `quick_recap` template to grasp key points in 5 minutes.

**Q: How to analyze 50 meetings at once?**
A: Use `team_report/generate_team_report.py`.

**Q: How long does analysis take?**
A: 30s~1min per meeting.

**Q: How to manage template versions?**
A: Manage in `prompt_templates.json`. Specify `template_version` or use default (latest).

**Q: Difference between analyze_meetings and analyze_multiple_meetings?**
A: `analyze_multiple_meetings` fetches data from MongoDB then analyzes. `analyze_meetings` analyzes already fetched data list.

## 🎯 Core Principles

1. **Organization, Not Evaluation**: "What was done", not "How well it was done".
2. **Practicality**: Immediately useful for actual work.
3. **Collaboration**: Tool to work better with team members.
4. **Clarity**: Clarify what to do next.

## 📝 License

MIT License

## 🤝 Contribution

Please submit bug reports or feature suggestions as issues.

---

**Maximize your meeting efficiency now!** 🚀
