from rest_framework.exceptions import PermissionDenied
from accounts.permissions import IsAdmin
from .models import Incident


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
