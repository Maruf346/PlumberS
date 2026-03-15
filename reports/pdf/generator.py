"""
PDF generation for all report types.
Brand color: #F54900
Uses ReportLab for clean, formal report layout.
"""
import io
import os
from django.contrib.contenttypes.models import ContentType
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, Image, KeepTogether
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT

from reports.models import (
    ReportPhoto, ReportType,
    RoofReportSubmission, ApplianceReportSubmission,
    DrainInspectionSubmission, LeakInspectionSubmission,
    SprayTestSubmission,
)

# ── Brand colours ─────────────────────────────────────────────────────────────
BRAND_ORANGE = colors.HexColor('#F54900')
BRAND_DARK = colors.HexColor('#1A1A1A')
BRAND_LIGHT_GREY = colors.HexColor('#F5F5F5')
BRAND_MID_GREY = colors.HexColor('#CCCCCC')
WHITE = colors.white
TEXT_GREY = colors.HexColor('#555555')

PAGE_W, PAGE_H = A4
MARGIN = 2 * cm


# ── Style helpers ─────────────────────────────────────────────────────────────

def _styles():
    base = getSampleStyleSheet()
    return {
        'title': ParagraphStyle(
            'ReportTitle',
            fontName='Helvetica-Bold',
            fontSize=20,
            textColor=WHITE,
            spaceAfter=2,
            alignment=TA_LEFT,
        ),
        'subtitle': ParagraphStyle(
            'Subtitle',
            fontName='Helvetica',
            fontSize=10,
            textColor=colors.HexColor('#FFCBB3'),
            spaceAfter=0,
            alignment=TA_LEFT,
        ),
        'section_heading': ParagraphStyle(
            'SectionHeading',
            fontName='Helvetica-Bold',
            fontSize=11,
            textColor=BRAND_ORANGE,
            spaceBefore=12,
            spaceAfter=4,
        ),
        'label': ParagraphStyle(
            'Label',
            fontName='Helvetica-Bold',
            fontSize=9,
            textColor=BRAND_DARK,
        ),
        'value': ParagraphStyle(
            'Value',
            fontName='Helvetica',
            fontSize=9,
            textColor=TEXT_GREY,
            leading=14,
        ),
        'footer': ParagraphStyle(
            'Footer',
            fontName='Helvetica',
            fontSize=8,
            textColor=BRAND_MID_GREY,
            alignment=TA_CENTER,
        ),
        'normal': base['Normal'],
    }


def _header_table(report_title, job_id, submitted_at):
    """Orange header banner with report title and job ID."""
    styles = _styles()
    title_para = Paragraph(report_title, styles['title'])
    meta_text = f"Job: {job_id}  |  Submitted: {submitted_at.strftime('%d %b %Y, %I:%M %p') if submitted_at else 'N/A'}"
    meta_para = Paragraph(meta_text, styles['subtitle'])

    header_table = Table(
        [[title_para], [meta_para]],
        colWidths=[PAGE_W - 2 * MARGIN],
    )
    header_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), BRAND_ORANGE),
        ('TOPPADDING', (0, 0), (-1, -1), 14),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 14),
        ('LEFTPADDING', (0, 0), (-1, -1), 16),
        ('RIGHTPADDING', (0, 0), (-1, -1), 16),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [BRAND_ORANGE]),
    ]))
    return header_table


def _section_heading(text):
    styles = _styles()
    return Paragraph(text, styles['section_heading'])


def _divider():
    return HRFlowable(
        width='100%',
        thickness=0.5,
        color=BRAND_MID_GREY,
        spaceAfter=6,
        spaceBefore=2,
    )


