"""
PDF generation for all report types.
Layout matches the Adelaide Plumbing & Gasfitting reference PDF exactly:
  - Logo top-left, contact block top-right on every page
  - Report title in teal (#2E86AB) below the header line
  - Two-column bordered data table rows (bold label | value)
  - Photos embedded inline maintaining original aspect ratio
  - Section headings in teal, bold, with underline rule
  - Footer: "Insurance Specialists" left | "Page X of Y" right
"""
import io
import os

from django.contrib.contenttypes.models import ContentType
from PIL import Image as PILImage

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame,
    Paragraph, Spacer, Table, TableStyle,
    HRFlowable, Image, KeepTogether,
)
from reportlab.platypus.flowables import HRFlowable
from reportlab.pdfgen import canvas as rl_canvas

from reports.models import (
    ReportPhoto, ReportType,
    RoofReportSubmission, ApplianceReportSubmission,
    DrainInspectionSubmission, LeakInspectionSubmission,
    SprayTestSubmission,
)

# ── Dimensions ────────────────────────────────────────────────────────────────
PAGE_W, PAGE_H = A4
L_MARGIN = 1.8 * cm
R_MARGIN = 1.8 * cm
T_MARGIN = 3.8 * cm          # space reserved for header drawn on canvas
B_MARGIN = 2.0 * cm          # space reserved for footer drawn on canvas
CONTENT_W = PAGE_W - L_MARGIN - R_MARGIN

# ── Colours ───────────────────────────────────────────────────────────────────
TEAL        = colors.HexColor('#2E86AB')   # headings + title
DARK        = colors.HexColor('#1A1A1A')   # label text
TEXT_GREY   = colors.HexColor('#444444')   # value text
LIGHT_GREY  = colors.HexColor('#F2F2F2')   # alternating row bg
MID_GREY    = colors.HexColor('#CCCCCC')   # divider lines
WHITE       = colors.white
BLACK       = colors.black

# ── Logo path (relative to Django project root /app/) ─────────────────────────
LOGO_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),   # .../reports/pdf/
    '..', '..', 'api', 'logo.png'                # → /app/api/logo.png
)
LOGO_PATH = os.path.normpath(LOGO_PATH)

# ── Contact block lines (right side of header) ───────────────────────────────
CONTACT_LINES = [
    'M: 0401 183 381',
    'E: admin@adlplumb.com.au',
    'ABN: 74 789 668 904',
    'PGE: 303673',
    '5/49 Kingston Ave',
    'Richmond, SA, 5033',
]


# ==================== STYLES ====================

def _s():
    """Return all paragraph styles."""
    return {
        'title': ParagraphStyle(
            'ReportTitle',
            fontName='Helvetica-Bold',
            fontSize=14,
            textColor=TEAL,
            spaceBefore=0,
            spaceAfter=6,
        ),
        'section': ParagraphStyle(
            'Section',
            fontName='Helvetica-Bold',
            fontSize=10,
            textColor=TEAL,
            spaceBefore=10,
            spaceAfter=2,
        ),
        'label': ParagraphStyle(
            'Label',
            fontName='Helvetica-Bold',
            fontSize=9,
            textColor=DARK,
            leading=13,
        ),
        'value': ParagraphStyle(
            'Value',
            fontName='Helvetica',
            fontSize=9,
            textColor=TEXT_GREY,
            leading=13,
        ),
        'contact': ParagraphStyle(
            'Contact',
            fontName='Helvetica',
            fontSize=8,
            textColor=DARK,
            leading=11,
            alignment=TA_RIGHT,
        ),
        'footer_l': ParagraphStyle(
            'FooterL',
            fontName='Helvetica',
            fontSize=8,
            textColor=MID_GREY,
            alignment=TA_LEFT,
        ),
        'footer_r': ParagraphStyle(
            'FooterR',
            fontName='Helvetica',
            fontSize=8,
            textColor=MID_GREY,
            alignment=TA_RIGHT,
        ),
    }


# ==================== HEADER / FOOTER (drawn on canvas) ====================

