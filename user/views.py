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
                full_name=serializer.validated_data['full_name'],
                email=serializer.validated_data['email'],
                password=serializer.validated_data['password']
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
@method_decorator(ratelimit(key='ip', rate='120/h', method='POST', block=True), name='dispatch')
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
@method_decorator(ratelimit(key='user', rate='120/h', method='POST', block=False), name='dispatch')
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
@method_decorator(ratelimit(key='user', rate='85/h', method='POST', block=True), name='dispatch')
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
@method_decorator(ratelimit(key='user', rate='180/h', method='GET', block=False), name='dispatch')
@method_decorator(ratelimit(key='user', rate='120/h', method=['PUT', 'PATCH'], block=True), name='dispatch')
@method_decorator(ratelimit(key='user', rate='125/d', method='DELETE', block=True), name='dispatch') 
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
@method_decorator(ratelimit(key='ip', rate='120/h', method='GET', block=False), name='dispatch')
class PublicProfileView(RetrieveAPIView):
    queryset = User.objects.all()
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'
    


#####################################################################################
##                     Google Sign-In Views and Helper Function                    ##
#####################################################################################

@extend_schema(
    summary="Google login redirect",
    description="Redirect user to Google OAuth authorization page.",
    responses={302: OpenApiResponse(description="Redirect to Google OAuth")},
)
@method_decorator(ratelimit(key='ip', rate='120/h', method='GET', block=True), name='dispatch')
class GoogleLoginRedirectView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        flow = Flow.from_client_config(
            {
                'web': {
                    'client_id': settings.GOOGLE_CLIENT_ID,
                    'client_secret': settings.GOOGLE_CLIENT_SECRET,
                    'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
                    'token_uri': 'https://oauth2.googleapis.com/token'
                }
            },
            scopes=[
                'openid',
                'email',
                'profile',
            ],
            redirect_uri=settings.GOOGLE_REDIRECT_URI
        )
        
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='select_account'
        )
        
        request.session['google_oauth_state'] = state
        return redirect(authorization_url)
    
    
@extend_schema(
    summary="Google OAuth callback",
    description="Handle Google OAuth callback and return authentication tokens.",
    responses={
        200: OpenApiResponse(description="Google login successful"),
        302: OpenApiResponse(description="Redirect to frontend"),
        400: OpenApiResponse(description="OAuth validation failed"),
    },
)
@method_decorator(ratelimit(key='ip', rate='120/h', method='GET', block=True), name='dispatch')
class GoogleOAuthCallbackView(APIView):
    permission_classes = [AllowAny]
    
    def get(self, request):
        state = request.session.get('google_oauth_state')
        
        flow = Flow.from_client_config(
            {
                'web': {
                    'client_id': settings.GOOGLE_CLIENT_ID,
                    'client_secret': settings.GOOGLE_CLIENT_SECRET,
                    'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
                    'token_uri': 'https://oauth2.googleapis.com/token'
                }
            },
            scopes = [
                'openid',
                'https://www.googleapis.com/auth/userinfo.email',
                'https://www.googleapis.com/auth/userinfo.profile'
            ],
            state=state,
            redirect_uri = settings.GOOGLE_REDIRECT_URI
        )
        
        # Extracts code from callback URL --> Sends it to Google’s token endpoint
        flow.fetch_token(authorization_response=request.build_absolute_uri())
        
        # Reuse existing serializer logic
        try:
            serializer = GoogleOAuthSerializer(
                data={'id_token': flow.credentials.id_token}
            )
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return redirect(
                f'{settings.FRONTEND_LOGIN_ERROR_URL}'
                f'?error={str(e.detail[0])}'
            )
        
        return Response(serializer.validated_data)  # comment this out when frontend is ready
    
        # Uncomment below to redirect to frontend with tokens in query params
        # return redirect(
        #     f'{settings.FRONTEND_LOGIN_SUCCESS_URL}'
        #     f'?access={serializer.validated_data['tokens']['access']}'
        #     f'refresh={serializer.validated_data['token']['refresh']}'
        #     f'is_new={serializer.validated_data['is_new_user']}'
        # )
        

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

