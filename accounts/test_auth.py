from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import User, UserToken
from incidents.models import Incident


class TokenAuthTestCase(TestCase):
    """
    Test suite for token-based authentication and lifecycle (login, multi-device, logout).
    """

    def setUp(self):
        self.client = APIClient()
        self.login_url = reverse('login')
        self.logout_url = reverse('logout')
        self.incidents_url = reverse('incident-list-create')

        self.student = User.objects.create_user(
            username='student_alice',
            password='securepassword123',
            role='student',
        )
        self.admin_user = User.objects.create_user(
            username='admin_bob',
            password='securepassword123',
            role='admin',
        )
        self.mgmt_user = User.objects.create_user(
            username='mgmt_carol',
            password='securepassword123',
            role='management',
        )
        self.inactive_user = User.objects.create_user(
            username='inactive_dave',
            password='securepassword123',
            role='student',
            is_active=False,
        )

    def test_login_success_returns_token_and_role(self):
        """
        Valid credentials return HTTP 200, a 64-char token string, and the user's role.
        """
        # Test student login
        response = self.client.post(
            self.login_url,
            {'username': 'student_alice', 'password': 'securepassword123'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('token', response.data)
        self.assertIsInstance(response.data['token'], str)
        self.assertEqual(len(response.data['token']), 64)
        self.assertEqual(response.data['role'], 'student')
        self.assertTrue(
            UserToken.objects.filter(key=response.data['token'], user=self.student).exists()
        )

        # Test admin login
        admin_res = self.client.post(
            self.login_url,
            {'username': 'admin_bob', 'password': 'securepassword123'},
            format='json',
        )
        self.assertEqual(admin_res.status_code, status.HTTP_200_OK)
        self.assertEqual(admin_res.data['role'], 'admin')

        # Test management login
        mgmt_res = self.client.post(
            self.login_url,
            {'username': 'mgmt_carol', 'password': 'securepassword123'},
            format='json',
        )
        self.assertEqual(mgmt_res.status_code, status.HTTP_200_OK)
        self.assertEqual(mgmt_res.data['role'], 'management')

    def test_login_wrong_password_fails(self):
        """
        Wrong password or non-existent user returns 400 or 401 with a generic error
        and does not create a token.
        """
        response = self.client.post(
            self.login_url,
            {'username': 'student_alice', 'password': 'wrongpassword'},
            format='json',
        )
        self.assertIn(response.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_401_UNAUTHORIZED])
        self.assertNotIn('token', response.data)
        # Error message must never reveal whether username or password was wrong
        error_msg = str(response.data).lower()
        self.assertNotIn('student_alice', error_msg)
        self.assertEqual(UserToken.objects.count(), 0)

        # Non-existent user
        non_existent_res = self.client.post(
            self.login_url,
            {'username': 'ghost_user', 'password': 'somepassword'},
            format='json',
        )
        self.assertIn(non_existent_res.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_401_UNAUTHORIZED])
        self.assertEqual(UserToken.objects.count(), 0)

    def test_login_inactive_user_fails(self):
        """
        Inactive users cannot log in even with correct credentials.
        """
        response = self.client.post(
            self.login_url,
            {'username': 'inactive_dave', 'password': 'securepassword123'},
            format='json',
        )
        self.assertIn(response.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_401_UNAUTHORIZED])
        self.assertNotIn('token', response.data)
        self.assertEqual(UserToken.objects.filter(user=self.inactive_user).count(), 0)

    def test_multi_device_login_creates_two_different_tokens_and_both_work(self):
        """
        Each login creates a new token row without invalidating existing sessions.
        Both tokens remain active and work concurrently.
        """
        res1 = self.client.post(
            self.login_url,
            {'username': 'student_alice', 'password': 'securepassword123'},
            format='json',
        )
        self.assertEqual(res1.status_code, status.HTTP_200_OK)
        token1 = res1.data['token']

        res2 = self.client.post(
            self.login_url,
            {'username': 'student_alice', 'password': 'securepassword123'},
            format='json',
        )
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        token2 = res2.data['token']

        # Tokens must be distinct
        self.assertNotEqual(token1, token2)
        self.assertEqual(UserToken.objects.filter(user=self.student).count(), 2)

        # Both tokens work on authenticated endpoints
        client1 = APIClient()
        client1.credentials(HTTP_AUTHORIZATION=f'Token {token1}')
        check1 = client1.get(self.incidents_url)
        self.assertEqual(check1.status_code, status.HTTP_200_OK)

        client2 = APIClient()
        client2.credentials(HTTP_AUTHORIZATION=f'Token {token2}')
        check2 = client2.get(self.incidents_url)
        self.assertEqual(check2.status_code, status.HTTP_200_OK)

    def test_logout_deletes_only_used_token_and_other_token_still_works(self):
        """
        Logging out deletes ONLY the token used in that request; other active
        tokens for the same user remain valid.
        """
        # Create two tokens for student_alice
        res1 = self.client.post(
            self.login_url,
            {'username': 'student_alice', 'password': 'securepassword123'},
            format='json',
        )
        token1 = res1.data['token']

        res2 = self.client.post(
            self.login_url,
            {'username': 'student_alice', 'password': 'securepassword123'},
            format='json',
        )
        token2 = res2.data['token']

        # Logout using token1
        logout_client = APIClient()
        logout_client.credentials(HTTP_AUTHORIZATION=f'Token {token1}')
        logout_res = logout_client.post(self.logout_url)
        self.assertEqual(logout_res.status_code, status.HTTP_204_NO_CONTENT)

        # token1 must be deleted from database
        self.assertFalse(UserToken.objects.filter(key=token1).exists())
        # token2 must still exist
        self.assertTrue(UserToken.objects.filter(key=token2).exists())

        # Attempting to use token1 now fails
        recheck_client1 = APIClient()
        recheck_client1.credentials(HTTP_AUTHORIZATION=f'Token {token1}')
        fail_res = recheck_client1.get(self.incidents_url)
        self.assertIn(fail_res.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

        # token2 continues to work
        recheck_client2 = APIClient()
        recheck_client2.credentials(HTTP_AUTHORIZATION=f'Token {token2}')
        ok_res = recheck_client2.get(self.incidents_url)
        self.assertEqual(ok_res.status_code, status.HTTP_200_OK)

    def test_request_without_or_with_bad_token_is_rejected(self):
        """
        Requests without a token, with unknown keys, or with invalid formats are rejected.
        """
        # 1. No token on logout
        anon_client = APIClient()
        res_no_auth = anon_client.post(self.logout_url)
        self.assertIn(res_no_auth.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

        # 2. Unknown key
        bad_token_client = APIClient()
        bad_token_client.credentials(HTTP_AUTHORIZATION='Token ' + 'f' * 64)
        res_bad_key = bad_token_client.post(self.logout_url)
        self.assertIn(res_bad_key.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

        # 3. Malformed header (Token keyword with no key)
        malformed_client = APIClient()
        malformed_client.credentials(HTTP_AUTHORIZATION='Token')
        res_malformed = malformed_client.post(self.logout_url)
        self.assertIn(res_malformed.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

        # 4. Unknown key on incident listing
        bad_inc_client = APIClient()
        bad_inc_client.credentials(HTTP_AUTHORIZATION='Token deadbeefbadkey')
        res_bad_inc = bad_inc_client.get(self.incidents_url)
        self.assertIn(res_bad_inc.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

        # 5. Inactive user token is rejected
        inactive_token = UserToken.objects.create(user=self.inactive_user)
        inactive_client = APIClient()
        inactive_client.credentials(HTTP_AUTHORIZATION=f'Token {inactive_token.key}')
        res_inactive = inactive_client.get(self.incidents_url)
        self.assertIn(res_inactive.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_token_works_on_get_incidents_for_student(self):
        """
        A student's token authorizes GET /api/incidents/ and returns only their own incidents.
        """
        # Create incidents
        own_incident = Incident.objects.create(
            category='Maintenance',
            description='Leaking pipe in dorm',
            location_text='Building 1',
            reported_by=self.student,
            status='Pending',
        )

        other_student = User.objects.create_user(
            username='other_student',
            password='securepassword123',
            role='student',
        )
        other_incident = Incident.objects.create(
            category='Noise',
            description='Loud music',
            location_text='Building 2',
            reported_by=other_student,
            status='Pending',
        )

        # Login student
        login_res = self.client.post(
            self.login_url,
            {'username': 'student_alice', 'password': 'securepassword123'},
            format='json',
        )
        self.assertEqual(login_res.status_code, status.HTTP_200_OK)
        token = login_res.data['token']

        # Access incidents endpoint
        auth_client = APIClient()
        auth_client.credentials(HTTP_AUTHORIZATION=f'Token {token}')
        incidents_res = auth_client.get(self.incidents_url)

        self.assertEqual(incidents_res.status_code, status.HTTP_200_OK)
        results = incidents_res.data if isinstance(incidents_res.data, list) else incidents_res.data.get('results', [])
        ids = [item['id'] for item in results]

        self.assertIn(own_incident.id, ids)
        self.assertNotIn(other_incident.id, ids)
