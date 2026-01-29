from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from io import BytesIO
from datetime import datetime


class PDFService:
    """Service for generating PDF self-reviews."""

    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        """Setup custom paragraph styles."""
        # Use unique names to avoid conflicts with existing styles
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
            textColor=colors.HexColor('#16213e')
        ))

        # Renamed from 'BodyText' to 'CustomBodyText' to avoid conflict
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
        for para in content_paragraphs:
            if para.startswith('## '):
                story.append(Paragraph(para[3:], self.styles['SectionHeader']))
            elif para.startswith('- ') or para.startswith('• '):
                story.append(Paragraph(f"• {para[2:]}", self.styles['BulletPoint']))
            elif para.startswith('* '):
                story.append(Paragraph(f"• {para[2:]}", self.styles['BulletPoint']))
            elif para.strip():
                story.append(Paragraph(para, self.styles['CustomBodyText']))

        # Build PDF
        doc.build(story)

        buffer.seek(0)
        return buffer.getvalue()

    def _parse_content(self, content: str) -> list:
        """Parse markdown-like content into paragraphs."""
        lines = content.split('\n')
        paragraphs = []
        current_para = []

        for line in lines:
            stripped = line.strip()

            # Headers and bullets are their own paragraphs
            if stripped.startswith('## ') or stripped.startswith('- ') or \
                    stripped.startswith('• ') or stripped.startswith('* '):
                if current_para:
                    paragraphs.append(' '.join(current_para))
                    current_para = []
                paragraphs.append(stripped)
            elif stripped:
                current_para.append(stripped)
            else:
                if current_para:
                    paragraphs.append(' '.join(current_para))
                    current_para = []

        if current_para:
            paragraphs.append(' '.join(current_para))

        return paragraphs