from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
from datetime import datetime
import os
import tempfile

def generate_chat_pdf(chat_history, session_id):
    """
    Generate a PDF export of the chat conversation
    """
    # Create temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
        pdf_path = tmp_file.name
    
    # Create the PDF document
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=18
    )
    
    # Get styles
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        textColor=colors.Color(0.545, 0.361, 0.965),  # Purple color
        alignment=TA_CENTER
    )
    
    header_style = ParagraphStyle(
        'CustomHeader',
        parent=styles['Heading2'],
        fontSize=14,
        spaceBefore=20,
        spaceAfter=10,
        textColor=colors.Color(0.4, 0.4, 0.4)
    )
    
    user_style = ParagraphStyle(
        'UserMessage',
        parent=styles['Normal'],
        fontSize=11,
        spaceBefore=10,
        spaceAfter=5,
        leftIndent=20,
        rightIndent=0,
        textColor=colors.Color(0.2, 0.2, 0.2),
        backColor=colors.Color(0.95, 0.95, 1.0),
        borderColor=colors.Color(0.545, 0.361, 0.965),
        borderWidth=1,
        borderPadding=10
    )
    
    ai_style = ParagraphStyle(
        'AIMessage',
        parent=styles['Normal'],
        fontSize=11,
        spaceBefore=10,
        spaceAfter=5,
        leftIndent=0,
        rightIndent=20,
        textColor=colors.Color(0.2, 0.2, 0.2),
        backColor=colors.Color(0.98, 0.98, 0.98),
        borderColor=colors.Color(0.8, 0.8, 0.8),
        borderWidth=1,
        borderPadding=10
    )
    
    meta_style = ParagraphStyle(
        'MetaInfo',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.Color(0.6, 0.6, 0.6),
        spaceAfter=10
    )
    
    # Build the PDF content
    story = []
    
    # Title
    story.append(Paragraph("AI Assistant Chat Export", title_style))
    story.append(Spacer(1, 12))
    
    # Export info
    export_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    info_data = [
        ['Export Date:', export_time],
        ['Session ID:', session_id[:16] + '...' if len(session_id) > 16 else session_id],
        ['Total Messages:', str(len(chat_history) * 2)],  # User + AI messages
        ['Total Conversations:', str(len(chat_history))]
    ]
    
    info_table = Table(info_data, colWidths=[2*inch, 4*inch])
    info_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.Color(0.95, 0.95, 0.95)),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.Color(0.8, 0.8, 0.8)),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    
    story.append(info_table)
    story.append(Spacer(1, 20))
    
    # Chat messages
    story.append(Paragraph("Chat Conversation", header_style))
    story.append(Spacer(1, 12))
    
    for i, entry in enumerate(chat_history, 1):
        # Conversation separator
        if i > 1:
            story.append(Spacer(1, 15))
            story.append(Paragraph("─" * 50, meta_style))
            story.append(Spacer(1, 10))
        
        # Timestamp
        timestamp = datetime.fromisoformat(entry['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
        story.append(Paragraph(f"<b>Conversation {i} - {timestamp}</b>", meta_style))
        story.append(Spacer(1, 8))
        
        # User message
        user_text = escape_html(entry['user_message'])
        story.append(Paragraph(f"<b>👤 User:</b><br/>{user_text}", user_style))
        
        # AI response
        ai_text = escape_html(entry['ai_response'])
        story.append(Paragraph(f"<b>🤖 AI Assistant:</b><br/>{ai_text}", ai_style))
        
        # Response metadata
        meta_info = [
            f"Response Time: {entry['response_time']}s",
            f"Input Tokens: {entry['input_tokens']}",
            f"Output Tokens: {entry['output_tokens']}"
        ]
        story.append(Paragraph(" | ".join(meta_info), meta_style))
    
    # Footer
    story.append(Spacer(1, 30))
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.Color(0.5, 0.5, 0.5),
        alignment=TA_CENTER
    )
    story.append(Paragraph("Generated by AI Assistant Chat Interface", footer_style))
    
    # Build PDF
    doc.build(story)
    
    return pdf_path

def escape_html(text):
    """
    Escape HTML characters for PDF generation
    """
    if not text:
        return ""
    
    # Basic HTML escaping
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    text = text.replace('"', '&quot;')
    text = text.replace("'", '&#39;')
    
    # Handle newlines
    text = text.replace('\n', '<br/>')
    
    return text

def cleanup_temp_files(file_path, max_age_hours=1):
    """
    Clean up temporary PDF files older than max_age_hours
    """
    try:
        if os.path.exists(file_path):
            file_age = datetime.now() - datetime.fromtimestamp(os.path.getctime(file_path))
            if file_age.total_seconds() > max_age_hours * 3600:
                os.remove(file_path)
                return True
    except Exception as e:
        print(f"Error cleaning up temp file {file_path}: {e}")
    
    return False