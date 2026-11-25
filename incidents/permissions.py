"""
Role-based permission classes and queryset utilities for Incidents in Guardly.

This module provides:
- IsIncidentAdmin: Permission class restricting access exclusively to authenticated Admin users.
- AdminIncidentQuerysetMixin: DRF view mixin supplying the full incident queryset (all incidents, newest first).
- get_admin_incident_queryset: Standalone helper function returning the complete incident queryset for administrators.
"""

from rest_framework.exceptions import PermissionDenied
from accounts.permissions import BaseRolePermission
from .models import Incident


class IsIncidentAdmin(BaseRolePermission):
    """
    Permission class allowing access only to active, authenticated Administrators.
    Used for administrative incident triage, reviewing queues, and status audits.
    """
    allowed_roles = {'admin'}
    message = "Access restricted to Admin accounts."

    def has_object_permission(self, request, view, obj) -> bool:
        """
        Administrators have full object-level access across all incidents on campus.
        """
        return self.has_permission(request, view)


# Alias for concise importing
IsAdmin = IsIncidentAdmin


class AdminIncidentQuerysetMixin:
    """
    Mixin for DRF class-based views that provides the administrator queryset.
    Admins see all incidents across the entire campus, ordered newest first (-created_at).
    """

    def get_queryset(self):
        return Incident.objects.all().order_by('-created_at')


def get_admin_incident_queryset(user=None):
    """
    Helper function returning all incidents ordered by creation date (newest first).

    If a `user` argument is provided, enforces that the user is authenticated, active,
    and possesses the 'admin' role, raising PermissionDenied otherwise.
    """
    if user is not None:
        is_auth = getattr(user, 'is_authenticated', False)
        is_active = getattr(user, 'is_active', True)
        role = getattr(user, 'role', None)

        if not (is_auth and is_active and role == 'admin'):
            raise PermissionDenied("Access restricted to Admin accounts.")

    return Incident.objects.all().order_by('-created_at')
