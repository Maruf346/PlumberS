from django.urls import path
from .views import (
    ReportTypeListView,
    JobReportListView,
    ReportFormFieldsView,
    ReportFormView,
    ReportSubmissionView,
    ReportDownloadView,
    # Typed submit views — one per report type
    RoofReportSubmitView,
    ApplianceReportSubmitView,
    DrainInspectionSubmitView,
    LeakInspectionSubmitView,
    SprayTestSubmitView,
)

urlpatterns = [
    # ── Admin: available report type choices ──────────────────────────────────
    path('types/', ReportTypeListView.as_view(), name='report-types'),

    # ── Read endpoints — unchanged ────────────────────────────────────────────
    path('<uuid:job_report_id>/formfields/', ReportFormFieldsView.as_view(), name='report-formfields'),
    path('<uuid:job_report_id>/form/', ReportFormView.as_view(), name='report-form'),
    path('<uuid:job_report_id>/submission/', ReportSubmissionView.as_view(), name='report-submission'),
    path('<uuid:job_report_id>/download/', ReportDownloadView.as_view(), name='report-download'),

    # ── Typed submit endpoints — one per report type ──────────────────────────
    # Generic /submit/ removed. Use the specific endpoint for your report type.
    # The correct submit_url is returned by /formfields/ automatically.
    path('<uuid:job_report_id>/submit/roof/', RoofReportSubmitView.as_view(), name='report-submit-roof'),
    path('<uuid:job_report_id>/submit/appliance/', ApplianceReportSubmitView.as_view(), name='report-submit-appliance'),
    path('<uuid:job_report_id>/submit/drain/', DrainInspectionSubmitView.as_view(), name='report-submit-drain'),
    path('<uuid:job_report_id>/submit/leak/', LeakInspectionSubmitView.as_view(), name='report-submit-leak'),
    path('<uuid:job_report_id>/submit/spray/', SprayTestSubmitView.as_view(), name='report-submit-spray'),
]

# ── Note: JobReportListView is registered in core/urls.py ─────────────────────
# path('api/jobs/<uuid:job_id>/reports/', JobReportListView.as_view(), name='job-reports')