from django.contrib.auth.models import AnonymousUser
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIClient
from unittest.mock import MagicMock

from accounts.models import User
from incidents.models import Incident
from incidents.permissions import (
    IsIncidentAdmin,
    IsAdmin,
    AdminIncidentQuerysetMixin,
    get_admin_incident_queryset,
)


class AdminPermissionClassUnitTestCase(SimpleTestCase):
    """
    Unit test suite for IsIncidentAdmin permission class.
    Tests permission checks for all roles, anonymous users, and object-level permissions.
    """

    def setUp(self):
        self.perm = IsIncidentAdmin()
        self.admin_user = User(username='admin_alice', role='admin', is_active=True)
        self.student_user = User(username='student_bob', role='student', is_active=True)
        self.mgmt_user = User(username='mgmt_charlie', role='management', is_active=True)
        self.inactive_admin = User(username='admin_inactive', role='admin', is_active=False)
        self.anon_user = AnonymousUser()

    def _build_request(self, user):
        req = MagicMock()
        req.user = user
        return req

    def test_admin_user_granted_permission(self):
        """Active admin user must be granted permission."""
        req = self._build_request(self.admin_user)
        self.assertTrue(self.perm.has_permission(req, None))
        self.assertTrue(self.perm.has_object_permission(req, None, object()))

    def test_student_user_denied_permission(self):
        """Student user must be denied admin permission."""
        req = self._build_request(self.student_user)
        self.assertFalse(self.perm.has_permission(req, None))
        self.assertIn("admin", self.perm.message.lower())

    def test_management_user_denied_permission(self):
        """Management user must be denied incident admin permission."""
        req = self._build_request(self.mgmt_user)
        self.assertFalse(self.perm.has_permission(req, None))

    def test_anonymous_user_denied_permission(self):
        """Anonymous unauthenticated user must be denied permission."""
        req = self._build_request(self.anon_user)
        self.assertFalse(self.perm.has_permission(req, None))

    def test_inactive_admin_denied_permission(self):
        """Inactive admin user must be denied permission."""
        req = self._build_request(self.inactive_admin)
        self.assertFalse(self.perm.has_permission(req, None))
        self.assertIn("inactive", self.perm.message)

    def test_is_admin_alias(self):
        """IsAdmin is an alias of IsIncidentAdmin."""
        self.assertIs(IsAdmin, IsIncidentAdmin)


class AdminIncidentQuerysetTestCase(TestCase):
    """
    Tests for the admin incident queryset function and view mixin.
    Verifies that all incidents across all students are returned, ordered newest first.
    """

    def setUp(self):
        self.student1 = User.objects.create_user(username='stu1', password='pw', role='student')
        self.student2 = User.objects.create_user(username='stu2', password='pw', role='student')
        self.admin = User.objects.create_user(username='adm1', password='pw', role='admin')
        self.mgmt = User.objects.create_user(username='mgt1', password='pw', role='management')

        self.inc1 = Incident.objects.create(
            category='Theft',
            description='Bag stolen from cafeteria',
            location_text='Cafeteria Hall',
            reported_by=self.student1,
            status='Pending',
        )
        self.inc2 = Incident.objects.create(
            category='Vandalism',
            description='Window cracked in dorm A',
            location_text='Dorm A Room 102',
            reported_by=self.student2,
            status='Under Review',
            is_anonymous=True,
        )

    def test_get_admin_incident_queryset_returns_all_incidents_ordered(self):
        """get_admin_incident_queryset returns incidents across all reporters ordered newest first."""
        qs = get_admin_incident_queryset()
        self.assertEqual(qs.count(), 2)
        # Newest first
        self.assertEqual(list(qs.values_list('id', flat=True)), [self.inc2.id, self.inc1.id])

    def test_get_admin_incident_queryset_enforces_admin_role_when_user_provided(self):
        """Passing an admin succeeds; passing student or management raises PermissionDenied."""
        # Admin succeeds
        qs = get_admin_incident_queryset(user=self.admin)
        self.assertEqual(qs.count(), 2)

        # Student raises PermissionDenied
        with self.assertRaises(PermissionDenied):
            get_admin_incident_queryset(user=self.student1)

        # Management raises PermissionDenied
        with self.assertRaises(PermissionDenied):
            get_admin_incident_queryset(user=self.mgmt)

    def test_admin_incident_queryset_mixin(self):
        """AdminIncidentQuerysetMixin provides all incidents ordered newest first."""
        mixin = AdminIncidentQuerysetMixin()
        qs = mixin.get_queryset()
        self.assertEqual(qs.count(), 2)
        self.assertEqual(list(qs.values_list('id', flat=True)), [self.inc2.id, self.inc1.id])


