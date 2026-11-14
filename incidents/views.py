from rest_framework import generics
from accounts.permissions import IsStudent
from .models import Incident
from .serializers import IncidentSerializer


class IncidentListCreateView(generics.ListCreateAPIView):
    serializer_class = IncidentSerializer
    permission_classes = [IsStudent]

    def get_queryset(self):
        return Incident.objects.filter(reported_by=self.request.user).order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(reported_by=self.request.user, status='Pending')