def _field_table(rows):
    """
    Renders a two-column label/value table.
    rows = [('Label', 'Value'), ...]
    Pass two rows per table row for a two-pair layout:
    rows = [('Label1', 'Val1', 'Label2', 'Val2'), ...]
    """
    styles = _styles()
    col_w = (PAGE_W - 2 * MARGIN) / 4

    table_data = []
    for row in rows:
        if len(row) == 2:
            label, value = row
            table_data.append([
                Paragraph(label, styles['label']),
                Paragraph(str(value) if value else '—', styles['value']),
                '', ''
            ])
        elif len(row) == 4:
            l1, v1, l2, v2 = row
            table_data.append([
                Paragraph(l1, styles['label']),
                Paragraph(str(v1) if v1 else '—', styles['value']),
                Paragraph(l2, styles['label']),
                Paragraph(str(v2) if v2 else '—', styles['value']),
            ])

    if not table_data:
        return Spacer(1, 0)

    t = Table(table_data, colWidths=[col_w * 0.8, col_w * 1.2, col_w * 0.8, col_w * 1.2])
    t.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [WHITE, BRAND_LIGHT_GREY]),
        ('LINEBELOW', (0, 0), (-1, -2), 0.3, BRAND_MID_GREY),
    ]))
    return t


def _text_block(label, value):
    """For long text fields (discussion, conclusion, etc.)."""
    styles = _styles()
    return Table(
        [
            [Paragraph(label, styles['label'])],
            [Paragraph(str(value) if value else '—', styles['value'])],
        ],
        colWidths=[PAGE_W - 2 * MARGIN],
    )


def _get_photos(submission_model_class, object_id, photo_type=None):
    """Fetch ReportPhoto instances for a given submission."""
    ct = ContentType.objects.get_for_model(submission_model_class)
    qs = ReportPhoto.objects.filter(content_type=ct, object_id=object_id)
    if photo_type:
        qs = qs.filter(photo_type=photo_type)
    return qs


def _photo_grid(photos, max_width=None):
    """
    Renders up to 3 photos per row in a grid.
    Returns a list of flowables.
    """
    flowables = []
    if not photos:
        return flowables

    available_w = (max_width or (PAGE_W - 2 * MARGIN))
    photo_w = (available_w - 2 * 4) / 3   # 3 per row, 4mm gap
    photo_h = photo_w * 0.75               # 4:3 ratio

    batch = []
    for photo in photos:
        try:
            path = photo.image.path
            if os.path.exists(path):
                img = Image(path, width=photo_w, height=photo_h)
                batch.append(img)
            else:
                batch.append(Paragraph('[Photo not found]', _styles()['value']))
        except Exception:
            batch.append(Paragraph('[Photo unavailable]', _styles()['value']))

        if len(batch) == 3:
            t = Table([batch], colWidths=[photo_w, photo_w, photo_w])
            t.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('LEFTPADDING', (0, 0), (-1, -1), 2),
                ('RIGHTPADDING', (0, 0), (-1, -1), 2),
            ]))
            flowables.append(t)
            flowables.append(Spacer(1, 4))
            batch = []

    if batch:
        # Pad to 3 columns
        while len(batch) < 3:
            batch.append('')
        t = Table([batch], colWidths=[photo_w, photo_w, photo_w])
        t.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 2),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ]))
        flowables.append(t)

    return flowables


def _footer(canvas, doc):
    """Page number footer on every page."""
    canvas.saveState()
    canvas.setFont('Helvetica', 8)
    canvas.setFillColor(BRAND_MID_GREY)
    canvas.drawCentredString(
        PAGE_W / 2, 1.2 * cm,
        f"Adelaide Plumbing & Gasfitting  |  Page {doc.page}"
    )
    canvas.setStrokeColor(BRAND_ORANGE)
    canvas.setLineWidth(1.5)
    canvas.line(MARGIN, 1.8 * cm, PAGE_W - MARGIN, 1.8 * cm)
    canvas.restoreState()


# ==================== REPORT BUILDERS ====================

