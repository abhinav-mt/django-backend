from rest_framework import generics
from accounts.permissions import IsStudent
from .models import Incident
from .permissions import IsAdmin, AdminIncidentQuerysetMixin
from .serializers import IncidentSerializer, AdminIncidentSerializer
from .throttles import IncidentCreateThrottle


class IncidentListCreateView(generics.ListCreateAPIView):
    serializer_class = IncidentSerializer
    permission_classes = [IsStudent]

    def get_throttles(self):
        if self.request and self.request.method == 'POST':
            return [IncidentCreateThrottle()]
        return []

    def get_queryset(self):
        return Incident.objects.filter(reported_by=self.request.user).order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(reported_by=self.request.user, status='Pending')


class AdminIncidentListView(AdminIncidentQuerysetMixin, generics.ListAPIView):
    """
    Admin-only endpoint to list all campus incidents (Task 19).
    Admins see all reports from all students, ordered newest first.
    Students, management, and unauthenticated users are denied.
    """
    serializer_class = AdminIncidentSerializer
    permission_classes = [IsAdmin]


class AdminIncidentDetailView(AdminIncidentQuerysetMixin, generics.RetrieveAPIView):
    """
    Admin-only endpoint to retrieve any specific campus incident by ID (Task 19).
    """
    serializer_class = AdminIncidentSerializer
    permission_classes = [IsAdmin]