# helper function
@method_decorator(ratelimit(key='ip', rate='120/h', method='GET', block=True), name='dispatch')
def generate_apple_client_secret():
    return jwt.encode(
        {
            'iss': settings.APPLE_TEAM_ID,          # Issuer: Identifies who is signing the token
            'iat': int(time.time()),                # Issued At (current timestamp)
            'exp': int(time.time()) + 86400 * 180,  # Expiry time(180 days); Apple allows max 6 months
            'aud': 'https://appleid.apple.com',     # Audience (Always fixed)
            'sub': settings.APPLE_CLIENT_ID         # Subject: Tells Apple which app this token is for
        },
        settings.APPLE_PRIVATE_KEY,                 # .p8 private key (Must be kept secret)
        algorithm='ES256',                          # Algo: Elliptic Curve signing
        headers={'kid': settings.APPLE_KEY_ID}
    )
    

@extend_schema(
    summary="Apple login redirect",
    description="Redirect user to Apple Sign-In authorization page.",
    responses={302: OpenApiResponse(description="Redirect to Apple OAuth")},
)
@method_decorator(ratelimit(key='ip', rate='120/h', method='GET', block=True), name='dispatch')
class AppleLoginRedirectView(APIView):
    permission_classes = [AllowAny]
    
    def get(self, request):
        params = {
            'response_type': 'code id_token',   
            'response_code': 'form_post',       # Apple sends response as POST form
            'client_id': settings.APPLE_CLIENT_ID,
            'redirect_uri': settings.APPLE_REDIRECT_URI,
            'scope': 'name email'
        }
        
        query = '&'.join(f'{k}={v}' for k, v in params.items())
        return redirect(f'https://appleid.apple.com/auth/authorize?{query}')
    
    
@extend_schema(
    summary="Apple OAuth callback",
    description="Handle Apple OAuth callback and return authentication tokens.",
    responses={
        200: OpenApiResponse(description="Apple login successful"),
        302: OpenApiResponse(description="Redirect to frontend"),
        400: OpenApiResponse(description="Apple OAuth failed"),
    },
)
@method_decorator(ratelimit(key='ip', rate='120/h', method='GET', block=True), name='dispatch')
class AppleOAuthCallbackView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request):
        id_token = request.data.get('id_token')
        user = request.data.get('user')
        
        if not id_token:
            return redirect(f'{settings.FRONTEND_LOGIN_ERROR_URL}?error=Apple login failed')
        
        try:
            serializer = AppleOAuthCallbackView(data = {'id_token': id_token, 'user': user})
            serializer.is_valid(raise_exception=True)
        except ValidationError as e:
            return redirect(
                f'{settings.FRONTEND_LOGIN_ERROR_URL}'
                f'?error=str{e.detail[0]}'
            )
        
        return Response(serializer.validated_data)

        # Uncomment below to redirect to frontend with tokens in query params
        # return redirect(
        #     f"{settings.FRONTEND_LOGIN_SUCCESS_URL}"
        #     f"?access={serializer.validated_data['tokens']['access']}"
        #     f"&refresh={serializer.validated_data['tokens']['refresh']}"
        #     f"&is_new={serializer.validated_data['is_new_user']}"
        # )


@extend_schema(
    summary="Apple mobile login",
    description="Accepts Apple ID token and returns JWT tokens.",
    responses={200: OpenApiResponse(description="Login successful")}
)
@method_decorator(ratelimit(key='ip', rate='120/h', method='POST', block=True), name='dispatch')
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
@method_decorator(ratelimit(key='ip', rate='120/h', method='POST', block=True), name='dispatch')
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
@method_decorator(ratelimit(key='user', rate='100/h', method='GET', block=False), name='dispatch')
@method_decorator(ratelimit(key='user', rate='120/h', method=['PUT', 'PATCH'], block=True), name='dispatch')
class AdminProfileView(RetrieveUpdateAPIView):
    serializer_class = AdminProfileSerializer
    permission_classes = [IsAdminUser]
    
    def get_object(self):
        return self.request.user


