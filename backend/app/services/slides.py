from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from typing import Optional
import uuid

COLORS = {
    'primary': {'red': 0.29, 'green': 0.33, 'blue': 0.55},
    'secondary': {'red': 0.38, 'green': 0.40, 'blue': 0.95},
    'accent': {'red': 0.06, 'green': 0.72, 'blue': 0.51},
    'dark': {'red': 0.10, 'green': 0.10, 'blue': 0.18},
    'light': {'red': 0.96, 'green': 0.96, 'blue': 0.98},
    'white': {'red': 1.0, 'green': 1.0, 'blue': 1.0},
    'warning': {'red': 0.96, 'green': 0.62, 'blue': 0.04},
}

# Limits for proper slide fitting
MAX_ITEMS_PER_SLIDE = 6
MAX_HIGHLIGHTS = 4
MAX_CHALLENGES = 3


def calculate_font_size(items: list, base_size: int = 16, min_size: int = 11) -> int:
    """Calculate appropriate font size based on content amount."""
    if not items:
        return base_size
    
    total_chars = sum(len(str(item)) for item in items)
    item_count = len(items)
    
    # Reduce font size based on total content
    if total_chars > 600 or item_count > 8:
        return min_size
    elif total_chars > 400 or item_count > 6:
        return max(min_size, base_size - 3)
    elif total_chars > 250 or item_count > 4:
        return max(min_size, base_size - 2)
    elif total_chars > 150:
        return max(min_size, base_size - 1)
    return base_size


def calculate_line_spacing(items: list, base_spacing: int = 140) -> int:
    """Calculate line spacing based on content amount."""
    if not items:
        return base_spacing
    
    item_count = len(items)
    total_chars = sum(len(str(item)) for item in items)
    
    if item_count > 6 or total_chars > 500:
        return 115
    elif item_count > 4 or total_chars > 350:
        return 125
    elif item_count > 3 or total_chars > 200:
        return 130
    return base_spacing


def split_items_for_slides(items: list, max_per_slide: int = MAX_ITEMS_PER_SLIDE) -> list:
    """Split a list of items into chunks that fit on slides."""
    if not items:
        return []
    chunks = []
    for i in range(0, len(items), max_per_slide):
        chunks.append(items[i:i + max_per_slide])
    return chunks


