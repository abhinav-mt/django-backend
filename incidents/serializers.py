from rest_framework import serializers
from .models import Incident


class IncidentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Incident
        fields = [
            'id',
            'category',
            'description',
            'location_text',
            'image_url',
            'is_anonymous',
            'status',
            'created_at',
        ]
        read_only_fields = ['id', 'status', 'created_at']
