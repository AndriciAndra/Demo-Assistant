import httpx
from typing import Optional
from datetime import datetime
from app.models.schemas import JiraProject, JiraSprint, JiraIssue


class JiraClient:
    """Client for Jira REST API."""
    
    def __init__(self, base_url: str, email: str, api_token: str):
        self.base_url = base_url.rstrip("/")
        self.auth = (email, api_token)
        self.headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
    
    async def _request(self, method: str, endpoint: str, **kwargs) -> dict:
        """Make authenticated request to Jira API."""
        url = f"{self.base_url}/rest/api/3/{endpoint}"
        
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method=method,
                url=url,
                auth=self.auth,
                headers=self.headers,
                **kwargs
            )
            response.raise_for_status()
            return response.json()
    
    async def _agile_request(self, method: str, endpoint: str, **kwargs) -> dict:
        """Make request to Jira Agile API."""
        url = f"{self.base_url}/rest/agile/1.0/{endpoint}"
        
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method=method,
                url=url,
                auth=self.auth,
                headers=self.headers,
                **kwargs
            )
            response.raise_for_status()
            return response.json()
    
    async def test_connection(self) -> bool:
        """Test if credentials are valid."""
        try:
            await self._request("GET", "myself")
            return True
        except Exception:
            return False
    
    async def get_projects(self) -> list[JiraProject]:
        """Get all accessible projects."""
        data = await self._request("GET", "project")
        return [
            JiraProject(
                key=p["key"],
                name=p["name"],
                project_type=p.get("projectTypeKey")
            )
            for p in data
        ]
    
    async def get_board_id(self, project_key: str) -> Optional[int]:
        """Get the board ID for a project."""
        data = await self._agile_request(
            "GET",
            "board",
            params={"projectKeyOrId": project_key}
        )
        boards = data.get("values", [])
        return boards[0]["id"] if boards else None
    
    async def get_sprints(self, board_id: int, state: str = None) -> list[JiraSprint]:
        """Get sprints for a board. State can be: active, closed, future."""
        params = {}
        if state:
            params["state"] = state
        
        data = await self._agile_request(
            "GET",
            f"board/{board_id}/sprint",
            params=params
        )
        
        sprints = []
        for s in data.get("values", []):
            sprints.append(JiraSprint(
                id=s["id"],
                name=s["name"],
                state=s["state"],
                start_date=s.get("startDate"),
                end_date=s.get("endDate"),
                goal=s.get("goal")
            ))
        return sprints
    
    async def get_sprint_issues(self, sprint_id: int) -> list[JiraIssue]:
        """Get all issues in a sprint."""
        data = await self._agile_request(
            "GET",
            f"sprint/{sprint_id}/issue",
            params={"maxResults": 100}
        )
        return self._parse_issues(data.get("issues", []))
    
    async def get_issues_by_date_range(
        self,
        project_key: str,
        start_date: datetime,
        end_date: datetime,
        assignee: Optional[str] = None
    ) -> list[JiraIssue]:
        """Get issues updated within a date range using JQL."""
        jql = f'project = "{project_key}" AND updated >= "{start_date.strftime("%Y-%m-%d")}" AND updated <= "{end_date.strftime("%Y-%m-%d")}"'
        
        if assignee:
            jql += f' AND assignee = "{assignee}"'
        
        jql += " ORDER BY updated DESC"
        
        data = await self._request(
            "GET",
            "search",
            params={
                "jql": jql,
                "maxResults": 100,
                "fields": "summary,status,issuetype,assignee,priority,labels,created,resolutiondate,customfield_10016"
            }
        )
        return self._parse_issues(data.get("issues", []))
    
    async def get_velocity(self, board_id: int, sprints: int = 5) -> dict:
        """Calculate velocity from recent completed sprints."""
        closed_sprints = await self.get_sprints(board_id, state="closed")
        recent_sprints = closed_sprints[-sprints:] if len(closed_sprints) > sprints else closed_sprints
        
        velocity_data = []
        for sprint in recent_sprints:
            issues = await self.get_sprint_issues(sprint.id)
            completed_points = sum(
                i.story_points or 0
                for i in issues
                if i.status.lower() in ["done", "closed", "resolved"]
            )
            velocity_data.append({
                "sprint_name": sprint.name,
                "completed_points": completed_points
            })
        
        avg_velocity = (
            sum(v["completed_points"] for v in velocity_data) / len(velocity_data)
            if velocity_data else 0
        )
        
        return {
            "sprints": velocity_data,
            "average_velocity": round(avg_velocity, 1)
        }
    
    def _parse_issues(self, issues: list[dict]) -> list[JiraIssue]:
        """Parse raw Jira issues into JiraIssue objects."""
        parsed = []
        for issue in issues:
            fields = issue.get("fields", {})
            
            # Get assignee name
            assignee = None
            if fields.get("assignee"):
                assignee = fields["assignee"].get("displayName")
            
            # Get story points (custom field - may vary by Jira instance)
            story_points = fields.get("customfield_10016")  # Common field ID
            
            parsed.append(JiraIssue(
                key=issue["key"],
                summary=fields.get("summary", ""),
                status=fields.get("status", {}).get("name", "Unknown"),
                issue_type=fields.get("issuetype", {}).get("name", "Task"),
                assignee=assignee,
                story_points=story_points,
                priority=fields.get("priority", {}).get("name"),
                labels=fields.get("labels", []),
                created=fields.get("created"),
                resolved=fields.get("resolutiondate")
            ))
        return parsed
    
    async def get_project_metrics(
        self,
        project_key: str,
        start_date: datetime,
        end_date: datetime
    ) -> dict:
        """Get comprehensive metrics for a project within date range."""
        issues = await self.get_issues_by_date_range(project_key, start_date, end_date)
        
        # Calculate metrics
        total_issues = len(issues)
        completed = [i for i in issues if i.status.lower() in ["done", "closed", "resolved"]]
        in_progress = [i for i in issues if i.status.lower() in ["in progress", "in review"]]
        
        # Story points
        total_points = sum(i.story_points or 0 for i in issues)
        completed_points = sum(i.story_points or 0 for i in completed)
        
        # By type
        by_type = {}
        for issue in issues:
            by_type[issue.issue_type] = by_type.get(issue.issue_type, 0) + 1
        
        # By assignee
        by_assignee = {}
        for issue in issues:
            name = issue.assignee or "Unassigned"
            by_assignee[name] = by_assignee.get(name, 0) + 1
        
        return {
            "total_issues": total_issues,
            "completed_issues": len(completed),
            "in_progress_issues": len(in_progress),
            "completion_rate": round(len(completed) / total_issues * 100, 1) if total_issues > 0 else 0,
            "total_story_points": total_points,
            "completed_story_points": completed_points,
            "by_type": by_type,
            "by_assignee": by_assignee,
            "issues": [i.model_dump() for i in issues]
        }
