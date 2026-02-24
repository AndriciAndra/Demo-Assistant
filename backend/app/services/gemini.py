import google.generativeai as genai
from app.config import get_settings
import json
import re

settings = get_settings()


def markdown_to_pdf(text: str) -> str:
    """
    Convert markdown formatting to ReportLab-compatible HTML tags.
    ReportLab Paragraph supports: <b>, <i>, <u>, <br/>, <font>
    """
    if not text:
        return text

    # Convert bold: **text** or __text__ -> <b>text</b>
    text = re.sub(r'\*\*\*(.+?)\*\*\*', r'<b><i>\1</i></b>', text)  # bold italic
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'__(.+?)__', r'<b>\1</b>', text)

    # Convert italic: *text* or _text_ -> <i>text</i>
    text = re.sub(r'\*(.+?)\*', r'<i>\1</i>', text)
    text = re.sub(r'(?<!\w)_(.+?)_(?!\w)', r'<i>\1</i>', text)

    # Remove markdown headers (## Title -> Title) - PDF will handle section styling separately
    text = re.sub(r'^#{1,6}\s*', '', text, flags=re.MULTILINE)

    # Remove code blocks
    text = re.sub(r'```[\s\S]*?```', '', text)
    text = re.sub(r'`(.+?)`', r'\1', text)

    # Remove horizontal rules
    text = re.sub(r'^[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)

    # Clean up extra whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()


def markdown_to_plain(text: str) -> str:
    """
    Remove all markdown formatting for plain text output (Google Slides).
    Slides formatting is done via API, not inline markup.
    """
    if not text:
        return text

    # Remove bold/italic markers
    text = re.sub(r'\*\*\*(.+?)\*\*\*', r'\1', text)
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*', r'\1', text)
    text = re.sub(r'__(.+?)__', r'\1', text)
    text = re.sub(r'_(.+?)_', r'\1', text)

    # Remove headers
    text = re.sub(r'^#{1,6}\s*', '', text, flags=re.MULTILINE)

    # Remove code blocks
    text = re.sub(r'```[\s\S]*?```', '', text)
    text = re.sub(r'`(.+?)`', r'\1', text)

    # Remove horizontal rules
    text = re.sub(r'^[-*_]{3,}\s*$', '', text, flags=re.MULTILINE)

    # Clean up extra whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()


class GeminiService:
    """Service for Google Gemini AI content generation."""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or settings.gemini_api_key
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-2.5-flash-lite')

    async def generate_demo_content(self, metrics: dict, project_name: str, sprint_name: str = None) -> dict:
        """
        Generate demo presentation content focused on WHAT was achieved, not just numbers.
        Tells the story of the sprint.
        """

        # Categorize issues by status and type for better narrative
        issues = metrics.get('issues', [])
        completed_issues = [i for i in issues if i.get('status', '').lower() in ['done', 'closed', 'resolved']]
        in_progress_issues = [i for i in issues if i.get('status', '').lower() in ['in progress', 'in review']]
        blocked_or_todo = [i for i in issues if
                           i.get('status', '').lower() not in ['done', 'closed', 'resolved', 'in progress',
                                                               'in review']]

        # Group completed by type for narrative
        completed_by_type = {}
        for issue in completed_issues:
            t = issue.get('issue_type', 'Task')
            if t not in completed_by_type:
                completed_by_type[t] = []
            completed_by_type[t].append(issue.get('summary', ''))

        prompt = f"""
You are creating content for a SPRINT DEMO PRESENTATION for project "{project_name}"{f' - {sprint_name}' if sprint_name else ''}.

Your goal is to tell the STORY of what was accomplished this sprint - NOT just list numbers.
The audience wants to understand WHAT was built, WHY it matters, and WHAT'S NEXT.

=== SPRINT DATA ===

COMPLETED WORK ({len(completed_issues)} items):
{self._format_issues_detailed(completed_issues)}

WORK IN PROGRESS ({len(in_progress_issues)} items):
{self._format_issues_detailed(in_progress_issues)}

REMAINING/BLOCKED ({len(blocked_or_todo)} items):
{self._format_issues_detailed(blocked_or_todo)}

WORK BY TYPE:
{json.dumps(completed_by_type, indent=2)}

=== INSTRUCTIONS ===

Create a compelling demo narrative that:
1. **Highlights** - What are the 3-4 MOST IMPORTANT things delivered? Focus on user/business value, not "completed X tasks"
2. **Features Delivered** - Group related work into logical features/capabilities. Describe what each enables.
3. **Technical Achievements** - Any significant technical work (architecture, integrations, performance)
4. **Challenges & Solutions** - Were there any blockers overcome? Complex problems solved?
5. **Work In Progress** - What's actively being worked on and expected soon?
6. **Next Steps** - What's planned for next sprint based on remaining work?

IMPORTANT GUIDELINES:
- DO NOT say "Completed 15 tasks" - instead say "Delivered user authentication with OAuth support"
- DO NOT focus on story points - focus on CAPABILITIES delivered
- DO write as if presenting to stakeholders who care about OUTCOMES
- DO group related items into cohesive features
- DO mention any bugs fixed as "improvements to X" or "stability fixes for Y"
- If there are blockers or incomplete items, frame them constructively

Generate a JSON response with this EXACT structure:
{{
    "title": "Sprint Demo: [Compelling title describing main achievement]",
    "subtitle": "[Project name] - [Sprint name or date range]",
    "executive_summary": "One paragraph (2-3 sentences) summarizing the sprint's main accomplishments and value delivered",
    "highlights": [
        "First major highlight focusing on value/capability",
        "Second major highlight",
        "Third major highlight"
    ],
    "sections": [
        {{
            "title": "Section title (e.g., 'User Authentication', 'Dashboard Improvements')",
            "description": "Brief description of this feature area",
            "items": ["Specific item delivered", "Another item", "etc"]
        }}
    ],
    "challenges_and_solutions": [
        {{
            "challenge": "What was the challenge",
            "solution": "How it was resolved"
        }}
    ],
    "in_progress": [
        "Work item in progress with expected outcome"
    ],
    "next_sprint_preview": [
        "What's planned next"
    ],
    "demo_talking_points": [
        "Key point to mention during live demo",
        "Another talking point"
    ]
}}

Return ONLY valid JSON, no markdown formatting or code blocks.
"""

        response = await self.model.generate_content_async(prompt)

        # Parse JSON from response
        try:
            content = response.text.strip()
            # Remove markdown code blocks if present
            if content.startswith("```"):
                lines = content.split("\n")
                content = "\n".join(lines[1:-1])
                if content.startswith("json"):
                    content = content[4:]
            parsed = json.loads(content)
            # Clean markdown from all string values in the JSON
            return self._clean_demo_content(parsed)
        except (json.JSONDecodeError, AttributeError) as e:
            # Fallback structure with better defaults
            return self._generate_fallback_demo_content(metrics, project_name, completed_issues)

    def _clean_demo_content(self, content: dict) -> dict:
        """Recursively clean markdown from all strings in demo content for Slides."""
        if isinstance(content, str):
            return markdown_to_plain(content)
        elif isinstance(content, list):
            return [self._clean_demo_content(item) for item in content]
        elif isinstance(content, dict):
            return {key: self._clean_demo_content(value) for key, value in content.items()}
        return content

    def _generate_fallback_demo_content(self, metrics: dict, project_name: str, completed_issues: list) -> dict:
        """Generate fallback content if AI fails."""
        # Group by type
        by_type = {}
        for issue in completed_issues[:10]:
            t = issue.get('issue_type', 'Task')
            if t not in by_type:
                by_type[t] = []
            by_type[t].append(issue.get('summary', 'Work item'))

        sections = []
        for issue_type, items in by_type.items():
            sections.append({
                "title": f"{issue_type}s Completed",
                "description": f"Key {issue_type.lower()}s delivered this sprint",
                "items": items[:5]
            })

        return {
            "title": f"Sprint Demo: {project_name}",
            "subtitle": "Sprint Progress Overview",
            "executive_summary": f"This sprint focused on delivering key functionality with {len(completed_issues)} items completed.",
            "highlights": [issue.get('summary', '') for issue in completed_issues[:3]],
            "sections": sections,
            "challenges_and_solutions": [],
            "in_progress": [],
            "next_sprint_preview": [],
            "demo_talking_points": []
        }

    async def generate_self_review(self, metrics: dict, user_name: str = None, template: str = None) -> str:
        """
        Generate self-review content that HIGHLIGHTS the person's contributions and value.
        Focus on impact and growth, not just numbers or ticket references.
        """

        issues = metrics.get('issues', [])
        completed_issues = [i for i in issues if i.get('status', '').lower() in ['done', 'closed', 'resolved']]

        # Analyze work patterns
        by_type = metrics.get('by_type', {})

        # Find notable items (bugs fixed, features built, etc.)
        bugs_fixed = [i for i in completed_issues if i.get('issue_type', '').lower() == 'bug']
        features = [i for i in completed_issues if i.get('issue_type', '').lower() in ['story', 'feature']]
        tasks = [i for i in completed_issues if i.get('issue_type', '').lower() == 'task']

        # Extract themes from work (summaries grouped by type)
        feature_summaries = [i.get('summary', '') for i in features[:10]]
        bug_summaries = [i.get('summary', '') for i in bugs_fixed[:10]]
        task_summaries = [i.get('summary', '') for i in tasks[:10]]

        base_context = f"""
=== WORK CONTEXT FOR SELF-REVIEW ===

OVERVIEW:
- Total items delivered: {len(completed_issues)}
- Features/Stories: {len(features)}
- Tasks completed: {len(tasks)}
- Bugs resolved: {len(bugs_fixed)}

FEATURE WORK THEMES (for context, DO NOT list these individually):
{chr(10).join(f'- {s}' for s in feature_summaries) if feature_summaries else '- No features this period'}

BUG FIX THEMES (for context, DO NOT list these individually):
{chr(10).join(f'- {s}' for s in bug_summaries) if bug_summaries else '- No bugs fixed this period'}

TASK THEMES (for context, DO NOT list these individually):
{chr(10).join(f'- {s}' for s in task_summaries) if task_summaries else '- No tasks this period'}
"""

        if template:
            prompt = f"""
You are helping {user_name or 'a software professional'} write their self-review/performance review.

{base_context}

=== TEMPLATE TO FOLLOW ===
{template}

=== CRITICAL INSTRUCTIONS ===

1. NEVER mention specific ticket numbers, issue keys, or task IDs
2. NEVER list individual tasks or say "For example, I worked on [specific ticket]"
3. DO write in flowing, professional prose
4. DO focus on THEMES, PATTERNS, and OVERALL IMPACT of the work
5. DO highlight skills demonstrated: problem-solving, technical expertise, collaboration
6. DO quantify impact where meaningful (e.g., "improved system reliability", "streamlined processes")
7. DO write confidently in first person ("I delivered", "I contributed", "I drove")

For bugs fixed → write about "improving system stability" or "enhancing user experience"
For features → write about "delivering new capabilities" or "enabling users to..."
For tasks → write about "supporting team objectives" or "driving operational improvements"

The review should read like a polished professional document, NOT a task list.
"""
        else:
            prompt = f"""
You are helping {user_name or 'a software professional'} write their self-review/performance review.

{base_context}

=== CRITICAL INSTRUCTIONS ===

Generate a compelling, narrative self-review that showcases contributions and impact.

ABSOLUTE RULES:
1. NEVER mention specific ticket numbers, issue keys, or task IDs
2. NEVER list individual tasks or say "I completed task X, Y, Z"
3. NEVER use bullet points for listing work items
4. DO write in flowing, professional prose paragraphs
5. DO focus on THEMES and OVERALL IMPACT
6. DO highlight skills and growth
7. DO write confidently in first person

=== STRUCTURE ===

**SUMMARY**
A powerful 2-3 sentence opening that captures overall impact and value delivered during this period. Set the tone for a strong review.

**KEY CONTRIBUTIONS**
Write 2-3 paragraphs describing the THEMES of your work and their impact. Group related work conceptually:
- If you built features → describe the capabilities delivered and who benefits
- If you fixed bugs → describe how you improved reliability/quality/user experience
- If you completed tasks → describe how you supported team and business objectives

Focus on the "so what" - why did this work matter?

**TECHNICAL EXCELLENCE**
A paragraph highlighting technical skills demonstrated through your work. Mention areas like problem-solving approaches, technical domains you contributed to, and quality in your work.

**COLLABORATION & IMPACT**
A paragraph on how you worked with others and your broader impact, including cross-functional collaboration, knowledge sharing, and supporting team success.

**GROWTH & DEVELOPMENT**
A paragraph reflecting on skills developed and areas of professional growth during this period.

**LOOKING AHEAD**
A brief forward-looking paragraph on goals and focus areas for the next period.

=== FORMATTING ===
- Use **bold** for section titles and key phrases you want to emphasize
- Write in flowing prose paragraphs
- NO bullet points for listing work items
- NO ticket references or task IDs

=== TONE ===
- Confident but not arrogant
- Professional and polished
- Specific about impact, general about tasks
- Reads like a narrative, not a report
"""

        response = await self.model.generate_content_async(prompt)
        # Convert markdown to PDF-compatible HTML tags
        return markdown_to_pdf(response.text)

    async def recommend_template(self, metrics: dict) -> str:
        """Generate a recommended template based on work data."""

        by_type = metrics.get('by_type', {})
        total = metrics.get('total_issues', 0)

        # Determine work focus
        has_bugs = by_type.get('Bug', 0) > 0
        has_features = by_type.get('Story', 0) > 0 or by_type.get('Feature', 0) > 0

        prompt = f"""
Based on this work profile, create a self-review template:

Work types: {by_type}
Total items: {total}

Create a template with sections and placeholder prompts like [Describe...] that fit this work profile.

For example, if someone fixed many bugs, include a "System Reliability" section.
If someone built features, include "Feature Delivery" section.

The template should:
1. Have 4-6 sections
2. Include guiding prompts in [brackets] for each section
3. Focus on IMPACT, not metrics
4. Be professional but allow personality

Return ONLY the template text, ready to be filled in.
"""

        response = await self.model.generate_content_async(prompt)
        return response.text

    def _format_issues_detailed(self, issues: list) -> str:
        """Format issues with full details for AI context."""
        if not issues:
            return "None"

        lines = []
        for issue in issues[:20]:  # Limit to 20 for context
            if isinstance(issue, dict):
                key = issue.get('key', '')
                summary = issue.get('summary', 'No summary')
                issue_type = issue.get('issue_type', 'Task')
                status = issue.get('status', 'Unknown')
                points = issue.get('story_points', '')

                line = f"- [{key}] ({issue_type}) {summary}"
                if status:
                    line += f" - Status: {status}"
                if points:
                    line += f" [{points} pts]"
                lines.append(line)

        return "\n".join(lines) if lines else "None"

    def _format_issues_simple(self, issues: list) -> str:
        """Format issues simply - just summaries."""
        if not issues:
            return "None"

        lines = []
        for issue in issues[:10]:
            if isinstance(issue, dict):
                summary = issue.get('summary', 'No summary')
                lines.append(f"- {summary}")

        return "\n".join(lines) if lines else "None"

    # Legacy method for backwards compatibility
    def _format_issues(self, issues: list) -> str:
        """Format issues for prompt (legacy)."""
        return self._format_issues_detailed(issues)