@extend_schema_view(
    get=extend_schema(
        tags=["admin"],
        summary="Retrieve user for approval",
        description="Retrieve a single user by ID for approval review",
        responses=UserApprovalSerializer,
    ),
    put=extend_schema(
        tags=["admin"],
        summary="Update user approval",
        description="Fully update user approval status (admin use)",
        request=UserApprovalSerializer,
        responses=UserApprovalSerializer,
    ),
    patch=extend_schema(
        tags=["admin"],
        summary="Partially update user approval",
        description="Partially update approval-related fields",
        request=UserApprovalSerializer,
        responses=UserApprovalSerializer,
    ),
    delete=extend_schema(
        tags=["admin"],
        summary="Delete user",
        description="Delete user account permanently",
        responses={204: None},
    ),
)
@method_decorator (ratelimit(key='user_or_ip', rate='300/h', method='GET', block=False), name='dispatch')
@method_decorator(ratelimit(key='user_or_ip', rate='220/h', method=['PUT', 'PATCH'], block=True), name='dispatch')
@method_decorator(ratelimit(key='user_or_ip', rate='120/h', method='DELETE', block=True), name='dispatch')
class UserApprovalViewSet(RetrieveUpdateDestroyAPIView):
    queryset = User.objects.all()
    permission_classes = [IsAdminUser]
    serializer_class = UserApprovalSerializer
    ordering_fields = ["created_at", "updated_at", "email", "full_name"]
    filterset_fields = ["is_active", "is_premium", "provider"]
    ordering = ["-created_at"]
    lookup_field = 'id'
       

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
@method_decorator(ratelimit(key='user', rate='130/h', method='GET', block=False), name='dispatch')
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
    summary="Yearly user growth statistics",
    description="Return monthly user registration statistics for a given year.",
    parameters=[
        OpenApiParameter(
            name="year",
            type=int,
            required=True,
            location=OpenApiParameter.QUERY,
            description="Year for statistics (e.g., 2025)",
        )
    ],
    responses={
        200: YearlyUserGrowthSerializer,
        400: OpenApiResponse(description="Invalid or missing year parameter"),
    },
)
@method_decorator(ratelimit(key='user', rate='180/h', method='GET', block=False), name='dispatch')
@method_decorator(cache_page(60 * 5), name='dispatch')
class UserStatsView(APIView):
    permission_classes = [IsAdminUser]
    
    def get(self, request):
        year_param = request.query_params.get('year')
        
        if not year_param:
            return Response(
                {'error': 'Year query parameter is required: .../stats/?year=2025'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        input_serializer = UserStatsInputSerializer(data={'year':year_param})
        input_serializer.is_valid(raise_exception=True)
        year = input_serializer.validated_data['year']
        
        queryset = (
            User.objects
            .filter(created_at__year=year)
            .annotate(month=ExtractMonth('created_at'))
            .values('month')
            .annotate(count=Count('id'))
            .order_by('month')
        )
        
        month_count_map = {item['month']: item['count'] for item in queryset}
        
        monthly_data = []
        total_users = 0
        
        for month_num in range(1, 13):
            count = month_count_map.get(month_num, 0)
            total_users += count
            
            monthly_data.append({
                'month': month_num,
                'month_name': calendar.month_name[month_num],
                'count': count
            })
        
        response_data = {
            'year': year,
            'total_users': total_users,
            'monthly_counts': monthly_data
        }
        
        serializer = YearlyUserGrowthSerializer(response_data)
        
        logger.info(f'Admin {request.user.email} requested registration stats for {year}')
        
        return Response(serializer.data, status=status.HTTP_200_OK)
        
        
@extend_schema(
    tags=["admin"],
    summary="Admin user list",
    description="Retrieve a list of all registered users with filtering and ordering options.",
)
@method_decorator(ratelimit(key='user', rate='180/h', method='GET', block=False), name='dispatch')
class UserListView(ListAPIView):
    queryset = User.objects.filter(is_staff=False).order_by('-created_at')
    serializer_class = UserSerializer
    permission_classes = [IsAdminUser]
    filterset_fields = ['is_active', 'is_premium', 'provider']
    ordering_fields = ['created_at', 'email', 'full_name']
    ordering = ['-created_at']