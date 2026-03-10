from rest_framework.views import APIView
from rest_framework.generics import ListAPIView, RetrieveUpdateDestroyAPIView, RetrieveAPIView, RetrieveUpdateAPIView
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAuthenticatedOrReadOnly, IsAdminUser
from django.contrib.auth import login, logout, get_user_model
from rest_framework import status
from django.db.models.functions import ExtractMonth
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.db.models import Count
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import *
from drf_spectacular.utils import OpenApiParameter, extend_schema, OpenApiResponse, extend_schema_view, inline_serializer
from rest_framework.generics import GenericAPIView
from google_auth_oauthlib.flow import Flow
from django.conf import settings
from django.shortcuts import redirect
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.shortcuts import get_object_or_404
from user.services import RegistrationService, PasswordResetService
import logging
import jwt
import time
from datetime import datetime
import calendar
from django_ratelimit.decorators import ratelimit
from notifications.services import NotificationTemplates


logger = logging.getLogger(__name__)

User = get_user_model()


# ==================== REGISTRATION VIEWS ====================

@method_decorator(ratelimit(key='ip', rate='4/m', method='POST', block=True), name='dispatch')
class InitiateRegistrationView(APIView):
    # Initiate registration by sending OTP to email
    permission_classes = [AllowAny]
    serializer_class = InitiateRegistrationSerializer
    
    @extend_schema(
        request=InitiateRegistrationSerializer,
        summary="Initiate user registration",
        description='Send OTP to email for user registration verification'
    )
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            result = RegistrationService.initiate_registration(
                email=serializer.validated_data['email'],
                password=serializer.validated_data['password'],
                username=serializer.validated_data['username'],
                birth_date=serializer.validated_data.get('birth_date'),
            )
            
            logger.info(f'Registration initiated for email: {serializer.validated_data['email']}')
            return Response(result, status=status.HTTP_200_OK)
        
        except ValueError as e:
            logger.warning(f'Registration initiation failed: {str(e)}')
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

        except Exception as e:
            logger.error(f"Unexpected error during registration initiation: {str(e)}")
            return Response(
                {'error': 'An unexpected error occurred. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
    
@method_decorator(ratelimit(key='ip', rate='5/m', method='POST', block=True), name='dispatch')
class VerifyRegistrationOTPView(APIView):
    # Verify OTP and complete user registration
    permission_classes = [AllowAny]
    serializer_class = VerifyRegistrationOTPSerializer
    
    @extend_schema(
        request=VerifyRegistrationOTPSerializer,
        summary="Verify registration OTP",
        description="Verifies the OTP sent during registration and completes user registration."
    )
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            result = RegistrationService.verify_and_complete_registration(
                email=serializer.validated_data['email'],
                otp=serializer.validated_data['otp']
            )
            
            user = result['user']
            
            response_data = {
                'message': 'Registration successful',
                'access_token': result['access_token'],
                'refresh_token': result['refresh_token'],
                'user': UserSerializer(user).data
            }
            
            logger.info(f"User registered successfully: {user.email}")
            
            # Send welcome email asynchronously
            from user.tasks import send_welcome_email
            send_welcome_email.delay(user.email, user.full_name)
            
            # Send welcome notification
            NotificationTemplates.welcome(user)
            
            # Notify admins
            NotificationTemplates.new_user_joined(user)
            
            return Response(response_data, status=status.HTTP_201_CREATED)
        
        except ValueError as e:
            logger.warning(f'OTP verification failed: {str(e)}')
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f'Unexpected error during OTP verification: {str(e)}')
            return Response(
                {'error': 'An unexpected error occurred. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    

# ==================== PASSWORD RESET VIEWS ====================

@method_decorator(ratelimit(key='ip', rate='4/m', method='POST', block=True), name='dispatch')
class InitiatePasswordResetView(APIView):
    # Initiate password reset by sending OTP to email
    permission_classes = [AllowAny]
    serializer_class = InitiatePasswordResetSerializer
    
    @extend_schema(
        request=InitiatePasswordResetSerializer,
        summary='Initiate password reset',
        description='Send OTP to email for password reset'
    )
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            result = PasswordResetService.initiate_password_reset(
                email=serializer.validated_data['email']
            )
            
            logger.info(f'Password reset initiated for email: {serializer.validated_data['email']}')
            return Response(result, status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.error(f'Unexpected error during password reset initiation: {str(e)}')
            return Response(
                {'error': 'An unexpected error occurred. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@method_decorator(ratelimit(key='ip', rate='6/m', method='POST', block=True), name='dispatch')
class VerifyPasswordResetOTPView(APIView):
    # Verify password reset OTP and get reset token
    permission_classes = [AllowAny]
    serializer_class = VerifyPasswordResetOTPSerializer
    
    @extend_schema(
        request=VerifyPasswordResetOTPSerializer,
        summary='Verify password reset OTP',
        description='Verify OTP and receive reset token for password change'
    )
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            result = PasswordResetService.verify_reset_otp(
                email=serializer.validated_data['email'],
                otp=serializer.validated_data['otp']
            )
            
            logger.info(f'Password reset OTP verified for email: {serializer.validated_data['email']}')
            return Response(result, status=status.HTTP_200_OK)
        
        except ValueError as v:
            logger.warning(f"Password reset OTP verification failed: {str(v)}")
            return Response(
                {'error': str(v)},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        except Exception as e:
            logger.error(f"Unexpected error during password reset OTP verification: {str(e)}")
            return Response(
                {'error': 'An unexpected error occurred. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@method_decorator(ratelimit(key='ip', rate='4/m', method='POST', block=True), name='dispatch')
class ResetPasswordView(APIView):
    # Reset password using reset token
    permission_classes = [AllowAny]
    serializer_class = ResetPasswordSerializer
    
    @extend_schema(
        request=ResetPasswordSerializer,
        summary='Reset password',
        description='Reset password using the reset token'
    )
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            result = PasswordResetService.reset_password(
                reset_token=serializer.validated_data['reset_token'],
                new_password=serializer.validated_data['new_password']
            )
            
            # Get user by ID from result and Send password update notification
            user_id = result.get('user_id')
            if user_id:
                try:
                    user = User.objects.get(id=user_id)
                    NotificationTemplates.password_updated(user)
                except User.DoesNotExist:
                    pass
                except Exception as e:
                    logger.error(f"Failed to send notification: {str(e)}")
            
            logger.info('Password reset successful')
            return Response(
                {'message': result['message']},
                status=status.HTTP_200_OK
            )
        
        except ValueError as e:
            logger.warning(f"Password reset failed: {str(e)}")
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Unexpected error during password reset: {str(e)}")
            return Response(
                {'error': 'An unexpected error occurred. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# ======================== USER VIEWS =========================


@extend_schema(
    summary="User login",
    description="Authenticate user and return access and refresh tokens.",
    request=UserLoginSerializer,
    # responses={
    #     200: OpenApiResponse(description="Login successful"),
    #     400: OpenApiResponse(description="Invalid credentials"),
    # },
)
class UserLoginView(APIView):
    permission_classes = [AllowAny]
    serializer_class = UserLoginSerializer
    
    def post(self, request):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        user = serializer.validated_data['user']
        # login(request, user)
        
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'message': 'Logged in successfully.',
            'user': UserProfileSerializer(user, context = {"request": request}).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token)
            }    
        },
        status = status.HTTP_200_OK
        )
        

@extend_schema(
    summary="User logout",
    description="Logout user by blacklisting refresh token and clearing session.",
    responses={205: OpenApiResponse(description="Logged out successfully")}
)
class UserLogoutView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = None
    
    def post(self, request):
        # logout(request)
        
        try:
            refresh_token = request.data.get('refresh')
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
                
            logout(request)
        
            return Response(
                {'message': 'Successfully logged out.'},
                status=status.HTTP_205_RESET_CONTENT
            )
        except Exception as e:
            return Response(
                {
                    'error': str(e)
                },
                status=status.HTTP_400_BAD_REQUEST
            )
            

@extend_schema(
    summary="Change password",
    description="Change password for authenticated user.",
    request=ChangePasswordSerializer
)
class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ChangePasswordSerializer
    
    def post(self, request):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        # Change pass
        user = request.user
        user.set_password(serializer.validated_data['new_password'])
        user.save()
        
        logger.info(f'Password changed successfully for user: {user.email}')
        
        # Send password update notification
        NotificationTemplates.password_changed(user)
        
        return Response(
            {'message': 'Password changed successfully!'},
            status=status.HTTP_200_OK
        )

           
@extend_schema_view(
    get=extend_schema(
        summary="Retrieve my profile",
        description="Retrieve currently authenticated user's profile.",
        responses=UserProfileSerializer,
    ),
    put=extend_schema(
        summary="Update my profile",
        description="Fully update your profile.",
        request=UserProfileSerializer,
        responses=UserProfileSerializer,
    ),
    patch=extend_schema(
        summary="Partially update my profile",
        description="Partially update your profile fields.",
        request=UserProfileSerializer,
        responses=UserProfileSerializer,
    ),
    delete=extend_schema(
        summary="Delete my account",
        description="Delete currently authenticated user's account.",
        responses={204: OpenApiResponse(description="Account deleted")},
    ),
)
class MyProfileView(RetrieveUpdateDestroyAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]
    
    def get_object(self):
        return self.request.user
    

# Maybe not needed. Can be used to view other users' profiles if needed.  
@extend_schema(
    summary="Retrieve public user profile",
    description="Retrieve public profile information of a user by ID.",
    responses=UserProfileSerializer,
)  
class PublicProfileView(RetrieveAPIView):
    queryset = User.objects.all()
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'
    


#####################################################################################
##                     Google Sign-In Views and Helper Function                    ##
#####################################################################################


class GoogleLoginMobileView(APIView):
    permission_classes = [AllowAny]
    serializer_class = GoogleOAuthSerializer
    
    @extend_schema(
        summary="Google OAuth Mobile Login",
        description="Handle Google OAuth mobile login and return authentication tokens.",
        responses={
            200: OpenApiResponse(description="Google login successful"),
            400: OpenApiResponse(description="OAuth validation failed"),
        },
    )
    @method_decorator(ratelimit(key='ip', rate="120/h", method="POST", block=True))
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)


#####################################################################################
##                     Apple Sign-In Views and Helper Function                     ##
#####################################################################################



@extend_schema(
    summary="Apple mobile login",
    description="Accepts Apple ID token and returns JWT tokens.",
    responses={200: OpenApiResponse(description="Login successful")}
)
class AppleLoginMobileView(APIView):
    permission_classes = [AllowAny]
    serializer_class = AppleOAuthSerializer
    
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)


#####################################################################################
##                                Admin Dashboard Views                            ##
#####################################################################################

@extend_schema(
    tags=["admin"],
    summary="Admin login",
    description="Authenticate admin user and return JWT tokens.",
    request=AdminLoginSerializer
)
class AdminLoginView(APIView):
    permission_classes = [AllowAny]
    serializer_class = AdminLoginSerializer
    
    def post(self, request):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        user = serializer.validated_data['user']
        # login(request, user)
        
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'message': 'Admin logged in successfully.',
            'user': UserProfileSerializer(user, context={"request": request}).data,
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token)
            }
        },
        status=status.HTTP_200_OK
        )


@extend_schema(
    tags=['admin'],
    summary="Admin / Manager dashboard login",
    description="Unified login for admin and manager roles. Returns JWT tokens and user role.",
    request=AdminDashboardLoginSerializer,
)
class AdminDashboardLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = AdminDashboardLoginSerializer(
            data=request.data,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']

        refresh = RefreshToken.for_user(user)

        return Response({
            'message': f'Welcome back, {user.full_name}.',
            'user': {
                'id': str(user.id),
                'full_name': user.full_name,
                'email': user.email,
                'phone': str(user.phone) if user.phone else None,
                'profile_picture': request.build_absolute_uri(user.profile_picture.url)
                                   if user.profile_picture else None,
                'role': user.role,  # 'admin' or 'manager' from your User.role property
            },
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        }, status=status.HTTP_200_OK)


@extend_schema_view(
    get=extend_schema(
        tags=["admin"],
        summary="Retrieve admin profile",
        description="Retrieve currently authenticated admin profile.",
        responses=AdminProfileSerializer,
    ),
    put=extend_schema(
        tags=["admin"],
        summary="Update admin profile",
        description="Fully update admin profile.",
        request=AdminProfileSerializer,
        responses=AdminProfileSerializer,
    ),
    patch=extend_schema(
        tags=["admin"],
        summary="Partially update admin profile",
        description="Partially update admin profile fields.",
        request=AdminProfileSerializer,
        responses=AdminProfileSerializer,
    ),
)
class AdminProfileView(RetrieveUpdateAPIView):
    serializer_class = AdminProfileSerializer
    permission_classes = [IsAdminUser]
    
    def get_object(self):
        return self.request.user

@extend_schema(
    tags=["admin"],
    summary="Total users count",
    description="Return total number of registered users.",
    responses={
        200: inline_serializer(
            name="TotalUsersCountResponse",
            fields={
                "total_users": serializers.IntegerField()
            }
        )
    },
)
class TotalUsersCountView(APIView):
    permission_classes = [IsAdminUser]
    
    def get(self, request):
        total_users = User.objects.filter(is_staff=False).count()
        return Response(
            {'total_users': total_users}, 
            status=status.HTTP_200_OK
        )

        
@extend_schema(
    tags=["admin"],
    summary="Admin user list",
    description="Retrieve a list of all registered users with filtering and ordering options.",
)
class UserListView(ListAPIView):
    queryset = User.objects.filter(is_staff=False).order_by('-created_at')
    serializer_class = UserSerializer
    permission_classes = [IsAdminUser]
    filterset_fields = ['is_active', 'provider']
    ordering_fields = ['created_at', 'email', 'full_name']
    ordering = ['-created_at']
    

@extend_schema(
    tags=["Manager"],
    summary="Admin manager list",
    description="Retrieve a list of all registered managers with filtering and ordering options.",
)
class ManagerListView(ListAPIView):
    queryset = User.objects.filter(is_staff=True, is_superuser=False).order_by('-created_at')
    serializer_class = UserSerializer
    permission_classes = [IsAdminUser]
    filterset_fields = ['is_active', 'provider']
    ordering_fields = ['created_at', 'email', 'full_name']
    ordering = ['-created_at']


class AdminManagerDetailView(RetrieveAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = ManagerDetailSerializer
    lookup_field = 'id'

    def get_queryset(self):
        return User.objects.filter(
            is_staff=True,
            is_superuser=False
        ).select_related('manager_profile')

    @extend_schema(
        tags=['Manager'],
        summary="Manager detail",
        description="Retrieve full manager profile including assigned jobs and staff count."
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


# ==================== ONBOARDING VIEWS ====================

class OnboardingStep1View(APIView):
    """
    Employee fills personal/professional details after registration.
    Requires auth. Creates or updates EmployeeProfile step 1.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = OnboardingStep1Serializer

    @extend_schema(
        summary="Onboarding Step 1",
        description="Submit personal and professional details during onboarding."
    )
    def patch(self, request):
        if not request.user.is_employee:
            return Response(
                {'error': 'Only employees go through onboarding.'},
                status=status.HTTP_403_FORBIDDEN
            )
        try:
            profile = request.user.employee_profile
        except EmployeeProfile.DoesNotExist:
            profile = EmployeeProfile.objects.create(user=request.user)

        serializer = self.serializer_class(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {'message': 'Step 1 complete.', 'data': serializer.data},
            status=status.HTTP_200_OK
        )


class OnboardingStep2View(APIView):
    # Employee fills work & safety profile (step 2). Marks onboarding complete.

    permission_classes = [IsAuthenticated]
    serializer_class = OnboardingStep2Serializer

    @extend_schema(
        summary="Onboarding Step 2",
        description="Submit work and safety details. Marks onboarding as complete."
    )
    def patch(self, request):
        if not request.user.is_employee:
            return Response(
                {'error': 'Only employees go through onboarding.'},
                status=status.HTTP_403_FORBIDDEN
            )
        try:
            profile = request.user.employee_profile
        except EmployeeProfile.DoesNotExist:
            return Response(
                {'error': 'Please complete step 1 first.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = self.serializer_class(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {'message': 'Onboarding complete.', 'data': serializer.data},
            status=status.HTTP_200_OK
        )


@extend_schema_view(
    get=extend_schema(
        summary="My Employee Profile",
        description="Retrieve full employee profile information for the authenticated employee.",
        responses={200: EmployeeProfileSerializer},
    )
)
class MyEmployeeProfileView(RetrieveAPIView):
    # Authenticated employee views their full profile.
    permission_classes = [IsAuthenticated]
    serializer_class = EmployeeProfileSerializer

    def get_object(self):
        try:
            return self.request.user.employee_profile
        except EmployeeProfile.DoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound('Employee profile not found. Please complete onboarding.')


class MyEmployeeProfileUpdateView(APIView):
    """
    PATCH — employee updates their own profile fields.
    DELETE — employee deletes their own account.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = EmployeeProfileUpdateSerializer

    def get_object(self, request):
        try:
            return request.user.employee_profile
        except EmployeeProfile.DoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound('Employee profile not found. Please complete onboarding first.')

    @extend_schema(
        summary="Update my employee profile",
        description="Employee updates their own profile picture, name, phone, profession, or employee ID.",
        request=EmployeeProfileUpdateSerializer,
        responses={200: EmployeeProfileSerializer}
    )
    def patch(self, request):
        if not request.user.is_employee:
            return Response(
                {'error': 'Only employees can access this endpoint.'},
                status=status.HTTP_403_FORBIDDEN
            )
        profile = self.get_object(request)
        serializer = self.serializer_class(
            profile,
            data=request.data,
            partial=True,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {
                'message': 'Profile updated successfully.',
                'data': EmployeeProfileSerializer(profile, context={'request': request}).data
            },
            status=status.HTTP_200_OK
        )

    @extend_schema(
        summary="Delete my account",
        description="Employee permanently deletes their own account.",
        responses={204: None}
    )
    def delete(self, request):
        user = request.user
        user.delete()
        return Response(
            {'message': 'Account deleted successfully.'},
            status=status.HTTP_204_NO_CONTENT
        )


# ==================== ADMIN USER MANAGEMENT VIEWS ====================

class AdminCreateManagerView(APIView):
    # Admin creates a manager account directly.
    permission_classes = [IsAdminUser]
    serializer_class = AdminCreateManagerSerializer

    @extend_schema(
        tags=['Manager'],
        summary="Create manager account",
        description="Admin creates a new manager user with profile."
    )
    def post(self, request):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {
                'message': 'Manager account created successfully.',
                'user': UserProfileSerializer(user, context={'request': request}).data
            },
            status=status.HTTP_201_CREATED
        )


class AdminUpdateManagerView(APIView):
    permission_classes = [IsAdminUser]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @extend_schema(
        tags=['Manager'],
        summary="Update manager profile",
        description="Admin updates a manager's name, phone, or profile picture.",
        request=AdminUpdateManagerSerializer,
        responses={200: AdminUpdateManagerSerializer},
    )
    def patch(self, request, id):
        manager = get_object_or_404(
            User,
            id=id,
            is_staff=True,
            is_superuser=False
        )
        serializer = AdminUpdateManagerSerializer(
            manager,
            data=request.data,
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({
            'message': 'Manager updated successfully.',
            'data': ManagerDetailSerializer(manager, context={'request': request}).data
        }, status=status.HTTP_200_OK)

    @extend_schema(
        tags=['Manager'],
        summary="Replace manager profile",
        description="Admin fully replaces a manager's name, phone, and profile picture.",
        request=AdminUpdateManagerSerializer,
        responses={200: AdminUpdateManagerSerializer},
    )
    def put(self, request, id):
        manager = get_object_or_404(
            User,
            id=id,
            is_staff=True,
            is_superuser=False
        )
        serializer = AdminUpdateManagerSerializer(
            manager,
            data=request.data,
            partial=False
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({
            'message': 'Manager updated successfully.',
            'data': ManagerDetailSerializer(manager, context={'request': request}).data
        }, status=status.HTTP_200_OK)


class AdminUserDetailView(RetrieveUpdateDestroyAPIView):
    """
    Admin views, updates, or deletes any user.
    PATCH is_active=False to block a user.
    """
    permission_classes = [IsAdminUser]
    serializer_class = AdminEmployeeListSerializer
    queryset = User.objects.all()
    lookup_field = 'id'

    @extend_schema(tags=['admin'], summary="Get user detail")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(tags=['admin'], summary="Update user details")
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)
    
    @extend_schema(tags=['admin'], summary="Block/update user")
    def patch(self, request, *args, **kwargs):
        return super().patch(request, *args, **kwargs)

    @extend_schema(tags=['admin'], summary="Delete user")
    def delete(self, request, *args, **kwargs):
        return super().delete(request, *args, **kwargs)


class AdminBlockUserView(APIView):
    # Dedicated endpoint to toggle user active status (block/unblock).
    permission_classes = [IsAdminUser]

    @extend_schema(
        tags=['admin'],
        summary="Block or unblock a user",
        responses={200: inline_serializer(
            name='BlockUserResponse',
            fields={'message': serializers.CharField(), 'is_active': serializers.BooleanField()}
        )}
    )
    def post(self, request, id):
        try:
            user = User.objects.get(id=id)
        except User.DoesNotExist:
            return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

        if user.is_superuser:
            return Response({'error': 'Cannot block an admin.'}, status=status.HTTP_403_FORBIDDEN)

        user.is_active = not user.is_active
        user.save()
        state = 'unblocked' if user.is_active else 'blocked'
        return Response(
            {'message': f'User {state} successfully.', 'is_active': user.is_active},
            status=status.HTTP_200_OK
        )


@extend_schema(
    tags=['admin'],
    summary="Admin user list with filtering and ordering",
    description="Retrieve a list of all users with options to filter by active status and provider, and order by creation date, email, or full name."
)
class AdminUserListView(ListAPIView):
    # Admin lists all users (employees + managers).
    permission_classes = [IsAdminUser]
    serializer_class = AdminEmployeeListSerializer
    filterset_fields = ['is_active', 'is_staff', 'provider']
    ordering_fields = ['created_at', 'email', 'full_name']
    ordering = ['-created_at']

    def get_queryset(self):
        return User.objects.exclude(is_superuser=True).order_by('-created_at')