def _draw_header_footer(canv, doc, report_title, total_pages):
    """
    Called on every page via onPage callbacks.
    Draws logo, contact block, report title line, and footer.
    """
    canv.saveState()
    s = _s()

    # ── Logo ──────────────────────────────────────────────────────────────────
    logo_h = 1.2 * cm
    logo_w = 4.5 * cm   # will be overridden by actual ratio below
    if os.path.exists(LOGO_PATH):
        try:
            pil = PILImage.open(LOGO_PATH)
            orig_w, orig_h = pil.size
            ratio = orig_w / orig_h
            logo_w = logo_h * ratio
            canv.drawImage(
                LOGO_PATH,
                L_MARGIN,
                PAGE_H - T_MARGIN + 0.6 * cm,
                width=logo_w,
                height=logo_h,
                preserveAspectRatio=True,
                mask='auto',
            )
        except Exception:
            pass

    # ── Contact block (right-aligned) ────────────────────────────────────────
    contact_x = PAGE_W - R_MARGIN
    contact_y = PAGE_H - 1.0 * cm
    line_h = 0.38 * cm
    canv.setFont('Helvetica', 8)
    canv.setFillColor(DARK)
    for line in CONTACT_LINES:
        canv.drawRightString(contact_x, contact_y, line)
        contact_y -= line_h

    # ── Horizontal rule below header ──────────────────────────────────────────
    rule_y = PAGE_H - T_MARGIN + 0.35 * cm
    canv.setStrokeColor(MID_GREY)
    canv.setLineWidth(0.5)
    canv.line(L_MARGIN, rule_y, PAGE_W - R_MARGIN, rule_y)

    # ── Report title (teal, bold, below rule) ─────────────────────────────────
    title_y = rule_y - 0.55 * cm
    canv.setFont('Helvetica-Bold', 13)
    canv.setFillColor(TEAL)
    canv.drawString(L_MARGIN, title_y, report_title.upper())

    # Underline the title
    title_text_w = canv.stringWidth(report_title.upper(), 'Helvetica-Bold', 13)
    canv.setStrokeColor(TEAL)
    canv.setLineWidth(0.8)
    canv.line(L_MARGIN, title_y - 2, L_MARGIN + title_text_w, title_y - 2)

    # ── Footer ────────────────────────────────────────────────────────────────
    footer_y = 1.2 * cm
    canv.setFont('Helvetica', 8)
    canv.setFillColor(MID_GREY)
    canv.drawString(L_MARGIN, footer_y, 'Insurance Specialists')
    canv.drawRightString(
        PAGE_W - R_MARGIN, footer_y,
        f'Page {doc.page} of {total_pages}'
    )

    # Footer rule
    canv.setStrokeColor(MID_GREY)
    canv.setLineWidth(0.5)
    canv.line(L_MARGIN, footer_y + 0.4 * cm, PAGE_W - R_MARGIN, footer_y + 0.4 * cm)

    canv.restoreState()


# ==================== CONTENT HELPERS ====================

def _section_heading(text):
    s = _s()
    return KeepTogether([
        Paragraph(text, s['section']),
        HRFlowable(width='100%', thickness=0.5, color=TEAL, spaceAfter=4, spaceBefore=0),
    ])