class AdminIncidentEndpointIntegrationTestCase(TestCase):
    """
    Integration test suite for the Admin incident API endpoints:
    - GET /api/incidents/admin/ (list all incidents)
    - GET /api/incidents/admin/<pk>/ (retrieve single incident)
    """

    def setUp(self):
        self.client = APIClient()
        self.list_url = reverse('admin-incident-list')

        self.student1 = User.objects.create_user(username='student_alpha', password='pw', role='student')
        self.student2 = User.objects.create_user(username='student_beta', password='pw', role='student')
        self.admin = User.objects.create_user(username='admin_boss', password='pw', role='admin')
        self.mgmt = User.objects.create_user(username='mgmt_leader', password='pw', role='management')

        self.inc_public = Incident.objects.create(
            category='Harassment',
            description='Harassment outside hostel',
            location_text='Hostel 2 Gate',
            reported_by=self.student1,
            status='Pending',
            is_anonymous=False,
        )
        self.inc_anon = Incident.objects.create(
            category='Ragging',
            description='Ragging in parking lot',
            location_text='Parking Lot C',
            reported_by=self.student2,
            status='Under Review',
            is_anonymous=True,
        )

    def test_admin_can_list_all_incidents(self):
        """Admin GET /api/incidents/admin/ returns all incidents across all students."""
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(self.list_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data if isinstance(response.data, list) else response.data.get('results', [])
        self.assertEqual(len(results), 2)

        # Verify ordering: newest first (inc_anon then inc_public)
        self.assertEqual(results[0]['id'], self.inc_anon.id)
        self.assertEqual(results[1]['id'], self.inc_public.id)

        # Verify reporter details: anonymous incident masks username
        self.assertEqual(results[0]['reporter_username'], 'Anonymous Student')
        self.assertTrue(results[0]['is_anonymous'])

        # Non-anonymous incident shows real reporter username
        self.assertEqual(results[1]['reporter_username'], 'student_alpha')
        self.assertFalse(results[1]['is_anonymous'])

    def test_admin_can_retrieve_single_incident(self):
        """Admin GET /api/incidents/admin/<pk>/ returns full details of any incident."""
        self.client.force_authenticate(user=self.admin)
        detail_url = reverse('admin-incident-detail', kwargs={'pk': self.inc_public.id})
        response = self.client.get(detail_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.inc_public.id)
        self.assertEqual(response.data['category'], 'Harassment')
        self.assertEqual(response.data['reporter_username'], 'student_alpha')

    def test_student_forbidden_from_admin_incident_endpoints(self):
        """Students must be rejected with 403 Forbidden on admin incident endpoints."""
        self.client.force_authenticate(user=self.student1)

        # List endpoint forbidden
        list_res = self.client.get(self.list_url)
        self.assertEqual(list_res.status_code, status.HTTP_403_FORBIDDEN)

        # Detail endpoint forbidden
        detail_url = reverse('admin-incident-detail', kwargs={'pk': self.inc_public.id})
        detail_res = self.client.get(detail_url)
        self.assertEqual(detail_res.status_code, status.HTTP_403_FORBIDDEN)

    def test_management_forbidden_from_admin_incident_endpoints(self):
        """Management users must be rejected with 403 Forbidden."""
        self.client.force_authenticate(user=self.mgmt)
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_denied_from_admin_incident_endpoints(self):
        """Unauthenticated requests must be denied with 401 or 403."""
        response = self.client.get(self.list_url)
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])
