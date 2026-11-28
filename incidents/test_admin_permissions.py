from django.contrib.auth.models import AnonymousUser
from django.test import SimpleTestCase
from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIRequestFactory, force_authenticate
from unittest.mock import MagicMock, patch

from accounts.models import User
from incidents.models import Incident
from incidents.permissions import (
    IsAdmin,
    AdminIncidentQuerysetMixin,
    get_admin_incident_queryset,
)
from incidents.serializers import AdminIncidentSerializer
from incidents.views import AdminIncidentListView, AdminIncidentDetailView


class AdminPermissionClassUnitTestCase(SimpleTestCase):
    """
    Unit test suite for IsAdmin permission class.
    Tests permission checks for all roles, anonymous users, and object-level permissions.
    """

    def setUp(self):
        self.perm = IsAdmin()
        self.admin_user = User(id=1, username='admin_alice', role='admin', is_active=True)
        self.student_user = User(id=2, username='student_bob', role='student', is_active=True)
        self.mgmt_user = User(id=3, username='mgmt_charlie', role='management', is_active=True)
        self.inactive_admin = User(id=4, username='admin_inactive', role='admin', is_active=False)
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
        """Management user must be denied admin permission."""
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


class AdminIncidentQuerysetTestCase(SimpleTestCase):
    """
    Tests for the admin incident queryset function and view mixin.
    Verifies that all incidents are queried with ordering newest first.
    """

    def setUp(self):
        self.student = User(id=10, username='stu', role='student', is_active=True)
        self.admin = User(id=11, username='adm', role='admin', is_active=True)
        self.mgmt = User(id=12, username='mgt', role='management', is_active=True)

    @patch('incidents.permissions.Incident.objects')
    def test_get_admin_incident_queryset_returns_ordered_queryset(self, mock_objects):
        """get_admin_incident_queryset orders all incidents by -created_at."""
        mock_qs = MagicMock()
        mock_objects.all.return_value.order_by.return_value = mock_qs

        qs = get_admin_incident_queryset()
        mock_objects.all.assert_called_once()
        mock_objects.all().order_by.assert_called_once_with('-created_at')
        self.assertEqual(qs, mock_qs)

    def test_get_admin_incident_queryset_enforces_admin_role(self):
        """Passing an admin succeeds; passing student or management raises PermissionDenied."""
        with patch('incidents.permissions.Incident.objects') as mock_objects:
            mock_objects.all.return_value.order_by.return_value = MagicMock()
            qs = get_admin_incident_queryset(user=self.admin)
            self.assertIsNotNone(qs)

        with self.assertRaises(PermissionDenied):
            get_admin_incident_queryset(user=self.student)

        with self.assertRaises(PermissionDenied):
            get_admin_incident_queryset(user=self.mgmt)

    @patch('incidents.permissions.Incident.objects')
    def test_admin_incident_queryset_mixin(self, mock_objects):
        """AdminIncidentQuerysetMixin provides all incidents ordered newest first."""
        mock_qs = MagicMock()
        mock_objects.all.return_value.order_by.return_value = mock_qs

        mixin = AdminIncidentQuerysetMixin()
        qs = mixin.get_queryset()
        mock_objects.all().order_by.assert_called_once_with('-created_at')
        self.assertEqual(qs, mock_qs)


