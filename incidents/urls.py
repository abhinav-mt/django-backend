from django.urls import path
from .views import IncidentListCreateView

urlpatterns = [
    path('', IncidentListCreateView.as_view(), name='incident-list-create'),
]
