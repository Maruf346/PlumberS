from django.shortcuts import render
from rest_framework import viewsets, views
from rest_framework.permissions import IsAdminUser, IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.generics import UpdateAPIView, RetrieveAPIView, ListAPIView
from rest_framework import status
from drf_spectacular.utils import extend_schema, extend_schema_view
from .serializers import *
from .models import *
import logging
from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator
from notifications.services import NotificationTemplates

from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.shortcuts import get_object_or_404

from user.permissions import IsAdmin, IsAdminOrManager, IsAdminOrManagerOrEmployee



logger = logging.getLogger(__name__)



# For admin
@extend_schema_view(
    list=extend_schema(
        # tags=['admin'],
        summary="List all support requests",
        description="Admin can retrieve a list of all support tickets submitted by users. "
                    "Supports filtering by user or email, searching by email/username, "
                    "and ordering by creation date."
    ),
    retrieve=extend_schema(
        # tags=['admin'],
        summary="Get a specific support request",
        description="Retrieve the details of a specific support ticket by its ID. "
                    "Admin only."
    )
)
@method_decorator(ratelimit(key='user_or_ip', rate='150/h', method='GET', block=False), name='dispatch')
class ListContactSupportViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAdminUser]
    queryset = ContactSupport.objects.all()
    serializer_class = ListContactSupportSerializer
    filterset_fields = ['user', 'email']
    ordering_fields = ['user', 'email', 'created_at']
    search_fields = ['email', 'user__email', 'user__full_name']
    ordering = ['-created_at']
    
    
@extend_schema(
    summary="Create a support request",
    description="Authenticated users can submit a support request. "
                "A notification is sent to the admin upon creation."
)
# @method_decorator(ratelimit(key='user_or_ip', rate='55/h', method='POST', block=True), name='dispatch')
class CreateContactSupportView(views.APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CreateContactSupportSerializer
    
    def post(self, request):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        # serializer.validated_data['user'] = request.user
        support_ticket = serializer.save()
        
        logger.info(
            f"Support request created: {support_ticket.subject} "
            f"by {request.user.email}"
        )
        
        # Send notification to admin
        NotificationTemplates.support_request_received(support_ticket)
        
        return Response(
            {'message': 'Support request sent successfully. We will contact you via email soon!'},
            status=status.HTTP_201_CREATED
        )        
        
      
@extend_schema_view(
    list=extend_schema(
        summary="List FAQs",
        description="Retrieve a list of frequently asked questions. "
                    "Supports searching by question/answer and ordering by creation or update date."
    ),
    retrieve=extend_schema(
        summary="Get a specific FAQ",
        description="Retrieve the details of a specific FAQ entry by its ID. "
                    "Authenticated users can view."
    )
)
@method_decorator(ratelimit(key='ip', rate='200/h', method='GET', block=False), name='dispatch')
class ListFAQViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [IsAuthenticated]
    queryset = FAQ.objects.all()
    serializer_class = FAQListSerializer
    ordering_fields = ['created_at', 'updated_at']
    search_fields = ['question', 'answer']
    ordering = ['-created_at']
    
    
@extend_schema_view(
    list=extend_schema(
        # tags=['admin'],
        summary="List FAQs (Admin)",
        description="Admin view to list all FAQs."
    ),
    retrieve=extend_schema(
        # tags=['admin'],
        summary="Retrieve FAQ",
        description="Retrieve details of a specific FAQ."
    ),
    create=extend_schema(
        # tags=['admin'],
        summary="Create FAQ",
        description="Admin can create a new FAQ."
    ),
    update=extend_schema(
        # tags=['admin'],
        summary="Update FAQ",
        description="Admin can fully update an existing FAQ."
    ),
    partial_update=extend_schema(
        # tags=['admin'],
        summary="Partially update FAQ",
        description="Admin can partially update an existing FAQ."
    ),
    destroy=extend_schema(
        # tags=['admin'],
        summary="Delete FAQ",
        description="Admin can delete an FAQ."
    ),
)
@method_decorator(ratelimit(key='user', rate='15/m', method='GET', block=False), name='dispatch')
@method_decorator(ratelimit(key='user', rate='20/m', method='POST', block=True), name='dispatch')
@method_decorator(ratelimit(key='user', rate='20/m', method=['PUT', 'PATCH'], block=True), name='dispatch')
@method_decorator(ratelimit(key='user', rate='10/m', method='DELETE', block=True), name='dispatch')
class FAQViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAdminUser]
    queryset = FAQ.objects.all()
    serializer_class = FAQSerializer
    ordering_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
    

