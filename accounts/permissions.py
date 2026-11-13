"""
Reusable DRF permission classes for Guardly Role-Based Access Control (RBAC).

This module defines permission classes tailored to Guardly's user roles:
    - 'student': Mobile app user reporting incidents and tracking own reports.
    - 'admin': Campus administrator triaging, reviewing, and auditing incidents.
    - 'management': Web portal administrator managing accounts and face biometrics.

DRF usage:
    from accounts.permissions import (
        IsStudent,
        IsAdmin,
        IsManagement,
        IsAdminOrManagement,
        require_roles,
    )

    class IncidentCreateView(APIView):
        permission_classes = [IsStudent]

    class IncidentReviewView(APIView):
        permission_classes = [IsAdmin]

    # Dynamic multi-role combination:
    class AdminDashboardView(APIView):
        permission_classes = [require_roles('admin', 'management')]
        # Or using DRF's built-in bitwise OR operator:
        # permission_classes = [IsAdmin | IsManagement]
"""

from typing import Set
from rest_framework.permissions import BasePermission


class BaseRolePermission(BasePermission):
    """
    Abstract base class for role-based permissions in Guardly.

    Subclasses must define `allowed_roles` as a set of allowed role strings
    matching `User.ROLE_CHOICES` ('student', 'admin', 'management').
    """
    allowed_roles: Set[str] = set()
    message: str = "You do not have the required permissions to perform this action."

    def has_permission(self, request, view) -> bool:
        """
        Check if the request user is authenticated, active, and possesses one of the allowed roles.
        """
        user = getattr(request, 'user', None)

        if not user or not user.is_authenticated:
            self.message = "Authentication credentials were not provided or are invalid."
            return False

        if not getattr(user, 'is_active', True):
            self.message = "This user account is inactive."
            return False

        user_role = getattr(user, 'role', None)
        if user_role not in self.allowed_roles:
            self.message = f"Access restricted. Required role(s): {', '.join(sorted(self.allowed_roles))}."
            return False

        return True

    def has_object_permission(self, request, view, obj) -> bool:
        """
        Default object-level check falls back to view-level permission check.
        Can be overridden in views or specialized subclasses for object ownership checks.
        """
        return self.has_permission(request, view)


class IsStudent(BaseRolePermission):
    """
    Permission class allowing access only to active, authenticated Students.
    """
    allowed_roles = {'student'}
    message = "Access restricted to Student accounts."


class IsAdmin(BaseRolePermission):
    """
    Permission class allowing access only to active, authenticated Admins.
    """
    allowed_roles = {'admin'}
    message = "Access restricted to Admin accounts."


class IsManagement(BaseRolePermission):
    """
    Permission class allowing access only to active, authenticated Management accounts.
    """
    allowed_roles = {'management'}
    message = "Access restricted to Management accounts."


class IsAdminOrManagement(BaseRolePermission):
    """
    Permission class allowing access to either Admin or Management users.
    Useful for shared oversight, escalation, or reporting endpoints.
    """
    allowed_roles = {'admin', 'management'}
    message = "Access restricted to Admin or Management accounts."


def require_roles(*roles: str):
    """
    Factory function returning a dynamic DRF permission class that permits
    any of the specified roles.

    Example:
        permission_classes = [require_roles('admin', 'management')]
    """
    clean_roles = set(roles)

    class DynamicRolePermission(BaseRolePermission):
        allowed_roles = clean_roles
        message = f"Access restricted to users with role(s): {', '.join(sorted(clean_roles))}."

    formatted_name = "_".join(sorted(r.capitalize() for r in clean_roles))
    DynamicRolePermission.__name__ = f"RequireRoles_{formatted_name}"
    DynamicRolePermission.__qualname__ = DynamicRolePermission.__name__
    return DynamicRolePermission

