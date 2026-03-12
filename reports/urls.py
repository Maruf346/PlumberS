from django.urls import path
from .views import (
    ReportTypeListView,
    JobReportListView,
    ReportFormView,
    ReportSubmitView,
    ReportSubmissionView,
    ReportDownloadView,
)

urlpatterns = [
    # ── Admin: available report type choices (for job creation form) ──────────
    path('types/', ReportTypeListView.as_view(), name='report-types'),

    # ── Admin: all reports for a specific job ─────────────────────────────────
    # Mounted under jobs router: /api/jobs/{job_id}/reports/
    # This view is registered in jobs/urls.py — see below.

    # ── Employee + Admin: per-report-record endpoints ─────────────────────────
    path('<uuid:job_report_id>/form/', ReportFormView.as_view(), name='report-form'),
    path('<uuid:job_report_id>/submit/', ReportSubmitView.as_view(), name='report-submit'),
    path('<uuid:job_report_id>/submission/', ReportSubmissionView.as_view(), name='report-submission'),
    path('<uuid:job_report_id>/download/', ReportDownloadView.as_view(), name='report-download'),
]

# ── Note on JobReportListView ─────────────────────────────────────────────────
# JobReportListView is mounted in core/urls.py under the jobs prefix:
#   path('api/jobs/<uuid:job_id>/reports/', JobReportListView.as_view(), ...)
# This keeps the URL structure logical (/jobs/{id}/reports/) while the
# view lives in the reports app where it belongs.
