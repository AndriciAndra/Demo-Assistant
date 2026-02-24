from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from typing import Optional
import uuid


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
        """
        Create a complete demo presentation from generated content.
        Supports both old and new content structures for backwards compatibility.
        """
        # Create presentation
        presentation_id = await self.create_presentation(content.get("title", "Demo"))

        # Build requests for slides
        requests = []

        # Slide 1: Title slide
        requests.extend(self._create_title_slide_requests(
            content.get("title", "Demo"),
            content.get("subtitle", "")
        ))

        # Slide 2: Executive Summary (if present - new structure)
        if content.get("executive_summary"):
            requests.extend(self._create_text_slide_requests(
                "Executive Summary",
                content["executive_summary"]
            ))

        # Slide 3: Highlights
        if content.get("highlights"):
            requests.extend(self._create_bullet_slide_requests(
                "Sprint Highlights",
                content["highlights"]
            ))

        # Content sections (new structure with description + items)
        for section in content.get("sections", []):
            section_title = section.get("title", "Section")

            # New structure: sections have 'items' not 'bullet_points'
            items = section.get("items") or section.get("bullet_points", [])
            description = section.get("description", "")

            if description and items:
                # Create slide with description as intro
                full_items = [description] + items
                requests.extend(self._create_bullet_slide_requests(
                    section_title,
                    full_items
                ))
            elif items:
                requests.extend(self._create_bullet_slide_requests(
                    section_title,
                    items
                ))

        # Challenges & Solutions slide (new structure)
        if content.get("challenges_and_solutions"):
            challenges = []
            for item in content["challenges_and_solutions"]:
                if isinstance(item, dict):
                    challenge = item.get("challenge", "")
                    solution = item.get("solution", "")
                    challenges.append(f"Challenge: {challenge}")
                    challenges.append(f"→ Solution: {solution}")
                else:
                    challenges.append(str(item))

            if challenges:
                requests.extend(self._create_bullet_slide_requests(
                    "Challenges & Solutions",
                    challenges
                ))

        # Work In Progress slide (new structure)
        if content.get("in_progress"):
            requests.extend(self._create_bullet_slide_requests(
                "Work In Progress",
                content["in_progress"]
            ))

        # Key achievements slide (old structure - backwards compatibility)
        if content.get("key_achievements"):
            requests.extend(self._create_bullet_slide_requests(
                "Key Achievements",
                content["key_achievements"]
            ))

        # Next Steps / Next Sprint Preview
        next_items = content.get("next_sprint_preview") or content.get("next_steps", [])
        if next_items:
            requests.extend(self._create_bullet_slide_requests(
                "Next Sprint Preview",
                next_items
            ))

        # Demo Talking Points (new structure)
        if content.get("demo_talking_points"):
            requests.extend(self._create_bullet_slide_requests(
                "Demo Talking Points",
                content["demo_talking_points"]
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
        """Create requests for the title slide."""
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
        slide_id = f"slide_{uuid.uuid4().hex[:8]}"
        title_id = f"title_{uuid.uuid4().hex[:8]}"
        body_id = f"body_{uuid.uuid4().hex[:8]}"

        bullet_text = "\n".join(f"• {bullet}" for bullet in bullets if bullet)

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

    def _create_text_slide_requests(self, title: str, text: str) -> list:
        """Create requests for a slide with a paragraph of text (no bullets)."""
        slide_id = f"slide_{uuid.uuid4().hex[:8]}"
        title_id = f"title_{uuid.uuid4().hex[:8]}"
        body_id = f"body_{uuid.uuid4().hex[:8]}"

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
                    "text": text
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