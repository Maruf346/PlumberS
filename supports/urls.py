from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import *



router = DefaultRouter()
router.register(r'contact', ListContactSupportViewSet, basename='contact-list')
router.register(r'faqs', ListFAQViewSet, basename='faq-list')
router.register(r'faq/manage', FAQViewSet, basename='faq-manage')


urlpatterns = [
    path('', include(router.urls)),
    
    # Contact Support
    path('contactus/create/', CreateContactSupportView.as_view(), name='contact-create'),
    
    # About Us
    path('about-us/', AboutUsPublicView.as_view(), name='about-us-public'),
    path('admin/about-us/', AboutUsAdminUpdateView.as_view(), name='about-us-admin'),
    
    # Terms and Conditions
    path('terms/', TermsAndConditionsPublicView.as_view(), name='terms-public'),
    path('admin/terms/', TermsAndConditionsAdminUpdateView.as_view(), name='terms-admin'),
    
    # Privacy Policy
    path('privacy/', PrivacyPolicyPublicView.as_view(), name='privacy-public'),
    path('admin/privacy/', PrivacyPolicyAdminUpdateView.as_view(), name='privacy-admin'),
]
