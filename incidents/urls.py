from django.urls import path
from .uploads import IncidentMediaUploadView
from .views import (
    IncidentListCreateView,
    AdminIncidentListView,
    AdminIncidentDetailView,
)

urlpatterns = [
    path('', IncidentListCreateView.as_view(), name='incident-list-create'),
    path('upload/', IncidentMediaUploadView.as_view(), name='incident-media-upload'),
    path('admin/', AdminIncidentListView.as_view(), name='admin-incident-list'),
    path('admin/<int:pk>/', AdminIncidentDetailView.as_view(), name='admin-incident-detail'),
]
