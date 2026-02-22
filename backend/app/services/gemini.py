import google.generativeai as genai
from app.config import get_settings
import json

settings = get_settings()


class GeminiService:
    """Service for Google Gemini AI content generation."""

    def __init__(self, api_key: str = None):
        self.api_key = api_key or settings.gemini_api_key
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel("gemini-2.5-flash")

    async def generate_demo_content(self, metrics: dict, project_name: str) -> dict:
        """Generate demo presentation content from metrics."""
        prompt = f"""
        Create content for a demo presentation about the work completed in project "{project_name}".

        Here are the metrics:
        - Total issues worked on: {metrics.get('total_issues', 0)}
        - Completed issues: {metrics.get('completed_issues', 0)}
        - Completion rate: {metrics.get('completion_rate', 0)}%
        - Story points completed: {metrics.get('completed_story_points', 0)}
        - Issues by type: {metrics.get('by_type', {})}

        Top completed items:
        {self._format_issues(metrics.get('issues', [])[:10])}

        Generate a JSON response with this structure:
        {{
            "title": "Demo presentation title",
            "subtitle": "Brief subtitle with date range",
            "highlights": ["highlight 1", "highlight 2", "highlight 3"],
            "sections": [
                {{
                    "title": "Section title",
                    "bullet_points": ["point 1", "point 2", "point 3"]
                }}
            ],
            "key_achievements": ["achievement 1", "achievement 2"],
            "next_steps": ["next step 1", "next step 2"]
        }}

        Make it professional, concise, and focused on value delivered.
        Return ONLY valid JSON, no markdown formatting.
        """

        response = self.model.generate_content(prompt)

        # Parse JSON from response
        try:
            content = response.text.strip()
            # Remove markdown code blocks if present
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            return json.loads(content)
        except (json.JSONDecodeError, AttributeError):
            # Fallback structure
            return {
                "title": f"{project_name} Demo",
                "subtitle": "Sprint Progress Overview",
                "highlights": [
                    f"Completed {metrics.get('completed_issues', 0)} issues",
                    f"{metrics.get('completion_rate', 0)}% completion rate",
                    f"{metrics.get('completed_story_points', 0)} story points delivered"
                ],
                "sections": [],
                "key_achievements": [],
                "next_steps": []
            }

    async def generate_self_review(self, metrics: dict, template: str = None) -> str:
        """Generate self-review content based on work metrics."""
        base_prompt = f"""
        Generate a professional self-review based on this work data:

        - Total issues handled: {metrics.get('total_issues', 0)}
        - Completed: {metrics.get('completed_issues', 0)}
        - Completion rate: {metrics.get('completion_rate', 0)}%
        - Story points delivered: {metrics.get('completed_story_points', 0)}
        - Work by type: {metrics.get('by_type', {})}

        Key items worked on:
        {self._format_issues(metrics.get('issues', [])[:15])}
        """

        if template:
            prompt = f"""
            {base_prompt}

            Use this template structure:
            {template}

            Fill in the template with relevant content from the metrics above.
            Be specific, quantitative, and professional.
            """
        else:
            prompt = f"""
            {base_prompt}

            Structure the self-review with these sections:
            1. Summary of Accomplishments
            2. Key Contributions
            3. Challenges Overcome
            4. Areas for Growth
            5. Goals for Next Period

            Be specific, quantitative, and professional.
            Use bullet points for clarity.
            """

        response = self.model.generate_content(prompt)
        return response.text

    async def recommend_template(self, metrics: dict) -> str:
        """Generate a recommended template based on work data."""
        prompt = f"""
        Based on this work data, suggest the best self-review template structure:

        - Issue types: {metrics.get('by_type', {})}
        - Total items: {metrics.get('total_issues', 0)}
        - Completion rate: {metrics.get('completion_rate', 0)}%

        Create a template with placeholders like [DESCRIBE_X] that would be most relevant.
        Include sections that highlight the type of work done.

        Return ONLY the template text, no explanations.
        """

        response = self.model.generate_content(prompt)
        return response.text

    def _format_issues(self, issues: list) -> str:
        """Format issues for prompt."""
        if not issues:
            return "No issues data available"

        lines = []
        for issue in issues[:15]:
            if isinstance(issue, dict):
                status = issue.get('status', 'Unknown')
                summary = issue.get('summary', 'No summary')
                issue_type = issue.get('issue_type', 'Task')
                lines.append(f"- [{issue_type}] {summary} ({status})")

        return "\n".join(lines) if lines else "No issues data available"