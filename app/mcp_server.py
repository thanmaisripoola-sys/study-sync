import datetime
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("study-sync-mcp")

@mcp.tool()
def parse_syllabus_dates(syllabus_text: str) -> str:
    """Parses syllabus text and extracts exam dates, assignments, and weekly topics.

    Args:
        syllabus_text: Raw content of a course syllabus.
    """
    # Simple rule-based extraction or categorization for the demo
    lines = syllabus_text.split("\n")
    exams = []
    assignments = []
    topics = []
    
    for line in lines:
        line_lower = line.lower()
        if "exam" in line_lower or "test" in line_lower or "midterm" in line_lower or "final" in line_lower:
            exams.append(line.strip())
        elif "assignment" in line_lower or "project" in line_lower or "hw" in line_lower or "homework" in line_lower:
            assignments.append(line.strip())
        elif "week" in line_lower or "chapter" in line_lower or "topic" in line_lower:
            topics.append(line.strip())
            
    result = []
    result.append("### Extracted Syllabus Details")
    
    result.append("\n**Exams & Tests:**")
    if exams:
        result.extend(f"- {e}" for e in exams[:5])
    else:
        result.append("- No specific exam references found.")
        
    result.append("\n**Assignments & Projects:**")
    if assignments:
        result.extend(f"- {a}" for a in assignments[:5])
    else:
        result.append("- No specific assignment references found.")
        
    result.append("\n**Weekly Topics / Chapters:**")
    if topics:
        result.extend(f"- {t}" for t in topics[:8])
    else:
        result.append("- No specific weekly schedule found in text.")
        
    return "\n".join(result)


@mcp.tool()
def generate_calendar_weeks(start_date_str: str, num_weeks: int = 4) -> str:
    """Generates consecutive calendar week intervals for study planning starting from a given date.

    Args:
        start_date_str: The starting date in YYYY-MM-DD format.
        num_weeks: Number of weeks to generate.
    """
    try:
        start_date = datetime.datetime.strptime(start_date_str, "%Y-%m-%d")
    except ValueError:
        return f"Error: Start date must be in YYYY-MM-DD format. Got: {start_date_str}"
        
    weeks = []
    for i in range(num_weeks):
        w_start = start_date + datetime.timedelta(weeks=i)
        w_end = w_start + datetime.timedelta(days=6)
        weeks.append(f"Week {i+1}: {w_start.strftime('%Y-%m-%d')} to {w_end.strftime('%Y-%m-%d')}")
        
    return "\n".join(weeks)


@mcp.tool()
def suggest_focus_techniques(subject_difficulty: str) -> str:
    """Recommends specific productivity/study techniques based on course/subject difficulty.

    Args:
        subject_difficulty: Difficulty category (e.g. 'high', 'medium', 'low', or subject name).
    """
    diff = subject_difficulty.lower()
    if "high" in diff or "hard" in diff or "difficult" in diff or "math" in diff or "science" in diff:
        return (
            "Recommended Techniques for High Difficulty:\n"
            "1. **Feynman Technique**: Explain concepts in simple terms to find knowledge gaps.\n"
            "2. **Active Recall**: Test yourself regularly instead of re-reading.\n"
            "3. **Pomodoro (50/10)**: Study intensely for 50 minutes, then take a 10-minute break."
        )
    elif "medium" in diff or "moderate" in diff:
        return (
            "Recommended Techniques for Medium Difficulty:\n"
            "1. **Spaced Repetition**: Review flashcards at increasing intervals.\n"
            "2. **Pomodoro (25/5)**: 25 minutes study, 5 minutes break. Repeat 4 times."
        )
    else:
        return (
            "Recommended Techniques for General/Low Difficulty:\n"
            "1. **Time Blocking**: Dedicate 1-hour slots to complete tasks.\n"
            "2. **Mind Mapping**: Create visual maps of the concepts."
        )

if __name__ == "__main__":
    mcp.run("stdio")
