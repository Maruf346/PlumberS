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
    # path('me/', MyProfileView.as_view(), name='me'),
    # path('profile/<uuid:id>/', PublicProfileView.as_view(), name='profile'),
    
    # Admin user management
    # path('', include(router.urls)),
    # path('total/', TotalUsersCountView.as_view(), name='total-users'),
    # path('admin/login/', AdminLoginView.as_view(), name='admin-login'),
    path('admin/login/', AdminDashboardLoginView.as_view(), name='admin-dashboard-login'),
    path('admin/profile/', AdminProfileView.as_view(), name='admin-profile'),
    path('admin/employeelist/', UserListView.as_view(), name='admin-employee-list'),
    path('admin/managerlist/', ManagerListView.as_view(), name='admin-manager-list'),
    path('admin/managers/<uuid:id>/', AdminManagerDetailView.as_view(), name='admin-manager-detail'),
    path('admin/manager/<uuid:id>/update/', AdminUpdateManagerView.as_view(), name='admin-manager-update'),
    path('admin/manager/<uuid:id>/delete/', AdminDeleteManagerView.as_view(), name='admin-manager-delete'),
    
    # Onboarding
    path('onboarding/step1/', OnboardingStep1View.as_view(), name='onboarding-step1'),
    path('onboarding/step2/', OnboardingStep2View.as_view(), name='onboarding-step2'),
    path('me/employee-profile/', MyEmployeeProfileView.as_view(), name='my-employee-profile'),
    path('me/employee-profile/update/', MyEmployeeProfileUpdateView.as_view(), name='my-employee-profile-update'),

    # Employee self-service
    # Admin
    path('vehicle-assignments/', AdminVehicleAssignmentListView.as_view(), name='vehicle-assignments'),
    path('<uuid:user_id>/assign-vehicle/', AdminAssignVehicleView.as_view(), name='assign-vehicle'),

    # Employee
    path('my-vehicle/', EmployeeMyVehicleView.as_view(), name='my-vehicle'),
    
    # Admin user management
    path('admin/users/', AdminUserListView.as_view(), name='admin-user-list'),
    path('admin/users/<uuid:id>/', AdminUserDetailView.as_view(), name='admin-user-detail'),
    path('admin/users/<uuid:id>/block/', AdminBlockUserView.as_view(), name='admin-block-user'),
    path('admin/managers/create/', AdminCreateManagerView.as_view(), name='admin-create-manager'),
]