def _build_roof_report(job_report, submission):
    story = []
    snap = submission.snapshot
    s = _styles()

    story.append(_header_table(
        'Root Report',
        snap.get('job_id', ''),
        submission.created_at
    ))
    story.append(Spacer(1, 12))

    # Pre-filled info
    story.append(_section_heading('Job Information'))
    story.append(_divider())
    story.append(_field_table([
        ('Job Number', snap.get('job_id'), 'Builder / Client', snap.get('client_name')),
        ('Site Address', snap.get('site_address'), 'Scheduled', snap.get('scheduled_datetime')),
        ('Inspection Conducted By', snap.get('employee_name'), 'Date / Time of Attendance',
         submission.attendance_datetime.strftime('%d %b %Y, %I:%M %p') if submission.attendance_datetime else '—'),
    ]))
    story.append(Spacer(1, 8))

    # Insured details
    story.append(_section_heading("Insured's Details"))
    story.append(_divider())
    story.append(_field_table([
        ('Name', snap.get('client_name'), 'Phone', snap.get('client_phone')),
        ('Email', snap.get('client_email'), 'Contact Person', snap.get('contact_person_name')),
        ('Address', snap.get('site_address'), '', ''),
    ]))
    story.append(Spacer(1, 8))

    # Discussion
    story.append(_section_heading('Discussion with Insured'))
    story.append(_divider())
    story.append(_text_block('', submission.discussion_with_insured))
    story.append(Spacer(1, 8))

    # Dwelling
    story.append(_section_heading('Property Details'))
    story.append(_divider())
    story.append(_field_table([
        ('Type of Dwelling', submission.get_type_of_dwelling_display() if submission.type_of_dwelling else '—',
         '', ''),
    ]))

    # Front of dwelling photos
    front_photos = list(_get_photos(RoofReportSubmission, submission.id, 'front_of_dwelling'))
    if front_photos:
        story.append(Spacer(1, 6))
        story.append(Paragraph('Front of Dwelling', s['label']))
        story.extend(_photo_grid(front_photos))
    story.append(Spacer(1, 8))

    # Damages
    story.append(_section_heading('Resulting Damages'))
    story.append(_divider())
    story.append(_text_block('', submission.resulting_damages))
    damage_photos = list(_get_photos(RoofReportSubmission, submission.id, 'damage_photo'))
    if damage_photos:
        story.append(Spacer(1, 6))
        story.append(Paragraph('Photos of Resulting Damages', s['label']))
        story.extend(_photo_grid(damage_photos))
    story.append(Spacer(1, 8))

    # Roof & leak findings
    story.append(_section_heading('Roof & Leak Assessment'))
    story.append(_divider())
    story.append(_field_table([
        ('Type of Roof', submission.get_type_of_roof_display() if submission.type_of_roof else '—',
         'Pitch of Roof', submission.pitch_of_roof),
        ('Leak Present', submission.get_leak_present_display() if submission.leak_present else '—',
         'Cause of Leak Found', submission.get_cause_of_leak_found_display() if submission.cause_of_leak_found else '—'),
        ('Leak Fixed', submission.get_leak_fixed_display() if submission.leak_fixed else '—',
         'Fixed by Insured', submission.get_leak_fixed_by_insured_display() if submission.leak_fixed_by_insured else '—'),
    ]))
    story.append(Spacer(1, 8))

    # Works required
    story.append(_section_heading('Works Required to Fix the Leak'))
    story.append(_divider())
    story.append(_text_block('', submission.works_required))
    story.append(Spacer(1, 8))

    # Conclusion
    story.append(_section_heading('Conclusion'))
    story.append(_divider())
    story.append(_text_block('', submission.conclusion))
    story.append(Spacer(1, 8))

    # Job photos
    job_photos = list(_get_photos(RoofReportSubmission, submission.id, 'job_photo'))
    if job_photos:
        story.append(_section_heading('Job Photos'))
        story.append(_divider())
        story.extend(_photo_grid(job_photos))

    return story


