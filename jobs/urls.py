from django.urls import path
from .views import *

urlpatterns = [
    # ── Dashboard ────────────────────────────────────────────────────────────
    path('dashboard/', JobDashboardView.as_view(), name='job-dashboard'),

    # ── Admin CRUD ───────────────────────────────────────────────────────────
    path('', AdminJobListView.as_view(), name='admin-job-list'),
    path('create/', AdminJobCreateView.as_view(), name='job-create'),
    path('<uuid:id>/', AdminJobDetailView.as_view(), name='admin-job-detail'),
    path('<uuid:id>/update/', AdminJobUpdateView.as_view(), name='job-update-delete'),
    path('<uuid:id>/schedule/', JobScheduleView.as_view(), name='job-schedule'),

    # ── Employee views ───────────────────────────────────────────────────────
    path('my/', EmployeeJobListView.as_view(), name='employee-job-list'),
    path('my/<uuid:id>/', EmployeeJobDetailView.as_view(), name='employee-job-detail'),
    path('<uuid:id>/status/', JobStatusUpdateView.as_view(), name='job-status-update'),

    # ── Attachments ──────────────────────────────────────────────────────────
    path('<uuid:id>/attachments/', JobAttachmentUploadView.as_view(), name='job-attachment-upload'),
    path('<uuid:id>/attachments/<uuid:attachment_id>/', JobAttachmentDeleteView.as_view(), name='job-attachment-delete'),

    # ── Photos — commented out (photos now submitted via reports app) ────────
    # path('<uuid:id>/photos/', JobPhotoUploadView.as_view(), name='job-photo-upload'),
    # path('<uuid:id>/photos/<uuid:photo_id>/', JobPhotoDeleteView.as_view(), name='job-photo-delete'),

    # ── Line items ───────────────────────────────────────────────────────────
    path('<uuid:id>/line-items/', JobLineItemView.as_view(), name='job-line-item'),
    path('<uuid:id>/line-items/<uuid:item_id>/', JobLineItemDetailView.as_view(), name='job-line-item-detail'),

    # ── Tasks — commented out (feature deferred) ─────────────────────────────
    # path('<uuid:id>/tasks/', JobTaskView.as_view(), name='job-task'),
    # path('<uuid:id>/tasks/<uuid:task_id>/complete/', JobTaskCompleteView.as_view(), name='job-task-complete'),

    # ── Notes / ticket thread ─────────────
    path('<uuid:id>/notes/', JobNoteListView.as_view(), name='job-note-list'),
    path('<uuid:id>/notes/send/', JobNoteSendView.as_view(), name='job-note-send'),
    path('<uuid:id>/notes/<uuid:note_id>/', JobNoteDeleteView.as_view(), name='job-note-delete'),

    # ── Activity timeline ─────────────────────────────────────────────────────
    path('<uuid:id>/activity/', JobActivityListView.as_view(), name='job-activity'),
    path('activities/recent/', RecentActivityView.as_view(), name='job-activity-recent'),

    # ── Mobile / Employee UI endpoints ───────────────────────────────────────
    path('employee/my-vehicles/', EmployeeVehicleListView.as_view(), name='employee-my-vehicles'),
    path('employee/my-jobs/', EmployeeMyJobsView.as_view(), name='employee-my-jobs'),
    path('employee/calendar/', EmployeeCalendarJobsView.as_view(), name='employee-calendar-jobs'),
    path('employee/<uuid:id>/', EmployeeJobDetailByIdView.as_view(), name='employee-job-detail-by-id'),
    path('employee/<uuid:id>/start/', EmployeeStartJobView.as_view(), name='employee-job-start'),
    path('employee/<uuid:id>/complete/', EmployeeCompleteJobView.as_view(), name='employee-job-complete'),
    path('employee/<uuid:id>/attachments/<uuid:attachment_id>/download/', EmployeeJobAttachmentDownloadView.as_view(), name='employee-attachment-download'),
]