from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from typing import Optional


class SlidesService:
    """Service for creating Google Slides presentations."""
    
    def __init__(self, credentials: Credentials):
        self.credentials = credentials
        self.service = build('slides', 'v1', credentials=credentials)
        self.drive_service = build('drive', 'v3', credentials=credentials)
    
    async def create_presentation(self, title: str) -> str:
        """Create a new presentation and return its ID."""
        presentation = self.service.presentations().create(
            body={"title": title}
        ).execute()
        return presentation.get('presentationId')
    
    async def create_demo_presentation(self, content: dict) -> dict:
        """Create a complete demo presentation from generated content."""
        # Create presentation
        presentation_id = await self.create_presentation(content.get("title", "Demo"))
        
        # Build requests for slides
        requests = []
        
        # Slide 1: Title slide (already exists, just update it)
        requests.extend(self._create_title_slide_requests(
            content.get("title", "Demo"),
            content.get("subtitle", "")
        ))
        
        # Slide 2: Highlights
        if content.get("highlights"):
            requests.extend(self._create_bullet_slide_requests(
                "Highlights",
                content["highlights"]
            ))
        
        # Content sections
        for section in content.get("sections", []):
            requests.extend(self._create_bullet_slide_requests(
                section.get("title", "Section"),
                section.get("bullet_points", [])
            ))
        
        # Key achievements slide
        if content.get("key_achievements"):
            requests.extend(self._create_bullet_slide_requests(
                "Key Achievements",
                content["key_achievements"]
            ))
        
        # Next steps slide
        if content.get("next_steps"):
            requests.extend(self._create_bullet_slide_requests(
                "Next Steps",
                content["next_steps"]
            ))
        
        # Execute all requests
        if requests:
            self.service.presentations().batchUpdate(
                presentationId=presentation_id,
                body={"requests": requests}
            ).execute()
        
        # Get presentation URL
        presentation_url = f"https://docs.google.com/presentation/d/{presentation_id}/edit"
        
        return {
            "presentation_id": presentation_id,
            "url": presentation_url
        }
    
    def _create_title_slide_requests(self, title: str, subtitle: str) -> list:
        """Create requests for updating the title slide."""
        # Get the first slide's page elements
        # For simplicity, we'll create a new slide with title layout
        return [
            {
                "createSlide": {
                    "insertionIndex": 0,
                    "slideLayoutReference": {
                        "predefinedLayout": "TITLE"
                    },
                    "placeholderIdMappings": [
                        {
                            "layoutPlaceholder": {"type": "CENTERED_TITLE"},
                            "objectId": "title_text"
                        },
                        {
                            "layoutPlaceholder": {"type": "SUBTITLE"},
                            "objectId": "subtitle_text"
                        }
                    ]
                }
            },
            {
                "insertText": {
                    "objectId": "title_text",
                    "text": title
                }
            },
            {
                "insertText": {
                    "objectId": "subtitle_text",
                    "text": subtitle
                }
            }
        ]
    
    def _create_bullet_slide_requests(self, title: str, bullets: list) -> list:
        """Create requests for a bullet point slide."""
        import uuid
        slide_id = f"slide_{uuid.uuid4().hex[:8]}"
        title_id = f"title_{uuid.uuid4().hex[:8]}"
        body_id = f"body_{uuid.uuid4().hex[:8]}"
        
        bullet_text = "\n".join(f"• {bullet}" for bullet in bullets)
        
        return [
            {
                "createSlide": {
                    "objectId": slide_id,
                    "slideLayoutReference": {
                        "predefinedLayout": "TITLE_AND_BODY"
                    },
                    "placeholderIdMappings": [
                        {
                            "layoutPlaceholder": {"type": "TITLE"},
                            "objectId": title_id
                        },
                        {
                            "layoutPlaceholder": {"type": "BODY"},
                            "objectId": body_id
                        }
                    ]
                }
            },
            {
                "insertText": {
                    "objectId": title_id,
                    "text": title
                }
            },
            {
                "insertText": {
                    "objectId": body_id,
                    "text": bullet_text
                }
            }
        ]
    
    async def share_presentation(
        self,
        presentation_id: str,
        email: str,
        role: str = "reader"
    ) -> None:
        """Share presentation with a user."""
        self.drive_service.permissions().create(
            fileId=presentation_id,
            body={
                "type": "user",
                "role": role,
                "emailAddress": email
            },
            sendNotificationEmail=False
        ).execute()
    
    async def copy_to_drive_folder(
        self,
        presentation_id: str,
        folder_id: str,
        new_name: Optional[str] = None
    ) -> str:
        """Copy presentation to a specific Drive folder."""
        body = {"parents": [folder_id]}
        if new_name:
            body["name"] = new_name
        
        copied = self.drive_service.files().copy(
            fileId=presentation_id,
            body=body
        ).execute()
        
        return copied.get("id")
