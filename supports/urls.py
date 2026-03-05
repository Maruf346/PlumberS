from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import *



router = DefaultRouter()
# router.register(r'contact', ListContactSupportViewSet, basename='contact-list')
router.register(r'faqs', ListFAQViewSet, basename='faq-list')
router.register(r'faq/manage', FAQViewSet, basename='faq-manage')


urlpatterns = [
    path('', include(router.urls)),
    
    # Contact Support
    # path('contactus/create/', CreateContactSupportView.as_view(), name='contact-create'),
    
    # About Us
    # path('about-us/', AboutUsPublicView.as_view(), name='about-us-public'),
    # path('admin/about-us/', AboutUsAdminUpdateView.as_view(), name='about-us-admin'),
    
    # Terms and Conditions
    path('terms/', TermsAndConditionsPublicView.as_view(), name='terms-public'),
    path('admin/terms/', TermsAndConditionsAdminUpdateView.as_view(), name='terms-admin'),
    
    # Privacy Policy
    path('privacy/', PrivacyPolicyPublicView.as_view(), name='privacy-public'),
    path('admin/privacy/', PrivacyPolicyAdminUpdateView.as_view(), name='privacy-admin'),
    
    # Feedback
    path('feedback/submit/', FeedbackSubmitView.as_view(), name='feedback-submit'),
    path('feedback/', AdminFeedbackListView.as_view(), name='feedback-list'),
    path('feedback/<uuid:id>/', AdminFeedbackDetailView.as_view(), name='feedback-detail'),
    path('feedback/<uuid:id>/delete/', AdminFeedbackDeleteView.as_view(), name='feedback-delete'),

    # Issue reports
    path('issues/submit/', IssueReportSubmitView.as_view(), name='issue-submit'),
    path('issues/', AdminIssueReportListView.as_view(), name='issue-list'),
    path('issues/<uuid:id>/', AdminIssueReportDetailView.as_view(), name='issue-detail'),
    path('issues/<uuid:id>/delete/', AdminIssueReportDeleteView.as_view(), name='issue-delete'),
]
