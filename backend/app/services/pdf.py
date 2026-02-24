from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from io import BytesIO
from datetime import datetime
import re


class PDFService:
    """Service for generating PDF self-reviews."""

    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        """Setup custom paragraph styles."""
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            spaceAfter=30,
            textColor=colors.HexColor('#1a1a2e')
        ))

        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=14,
            spaceBefore=20,
            spaceAfter=10,
            textColor=colors.HexColor('#16213e'),
            fontName='Helvetica-Bold'
        ))

        self.styles.add(ParagraphStyle(
            name='CustomBodyText',
            parent=self.styles['Normal'],
            fontSize=11,
            leading=14,
            spaceAfter=8
        ))

        self.styles.add(ParagraphStyle(
            name='BulletPoint',
            parent=self.styles['Normal'],
            fontSize=11,
            leftIndent=20,
            spaceAfter=4
        ))

    async def generate_self_review_pdf(
            self,
            content: str,
            metrics: dict,
            user_name: str,
            date_range_start: datetime,
            date_range_end: datetime
    ) -> bytes:
        """Generate a PDF self-review document."""
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72
        )

        story = []

        # Title
        story.append(Paragraph("Self-Review Report", self.styles['CustomTitle']))

        # Metadata
        date_range = f"{date_range_start.strftime('%B %d, %Y')} - {date_range_end.strftime('%B %d, %Y')}"
        story.append(Paragraph(f"<b>Name:</b> {user_name}", self.styles['CustomBodyText']))
        story.append(Paragraph(f"<b>Period:</b> {date_range}", self.styles['CustomBodyText']))
        story.append(Paragraph(
            f"<b>Generated:</b> {datetime.now().strftime('%B %d, %Y')}",
            self.styles['CustomBodyText']
        ))

        story.append(Spacer(1, 20))

        # Metrics Summary Table
        story.append(Paragraph("Performance Metrics", self.styles['SectionHeader']))

        metrics_data = [
            ["Metric", "Value"],
            ["Total Issues", str(metrics.get('total_issues', 0))],
            ["Completed", str(metrics.get('completed_issues', 0))],
            ["Completion Rate", f"{metrics.get('completion_rate', 0)}%"],
            ["Story Points Delivered", str(metrics.get('completed_story_points', 0))],
        ]

        table = Table(metrics_data, colWidths=[3 * inch, 2 * inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1a2e')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f5f5f5')),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 11),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#dddddd')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        ]))

        story.append(table)
        story.append(Spacer(1, 20))

        # Work by Type
        if metrics.get('by_type'):
            story.append(Paragraph("Work Distribution by Type", self.styles['SectionHeader']))
            type_data = [["Type", "Count"]]
            for issue_type, count in metrics['by_type'].items():
                type_data.append([issue_type, str(count)])

            type_table = Table(type_data, colWidths=[3 * inch, 2 * inch])
            type_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#16213e')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#dddddd')),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ]))
            story.append(type_table)
            story.append(Spacer(1, 20))

        # AI Generated Content
        story.append(Paragraph("Review Content", self.styles['SectionHeader']))

        # Parse and format the AI-generated content
        content_paragraphs = self._parse_content(content)
        for para_type, para_text in content_paragraphs:
            if para_type == 'header':
                story.append(Paragraph(para_text, self.styles['SectionHeader']))
            elif para_type == 'bullet':
                story.append(Paragraph(f"• {para_text}", self.styles['BulletPoint']))
            elif para_type == 'body':
                # para_text already has <b> tags from markdown_to_pdf conversion
                story.append(Paragraph(para_text, self.styles['CustomBodyText']))

        # Build PDF
        doc.build(story)

        buffer.seek(0)
        return buffer.getvalue()

    def _parse_content(self, content: str) -> list:
        """
        Parse content into structured paragraphs with type information.
        Returns list of tuples: (type, text) where type is 'header', 'bullet', or 'body'

        Recognizes:
        - ## Header or ### Header -> header
        - **SECTION TITLE** at start of line -> header
        - Lines starting with - or * or • -> bullet
        - Everything else -> body (preserves <b> tags for inline bold)
        """
        lines = content.split('\n')
        paragraphs = []
        current_para = []

        for line in lines:
            stripped = line.strip()

            # Skip empty lines - they end current paragraph
            if not stripped:
                if current_para:
                    paragraphs.append(('body', ' '.join(current_para)))
                    current_para = []
                continue

            # Check for markdown headers: ## Title or ### Title
            if stripped.startswith('## ') or stripped.startswith('### '):
                if current_para:
                    paragraphs.append(('body', ' '.join(current_para)))
                    current_para = []
                # Remove ## and any remaining markdown
                header_text = re.sub(r'^#{1,6}\s*', '', stripped)
                header_text = re.sub(r'\*\*(.+?)\*\*', r'\1', header_text)  # Remove ** if present
                paragraphs.append(('header', header_text))
                continue

            # Check for bold section title at start of line: **TITLE** or <b>TITLE</b>
            bold_match = re.match(r'^\*\*([A-Z][A-Z\s&]+)\*\*\s*$', stripped)
            if not bold_match:
                bold_match = re.match(r'^<b>([A-Z][A-Z\s&]+)</b>\s*$', stripped)

            if bold_match:
                if current_para:
                    paragraphs.append(('body', ' '.join(current_para)))
                    current_para = []
                paragraphs.append(('header', bold_match.group(1)))
                continue

            # Check for bullet points
            if stripped.startswith('- ') or stripped.startswith('* ') or stripped.startswith('• '):
                if current_para:
                    paragraphs.append(('body', ' '.join(current_para)))
                    current_para = []
                bullet_text = stripped[2:].strip()
                # Convert any remaining markdown bold to HTML
                bullet_text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', bullet_text)
                paragraphs.append(('bullet', bullet_text))
                continue

            # Regular text - accumulate into paragraph
            # Convert markdown bold to HTML bold for ReportLab
            processed_line = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', stripped)
            current_para.append(processed_line)

        # Don't forget the last paragraph
        if current_para:
            paragraphs.append(('body', ' '.join(current_para)))

        return paragraphs