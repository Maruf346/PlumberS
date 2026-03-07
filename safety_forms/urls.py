from django.urls import path
from .views import *



urlpatterns = [
    # Utility
    path('field-types/', FieldTypeListView.as_view(), name='field-type-list'),

    # Templates — shared read
    path('', SafetyFormTemplateListView.as_view(), name='form-template-list'),
    path('<uuid:id>/', SafetyFormTemplateDetailView.as_view(), name='form-template-detail'),

    # Templates — admin write
    path('create/', AdminSafetyFormTemplateCreateView.as_view(), name='form-template-create'),
    path('<uuid:id>/update/', AdminSafetyFormTemplateUpdateView.as_view(), name='form-template-update'),

    # Fields — admin
    path('<uuid:template_id>/fields/add/', AdminFieldCreateView.as_view(), name='field-create'),
    path('<uuid:template_id>/fields/<uuid:field_id>/', AdminFieldUpdateView.as_view(), name='field-update-delete'),
    path('<uuid:template_id>/fields/reorder/', AdminFieldReorderView.as_view(), name='field-reorder'),
    
    
    # Employees safety form interactions
    ##########################################################################################
    # Employee — per job
    path('job/<uuid:job_id>/', JobSafetyFormsView.as_view(), name='job-safety-forms-status'),
    path('job/<uuid:job_id>/template/<uuid:template_id>/', SafetyFormTemplateDetailForEmployeeView.as_view(), name='job-safety-form-detail'),
    path('job/<uuid:job_id>/template/<uuid:template_id>/submit/', SafetyFormSubmitView.as_view(), name='safety-form-submit'),

    # Submission detail
    path('submission/<uuid:submission_id>/', SafetyFormSubmissionDetailView.as_view(), name='safety-form-submission-detail'),

    # Admin — all submissions for a job
    path('admin/job/<uuid:job_id>/submissions/', AdminJobSafetySubmissionsView.as_view(), name='admin-job-submissions'),
]