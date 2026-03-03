from django.urls import path, include
from .views import *
from rest_framework.routers import DefaultRouter


router = DefaultRouter()

# router.register("approve", UserApprovalViewSet, basename='user_approval')


urlpatterns = [
        
    # OAuth2 logins
    # path('auth/google/login/', GoogleLoginRedirectView.as_view(), name='google-login'),
    # path('auth/google/callback/', GoogleOAuthCallbackView.as_view(), name='google-login-callback'),
    path('auth/google/login/', GoogleLoginMobileView.as_view(), name='google-mobile-login'),
    
    # path("auth/apple/login/", AppleLoginRedirectView.as_view(), name='apple-login'),
    # path("auth/apple/callback/", AppleOAuthCallbackView.as_view(), name='apple-login-callback'),
    path('auth/apple/login/', AppleLoginMobileView.as_view(), name='apple-mobile-login'),
    
    # Registration endpoints
    path('register/initiate/', InitiateRegistrationView.as_view(), name='register-initiate'),
    path('register/verify/', VerifyRegistrationOTPView.as_view(), name='register-verify'),
    
    # Password reset endpoints
    path('password-reset/initiate/', InitiatePasswordResetView.as_view(), name='password-reset-initiate'),
    path('password-reset/verify/', VerifyPasswordResetOTPView.as_view(), name='password-reset-verify'),
    path('password-reset/confirm/', ResetPasswordView.as_view(), name='password-reset-confirm'),
    
    # User endpoints
    path('login/', UserLoginView.as_view(), name='login'),
    path('logout/', UserLogoutView.as_view(), name='logout'),
    # path('password/change/', ChangePasswordView.as_view(), name='password-change'),
    path('me/', MyProfileView.as_view(), name='me'),
    path('profile/<uuid:id>/', PublicProfileView.as_view(), name='profile'),
    
    # Admin user management
    # path('', include(router.urls)),
    path('approve/<uuid:id>/', UserApprovalViewSet.as_view(), name='user-approval'),
    path('total/', TotalUsersCountView.as_view(), name='total-users'),
    path('admin/login/', AdminLoginView.as_view(), name='admin-login'),
    path('admin/profile/', AdminProfileView.as_view(), name='admin-profile'),
    path('admin/userlist/', UserListView.as_view(), name='admin-user-list'),
    path('stats/', UserStatsView.as_view(), name='user-stats'),
]