def _build_appliance_report(job_report, submission):
    story = []
    snap = submission.snapshot
    s = _styles()

    story.append(_header_table('Appliance Report', snap.get('job_id', ''), submission.created_at))
    story.append(Spacer(1, 12))

    story.append(_section_heading('Job Information'))
    story.append(_divider())
    story.append(_field_table([
        ('Site Address', snap.get('site_address'), 'Builder / Client', snap.get('client_name')),
        ('Inspection Conducted By', snap.get('employee_name'),
         'Date / Time of Attendance',
         submission.attendance_datetime.strftime('%d %b %Y, %I:%M %p') if submission.attendance_datetime else '—'),
    ]))
    story.append(Spacer(1, 8))

    story.append(_section_heading("Insured's Details"))
    story.append(_divider())
    story.append(_field_table([
        ('Name', snap.get('client_name'), 'Phone', snap.get('client_phone')),
        ('Email', snap.get('client_email'), 'Contact Person', snap.get('contact_person_name')),
    ]))
    story.append(Spacer(1, 8))

    front_photos = list(_get_photos(ApplianceReportSubmission, submission.id, 'front_of_property'))
    if front_photos:
        story.append(_section_heading('Front of Property'))
        story.append(_divider())
        story.extend(_photo_grid(front_photos))
        story.append(Spacer(1, 8))

    story.append(_section_heading('Discussion with Insured'))
    story.append(_divider())
    story.append(_text_block('', submission.discussion_with_insured))
    story.append(Spacer(1, 8))

    story.append(_section_heading('Appliance Details'))
    story.append(_divider())
    story.append(_field_table([
        ('Brand', submission.appliance_brand, 'Model No.', submission.model_no),
        ('Approximate Age', submission.approx_age, '', ''),
    ]))
    story.append(Spacer(1, 8))

    story.append(_section_heading('Conclusion'))
    story.append(_divider())
    story.append(_text_block('', submission.conclusion))
    story.append(Spacer(1, 8))

    job_photos = list(_get_photos(ApplianceReportSubmission, submission.id, 'job_photo'))
    if job_photos:
        story.append(_section_heading('Job Photos'))
        story.append(_divider())
        story.extend(_photo_grid(job_photos))

    return story


def _build_drain_inspection(job_report, submission):
    story = []
    snap = submission.snapshot
    s = _styles()

    story.append(_header_table('Drain Inspection Report', snap.get('job_id', ''), submission.created_at))
    story.append(Spacer(1, 12))

    story.append(_section_heading('Job Information'))
    story.append(_divider())
    story.append(_field_table([
        ('Job Number', snap.get('job_id'), 'Client', snap.get('client_name')),
        ('Site Address', snap.get('site_address'),
         'Date / Time of Attendance',
         submission.attendance_datetime.strftime('%d %b %Y, %I:%M %p') if submission.attendance_datetime else '—'),
        ('Person Undertaking Investigation', snap.get('employee_name'), '', ''),
    ]))
    story.append(Spacer(1, 8))

    story.append(_section_heading('Site Contact Details'))
    story.append(_divider())
    story.append(_field_table([
        ('Name', snap.get('client_name'), 'Phone', snap.get('client_phone')),
        ('Email', snap.get('client_email'), 'Contact Person', snap.get('contact_person_name')),
    ]))
    story.append(Spacer(1, 8))

    front_photos = list(_get_photos(DrainInspectionSubmission, submission.id, 'front_of_dwelling'))
    if front_photos:
        story.append(_section_heading('Front of Dwelling'))
        story.append(_divider())
        story.extend(_photo_grid(front_photos))
        story.append(Spacer(1, 8))

    story.append(_section_heading('Property & Inspection Details'))
    story.append(_divider())
    story.append(_field_table([
        ('Property Construction',
         submission.get_property_construction_display() if submission.property_construction else '—',
         'Area of Inspection',
         submission.get_area_of_inspection_display() if submission.area_of_inspection else '—'),
        ('Pipe Construction',
         submission.get_pipe_construction_display() if submission.pipe_construction else '—',
         '', ''),
    ]))
    story.append(Spacer(1, 8))

    story.append(_section_heading('Discussion with Insured'))
    story.append(_divider())
    story.append(_text_block('', submission.discussion_with_insured))
    story.append(Spacer(1, 8))

    story.append(_section_heading('Resultant Damage / Affected Area'))
    story.append(_divider())
    story.append(_text_block('', submission.resultant_damage))
    damage_photos = list(_get_photos(DrainInspectionSubmission, submission.id, 'damage_photo'))
    if damage_photos:
        story.append(Spacer(1, 6))
        story.extend(_photo_grid(damage_photos))
    story.append(Spacer(1, 8))

    story.append(_section_heading('Conclusion'))
    story.append(_divider())
    story.append(_text_block('', submission.conclusion))
    story.append(Spacer(1, 8))

    job_photos = list(_get_photos(DrainInspectionSubmission, submission.id, 'job_photo'))
    if job_photos:
        story.append(_section_heading('Job Photos'))
        story.append(_divider())
        story.extend(_photo_grid(job_photos))

    return story


