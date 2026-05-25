from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from django.db.models import Q
from drf_spectacular.utils import extend_schema, OpenApiParameter

from user.permissions import IsAdminOrManager
from .models import Note, Task
from .serializers import NoteSerializer, NoteWriteSerializer, TaskSerializer, TaskWriteSerializer


# ==================== NOTE VIEWS ====================

class NoteListCreateView(APIView):
    permission_classes = [IsAdminOrManager]

    @extend_schema(
        tags=['notes'],
        summary="List all notes",
        parameters=[
            OpenApiParameter('job_id', str, description='Filter by job UUID'),
            OpenApiParameter('date', str, description='Filter by scheduled date YYYY-MM-DD'),
            OpenApiParameter('staff_id', str, description='Filter by staff UUID'),
            OpenApiParameter('unassigned', str, description='true = notes with no staff'),
            OpenApiParameter('unscheduled', str, description='true = notes with no scheduled_datetime and no end_time'),
        ],
        responses={200: NoteSerializer(many=True)},
    )
    def get(self, request):
        user = request.user
        if user.is_superuser:
            qs = Note.objects.all()
        else:
            qs = Note.objects.filter(staff=user)

        qs = qs.select_related('job', 'created_by').prefetch_related(
            'staff', 'staff__user_color', 'tasks', 'tasks__staff'
        )

        job_id = request.query_params.get('job_id')
        if job_id:
            qs = qs.filter(job__id=job_id)

        date = request.query_params.get('date')
        if date:
            qs = qs.filter(scheduled_datetime__date=date)

        staff_id = request.query_params.get('staff_id')
        if staff_id:
            qs = qs.filter(staff__id=staff_id)

        unassigned = request.query_params.get('unassigned')
        if unassigned and unassigned.lower() == 'true':
            qs = qs.filter(staff__isnull=True)

        unscheduled = request.query_params.get('unscheduled')
        if unscheduled and unscheduled.lower() == 'true':
            qs = qs.filter(scheduled_datetime__isnull=True, end_time__isnull=True)

        qs = qs.distinct().order_by('scheduled_datetime')
        return Response(NoteSerializer(qs, many=True).data)

    @extend_schema(
        tags=['notes'],
        summary="Create a note",
        request=NoteWriteSerializer,
        responses={201: NoteSerializer},
    )
    def post(self, request):
        if not request.user.is_superuser:
            return Response({'error': 'Admin access required.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = NoteWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        note = serializer.save(created_by=request.user)

        if note.job:
            try:
                from notifications.services import NotificationTemplates
                for member in note.staff.all():
                    NotificationTemplates.note_assigned(member, note)
            except Exception:
                pass

        return Response(NoteSerializer(note).data, status=status.HTTP_201_CREATED)


class NoteDetailView(APIView):
    permission_classes = [IsAdminOrManager]

    def _get_note(self, id):
        return get_object_or_404(
            Note.objects.select_related('job', 'created_by').prefetch_related(
                'staff', 'staff__user_color', 'tasks', 'tasks__staff'
            ),
            id=id,
        )

    @extend_schema(tags=['notes'], summary="Get note detail", responses={200: NoteSerializer})
    def get(self, request, id):
        return Response(NoteSerializer(self._get_note(id)).data)

    @extend_schema(
        tags=['notes'],
        summary="Update note",
        request=NoteWriteSerializer,
        responses={200: NoteSerializer},
    )
    def patch(self, request, id):
        if not request.user.is_superuser:
            return Response({'error': 'Admin access required.'}, status=status.HTTP_403_FORBIDDEN)

        note = self._get_note(id)
        serializer = NoteWriteSerializer(note, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        note = serializer.save()

        if note.job:
            try:
                from notifications.services import NotificationTemplates
                for member in note.staff.all():
                    NotificationTemplates.note_assigned(member, note)
            except Exception:
                pass

        return Response(NoteSerializer(note).data)

    @extend_schema(tags=['notes'], summary="Delete note", responses={204: None})
    def delete(self, request, id):
        if not request.user.is_superuser:
            return Response({'error': 'Admin access required.'}, status=status.HTTP_403_FORBIDDEN)
        self._get_note(id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ==================== TASK VIEWS ====================

class TaskListCreateView(APIView):
    permission_classes = [IsAdminOrManager]

    @extend_schema(
        tags=['tasks'],
        summary="List all tasks",
        parameters=[
            OpenApiParameter('search', str, description='Search by task name or description'),
        ],
        responses={200: TaskSerializer(many=True)},
    )
    def get(self, request):
        from core.pagination import FlexiblePageNumberPagination

        qs = Task.objects.select_related('staff', 'created_by').order_by('-created_at')

        search = request.query_params.get('search')
        if search:
            qs = qs.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search)
            )

        paginator = FlexiblePageNumberPagination()
        page = paginator.paginate_queryset(qs, request)
        if page is not None:
            return paginator.get_paginated_response(TaskSerializer(page, many=True).data)
        return Response(TaskSerializer(qs, many=True).data)

    @extend_schema(
        tags=['tasks'],
        summary="Create a task",
        request=TaskWriteSerializer,
        responses={201: TaskSerializer},
    )
    def post(self, request):
        if not request.user.is_superuser:
            return Response({'error': 'Admin access required.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = TaskWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        task = serializer.save(created_by=request.user)
        return Response(TaskSerializer(task).data, status=status.HTTP_201_CREATED)


class TaskDetailView(APIView):
    permission_classes = [IsAdminOrManager]

    def _get_task(self, id):
        return get_object_or_404(Task.objects.select_related('staff', 'created_by'), id=id)

    @extend_schema(tags=['tasks'], summary="Get task detail", responses={200: TaskSerializer})
    def get(self, request, id):
        return Response(TaskSerializer(self._get_task(id)).data)

    @extend_schema(
        tags=['tasks'],
        summary="Update task",
        request=TaskWriteSerializer,
        responses={200: TaskSerializer},
    )
    def patch(self, request, id):
        if not request.user.is_superuser:
            return Response({'error': 'Admin access required.'}, status=status.HTTP_403_FORBIDDEN)

        task = self._get_task(id)
        serializer = TaskWriteSerializer(task, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        return Response(TaskSerializer(serializer.save()).data)

    @extend_schema(tags=['tasks'], summary="Delete task", responses={204: None})
    def delete(self, request, id):
        if not request.user.is_superuser:
            return Response({'error': 'Admin access required.'}, status=status.HTTP_403_FORBIDDEN)
        self._get_task(id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
