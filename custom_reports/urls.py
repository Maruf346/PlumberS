from django.urls import path

from .views import *


urlpatterns = [
    path('field-types/', CustomReportFieldTypeListView.as_view(), name='custom-report-field-type-list'),

    path('', CustomReportTemplateListView.as_view(), name='custom-report-template-list'),
    path('<uuid:id>/', CustomReportTemplateDetailView.as_view(), name='custom-report-template-detail'),

    path('create/', AdminCustomReportTemplateCreateView.as_view(), name='custom-report-template-create'),
    path('<uuid:id>/update/', AdminCustomReportTemplateUpdateView.as_view(), name='custom-report-template-update'),

    path('<uuid:template_id>/fields/add/', AdminCustomReportFieldCreateView.as_view(), name='custom-report-field-create'),
    path('<uuid:template_id>/fields/<uuid:field_id>/', AdminCustomReportFieldUpdateView.as_view(), name='custom-report-field-update-delete'),
    path('<uuid:template_id>/fields/reorder/', AdminCustomReportFieldReorderView.as_view(), name='custom-report-field-reorder'),

    path('job/<uuid:job_id>/', JobCustomReportsView.as_view(), name='job-custom-reports-status'),
    path('job/<uuid:job_id>/template/<uuid:template_id>/', CustomReportTemplateDetailForEmployeeView.as_view(), name='job-custom-report-detail'),
    path('job/<uuid:job_id>/template/<uuid:template_id>/submit/', CustomReportSubmitView.as_view(), name='custom-report-submit'),

    path('submission/<uuid:submission_id>/', CustomReportSubmissionDetailView.as_view(), name='custom-report-submission-detail'),
    path('admin/job/<uuid:job_id>/submissions/', AdminJobCustomReportSubmissionsView.as_view(), name='admin-job-custom-report-submissions'),
]
