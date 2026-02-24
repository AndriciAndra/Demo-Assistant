import google.generativeai as genai
from app.config import get_settings
import json

settings = get_settings()


class GeminiService:
    """Service for Google Gemini AI content generation."""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or settings.gemini_api_key
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-2.5-flash')

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
            return json.loads(content)
        except (json.JSONDecodeError, AttributeError) as e:
            # Fallback structure with better defaults
            return self._generate_fallback_demo_content(metrics, project_name, completed_issues)

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
        Focus on impact and growth, not just numbers.
        """

        issues = metrics.get('issues', [])
        completed_issues = [i for i in issues if i.get('status', '').lower() in ['done', 'closed', 'resolved']]

        # Analyze work patterns
        by_type = metrics.get('by_type', {})

        # Find notable items (bugs fixed, features built, etc.)
        bugs_fixed = [i for i in completed_issues if i.get('issue_type', '').lower() == 'bug']
        features = [i for i in completed_issues if i.get('issue_type', '').lower() in ['story', 'feature']]
        tasks = [i for i in completed_issues if i.get('issue_type', '').lower() == 'task']

        base_context = f"""
=== WORK DATA FOR SELF-REVIEW ===

COMPLETED WORK ({len(completed_issues)} items total):
{self._format_issues_detailed(completed_issues)}

WORK BREAKDOWN:
- Features/Stories: {len(features)} items
- Tasks: {len(tasks)} items  
- Bugs Fixed: {len(bugs_fixed)} items

NOTABLE FEATURES DELIVERED:
{self._format_issues_simple(features[:5])}

BUGS RESOLVED:
{self._format_issues_simple(bugs_fixed[:5])}

KEY TASKS:
{self._format_issues_simple(tasks[:5])}
"""

        if template:
            prompt = f"""
You are helping {user_name or 'a software developer'} write their self-review/performance review.

{base_context}

=== TEMPLATE TO FOLLOW ===
{template}

=== INSTRUCTIONS ===
Fill in the template using the work data above. 

IMPORTANT GUIDELINES:
- Focus on IMPACT and VALUE delivered, not just "I completed X tasks"
- Highlight SKILLS demonstrated through the work (problem-solving, collaboration, technical expertise)
- For bugs fixed, frame as "Improved system stability" or "Enhanced user experience by resolving..."
- For features, describe the CAPABILITY delivered and WHO benefits
- Show GROWTH and LEARNING where applicable
- Be confident but not arrogant - use "I delivered", "I resolved", "I led"
- Include specific examples from the work items
- If there were challenges, show how they were overcome

Write in first person. Be professional, confident, and specific.
Do NOT include raw metrics like "completed 47 story points" - translate to outcomes.
"""
        else:
            prompt = f"""
You are helping {user_name or 'a software developer'} write their self-review/performance review.

{base_context}

=== INSTRUCTIONS ===
Generate a compelling self-review that showcases the person's contributions and value.

Structure the review with these sections:

## Summary
A powerful 2-3 sentence opening that captures the overall impact during this period.

## Key Accomplishments
The most significant contributions. For each:
- What was delivered
- Why it matters (impact on users/team/business)
- Skills demonstrated

## Technical Contributions
Specific technical work completed:
- Features built and their value
- Bugs resolved and stability improvements
- Any architectural or infrastructure work

## Collaboration & Leadership
How you supported the team:
- Cross-functional work
- Mentoring or knowledge sharing
- Process improvements

## Challenges Overcome
Problems faced and how they were solved. Shows resilience and problem-solving.

## Growth & Learning
Skills developed, new technologies learned, areas of improvement.

## Goals for Next Period
Forward-looking objectives based on current trajectory.

IMPORTANT GUIDELINES:
- Write in FIRST PERSON ("I delivered", "I resolved")
- Focus on OUTCOMES and IMPACT, not task counts
- Be SPECIFIC - reference actual work items
- Show CONFIDENCE - this is your time to shine
- Avoid metrics like "completed 15 tasks" - instead "Delivered the complete authentication system"
- Frame bug fixes positively: "Enhanced reliability of X" not "Fixed 5 bugs"
- Every point should answer "So what? Why does this matter?"

Write as polished prose with clear sections. Be professional but personable.
"""

        response = await self.model.generate_content_async(prompt)
        return response.text

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