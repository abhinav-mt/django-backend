from rest_framework import generics
from accounts.permissions import IsStudent
from .models import Incident
from .serializers import IncidentSerializer
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