@extend_schema(
    summary="Get About Us content",
    description="Retrieve the About Us information for public or authenticated users."
)
@method_decorator(ratelimit(key='ip', rate='200/h', method='GET', block=False), name='dispatch')
class AboutUsPublicView(RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AboutUsSerializer
    
    def get_object(self):
        return AboutUs.objects.first()
    

@extend_schema(
    # tags=['admin'],
    summary="Update About Us",
    description="Admin can update the About Us content. Only PATCH requests are allowed."
)
@method_decorator(ratelimit(key='user', rate='80/h', method=['PUT', 'PATCH'], block=True), name='dispatch')
class AboutUsAdminUpdateView(UpdateAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = AboutUsSerializer
    http_method_names = ['patch']
    
    def get_object(self):
        return AboutUs.objects.first()
    
    def perform_update(self, serializer):
        serializer.save()
        logger.info('About Us updated')
        
        
@extend_schema(
    summary="Get Terms and Conditions",
    description="Retrieve the Terms and Conditions content for public or authenticated users."
)
@method_decorator(ratelimit(key='ip', rate='200/h', method='GET', block=False), name='dispatch')
class TermsAndConditionsPublicView(RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = TermsAndConditionsSerializer
    
    def get_object(self):
        return TermsAndConditions.objects.first()


@extend_schema(
    # tags=['admin'],
    summary="Update Terms and Conditions",
    description="Admin can update the Terms and Conditions content. Only PATCH requests are allowed."
)
@method_decorator(ratelimit(key='user', rate='110/h', method=['PUT', 'PATCH'], block=True), name='dispatch')
class TermsAndConditionsAdminUpdateView(UpdateAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = TermsAndConditionsSerializer
    
    http_method_names = ['patch']
    
    def get_object(self):
        return TermsAndConditions.objects.first()
    
    def perform_update(self, serializer):
        serializer.save()
        logger.info('Terms and Conditions updated')


@extend_schema(
    summary="Get Privacy Policy",
    description="Retrieve the Privacy Policy content for public or authenticated users."
)
@method_decorator(ratelimit(key='ip', rate='200/h', method='GET', block=False), name='dispatch')
class PrivacyPolicyPublicView(RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PrivacyPolicySerializer
    
    def get_object(self):
        return PrivacyPolicy.objects.first()
        
    
@extend_schema(
    # tags=['admin'],
    summary="Update Privacy Policy",
    description="Admin can update the Privacy Policy content. Only PATCH requests are allowed."
)
@method_decorator(ratelimit(key='user', rate='110/h', method=['PUT', 'PATCH'], block=True), name='dispatch')
class PrivacyPolicyAdminUpdateView(UpdateAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = PrivacyPolicySerializer
    http_method_names = ['patch']
    
    def get_object(self):
        return PrivacyPolicy.objects.first()
    
    def perform_update(self, serializer):
        serializer.save()
        logger.info('Privacy Policy updated')
        

# ==================== FEEDBACK ====================

class FeedbackSubmitView(APIView):
    """Any authenticated staff member submits feedback."""
    permission_classes = [IsAdminOrManagerOrEmployee]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    @extend_schema(
        summary="Submit feedback",
        request=FeedbackSubmitSerializer,
        responses={201: FeedbackSubmitSerializer}
    )
    def post(self, request):
        serializer = FeedbackSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        feedback = serializer.save(user=request.user)

        try:
            from notifications.services import NotificationTemplates
            NotificationTemplates.support_feedback_received(feedback) # Notify admin about new feedback
        except Exception:
            pass

        return Response(
            {'message': 'Feedback submitted successfully.', 'data': serializer.data},
            status=status.HTTP_201_CREATED
        )


class AdminFeedbackListView(ListAPIView):
    """Admin/manager lists all submitted feedback."""
    permission_classes = [IsAdminOrManager]
    serializer_class = FeedbackListSerializer
    ordering_fields = ['created_at']
    ordering = ['-created_at']

    def get_queryset(self):
        return Feedback.objects.select_related('user').all()

    @extend_schema(summary="List all feedback (admin)")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class AdminFeedbackDetailView(RetrieveAPIView):
    """Admin/manager retrieves a single feedback entry."""
    permission_classes = [IsAdminOrManager]
    serializer_class = FeedbackDetailSerializer
    lookup_field = 'id'

    def get_queryset(self):
        return Feedback.objects.select_related('user').all()

    @extend_schema(summary="Retrieve feedback detail (admin)")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class AdminFeedbackDeleteView(APIView):
    """Admin deletes a feedback entry."""
    permission_classes = [IsAdmin]

    @extend_schema(summary="Delete feedback (admin)", responses={204: None})
    def delete(self, request, id):
        feedback = get_object_or_404(Feedback, id=id)
        feedback.delete()
        return Response({'message': 'Feedback deleted.'}, status=status.HTTP_204_NO_CONTENT)


# ==================== ISSUE REPORT ====================

class IssueReportSubmitView(APIView):
    """Any authenticated staff member submits an issue report."""
    permission_classes = [IsAdminOrManagerOrEmployee]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @extend_schema(
        summary="Submit issue report",
        request=IssueReportSubmitSerializer,
        responses={201: IssueReportSubmitSerializer}
    )
    def post(self, request):
        serializer = IssueReportSubmitSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        report = serializer.save(user=request.user)

        try:
            from notifications.services import NotificationTemplates
            NotificationTemplates.issue_report_received(report)  # Notify admin about new issue report
        except Exception:
            pass

        return Response(
            {'message': 'Issue report submitted successfully.', 'data': serializer.data},
            status=status.HTTP_201_CREATED
        )


class AdminIssueReportListView(ListAPIView):
    """Admin/manager lists all submitted issue reports."""
    permission_classes = [IsAdminOrManager]
    serializer_class = IssueReportListSerializer
    ordering_fields = ['created_at']
    ordering = ['-created_at']

    def get_queryset(self):
        return IssueReport.objects.select_related('user').all()

    @extend_schema(summary="List all issue reports (admin)")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class AdminIssueReportDetailView(RetrieveAPIView):
    """Admin/manager retrieves a single issue report."""
    permission_classes = [IsAdminOrManager]
    serializer_class = IssueReportDetailSerializer
    lookup_field = 'id'

    def get_queryset(self):
        return IssueReport.objects.select_related('user').all()

    @extend_schema(summary="Retrieve issue report detail (admin)")
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class AdminIssueReportDeleteView(APIView):
    """Admin deletes an issue report."""
    permission_classes = [IsAdmin]

    @extend_schema(summary="Delete issue report (admin)", responses={204: None})
    def delete(self, request, id):
        report = get_object_or_404(IssueReport, id=id)
        report.delete()
        return Response({'message': 'Issue report deleted.'}, status=status.HTTP_204_NO_CONTENT)