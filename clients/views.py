from rest_framework.views import APIView
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework import status
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter

from .models import Client
from .serializers import ClientSerializer, ClientListSerializer, ClientDetailSerializer
from user.permissions import IsAdmin, IsAdminOrReadOnly, IsAdminOrManagerOrEmployee


# ==================== ADMIN VIEWS ====================

class ClientCreateView(APIView):
    """Admin creates a new client."""
    permission_classes = [IsAdmin]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    serializer_class = ClientSerializer

    @extend_schema(
        tags=['clients'],
        summary="Create client",
        description="Admin only. Add a new client to the system.",
        request=ClientSerializer,
        responses={201: ClientSerializer}
    )
    def post(self, request):
        serializer = ClientSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {'message': 'Client created successfully.', 'data': serializer.data},
            status=status.HTTP_201_CREATED
        )


class ClientUpdateView(APIView):
    # Admin updates or deletes a client.
    permission_classes = [IsAdmin]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    serializer_class = ClientSerializer

    def get_object(self, id):
        return get_object_or_404(Client, id=id)

    @extend_schema(
        tags=['clients'],
        summary="Update client",
        description="Admin only. Fully update a client record.",
        request=ClientSerializer,
        responses={200: ClientSerializer}
    )
    def put(self, request, id):
        client = self.get_object(id)
        serializer = ClientSerializer(client, data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {'message': 'Client updated.', 'data': serializer.data},
            status=status.HTTP_200_OK
        )

    @extend_schema(
        tags=['clients'],
        summary="Partially update client",
        description="Admin only. Partially update a client record.",
        request=ClientSerializer,
        responses={200: ClientSerializer}
    )
    def patch(self, request, id):
        client = self.get_object(id)
        serializer = ClientSerializer(
            client, data=request.data, partial=True, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {'message': 'Client updated.', 'data': serializer.data},
            status=status.HTTP_200_OK
        )

    @extend_schema(
        tags=['clients'],
        summary="Delete client",
        description="Admin only. Permanently delete a client.",
        responses={204: None}
    )
    def delete(self, request, id):
        client = self.get_object(id)
        client.delete()
        return Response(
            {'message': 'Client deleted.'},
            status=status.HTTP_204_NO_CONTENT
        )


class AdminClientListView(ListAPIView):
    """
    Admin sees all clients including inactive ones.
    Supports filtering by is_active.
    """
    permission_classes = [IsAdmin]
    serializer_class = ClientListSerializer
    filterset_fields = ['is_active']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']
    search_fields = ['name', 'email']

    def get_queryset(self):
        return Client.objects.all()

    @extend_schema(
        tags=['clients'],
        summary="Admin — list all clients",
        description="Admin only. Returns all clients including inactive."
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


# ==================== SHARED VIEWS (all authenticated staff) ====================

class ClientListView(ListAPIView):
    """
    All authenticated users (employee, manager, admin) can list active clients.
    Returns lightweight list serializer — no site_access.
    """
    permission_classes = [IsAdminOrManagerOrEmployee]
    serializer_class = ClientListSerializer
    filterset_fields = ['is_active']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']

    def get_queryset(self):
        return Client.objects.filter(is_active=True)

    @extend_schema(
        tags=['clients'],
        summary="List active clients",
        description="Any authenticated staff member can list active clients."
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class ClientDetailView(RetrieveAPIView):
    """
    Any authenticated staff member can retrieve full client details
    including site_access (needed when going to a job site).
    """
    permission_classes = [IsAdminOrManagerOrEmployee]
    serializer_class = ClientDetailSerializer
    lookup_field = 'id'

    def get_queryset(self):
        # Employees only see active clients; admin sees all
        if self.request.user.is_superuser:
            return Client.objects.all()
        return Client.objects.filter(is_active=True)

    @extend_schema(
        tags=['clients'],
        summary="Retrieve client detail",
        description="Returns full client info including site access notes and maps link."
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)