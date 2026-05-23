from django.urls import path
from .views import NoteListCreateView, NoteDetailView, TaskListCreateView, TaskDetailView

urlpatterns = [
    path('', NoteListCreateView.as_view(), name='note-list-create'),
    path('tasks/', TaskListCreateView.as_view(), name='task-list-create'),
    path('tasks/<uuid:id>/', TaskDetailView.as_view(), name='task-detail'),
    path('<uuid:id>/', NoteDetailView.as_view(), name='note-detail'),
]
