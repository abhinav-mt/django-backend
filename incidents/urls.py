from django.urls import path
from .uploads import IncidentMediaUploadView
from .views import IncidentListCreateView

urlpatterns = [
    path('', IncidentListCreateView.as_view(), name='incident-list-create'),
    path('upload/', IncidentMediaUploadView.as_view(), name='incident-media-upload'),
]