class AdminIncidentSerializerTestCase(SimpleTestCase):
    """
    Tests for AdminIncidentSerializer handling of anonymity and reporter fields.
    """

    def setUp(self):
        self.student = User(id=5, username='student_sam', role='student')
        self.inc_anon = Incident(
            id=1,
            category='Theft',
            description='Laptop stolen',
            location_text='Lab 2',
            reported_by=self.student,
            is_anonymous=True,
            status='Pending',
        )
        self.inc_named = Incident(
            id=2,
            category='Noise',
            description='Loud party',
            location_text='Dorm B',
            reported_by=self.student,
            is_anonymous=False,
            status='Under Review',
        )

    def test_anonymous_incident_returns_none_for_reported_by(self):
        """When is_anonymous is True, reported_by must be None and reporter_username masked."""
        serializer = AdminIncidentSerializer(self.inc_anon)
        data = serializer.data
        self.assertIsNone(data['reported_by'])
        self.assertEqual(data['reporter_username'], 'Anonymous Student')
        self.assertTrue(data['is_anonymous'])

    def test_named_incident_returns_reported_by_id_and_username(self):
        """When is_anonymous is False, reported_by returns student ID and real username."""
        serializer = AdminIncidentSerializer(self.inc_named)
        data = serializer.data
        self.assertEqual(data['reported_by'], 5)
        self.assertEqual(data['reporter_username'], 'student_sam')
        self.assertFalse(data['is_anonymous'])


class AdminIncidentEndpointIntegrationTestCase(SimpleTestCase):
    """
    Test suite for the Admin incident API endpoints:
    - GET /api/incidents/admin/ (list all incidents)
    - GET /api/incidents/admin/<pk>/ (retrieve single incident)
    """

    def setUp(self):
        self.factory = APIRequestFactory()
        self.list_url = '/api/incidents/admin/'
        self.detail_url = '/api/incidents/admin/1/'

        self.admin = User(id=1, username='admin_boss', role='admin', is_active=True)
        self.mgmt = User(id=2, username='mgmt_leader', role='management', is_active=True)
        self.student = User(id=3, username='student_alpha', role='student', is_active=True)

        self.incident = Incident(
            id=1,
            category='Harassment',
            description='Harassment outside hostel',
            location_text='Hostel 2 Gate',
            reported_by=self.student,
            status='Pending',
            is_anonymous=False,
        )

    def test_admin_can_call_list_endpoint_and_receive_200(self):
        """Admin calling the admin LIST endpoint must receive a 200 OK response."""
        request = self.factory.get(self.list_url)
        force_authenticate(request, user=self.admin)

        with patch.object(AdminIncidentListView, 'get_queryset', return_value=[self.incident]):
            response = AdminIncidentListView.as_view()(request)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data if isinstance(response.data, list) else response.data.get('results', [])
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['id'], 1)
        self.assertEqual(results[0]['category'], 'Harassment')
        self.assertEqual(results[0]['reporter_username'], 'student_alpha')

    def test_management_calling_list_endpoint_gets_403(self):
        """Management calling the admin LIST endpoint must receive a 403 Forbidden response."""
        request = self.factory.get(self.list_url)
        force_authenticate(request, user=self.mgmt)

        response = AdminIncidentListView.as_view()(request)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_student_calling_list_endpoint_gets_403(self):
        """Student calling the admin LIST endpoint must receive a 403 Forbidden response."""
        request = self.factory.get(self.list_url)
        force_authenticate(request, user=self.student)

        response = AdminIncidentListView.as_view()(request)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_calling_list_endpoint_denied(self):
        """Unauthenticated requests to the admin LIST endpoint must be rejected."""
        request = self.factory.get(self.list_url)
        response = AdminIncidentListView.as_view()(request)
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_admin_can_call_detail_endpoint_and_receive_200(self):
        """Admin calling the admin DETAIL endpoint must receive a 200 OK response."""
        request = self.factory.get(self.detail_url)
        force_authenticate(request, user=self.admin)

        with patch.object(AdminIncidentDetailView, 'get_object', return_value=self.incident):
            response = AdminIncidentDetailView.as_view()(request, pk=1)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], 1)
        self.assertEqual(response.data['category'], 'Harassment')

    def test_student_calling_detail_endpoint_gets_403(self):
        """Student calling the admin DETAIL endpoint must receive a 403 Forbidden response."""
        request = self.factory.get(self.detail_url)
        force_authenticate(request, user=self.student)

        response = AdminIncidentDetailView.as_view()(request, pk=1)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
