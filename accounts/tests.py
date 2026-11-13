from django.test import SimpleTestCase
from django.contrib.auth.models import AnonymousUser
from unittest.mock import MagicMock

from accounts.models import User
from accounts.permissions import (
    BaseRolePermission,
    IsStudent,
    IsAdmin,
    IsManagement,
    IsAdminOrManagement,
    require_roles,
)


class RolePermissionsTestCase(SimpleTestCase):
    """
    Test suite for Guardly role-based DRF permission classes.
    Uses SimpleTestCase to run isolated, database-independent unit tests.
    """

    def setUp(self):
        # Create unsaved User instances for each role
        self.student_user = User(username='student_test', role='student', is_active=True)
        self.admin_user = User(username='admin_test', role='admin', is_active=True)
        self.mgmt_user = User(username='mgmt_test', role='management', is_active=True)
        self.inactive_student = User(username='inactive_student', role='student', is_active=False)
        self.anon_user = AnonymousUser()

    def _build_request(self, user):
        """Helper to construct a mock DRF request with the given user."""
        request = MagicMock()
        request.user = user
        return request

    # ---------------------------------------------------------
    # Anonymous & Inactive User Tests
    # ---------------------------------------------------------
    def test_anonymous_user_denied_across_all_permissions(self):
        """Unauthenticated requests must be denied by all role permissions."""
        request = self._build_request(self.anon_user)

        for perm_class in [IsStudent, IsAdmin, IsManagement, IsAdminOrManagement]:
            perm = perm_class()
            self.assertFalse(
                perm.has_permission(request, None),
                f"{perm_class.__name__} should deny AnonymousUser."
            )
            self.assertIn("Authentication credentials", perm.message)

    def test_none_user_denied(self):
        """Requests with user=None must be safely handled and denied."""
        request = self._build_request(None)
        perm = IsStudent()
        self.assertFalse(perm.has_permission(request, None))
        self.assertIn("Authentication credentials", perm.message)

    def test_inactive_user_denied(self):
        """Inactive accounts must be denied access even if the role matches."""
        request = self._build_request(self.inactive_student)
        perm = IsStudent()
        self.assertFalse(perm.has_permission(request, None))
        self.assertIn("inactive", perm.message)

    # ---------------------------------------------------------
    # IsStudent Permission Tests
    # ---------------------------------------------------------
    def test_is_student_allows_student_only(self):
        perm = IsStudent()

        # Student allowed
        self.assertTrue(perm.has_permission(self._build_request(self.student_user), None))

        # Admin and Management denied
        self.assertFalse(perm.has_permission(self._build_request(self.admin_user), None))
        self.assertFalse(perm.has_permission(self._build_request(self.mgmt_user), None))

    # ---------------------------------------------------------
    # IsAdmin Permission Tests
    # ---------------------------------------------------------
    def test_is_admin_allows_admin_only(self):
        perm = IsAdmin()

        # Admin allowed
        self.assertTrue(perm.has_permission(self._build_request(self.admin_user), None))

        # Student and Management denied
        self.assertFalse(perm.has_permission(self._build_request(self.student_user), None))
        self.assertFalse(perm.has_permission(self._build_request(self.mgmt_user), None))

    # ---------------------------------------------------------
    # IsManagement Permission Tests
    # ---------------------------------------------------------
    def test_is_management_allows_management_only(self):
        perm = IsManagement()

        # Management allowed
        self.assertTrue(perm.has_permission(self._build_request(self.mgmt_user), None))

        # Student and Admin denied
        self.assertFalse(perm.has_permission(self._build_request(self.student_user), None))
        self.assertFalse(perm.has_permission(self._build_request(self.admin_user), None))

    # ---------------------------------------------------------
    # Composite & Dynamic Permissions Tests
    # ---------------------------------------------------------
    def test_is_admin_or_management(self):
        perm = IsAdminOrManagement()

        # Admin and Management allowed
        self.assertTrue(perm.has_permission(self._build_request(self.admin_user), None))
        self.assertTrue(perm.has_permission(self._build_request(self.mgmt_user), None))

        # Student denied
        self.assertFalse(perm.has_permission(self._build_request(self.student_user), None))

    def test_require_roles_factory(self):
        """Factory require_roles should permit specified roles and reject others."""
        custom_perm_class = require_roles('student', 'management')
        perm = custom_perm_class()

        self.assertTrue(perm.has_permission(self._build_request(self.student_user), None))
        self.assertTrue(perm.has_permission(self._build_request(self.mgmt_user), None))
        self.assertFalse(perm.has_permission(self._build_request(self.admin_user), None))

    def test_drf_bitwise_or_operator(self):
        """Subclasses of BasePermission can be combined using bitwise OR (|)."""
        combined_perm = (IsAdmin | IsManagement)()

        self.assertTrue(combined_perm.has_permission(self._build_request(self.admin_user), None))
        self.assertTrue(combined_perm.has_permission(self._build_request(self.mgmt_user), None))
        self.assertFalse(combined_perm.has_permission(self._build_request(self.student_user), None))

    # ---------------------------------------------------------
    # Object Permission Tests
    # ---------------------------------------------------------
    def test_has_object_permission_delegates_to_has_permission(self):
        """has_object_permission should default to checking role permission."""
        perm = IsAdmin()
        dummy_obj = object()

        self.assertTrue(
            perm.has_object_permission(self._build_request(self.admin_user), None, dummy_obj)
        )
        self.assertFalse(
            perm.has_object_permission(self._build_request(self.student_user), None, dummy_obj)
        )