def _build_leak_inspection(job_report, submission):
    story = []
    snap = submission.snapshot
    s = _styles()

    story.append(_header_table('Leak Inspection Report', snap.get('job_id', ''), submission.created_at))
    story.append(Spacer(1, 12))

    story.append(_section_heading('Job Information'))
    story.append(_divider())
    story.append(_field_table([
        ('Job Number', snap.get('job_id'), 'Client', snap.get('client_name')),
        ('Site Address', snap.get('site_address'),
         'Date / Time of Attendance',
         submission.attendance_datetime.strftime('%d %b %Y, %I:%M %p') if submission.attendance_datetime else '—'),
        ('Person Undertaking Investigation', snap.get('employee_name'), '', ''),
    ]))
    story.append(Spacer(1, 8))

    story.append(_section_heading('Site Contact Details'))
    story.append(_divider())
    story.append(_field_table([
        ('Name', snap.get('client_name'), 'Phone', snap.get('client_phone')),
        ('Email', snap.get('client_email'), 'Contact Person', snap.get('contact_person_name')),
    ]))
    story.append(Spacer(1, 8))

    front_photos = list(_get_photos(LeakInspectionSubmission, submission.id, 'front_of_dwelling'))
    if front_photos:
        story.append(_section_heading('Front of Dwelling'))
        story.append(_divider())
        story.extend(_photo_grid(front_photos))
        story.append(Spacer(1, 8))

    story.append(_section_heading('Property Details'))
    story.append(_divider())
    story.append(_field_table([
        ('Property Construction',
         submission.get_property_construction_display() if submission.property_construction else '—',
         'Testing Location',
         submission.get_testing_location_display() if submission.testing_location else '—'),
    ]))
    story.append(Spacer(1, 8))

    story.append(_section_heading('Discussion with Site Contact'))
    story.append(_divider())
    story.append(_text_block('', submission.discussion_with_site_contact))
    story.append(Spacer(1, 8))

    story.append(_section_heading('Resultant Damage / Affected Area'))
    story.append(_divider())
    story.append(_text_block('', submission.resultant_damage))
    damage_photos = list(_get_photos(LeakInspectionSubmission, submission.id, 'damage_photo'))
    if damage_photos:
        story.append(Spacer(1, 6))
        story.extend(_photo_grid(damage_photos))
    story.append(Spacer(1, 8))

    whole_area = list(_get_photos(LeakInspectionSubmission, submission.id, 'whole_area'))
    if whole_area:
        story.append(_section_heading('Picture of Whole Area'))
        story.append(_divider())
        story.extend(_photo_grid(whole_area[:1]))
        story.append(Spacer(1, 8))

    story.append(_section_heading('Pressure Tests'))
    story.append(_divider())
    story.append(_field_table([
        ('Cold Line', submission.get_pressure_cold_line_display() if submission.pressure_cold_line else '—',
         'Hot Line', submission.get_pressure_hot_line_display() if submission.pressure_hot_line else '—'),
        ('Shower Breech/Mixer', submission.get_pressure_shower_breech_display() if submission.pressure_shower_breech else '—',
         'Bath Breech/Mixer', submission.get_pressure_bath_breech_display() if submission.pressure_bath_breech else '—'),
    ]))
    test_photo = list(_get_photos(LeakInspectionSubmission, submission.id, 'test_results'))
    if test_photo:
        story.append(Spacer(1, 6))
        story.extend(_photo_grid(test_photo[:1]))
    story.append(Spacer(1, 8))

    story.append(_section_heading('Flood & Spray Tests'))
    story.append(_divider())
    story.append(_field_table([
        ('Flood Test — Shower Alcove',
         submission.get_flood_test_shower_display() if submission.flood_test_shower else '—',
         'Flood Test — Bath',
         submission.get_flood_test_bath_display() if submission.flood_test_bath else '—'),
        ('Spray Test — Wall Tiles',
         submission.get_spray_test_wall_tiles_display() if submission.spray_test_wall_tiles else '—',
         'Spray Test — Shower Screen',
         submission.get_spray_test_shower_screen_display() if submission.spray_test_shower_screen else '—'),
    ]))
    story.append(Spacer(1, 8))

    story.append(_section_heading('Condition Assessment'))
    story.append(_divider())
    story.append(_field_table([
        ('Tile Condition',
         submission.get_tile_condition_display() if submission.tile_condition else '—',
         'Grout Condition',
         submission.get_grout_condition_display() if submission.grout_condition else '—'),
        ('Silicone Condition',
         submission.get_silicone_condition_display() if submission.silicone_condition else '—',
         'Silicone Around Spindles',
         'Yes' if submission.silicone_around_spindles else ('No' if submission.silicone_around_spindles is False else '—')),
    ]))
    spindle_photos = list(_get_photos(LeakInspectionSubmission, submission.id, 'spindle_photo'))
    if spindle_photos:
        story.append(Spacer(1, 6))
        story.append(Paragraph('Pictures of Spindle/Mixer', s['label']))
        story.extend(_photo_grid(spindle_photos))
    story.append(Spacer(1, 8))

    story.append(_section_heading('Conclusion'))
    story.append(_divider())
    story.append(_text_block('', submission.conclusion))
    story.append(Spacer(1, 8))

    job_photos = list(_get_photos(LeakInspectionSubmission, submission.id, 'job_photo'))
    if job_photos:
        story.append(_section_heading('Job Photos'))
        story.append(_divider())
        story.extend(_photo_grid(job_photos))

    return story