def _row(label, value, shade=False):
    """Single full-width label | value row."""
    s = _s()
    bg = LIGHT_GREY if shade else WHITE
    t = Table(
        [[Paragraph(label, s['label']), Paragraph(str(value) if value else '—', s['value'])]],
        colWidths=[CONTENT_W * 0.38, CONTENT_W * 0.62],
    )
    t.setStyle(TableStyle([
        ('BACKGROUND',   (0, 0), (-1, -1), bg),
        ('BOX',          (0, 0), (-1, -1), 0.4, MID_GREY),
        ('LINEBEFORE',   (1, 0), (1, 0),   0.4, MID_GREY),
        ('TOPPADDING',   (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING',(0, 0), (-1, -1), 5),
        ('LEFTPADDING',  (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('VALIGN',       (0, 0), (-1, -1), 'TOP'),
    ]))
    return t


def _rows(pairs):
    """
    Render a list of (label, value) tuples as alternating-shade rows.
    pairs = [('Label', 'Value'), ...]
    """
    return [_row(label, value, shade=(i % 2 == 1)) for i, (label, value) in enumerate(pairs)]


def _photo_row(label, photos_list):
    """
    Label row followed by photos embedded maintaining original aspect ratio.
    Up to 3 photos per row.
    """
    if not photos_list:
        return []

    s = _s()
    flowables = []

    # Label row
    t = Table(
        [[Paragraph(label, s['label'])]],
        colWidths=[CONTENT_W],
    )
    t.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), LIGHT_GREY),
        ('BOX',           (0, 0), (-1, -1), 0.4, MID_GREY),
        ('TOPPADDING',    (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING',   (0, 0), (-1, -1), 6),
    ]))
    flowables.append(t)

    # Build photo grid — 3 per row, preserve aspect ratio
    gap = 0.2 * cm
    max_photo_w = (CONTENT_W - 2 * gap) / 3
    max_photo_h = max_photo_w * 1.05   # generous height cap; aspect ratio wins

    batch = []
    col_widths = []

    for photo in photos_list:
        try:
            path = photo.image.path
            if not os.path.exists(path):
                raise FileNotFoundError
            # Determine natural aspect ratio
            pil = PILImage.open(path)
            orig_w, orig_h = pil.size
            ratio = orig_w / orig_h
            # Fit within max_photo_w × max_photo_h preserving ratio
            if ratio >= 1:
                pw = min(max_photo_w, max_photo_h * ratio)
                ph = pw / ratio
            else:
                ph = min(max_photo_h, max_photo_w / ratio)
                pw = ph * ratio
            img = Image(path, width=pw, height=ph)
            batch.append(img)
            col_widths.append(max_photo_w)
        except Exception:
            batch.append(Paragraph('[Photo unavailable]', s['value']))
            col_widths.append(max_photo_w)

        if len(batch) == 3:
            photo_table = Table([batch], colWidths=col_widths)
            photo_table.setStyle(TableStyle([
                ('BOX',           (0, 0), (-1, -1), 0.4, MID_GREY),
                ('INNERGRID',     (0, 0), (-1, -1), 0.4, MID_GREY),
                ('ALIGN',         (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING',    (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('LEFTPADDING',   (0, 0), (-1, -1), 3),
                ('RIGHTPADDING',  (0, 0), (-1, -1), 3),
            ]))
            flowables.append(photo_table)
            flowables.append(Spacer(1, 0.15 * cm))
            batch = []
            col_widths = []

    # Remaining photos (< 3) — pad with empty cells
    if batch:
        while len(batch) < 3:
            batch.append('')
            col_widths.append(max_photo_w)
        photo_table = Table([batch], colWidths=col_widths)
        photo_table.setStyle(TableStyle([
            ('BOX',           (0, 0), (-1, -1), 0.4, MID_GREY),
            ('INNERGRID',     (0, 0), (-1, -1), 0.4, MID_GREY),
            ('ALIGN',         (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN',        (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING',    (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING',   (0, 0), (-1, -1), 3),
            ('RIGHTPADDING',  (0, 0), (-1, -1), 3),
        ]))
        flowables.append(photo_table)

    flowables.append(Spacer(1, 0.2 * cm))
    return flowables


def _get_photos(model_class, object_id, photo_type=None):
    ct = ContentType.objects.get_for_model(model_class)
    qs = ReportPhoto.objects.filter(content_type=ct, object_id=object_id)
    if photo_type:
        qs = qs.filter(photo_type=photo_type)
    return list(qs)


def _sp(h=0.3):
    return Spacer(1, h * cm)


# ==================== REPORT BUILDERS ====================

def _build_roof_report(job_report, submission):
    snap = submission.snapshot
    story = []

    story.append(_sp(0.2))
    story.extend(_rows([
        ('Job Number',                snap.get('job_id', '—')),
        ('Builder / Client',          snap.get('client_name', '—')),
        ('Site Address',              snap.get('site_address', '—')),
        ('Scheduled',                 snap.get('scheduled_datetime', '—')),
        ('Inspection Conducted By',   snap.get('employee_name', '—')),
        ('Date / Time of Attendance', submission.attendance_datetime.strftime('%d/%m/%Y %I:%M %p')
                                      if submission.attendance_datetime else '—'),
    ]))
    story.append(_sp())

    # Front of dwelling photo
    front = _get_photos(RoofReportSubmission, submission.id, 'front_of_dwelling')
    story.extend(_photo_row('Front of Dwelling', front))

    story.append(_section_heading("Insured's Details"))
    story.extend(_rows([
        ('Name',           snap.get('client_name', '—')),
        ('Phone',          snap.get('client_phone', '—')),
        ('Email',          snap.get('client_email', '—')),
        ('Contact Person', snap.get('contact_person_name', '—')),
        ('Address',        snap.get('site_address', '—')),
    ]))
    story.append(_sp())

    story.append(_section_heading('Property Construction'))
    story.extend(_rows([
        ('Type of Dwelling', submission.get_type_of_dwelling_display()
                             if submission.type_of_dwelling else '—'),
    ]))
    story.append(_sp())

    story.append(_section_heading('Discussion with Insured'))
    story.extend(_rows([('', submission.discussion_with_insured or '—')]))
    story.append(_sp())

    story.append(_section_heading('Resulting Damages / Affected Area'))
    story.extend(_rows([('', submission.resulting_damages or '—')]))
    damage = _get_photos(RoofReportSubmission, submission.id, 'damage_photo')
    story.extend(_photo_row('Picture of resultant damage / affected area', damage))

    story.append(_section_heading('Roof & Leak Assessment'))
    story.extend(_rows([
        ('Type of Roof',       submission.get_type_of_roof_display()
                               if submission.type_of_roof else '—'),
        ('Pitch of Roof',      submission.pitch_of_roof or '—'),
        ('Leak Present',       submission.get_leak_present_display()
                               if submission.leak_present else '—'),
        ('Cause of Leak Found',submission.get_cause_of_leak_found_display()
                               if submission.cause_of_leak_found else '—'),
        ('Leak Fixed',         submission.get_leak_fixed_display()
                               if submission.leak_fixed else '—'),
        ('Fixed by Insured',   submission.get_leak_fixed_by_insured_display()
                               if submission.leak_fixed_by_insured else '—'),
    ]))
    story.append(_sp())

    story.append(_section_heading('Works Required to Fix the Leak'))
    story.extend(_rows([('', submission.works_required or '—')]))
    story.append(_sp())

    story.append(_section_heading('Conclusion'))
    story.extend(_rows([('Conclusion', submission.conclusion or '—')]))
    story.append(_sp())

    job_photos = _get_photos(RoofReportSubmission, submission.id, 'job_photo')
    story.extend(_photo_row('Job Photos', job_photos))

    return story


def _build_appliance_report(job_report, submission):
    snap = submission.snapshot
    story = []

    story.append(_sp(0.2))
    story.extend(_rows([
        ('Site Address',              snap.get('site_address', '—')),
        ('Builder / Client',          snap.get('client_name', '—')),
        ('Inspection Conducted By',   snap.get('employee_name', '—')),
        ('Date / Time of Attendance', submission.attendance_datetime.strftime('%d/%m/%Y %I:%M %p')
                                      if submission.attendance_datetime else '—'),
    ]))
    story.append(_sp())

    front = _get_photos(ApplianceReportSubmission, submission.id, 'front_of_property')
    story.extend(_photo_row('Front of Property', front))

    story.append(_section_heading("Insured's Details"))
    story.extend(_rows([
        ('Name',           snap.get('client_name', '—')),
        ('Phone',          snap.get('client_phone', '—')),
        ('Email',          snap.get('client_email', '—')),
        ('Contact Person', snap.get('contact_person_name', '—')),
    ]))
    story.append(_sp())

    story.append(_section_heading('Discussion with Insured'))
    story.extend(_rows([('', submission.discussion_with_insured or '—')]))
    story.append(_sp())

    story.append(_section_heading('Appliance Details'))
    story.extend(_rows([
        ('Brand',            submission.appliance_brand or '—'),
        ('Model No.',        submission.model_no or '—'),
        ('Approximate Age',  submission.approx_age or '—'),
    ]))
    story.append(_sp())

    story.append(_section_heading('Conclusion'))
    story.extend(_rows([('Conclusion', submission.conclusion or '—')]))
    story.append(_sp())

    job_photos = _get_photos(ApplianceReportSubmission, submission.id, 'job_photo')
    story.extend(_photo_row('Job Photos', job_photos))

    return story


def _build_drain_inspection(job_report, submission):
    snap = submission.snapshot
    story = []

    story.append(_sp(0.2))
    story.extend(_rows([
        ('Job Number',                snap.get('job_id', '—')),
        ('Client',                    snap.get('client_name', '—')),
        ('Site Address',              snap.get('site_address', '—')),
        ('Person Undertaking Investigation', snap.get('employee_name', '—')),
        ('Date / Time of Attendance', submission.attendance_datetime.strftime('%d/%m/%Y %I:%M %p')
                                      if submission.attendance_datetime else '—'),
    ]))
    story.append(_sp())

    front = _get_photos(DrainInspectionSubmission, submission.id, 'front_of_dwelling')
    story.extend(_photo_row('Front of Dwelling', front))

    story.append(_section_heading('Site Contact Details'))
    story.extend(_rows([
        ('Name',           snap.get('client_name', '—')),
        ('Phone',          snap.get('client_phone', '—')),
        ('Email',          snap.get('client_email', '—')),
        ('Contact Person', snap.get('contact_person_name', '—')),
    ]))
    story.append(_sp())

    story.append(_section_heading('Property Construction'))
    story.extend(_rows([
        ('Property Construction', submission.get_property_construction_display()
                                  if submission.property_construction else '—'),
    ]))
    story.append(_sp())

    story.append(_section_heading('Discussion with Insured'))
    story.extend(_rows([('', submission.discussion_with_insured or '—')]))
    story.append(_sp())

    story.append(_section_heading('Resultant Damage / Affected Area'))
    story.extend(_rows([('', submission.resultant_damage or '—')]))
    damage = _get_photos(DrainInspectionSubmission, submission.id, 'damage_photo')
    story.extend(_photo_row('Picture of resultant damage / affected area', damage))

    story.append(_section_heading('Inspection Details'))
    story.extend(_rows([
        ('Area of Inspection', submission.get_area_of_inspection_display()
                               if submission.area_of_inspection else '—'),
        ('Pipe Construction',  submission.get_pipe_construction_display()
                               if submission.pipe_construction else '—'),
    ]))
    story.append(_sp())

    story.append(_section_heading('Conclusion'))
    story.extend(_rows([('Conclusion', submission.conclusion or '—')]))
    story.append(_sp())

    job_photos = _get_photos(DrainInspectionSubmission, submission.id, 'job_photo')
    story.extend(_photo_row('Job Photos', job_photos))

    return story


def _build_leak_inspection(job_report, submission):
    snap = submission.snapshot
    story = []

    story.append(_sp(0.2))
    story.extend(_rows([
        ('Job Number',                snap.get('job_id', '—')),
        ('Client',                    snap.get('client_name', '—')),
        ('Site Address',              snap.get('site_address', '—')),
        ('Site Contact Details',      f"{snap.get('contact_person_name', '')}  "
                                      f"{snap.get('client_phone', '')}".strip()),
        ('Person Undertaking Investigation', snap.get('employee_name', '—')),
        ('Date / Time of Attendance', submission.attendance_datetime.strftime('%d/%m/%Y %I:%M %p')
                                      if submission.attendance_datetime else '—'),
    ]))
    story.append(_sp())

    front = _get_photos(LeakInspectionSubmission, submission.id, 'front_of_dwelling')
    story.extend(_photo_row('Front of Dwelling', front))

    story.append(_section_heading('Property Construction'))
    story.extend(_rows([
        ('Property Construction', submission.get_property_construction_display()
                                  if submission.property_construction else '—'),
    ]))
    story.append(_sp())

    story.append(_section_heading('Discussion with Site Contact'))
    story.extend(_rows([('', submission.discussion_with_site_contact or '—')]))
    story.append(_sp())

    story.append(_section_heading('Resultant Damage / Affected Area'))
    story.extend(_rows([('', submission.resultant_damage or '—')]))
    damage = _get_photos(LeakInspectionSubmission, submission.id, 'damage_photo')
    story.extend(_photo_row('Picture of resultant damage / affected area', damage))

    story.append(_section_heading('Pressure Testing'))
    story.extend(_rows([
        ('Testing Location',                  submission.get_testing_location_display()
                                              if submission.testing_location else '—'),
        ('Pressure test to domestic cold line',  submission.get_pressure_cold_line_display()
                                              if submission.pressure_cold_line else '—'),
        ('Pressure test to domestic hot line',   submission.get_pressure_hot_line_display()
                                              if submission.pressure_hot_line else '—'),
        ('Pressure test to shower breech/mixer', submission.get_pressure_shower_breech_display()
                                              if submission.pressure_shower_breech else '—'),
        ('Pressure test to bath breech/mixer',   submission.get_pressure_bath_breech_display()
                                              if submission.pressure_bath_breech else '—'),
    ]))
    test_photo = _get_photos(LeakInspectionSubmission, submission.id, 'test_results')
    story.extend(_photo_row('Picture of test results', test_photo))

    story.append(_section_heading('Flood / Spray Testing'))
    story.extend(_rows([
        ('Flood test shower alcove',   submission.get_flood_test_shower_display()
                                       if submission.flood_test_shower else '—'),
        ('Flood test bath',            submission.get_flood_test_bath_display()
                                       if submission.flood_test_bath else '—'),
        ('Spray test wall tiles',      submission.get_spray_test_wall_tiles_display()
                                       if submission.spray_test_wall_tiles else '—'),
        ('Spray test to shower screen',submission.get_spray_test_shower_screen_display()
                                       if submission.spray_test_shower_screen else '—'),
    ]))
    story.append(_sp())

    # Whole area photo
    whole = _get_photos(LeakInspectionSubmission, submission.id, 'whole_area')
    story.extend(_photo_row('Picture of Whole Area', whole))

    story.append(_section_heading('Tiles, Grout and Silicone Seal'))
    story.extend(_rows([
        ('Tile condition',    submission.get_tile_condition_display()
                              if submission.tile_condition else '—'),
        ('Grout condition',   submission.get_grout_condition_display()
                              if submission.grout_condition else '—'),
        ('Silicone condition',submission.get_silicone_condition_display()
                              if submission.silicone_condition else '—'),
        ('Silicone around spindles and penetrations',
                              'YES' if submission.silicone_around_spindles
                              else ('NO' if submission.silicone_around_spindles is False else '—')),
    ]))
    spindle = _get_photos(LeakInspectionSubmission, submission.id, 'spindle_photo')
    story.extend(_photo_row('Pictures of spindle/mixer', spindle))

    story.append(_section_heading('Conclusion'))
    story.extend(_rows([('Conclusion', submission.conclusion or '—')]))
    story.append(_sp())

    job_photos = _get_photos(LeakInspectionSubmission, submission.id, 'job_photo')
    story.extend(_photo_row('Job Photos', job_photos))

    return story


def _build_spray_test(job_report, submission):
    snap = submission.snapshot
    story = []

    story.append(_sp(0.2))
    story.extend(_rows([
        ('Job Number',                snap.get('job_id', '—')),
        ('Client',                    snap.get('client_name', '—')),
        ('Site Address',              snap.get('site_address', '—')),
        ('Site Contact Details',      f"{snap.get('contact_person_name', '')}  "
                                      f"{snap.get('client_phone', '')}".strip()),
        ('Person Undertaking Investigation', snap.get('employee_name', '—')),
        ('Date / Time of Attendance', submission.attendance_datetime.strftime('%d/%m/%Y %I:%M %p')
                                      if submission.attendance_datetime else '—'),
    ]))
    story.append(_sp())

    front = _get_photos(SprayTestSubmission, submission.id, 'front_of_dwelling')
    story.extend(_photo_row('Front of Dwelling', front))

    story.append(_section_heading('Property Construction'))
    story.extend(_rows([
        ('Property Construction', submission.get_property_construction_display()
                                  if submission.property_construction else '—'),
    ]))
    story.append(_sp())

    story.append(_section_heading('Discussion with Insured'))
    story.extend(_rows([('', submission.discussion_with_insured or '—')]))
    story.append(_sp())

    story.append(_section_heading('Resultant Damage / Affected Area'))
    story.extend(_rows([('', submission.resultant_damage or '—')]))
    damage = _get_photos(SprayTestSubmission, submission.id, 'damage_photo')
    story.extend(_photo_row('Picture of resultant damage / affected area', damage))

    story.append(_section_heading('Testing'))
    story.extend(_rows([
        ('Testing Location', submission.get_testing_location_display()
                             if submission.testing_location else '—'),
    ]))
    whole = _get_photos(SprayTestSubmission, submission.id, 'whole_area')
    story.extend(_photo_row('Picture of Whole Area', whole))

    story.append(_section_heading('Flood / Spray Testing'))
    story.extend(_rows([
        ('Flood Test',       submission.get_flood_test_display()
                             if submission.flood_test else '—'),
        ('Flood Test Notes', submission.flood_test_notes or '—'),
        ('Spray Test',       submission.get_spray_test_display()
                             if submission.spray_test else '—'),
        ('Spray Test Notes', submission.spray_test_notes or '—'),
    ]))
    story.append(_sp())

    story.append(_section_heading('Tiles, Grout and Silicone Seal'))
    story.extend(_rows([
        ('Tile condition',       submission.get_tile_condition_display()
                                 if submission.tile_condition else '—'),
        ('Tile Notes',           submission.tile_condition_notes or '—'),
        ('Grout condition',      submission.get_grout_condition_display()
                                 if submission.grout_condition else '—'),
        ('Grout Notes',          submission.grout_condition_notes or '—'),
        ('Silicone condition',   submission.get_silicone_condition_display()
                                 if submission.silicone_condition else '—'),
        ('Silicone Notes',       submission.silicone_condition_notes or '—'),
    ]))
    story.append(_sp())

    story.append(_section_heading('Conclusion'))
    story.extend(_rows([('Conclusion', submission.conclusion or '—')]))
    story.append(_sp())

    job_photos = _get_photos(SprayTestSubmission, submission.id, 'job_photo')
    story.extend(_photo_row('Job Photos', job_photos))

    return story


# ==================== MAIN ENTRY POINT ====================

_BUILDERS = {
    ReportType.ROOF:             _build_roof_report,
    ReportType.APPLIANCE:        _build_appliance_report,
    ReportType.DRAIN_INSPECTION: _build_drain_inspection,
    ReportType.LEAK_INSPECTION:  _build_leak_inspection,
    ReportType.SPRAY_TEST:       _build_spray_test,
}

_TITLES = {
    ReportType.ROOF:             'Roof Report',
    ReportType.APPLIANCE:        'Appliance Report',
    ReportType.DRAIN_INSPECTION: 'Drain Inspection Report',
    ReportType.LEAK_INSPECTION:  'Leak Detection Report',
    ReportType.SPRAY_TEST:       'Spray Test Report',
}


def generate_pdf(job_report, submission):
    """
    Two-pass PDF generation:
      Pass 1 — build story into a dummy buffer to count total pages.
      Pass 2 — rebuild with total_pages injected into the footer callback.
    Returns a BytesIO buffer ready for FileResponse.
    """
    builder = _BUILDERS.get(job_report.report_type)
    if not builder:
        raise ValueError(f'No PDF builder for report type: {job_report.report_type}')

    report_title = _TITLES.get(job_report.report_type, job_report.get_report_type_display())

    def _build(buffer, total_pages):
        doc = BaseDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=L_MARGIN,
            rightMargin=R_MARGIN,
            topMargin=T_MARGIN,
            bottomMargin=B_MARGIN,
            title=f"{report_title} — {job_report.job.job_id}",
            author='Adelaide Plumbing & Gasfitting',
        )
        frame = Frame(
            L_MARGIN, B_MARGIN,
            PAGE_W - L_MARGIN - R_MARGIN,
            PAGE_H - T_MARGIN - B_MARGIN,
            id='main',
        )
        def on_page(canv, doc):
            _draw_header_footer(canv, doc, report_title, total_pages)

        template = PageTemplate(id='main', frames=[frame], onPage=on_page)
        doc.addPageTemplates([template])
        story = builder(job_report, submission)
        doc.build(story)

    # Pass 1 — count pages
    dummy = io.BytesIO()
    _build(dummy, total_pages=999)   # placeholder
    dummy.seek(0)
    # Count pages from pass 1 using pypdf
    try:
        from pypdf import PdfReader
        total_pages = len(PdfReader(dummy).pages)
    except Exception:
        total_pages = 1

    # Pass 2 — real build with correct page count
    buffer = io.BytesIO()
    _build(buffer, total_pages=total_pages)
    return buffer