class SlidesService:
    def __init__(self, credentials: Credentials):
        self.credentials = credentials
        self.service = build('slides', 'v1', credentials=credentials)
        self.drive_service = build('drive', 'v3', credentials=credentials)

    async def create_presentation(self, title: str) -> str:
        presentation = self.service.presentations().create(body={"title": title}).execute()
        return presentation.get('presentationId')

    async def create_demo_presentation(self, content: dict) -> dict:
        title = content.get("title", "Sprint Demo")
        presentation_id = await self.create_presentation(title)
        
        # Get the presentation to find the default blank slide
        presentation = self.service.presentations().get(presentationId=presentation_id).execute()
        slides = presentation.get('slides', [])
        
        # Store the default slide ID to delete it later
        default_slide_id = slides[0].get('objectId') if slides else None
        
        requests = []

        # Title slide
        requests.extend(self._create_title_slide(title, content.get("subtitle", "")))

        # Executive summary
        if content.get("executive_summary"):
            requests.extend(self._create_summary_slide("Executive Summary", content["executive_summary"]))

        # Highlights - split if more than MAX_HIGHLIGHTS
        if content.get("highlights"):
            highlights = content["highlights"]
            highlight_chunks = split_items_for_slides(highlights, MAX_HIGHLIGHTS)
            for i, chunk in enumerate(highlight_chunks):
                slide_title = "Key Highlights"
                if len(highlight_chunks) > 1:
                    slide_title = f"Key Highlights ({i + 1}/{len(highlight_chunks)})"
                requests.extend(self._create_highlights_slide(slide_title, chunk))

        # Sections - split into multiple slides if needed
        for section in content.get("sections", []):
            items = section.get("items") or section.get("bullet_points", [])
            if items:
                item_chunks = split_items_for_slides(items, MAX_ITEMS_PER_SLIDE)
                
                for i, chunk in enumerate(item_chunks):
                    section_title = section.get("title", "Section")
                    if len(item_chunks) > 1:
                        section_title = f"{section_title} ({i + 1}/{len(item_chunks)})"
                    
                    desc = section.get("description", "")
                    requests.extend(self._create_content_slide(section_title, chunk, desc))

        # Challenges - split if more than MAX_CHALLENGES
        if content.get("challenges_and_solutions"):
            challenges = content["challenges_and_solutions"]
            challenge_chunks = split_items_for_slides(challenges, MAX_CHALLENGES)
            for i, chunk in enumerate(challenge_chunks):
                slide_title = "Challenges & Solutions"
                if len(challenge_chunks) > 1:
                    slide_title = f"Challenges & Solutions ({i + 1}/{len(challenge_chunks)})"
                requests.extend(self._create_challenges_slide(chunk, slide_title))

        # Work in progress - split if needed
        if content.get("in_progress"):
            in_progress = content["in_progress"]
            item_chunks = split_items_for_slides(in_progress, MAX_ITEMS_PER_SLIDE)
            for i, chunk in enumerate(item_chunks):
                slide_title = "Work In Progress"
                if len(item_chunks) > 1:
                    slide_title = f"Work In Progress ({i + 1}/{len(item_chunks)})"
                requests.extend(self._create_status_slide(slide_title, chunk, COLORS['warning']))

        # Next sprint - split if needed
        next_items = content.get("next_sprint_preview") or content.get("next_steps", [])
        if next_items:
            item_chunks = split_items_for_slides(next_items, MAX_ITEMS_PER_SLIDE)
            for i, chunk in enumerate(item_chunks):
                slide_title = "Next Sprint Preview"
                if len(item_chunks) > 1:
                    slide_title = f"Next Sprint Preview ({i + 1}/{len(item_chunks)})"
                requests.extend(self._create_status_slide(slide_title, chunk, COLORS['accent']))

        # Thank you slide
        requests.extend(self._create_thank_you_slide())

        # Delete the default blank slide that Google creates automatically
        if default_slide_id:
            requests.append({"deleteObject": {"objectId": default_slide_id}})

        if requests:
            self.service.presentations().batchUpdate(presentationId=presentation_id,
                                                     body={"requests": requests}).execute()

        return {"presentation_id": presentation_id,
                "url": f"https://docs.google.com/presentation/d/{presentation_id}/edit"}

    def _create_title_slide(self, title: str, subtitle: str) -> list:
        slide_id, title_id, subtitle_id, bg_id = [f"{x}_{uuid.uuid4().hex[:8]}" for x in
                                                  ['slide', 'title', 'sub', 'bg']]
        # Adjust font size based on title length
        title_font_size = 32 if len(title) > 50 else (36 if len(title) > 35 else 40)
        subtitle_font_size = 16 if len(subtitle) > 60 else (18 if len(subtitle) > 40 else 20)
        
        return [
            {"createSlide": {"objectId": slide_id, "insertionIndex": 0,
                             "slideLayoutReference": {"predefinedLayout": "BLANK"}}},
            {"createShape": {"objectId": bg_id, "shapeType": "RECTANGLE",
                             "elementProperties": {"pageObjectId": slide_id,
                                                   "size": {"width": {"magnitude": 720, "unit": "PT"},
                                                            "height": {"magnitude": 540, "unit": "PT"}},
                                                   "transform": {"scaleX": 1, "scaleY": 1, "translateX": 0,
                                                                 "translateY": 0, "unit": "PT"}}}},
            {"updateShapeProperties": {"objectId": bg_id, "fields": "shapeBackgroundFill.solidFill.color,outline",
                                       "shapeProperties": {"shapeBackgroundFill": {
                                           "solidFill": {"color": {"rgbColor": COLORS['dark']}}},
                                                           "outline": {"propertyState": "NOT_RENDERED"}}}},
            {"createShape": {"objectId": title_id, "shapeType": "TEXT_BOX",
                             "elementProperties": {"pageObjectId": slide_id,
                                                   "size": {"width": {"magnitude": 620, "unit": "PT"},
                                                            "height": {"magnitude": 120, "unit": "PT"}},
                                                   "transform": {"scaleX": 1, "scaleY": 1, "translateX": 50,
                                                                 "translateY": 170, "unit": "PT"}}}},
            {"insertText": {"objectId": title_id, "text": title}},
            {"updateTextStyle": {"objectId": title_id, "fields": "fontSize,foregroundColor,bold,fontFamily",
                                 "style": {"fontSize": {"magnitude": title_font_size, "unit": "PT"},
                                           "foregroundColor": {"opaqueColor": {"rgbColor": COLORS['white']}},
                                           "bold": True, "fontFamily": "Arial"}}},
            {"updateParagraphStyle": {"objectId": title_id, "fields": "alignment", "style": {"alignment": "CENTER"}}},
            {"createShape": {"objectId": subtitle_id, "shapeType": "TEXT_BOX",
                             "elementProperties": {"pageObjectId": slide_id,
                                                   "size": {"width": {"magnitude": 620, "unit": "PT"},
                                                            "height": {"magnitude": 50, "unit": "PT"}},
                                                   "transform": {"scaleX": 1, "scaleY": 1, "translateX": 50,
                                                                 "translateY": 300, "unit": "PT"}}}},
            {"insertText": {"objectId": subtitle_id, "text": subtitle}},
            {"updateTextStyle": {"objectId": subtitle_id, "fields": "fontSize,foregroundColor,fontFamily",
                                 "style": {"fontSize": {"magnitude": subtitle_font_size, "unit": "PT"},
                                           "foregroundColor": {"opaqueColor": {"rgbColor": COLORS['light']}},
                                           "fontFamily": "Arial"}}},
            {"updateParagraphStyle": {"objectId": subtitle_id, "fields": "alignment", "style": {"alignment": "CENTER"}}}
        ]

    def _create_summary_slide(self, title: str, text: str) -> list:
        slide_id, title_id, body_id, accent_id = [f"{x}_{uuid.uuid4().hex[:8]}" for x in
                                                  ['slide', 'title', 'body', 'accent']]
        # Calculate font size based on text length
        text_len = len(text)
        if text_len > 600:
            font_size = 12
            line_spacing = 120
        elif text_len > 400:
            font_size = 14
            line_spacing = 125
        elif text_len > 250:
            font_size = 16
            line_spacing = 130
        else:
            font_size = 18
            line_spacing = 140
        
        return [
            {"createSlide": {"objectId": slide_id, "slideLayoutReference": {"predefinedLayout": "BLANK"}}},
            {"createShape": {"objectId": accent_id, "shapeType": "RECTANGLE",
                             "elementProperties": {"pageObjectId": slide_id,
                                                   "size": {"width": {"magnitude": 8, "unit": "PT"},
                                                            "height": {"magnitude": 540, "unit": "PT"}},
                                                   "transform": {"scaleX": 1, "scaleY": 1, "translateX": 0,
                                                                 "translateY": 0, "unit": "PT"}}}},
            {"updateShapeProperties": {"objectId": accent_id, "fields": "shapeBackgroundFill.solidFill.color,outline",
                                       "shapeProperties": {"shapeBackgroundFill": {
                                           "solidFill": {"color": {"rgbColor": COLORS['secondary']}}},
                                                           "outline": {"propertyState": "NOT_RENDERED"}}}},
            {"createShape": {"objectId": title_id, "shapeType": "TEXT_BOX",
                             "elementProperties": {"pageObjectId": slide_id,
                                                   "size": {"width": {"magnitude": 650, "unit": "PT"},
                                                            "height": {"magnitude": 50, "unit": "PT"}},
                                                   "transform": {"scaleX": 1, "scaleY": 1, "translateX": 40,
                                                                 "translateY": 30, "unit": "PT"}}}},
            {"insertText": {"objectId": title_id, "text": title}},
            {"updateTextStyle": {"objectId": title_id, "fields": "fontSize,foregroundColor,bold,fontFamily",
                                 "style": {"fontSize": {"magnitude": 28, "unit": "PT"},
                                           "foregroundColor": {"opaqueColor": {"rgbColor": COLORS['dark']}},
                                           "bold": True, "fontFamily": "Arial"}}},
            {"createShape": {"objectId": body_id, "shapeType": "TEXT_BOX",
                             "elementProperties": {"pageObjectId": slide_id,
                                                   "size": {"width": {"magnitude": 640, "unit": "PT"},
                                                            "height": {"magnitude": 420, "unit": "PT"}},
                                                   "transform": {"scaleX": 1, "scaleY": 1, "translateX": 45,
                                                                 "translateY": 90, "unit": "PT"}}}},
            {"insertText": {"objectId": body_id, "text": text}},
            {"updateTextStyle": {"objectId": body_id, "fields": "fontSize,foregroundColor,fontFamily",
                                 "style": {"fontSize": {"magnitude": font_size, "unit": "PT"},
                                           "foregroundColor": {"opaqueColor": {"rgbColor": COLORS['primary']}},
                                           "fontFamily": "Arial"}}},
            {"updateParagraphStyle": {"objectId": body_id, "fields": "lineSpacing", "style": {"lineSpacing": line_spacing}}}
        ]

    def _create_highlights_slide(self, title: str, highlights: list) -> list:
        slide_id, title_id = f"slide_{uuid.uuid4().hex[:8]}", f"title_{uuid.uuid4().hex[:8]}"
        
        num_highlights = len(highlights)
        # Calculate dimensions based on number of highlights
        if num_highlights <= 2:
            card_height = 100
            card_spacing = 115
            text_font_size = 16
        elif num_highlights <= 3:
            card_height = 90
            card_spacing = 100
            text_font_size = 15
        else:
            card_height = 80
            card_spacing = 90
            text_font_size = 14
        
        requests = [
            {"createSlide": {"objectId": slide_id, "slideLayoutReference": {"predefinedLayout": "BLANK"}}},
            {"createShape": {"objectId": title_id, "shapeType": "TEXT_BOX",
                             "elementProperties": {"pageObjectId": slide_id,
                                                   "size": {"width": {"magnitude": 650, "unit": "PT"},
                                                            "height": {"magnitude": 50, "unit": "PT"}},
                                                   "transform": {"scaleX": 1, "scaleY": 1, "translateX": 40,
                                                                 "translateY": 25, "unit": "PT"}}}},
            {"insertText": {"objectId": title_id, "text": title}},
            {"updateTextStyle": {"objectId": title_id, "fields": "fontSize,foregroundColor,bold,fontFamily",
                                 "style": {"fontSize": {"magnitude": 28, "unit": "PT"},
                                           "foregroundColor": {"opaqueColor": {"rgbColor": COLORS['dark']}},
                                           "bold": True, "fontFamily": "Arial"}}}
        ]
        
        y = 85
        for i, h in enumerate(highlights):
            card_id, num_id, text_id = [f"{x}_{uuid.uuid4().hex[:8]}" for x in ['card', 'num', 'text']]
            
            # Adjust font size for longer highlight text
            item_font_size = text_font_size - 1 if len(h) > 100 else text_font_size
            
            requests.extend([
                {"createShape": {"objectId": card_id, "shapeType": "ROUND_RECTANGLE",
                                 "elementProperties": {"pageObjectId": slide_id,
                                                       "size": {"width": {"magnitude": 640, "unit": "PT"},
                                                                "height": {"magnitude": card_height, "unit": "PT"}},
                                                       "transform": {"scaleX": 1, "scaleY": 1, "translateX": 40,
                                                                     "translateY": y, "unit": "PT"}}}},
                {"updateShapeProperties": {"objectId": card_id, "fields": "shapeBackgroundFill.solidFill.color,outline",
                                           "shapeProperties": {"shapeBackgroundFill": {
                                               "solidFill": {"color": {"rgbColor": COLORS['light']}}},
                                                               "outline": {"propertyState": "NOT_RENDERED"}}}},
                {"createShape": {"objectId": num_id, "shapeType": "ELLIPSE",
                                 "elementProperties": {"pageObjectId": slide_id,
                                                       "size": {"width": {"magnitude": 32, "unit": "PT"},
                                                                "height": {"magnitude": 32, "unit": "PT"}},
                                                       "transform": {"scaleX": 1, "scaleY": 1, "translateX": 52,
                                                                     "translateY": y + (card_height - 32) // 2, "unit": "PT"}}}},
                {"updateShapeProperties": {"objectId": num_id, "fields": "shapeBackgroundFill.solidFill.color,outline",
                                           "shapeProperties": {"shapeBackgroundFill": {
                                               "solidFill": {"color": {"rgbColor": COLORS['secondary']}}},
                                                               "outline": {"propertyState": "NOT_RENDERED"}}}},
                {"insertText": {"objectId": num_id, "text": str(i + 1)}},
                {"updateTextStyle": {"objectId": num_id, "fields": "fontSize,foregroundColor,bold,fontFamily",
                                     "style": {"fontSize": {"magnitude": 14, "unit": "PT"},
                                               "foregroundColor": {"opaqueColor": {"rgbColor": COLORS['white']}},
                                               "bold": True, "fontFamily": "Arial"}}},
                {"updateParagraphStyle": {"objectId": num_id, "fields": "alignment", "style": {"alignment": "CENTER"}}},
                {"createShape": {"objectId": text_id, "shapeType": "TEXT_BOX",
                                 "elementProperties": {"pageObjectId": slide_id,
                                                       "size": {"width": {"magnitude": 540, "unit": "PT"},
                                                                "height": {"magnitude": card_height - 10, "unit": "PT"}},
                                                       "transform": {"scaleX": 1, "scaleY": 1, "translateX": 95,
                                                                     "translateY": y + 5, "unit": "PT"}}}},
                {"insertText": {"objectId": text_id, "text": h}},
                {"updateTextStyle": {"objectId": text_id, "fields": "fontSize,foregroundColor,fontFamily",
                                     "style": {"fontSize": {"magnitude": item_font_size, "unit": "PT"},
                                               "foregroundColor": {"opaqueColor": {"rgbColor": COLORS['dark']}},
                                               "fontFamily": "Arial"}}}
            ])
            y += card_spacing
        return requests

    def _create_content_slide(self, title: str, items: list, desc: str = "") -> list:
        slide_id, title_id, body_id, accent_id = [f"{x}_{uuid.uuid4().hex[:8]}" for x in
                                                  ['slide', 'title', 'body', 'accent']]
        
        # Build text content
        text_parts = []
        if desc:
            text_parts.append(desc + "\n")
        text_parts.extend(f"→  {item}" for item in items if item)
        text = "\n".join(text_parts)
        
        # Calculate font size and spacing based on content
        font_size = calculate_font_size(items, base_size=16, min_size=11)
        line_spacing = calculate_line_spacing(items, base_spacing=140)
        
        return [
            {"createSlide": {"objectId": slide_id, "slideLayoutReference": {"predefinedLayout": "BLANK"}}},
            {"createShape": {"objectId": accent_id, "shapeType": "RECTANGLE",
                             "elementProperties": {"pageObjectId": slide_id,
                                                   "size": {"width": {"magnitude": 720, "unit": "PT"},
                                                            "height": {"magnitude": 6, "unit": "PT"}},
                                                   "transform": {"scaleX": 1, "scaleY": 1, "translateX": 0,
                                                                 "translateY": 0, "unit": "PT"}}}},
            {"updateShapeProperties": {"objectId": accent_id, "fields": "shapeBackgroundFill.solidFill.color,outline",
                                       "shapeProperties": {"shapeBackgroundFill": {
                                           "solidFill": {"color": {"rgbColor": COLORS['secondary']}}},
                                                           "outline": {"propertyState": "NOT_RENDERED"}}}},
            {"createShape": {"objectId": title_id, "shapeType": "TEXT_BOX",
                             "elementProperties": {"pageObjectId": slide_id,
                                                   "size": {"width": {"magnitude": 650, "unit": "PT"},
                                                            "height": {"magnitude": 50, "unit": "PT"}},
                                                   "transform": {"scaleX": 1, "scaleY": 1, "translateX": 40,
                                                                 "translateY": 20, "unit": "PT"}}}},
            {"insertText": {"objectId": title_id, "text": title}},
            {"updateTextStyle": {"objectId": title_id, "fields": "fontSize,foregroundColor,bold,fontFamily",
                                 "style": {"fontSize": {"magnitude": 24, "unit": "PT"},
                                           "foregroundColor": {"opaqueColor": {"rgbColor": COLORS['dark']}},
                                           "bold": True, "fontFamily": "Arial"}}},
            {"createShape": {"objectId": body_id, "shapeType": "TEXT_BOX",
                             "elementProperties": {"pageObjectId": slide_id,
                                                   "size": {"width": {"magnitude": 650, "unit": "PT"},
                                                            "height": {"magnitude": 450, "unit": "PT"}},
                                                   "transform": {"scaleX": 1, "scaleY": 1, "translateX": 40,
                                                                 "translateY": 75, "unit": "PT"}}}},
            {"insertText": {"objectId": body_id, "text": text}},
            {"updateTextStyle": {"objectId": body_id, "fields": "fontSize,foregroundColor,fontFamily",
                                 "style": {"fontSize": {"magnitude": font_size, "unit": "PT"},
                                           "foregroundColor": {"opaqueColor": {"rgbColor": COLORS['primary']}},
                                           "fontFamily": "Arial"}}},
            {"updateParagraphStyle": {"objectId": body_id, "fields": "lineSpacing,spaceAbove",
                                      "style": {"lineSpacing": line_spacing, "spaceAbove": {"magnitude": 5, "unit": "PT"}}}}
        ]

    def _create_challenges_slide(self, challenges: list, title: str = "Challenges & Solutions") -> list:
        slide_id, title_id = f"slide_{uuid.uuid4().hex[:8]}", f"title_{uuid.uuid4().hex[:8]}"
        
        num_challenges = len(challenges)
        # Calculate dimensions based on number of challenges
        if num_challenges <= 2:
            card_height = 120
            card_spacing = 135
            font_size = 13
        else:
            card_height = 100
            card_spacing = 110
            font_size = 12
        
        requests = [
            {"createSlide": {"objectId": slide_id, "slideLayoutReference": {"predefinedLayout": "BLANK"}}},
            {"createShape": {"objectId": title_id, "shapeType": "TEXT_BOX",
                             "elementProperties": {"pageObjectId": slide_id,
                                                   "size": {"width": {"magnitude": 650, "unit": "PT"},
                                                            "height": {"magnitude": 50, "unit": "PT"}},
                                                   "transform": {"scaleX": 1, "scaleY": 1, "translateX": 40,
                                                                 "translateY": 15, "unit": "PT"}}}},
            {"insertText": {"objectId": title_id, "text": title}},
            {"updateTextStyle": {"objectId": title_id, "fields": "fontSize,foregroundColor,bold,fontFamily",
                                 "style": {"fontSize": {"magnitude": 24, "unit": "PT"},
                                           "foregroundColor": {"opaqueColor": {"rgbColor": COLORS['dark']}},
                                           "bold": True, "fontFamily": "Arial"}}}
        ]
        
        y = 65
        for item in challenges:
            if not isinstance(item, dict):
                continue
            ch_id, sol_id, arr_id = [f"{x}_{uuid.uuid4().hex[:8]}" for x in ['ch', 'sol', 'arr']]
            
            # Adjust font for longer text
            ch_text = item.get('challenge', '')
            sol_text = item.get('solution', '')
            item_font = font_size - 1 if len(ch_text) > 120 or len(sol_text) > 120 else font_size
            
            requests.extend([
                {"createShape": {"objectId": ch_id, "shapeType": "ROUND_RECTANGLE",
                                 "elementProperties": {"pageObjectId": slide_id,
                                                       "size": {"width": {"magnitude": 290, "unit": "PT"},
                                                                "height": {"magnitude": card_height, "unit": "PT"}},
                                                       "transform": {"scaleX": 1, "scaleY": 1, "translateX": 25,
                                                                     "translateY": y, "unit": "PT"}}}},
                {"updateShapeProperties": {"objectId": ch_id, "fields": "shapeBackgroundFill.solidFill.color,outline",
                                           "shapeProperties": {"shapeBackgroundFill": {"solidFill": {
                                               "color": {"rgbColor": {'red': 1, 'green': 0.95, 'blue': 0.95}}}},
                                                               "outline": {"propertyState": "NOT_RENDERED"}}}},
                {"insertText": {"objectId": ch_id, "text": f"Challenge:\n{ch_text}"}},
                {"updateTextStyle": {"objectId": ch_id, "fields": "fontSize,foregroundColor,fontFamily",
                                     "style": {"fontSize": {"magnitude": item_font, "unit": "PT"},
                                               "foregroundColor": {"opaqueColor": {"rgbColor": COLORS['dark']}},
                                               "fontFamily": "Arial"}}},
                {"createShape": {"objectId": arr_id, "shapeType": "RIGHT_ARROW",
                                 "elementProperties": {"pageObjectId": slide_id,
                                                       "size": {"width": {"magnitude": 40, "unit": "PT"},
                                                                "height": {"magnitude": 22, "unit": "PT"}},
                                                       "transform": {"scaleX": 1, "scaleY": 1, "translateX": 325,
                                                                     "translateY": y + (card_height - 22) // 2, "unit": "PT"}}}},
                {"updateShapeProperties": {"objectId": arr_id, "fields": "shapeBackgroundFill.solidFill.color,outline",
                                           "shapeProperties": {"shapeBackgroundFill": {
                                               "solidFill": {"color": {"rgbColor": COLORS['accent']}}},
                                                               "outline": {"propertyState": "NOT_RENDERED"}}}},
                {"createShape": {"objectId": sol_id, "shapeType": "ROUND_RECTANGLE",
                                 "elementProperties": {"pageObjectId": slide_id,
                                                       "size": {"width": {"magnitude": 290, "unit": "PT"},
                                                                "height": {"magnitude": card_height, "unit": "PT"}},
                                                       "transform": {"scaleX": 1, "scaleY": 1, "translateX": 380,
                                                                     "translateY": y, "unit": "PT"}}}},
                {"updateShapeProperties": {"objectId": sol_id, "fields": "shapeBackgroundFill.solidFill.color,outline",
                                           "shapeProperties": {"shapeBackgroundFill": {"solidFill": {
                                               "color": {"rgbColor": {'red': 0.9, 'green': 1, 'blue': 0.95}}}},
                                                               "outline": {"propertyState": "NOT_RENDERED"}}}},
                {"insertText": {"objectId": sol_id, "text": f"Solution:\n{sol_text}"}},
                {"updateTextStyle": {"objectId": sol_id, "fields": "fontSize,foregroundColor,fontFamily",
                                     "style": {"fontSize": {"magnitude": item_font, "unit": "PT"},
                                               "foregroundColor": {"opaqueColor": {"rgbColor": COLORS['dark']}},
                                               "fontFamily": "Arial"}}}
            ])
            y += card_spacing
        return requests

    def _create_status_slide(self, title: str, items: list, color: dict) -> list:
        slide_id, title_id, body_id, accent_id = [f"{x}_{uuid.uuid4().hex[:8]}" for x in
                                                  ['slide', 'title', 'body', 'accent']]
        
        text = "\n".join(f"●  {item}" for item in items if item)
        
        # Calculate font size and spacing
        font_size = calculate_font_size(items, base_size=17, min_size=12)
        line_spacing = calculate_line_spacing(items, base_spacing=145)
        
        return [
            {"createSlide": {"objectId": slide_id, "slideLayoutReference": {"predefinedLayout": "BLANK"}}},
            {"createShape": {"objectId": accent_id, "shapeType": "RECTANGLE",
                             "elementProperties": {"pageObjectId": slide_id,
                                                   "size": {"width": {"magnitude": 10, "unit": "PT"},
                                                            "height": {"magnitude": 540, "unit": "PT"}},
                                                   "transform": {"scaleX": 1, "scaleY": 1, "translateX": 710,
                                                                 "translateY": 0, "unit": "PT"}}}},
            {"updateShapeProperties": {"objectId": accent_id, "fields": "shapeBackgroundFill.solidFill.color,outline",
                                       "shapeProperties": {
                                           "shapeBackgroundFill": {"solidFill": {"color": {"rgbColor": color}}},
                                           "outline": {"propertyState": "NOT_RENDERED"}}}},
            {"createShape": {"objectId": title_id, "shapeType": "TEXT_BOX",
                             "elementProperties": {"pageObjectId": slide_id,
                                                   "size": {"width": {"magnitude": 650, "unit": "PT"},
                                                            "height": {"magnitude": 50, "unit": "PT"}},
                                                   "transform": {"scaleX": 1, "scaleY": 1, "translateX": 40,
                                                                 "translateY": 30, "unit": "PT"}}}},
            {"insertText": {"objectId": title_id, "text": title}},
            {"updateTextStyle": {"objectId": title_id, "fields": "fontSize,foregroundColor,bold,fontFamily",
                                 "style": {"fontSize": {"magnitude": 26, "unit": "PT"},
                                           "foregroundColor": {"opaqueColor": {"rgbColor": COLORS['dark']}},
                                           "bold": True, "fontFamily": "Arial"}}},
            {"createShape": {"objectId": body_id, "shapeType": "TEXT_BOX",
                             "elementProperties": {"pageObjectId": slide_id,
                                                   "size": {"width": {"magnitude": 640, "unit": "PT"},
                                                            "height": {"magnitude": 440, "unit": "PT"}},
                                                   "transform": {"scaleX": 1, "scaleY": 1, "translateX": 45,
                                                                 "translateY": 85, "unit": "PT"}}}},
            {"insertText": {"objectId": body_id, "text": text}},
            {"updateTextStyle": {"objectId": body_id, "fields": "fontSize,foregroundColor,fontFamily",
                                 "style": {"fontSize": {"magnitude": font_size, "unit": "PT"},
                                           "foregroundColor": {"opaqueColor": {"rgbColor": COLORS['primary']}},
                                           "fontFamily": "Arial"}}},
            {"updateParagraphStyle": {"objectId": body_id, "fields": "lineSpacing,spaceAbove",
                                      "style": {"lineSpacing": line_spacing, "spaceAbove": {"magnitude": 8, "unit": "PT"}}}}
        ]

    def _create_thank_you_slide(self) -> list:
        slide_id, text_id, sub_id, bg_id = [f"{x}_{uuid.uuid4().hex[:8]}" for x in ['slide', 'text', 'sub', 'bg']]
        return [
            {"createSlide": {"objectId": slide_id, "slideLayoutReference": {"predefinedLayout": "BLANK"}}},
            {"createShape": {"objectId": bg_id, "shapeType": "RECTANGLE",
                             "elementProperties": {"pageObjectId": slide_id,
                                                   "size": {"width": {"magnitude": 720, "unit": "PT"},
                                                            "height": {"magnitude": 540, "unit": "PT"}},
                                                   "transform": {"scaleX": 1, "scaleY": 1, "translateX": 0,
                                                                 "translateY": 0, "unit": "PT"}}}},
            {"updateShapeProperties": {"objectId": bg_id, "fields": "shapeBackgroundFill.solidFill.color,outline",
                                       "shapeProperties": {"shapeBackgroundFill": {
                                           "solidFill": {"color": {"rgbColor": COLORS['secondary']}}},
                                                           "outline": {"propertyState": "NOT_RENDERED"}}}},
            {"createShape": {"objectId": text_id, "shapeType": "TEXT_BOX",
                             "elementProperties": {"pageObjectId": slide_id,
                                                   "size": {"width": {"magnitude": 600, "unit": "PT"},
                                                            "height": {"magnitude": 80, "unit": "PT"}},
                                                   "transform": {"scaleX": 1, "scaleY": 1, "translateX": 60,
                                                                 "translateY": 200, "unit": "PT"}}}},
            {"insertText": {"objectId": text_id, "text": "Thank You"}},
            {"updateTextStyle": {"objectId": text_id, "fields": "fontSize,foregroundColor,bold,fontFamily",
                                 "style": {"fontSize": {"magnitude": 48, "unit": "PT"},
                                           "foregroundColor": {"opaqueColor": {"rgbColor": COLORS['white']}},
                                           "bold": True, "fontFamily": "Arial"}}},
            {"updateParagraphStyle": {"objectId": text_id, "fields": "alignment", "style": {"alignment": "CENTER"}}},
            {"createShape": {"objectId": sub_id, "shapeType": "TEXT_BOX",
                             "elementProperties": {"pageObjectId": slide_id,
                                                   "size": {"width": {"magnitude": 600, "unit": "PT"},
                                                            "height": {"magnitude": 40, "unit": "PT"}},
                                                   "transform": {"scaleX": 1, "scaleY": 1, "translateX": 60,
                                                                 "translateY": 290, "unit": "PT"}}}},
            {"insertText": {"objectId": sub_id, "text": "Questions?"}},
            {"updateTextStyle": {"objectId": sub_id, "fields": "fontSize,foregroundColor,fontFamily",
                                 "style": {"fontSize": {"magnitude": 24, "unit": "PT"},
                                           "foregroundColor": {"opaqueColor": {"rgbColor": COLORS['light']}},
                                           "fontFamily": "Arial"}}},
            {"updateParagraphStyle": {"objectId": sub_id, "fields": "alignment", "style": {"alignment": "CENTER"}}}
        ]

    async def share_presentation(self, presentation_id: str, email: str, role: str = "reader") -> None:
        self.drive_service.permissions().create(fileId=presentation_id,
                                                body={"type": "user", "role": role, "emailAddress": email},
                                                sendNotificationEmail=False).execute()

    async def copy_to_drive_folder(self, presentation_id: str, folder_id: str, new_name: Optional[str] = None) -> str:
        body = {"parents": [folder_id]}
        if new_name: body["name"] = new_name
        return self.drive_service.files().copy(fileId=presentation_id, body=body).execute().get("id")