def _build_spray_test(job_report, submission):
    story = []
    snap = submission.snapshot
    s = _styles()

    story.append(_header_table('Spray Test Report', snap.get('job_id', ''), submission.created_at))
    story.append(Spacer(1, 12))

    story.append(_section_heading('Job Information'))
    story.append(_divider())
    story.append(_field_table([
        ('Job Number', snap.get('job_id'), 'Client', snap.get('client_name')),
        ('Site Address', snap.get('site_address'),
         'Date / Time of Attendance',
         submission.attendance_datetime.strftime('%d %b %Y, %I:%M %p') if submission.attendance_datetime else '—'),
        ('Person Undertaking Investigation', snap.get('employee_name'), '', ''),
    ]))
    story.append(Spacer(1, 8))

    story.append(_section_heading('Site Contact Details'))
    story.append(_divider())
    story.append(_field_table([
        ('Name', snap.get('client_name'), 'Phone', snap.get('client_phone')),
        ('Email', snap.get('client_email'), 'Contact Person', snap.get('contact_person_name')),
    ]))
    story.append(Spacer(1, 8))

    front_photos = list(_get_photos(SprayTestSubmission, submission.id, 'front_of_dwelling'))
    if front_photos:
        story.append(_section_heading('Front of Dwelling'))
        story.append(_divider())
        story.extend(_photo_grid(front_photos))
        story.append(Spacer(1, 8))

    story.append(_section_heading('Property Details'))
    story.append(_divider())
    story.append(_field_table([
        ('Property Construction',
         submission.get_property_construction_display() if submission.property_construction else '—',
         'Testing Location',
         submission.get_testing_location_display() if submission.testing_location else '—'),
    ]))
    story.append(Spacer(1, 8))

    story.append(_section_heading('Discussion with Insured'))
    story.append(_divider())
    story.append(_text_block('', submission.discussion_with_insured))
    story.append(Spacer(1, 8))

    story.append(_section_heading('Resultant Damage / Affected Area'))
    story.append(_divider())
    story.append(_text_block('', submission.resultant_damage))
    damage_photos = list(_get_photos(SprayTestSubmission, submission.id, 'damage_photo'))
    if damage_photos:
        story.append(Spacer(1, 6))
        story.extend(_photo_grid(damage_photos))
    story.append(Spacer(1, 8))

    whole_area = list(_get_photos(SprayTestSubmission, submission.id, 'whole_area'))
    if whole_area:
        story.append(_section_heading('Picture of Whole Area'))
        story.append(_divider())
        story.extend(_photo_grid(whole_area[:1]))
        story.append(Spacer(1, 8))

    story.append(_section_heading('Test Results'))
    story.append(_divider())
    story.append(_field_table([
        ('Flood Test',
         submission.get_flood_test_display() if submission.flood_test else '—',
         'Spray Test',
         submission.get_spray_test_display() if submission.spray_test else '—'),
    ]))
    story.append(Spacer(1, 4))
    if submission.flood_test_notes:
        story.append(_text_block('Flood Test Notes', submission.flood_test_notes))
    if submission.spray_test_notes:
        story.append(_text_block('Spray Test Notes', submission.spray_test_notes))
    story.append(Spacer(1, 8))

    story.append(_section_heading('Condition Assessment'))
    story.append(_divider())
    story.append(_field_table([
        ('Tile Condition',
         submission.get_tile_condition_display() if submission.tile_condition else '—',
         'Grout Condition',
         submission.get_grout_condition_display() if submission.grout_condition else '—'),
        ('Silicone Condition',
         submission.get_silicone_condition_display() if submission.silicone_condition else '—',
         '', ''),
    ]))
    if submission.tile_condition_notes:
        story.append(_text_block('Tile Notes', submission.tile_condition_notes))
    if submission.grout_condition_notes:
        story.append(_text_block('Grout Notes', submission.grout_condition_notes))
    if submission.silicone_condition_notes:
        story.append(_text_block('Silicone Notes', submission.silicone_condition_notes))
    story.append(Spacer(1, 8))

    story.append(_section_heading('Conclusion'))
    story.append(_divider())
    story.append(_text_block('', submission.conclusion))
    story.append(Spacer(1, 8))

    job_photos = list(_get_photos(SprayTestSubmission, submission.id, 'job_photo'))
    if job_photos:
        story.append(_section_heading('Job Photos'))
        story.append(_divider())
        story.extend(_photo_grid(job_photos))

    return story


# ==================== MAIN ENTRY POINT ====================

_BUILDERS = {
    ReportType.ROOF: _build_roof_report,
    ReportType.APPLIANCE: _build_appliance_report,
    ReportType.DRAIN_INSPECTION: _build_drain_inspection,
    ReportType.LEAK_INSPECTION: _build_leak_inspection,
    ReportType.SPRAY_TEST: _build_spray_test,
}


def generate_pdf(job_report, submission):
    """
    Generate a PDF for the given job_report + submission.
    Returns a BytesIO buffer ready for FileResponse.
    """
    builder = _BUILDERS.get(job_report.report_type)
    if not builder:
        raise ValueError(f'No PDF builder registered for report type: {job_report.report_type}')

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=2.5 * cm,
        title=f"{job_report.get_report_type_display()} — {job_report.job.job_id}",
        author='Adelaide Plumbing & Gasfitting',
    )

    story = builder(job_report, submission)
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buffer
