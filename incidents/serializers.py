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


class AdminIncidentSerializer(serializers.ModelSerializer):
    """
    Serializer for admin incident views.
    Includes reporter metadata, review state, and timestamps.
    Respects anonymity: if is_anonymous is True, reporter details are masked and reported_by is None.
    """
    reported_by = serializers.SerializerMethodField()
    reporter_username = serializers.SerializerMethodField()
    first_rejected_by_username = serializers.CharField(
        source='first_rejected_by.username', read_only=True, default=None
    )
    second_rejected_by_username = serializers.CharField(
        source='second_rejected_by.username', read_only=True, default=None
    )

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
            'rejection_reason',
            'first_rejected_by',
            'first_rejected_by_username',
            'second_rejected_by',
            'second_rejected_by_username',
            'created_at',
            'reported_by',
            'reporter_username',
        ]
        read_only_fields = fields

    def get_reported_by(self, obj):
        if obj.is_anonymous:
            return None
        return obj.reported_by_id if obj.reported_by_id else (obj.reported_by.id if obj.reported_by else None)

    def get_reporter_username(self, obj):
        if obj.is_anonymous:
            return "Anonymous Student"
        return obj.reported_by.username if obj.reported_by else None

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        if instance.is_anonymous:
            ret['reported_by'] = None
        return ret
