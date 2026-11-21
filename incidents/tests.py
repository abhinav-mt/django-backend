from unittest.mock import patch

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from accounts.models import User
from incidents.models import Incident


class StudentIncidentEndpointsTestCase(TestCase):
    """
    Test suite for student-facing incident endpoints (/api/incidents/).
    Verifies creation, listing isolation, role permissions, and method restrictions.
    """

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.url = reverse('incident-list-create')

        # Test users with distinct roles
        self.student = User.objects.create_user(
            username='student1',
            password='testpassword123',
            role='student',
        )
        self.other_student = User.objects.create_user(
            username='student2',
            password='testpassword123',
            role='student',
        )
        self.admin_user = User.objects.create_user(
            username='admin1',
            password='testpassword123',
            role='admin',
        )
        self.mgmt_user = User.objects.create_user(
            username='mgmt1',
            password='testpassword123',
            role='management',
        )

        self.valid_payload = {
            'category': 'Vandalism',
            'description': 'Graffiti spotted on the library wall.',
            'location_text': 'Central Library, East Wing',
            'image_url': 'https://example.com/images/graffiti.jpg',
            'is_anonymous': False,
        }

    # -------------------------------------------------------------------------
    # 1. Student POST: Incident creation & defaults
    # -------------------------------------------------------------------------
    def test_student_can_post_and_incident_saved_with_defaults(self):
        """
        A student can POST an incident, which is saved with reported_by = student
        and status = 'Pending'.
        """
        self.client.force_authenticate(user=self.student)
        response = self.client.post(self.url, data=self.valid_payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', response.data)
        self.assertEqual(response.data['status'], 'Pending')
        self.assertIn('created_at', response.data)

        # Database verification
        incident = Incident.objects.get(id=response.data['id'])
        self.assertEqual(incident.reported_by, self.student)
        self.assertEqual(incident.status, 'Pending')
        self.assertEqual(incident.category, self.valid_payload['category'])
        self.assertEqual(incident.description, self.valid_payload['description'])
        self.assertEqual(incident.location_text, self.valid_payload['location_text'])
        self.assertEqual(incident.image_url, self.valid_payload['image_url'])
        self.assertFalse(incident.is_anonymous)

        # Ensure restricted fields are never exposed in response
        self.assertNotIn('reported_by', response.data)
        self.assertNotIn('rejection_reason', response.data)
        self.assertNotIn('first_rejected_by', response.data)
        self.assertNotIn('second_rejected_by', response.data)

    # -------------------------------------------------------------------------
    # 2. Student cannot tamper with server-controlled/unexposed fields
    # -------------------------------------------------------------------------
    def test_student_cannot_tamper_reported_by_status_or_rejection_fields(self):
        """
        A student sending reported_by, status, rejection_reason, or rejection
        reviewers in the request body cannot change them.
        """
        self.client.force_authenticate(user=self.student)
        tampered_payload = {
            'category': 'Harassment',
            'description': 'Bullying incident',
            'location_text': 'Student Center Hallway',
            'status': 'Resolved',
            'reported_by': self.other_student.id,
            'rejection_reason': 'Invalid report rationale',
            'first_rejected_by': self.admin_user.id,
            'second_rejected_by': self.admin_user.id,
        }

        response = self.client.post(self.url, data=tampered_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        incident = Incident.objects.get(id=response.data['id'])
        # Server must enforce real authenticated user and 'Pending' status
        self.assertEqual(incident.reported_by, self.student)
        self.assertEqual(incident.status, 'Pending')
        self.assertIsNone(incident.rejection_reason)
        self.assertIsNone(incident.first_rejected_by)
        self.assertIsNone(incident.second_rejected_by)

        # Response must reflect Pending and never expose forbidden fields
        self.assertEqual(response.data['status'], 'Pending')
        self.assertNotIn('reported_by', response.data)
        self.assertNotIn('rejection_reason', response.data)
        self.assertNotIn('first_rejected_by', response.data)
        self.assertNotIn('second_rejected_by', response.data)

    # -------------------------------------------------------------------------
    # 3. Listing isolation: Students can only view their own incidents
    # -------------------------------------------------------------------------
    def test_student_get_returns_only_own_incidents(self):
        """
        A student's GET request returns only their own incidents, never another student's.
        Also verifies ordering by -created_at.
        """
        # Create incidents for student 1
        inc1 = Incident.objects.create(
            category='Theft',
            description='Laptop missing from lab',
            location_text='Computer Lab 1',
            reported_by=self.student,
            status='Pending',
        )
        inc2 = Incident.objects.create(
            category='Safety Hazard',
            description='Broken handrail',
            location_text='Stairwell B',
            reported_by=self.student,
            status='Under Review',
        )

        # Create incidents for student 2
        inc3 = Incident.objects.create(
            category='Noise',
            description='Loud music past quiet hours',
            location_text='Dorm 4',
            reported_by=self.other_student,
            status='Pending',
        )
        inc4 = Incident.objects.create(
            category='Vandalism',
            description='Damaged whiteboard',
            location_text='Room 204',
            reported_by=self.other_student,
            status='Resolved',
        )

        # Authenticate as student 1
        self.client.force_authenticate(user=self.student)
        response1 = self.client.get(self.url)
        self.assertEqual(response1.status_code, status.HTTP_200_OK)

        results1 = response1.data if isinstance(response1.data, list) else response1.data.get('results', [])
        ids1 = [item['id'] for item in results1]

        self.assertEqual(len(ids1), 2)
        self.assertIn(inc1.id, ids1)
        self.assertIn(inc2.id, ids1)
        self.assertNotIn(inc3.id, ids1)
        self.assertNotIn(inc4.id, ids1)

        # Verify ordering is newest first (-created_at)
        self.assertEqual(ids1, [inc2.id, inc1.id])

        # Authenticate as student 2
        self.client.force_authenticate(user=self.other_student)
        response2 = self.client.get(self.url)
        self.assertEqual(response2.status_code, status.HTTP_200_OK)

        results2 = response2.data if isinstance(response2.data, list) else response2.data.get('results', [])
        ids2 = [item['id'] for item in results2]

        self.assertEqual(len(ids2), 2)
        self.assertIn(inc3.id, ids2)
        self.assertIn(inc4.id, ids2)
        self.assertNotIn(inc1.id, ids2)
        self.assertNotIn(inc2.id, ids2)

    # -------------------------------------------------------------------------
    # 4. Authentication and Role-based Access Control
    # -------------------------------------------------------------------------
    def test_unauthenticated_client_denied(self):
        """Unauthenticated requests to GET or POST must be denied (401 or 403)."""
        unauthenticated_client = APIClient()

        get_res = unauthenticated_client.get(self.url)
        self.assertIn(get_res.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

        post_res = unauthenticated_client.post(self.url, data=self.valid_payload, format='json')
        self.assertIn(post_res.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_admin_user_denied(self):
        """Admin users must be denied access to student incident endpoints (401 or 403)."""
        self.client.force_authenticate(user=self.admin_user)

        get_res = self.client.get(self.url)
        self.assertIn(get_res.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

        post_res = self.client.post(self.url, data=self.valid_payload, format='json')
        self.assertIn(post_res.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_management_user_denied(self):
        """Management users must be denied access to student incident endpoints (401 or 403)."""
        self.client.force_authenticate(user=self.mgmt_user)

        get_res = self.client.get(self.url)
        self.assertIn(get_res.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

        post_res = self.client.post(self.url, data=self.valid_payload, format='json')
        self.assertIn(post_res.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    # -------------------------------------------------------------------------
    # 5. Unsupported HTTP Methods return 405
    # -------------------------------------------------------------------------
    def test_put_patch_delete_methods_not_allowed(self):
        """PUT, PATCH, and DELETE on /api/incidents/ must return 405 Method Not Allowed."""
        self.client.force_authenticate(user=self.student)

        put_res = self.client.put(self.url, data=self.valid_payload, format='json')
        self.assertEqual(put_res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        patch_res = self.client.patch(self.url, data={'category': 'Updated'}, format='json')
        self.assertEqual(patch_res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        delete_res = self.client.delete(self.url)
        self.assertEqual(delete_res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    # -------------------------------------------------------------------------
    # 6. Anonymous flag handling
    # -------------------------------------------------------------------------
    def test_anonymous_incident_stored_correctly_with_real_student(self):
        """
        is_anonymous=True is stored properly on the incident, but reported_by is still
        the real authenticated student.
        """
        self.client.force_authenticate(user=self.student)
        anon_payload = {
            'category': 'Academic Integrity',
            'description': 'Cheating observed during midterm exam',
            'location_text': 'Auditorium A',
            'is_anonymous': True,
        }

        response = self.client.post(self.url, data=anon_payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['is_anonymous'])

        incident = Incident.objects.get(id=response.data['id'])
        self.assertTrue(incident.is_anonymous)
        self.assertEqual(incident.reported_by, self.student)
        self.assertEqual(incident.status, 'Pending')

    def tearDown(self):
        cache.clear()
        super().tearDown()

    # -------------------------------------------------------------------------
    # 7. Rate limiting on incident report submission (POST only)
    # -------------------------------------------------------------------------
    def test_student_can_post_10_reports_and_11th_returns_429(self):
        """
        A student can POST 10 incident reports within the rate-limit window.
        The 11th POST request is throttled and returns HTTP 429 Too Many Requests.
        """
        self.client.force_authenticate(user=self.student)

        for i in range(10):
            response = self.client.post(self.url, data=self.valid_payload, format='json')
            self.assertEqual(
                response.status_code,
                status.HTTP_201_CREATED,
                f"POST #{i + 1} failed unexpectedly with status {response.status_code}"
            )

        # The 11th request must hit the rate limit
        response_11th = self.client.post(self.url, data=self.valid_payload, format='json')
        self.assertEqual(response_11th.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_get_incidents_still_returns_200_after_hitting_rate_limit(self):
        """
        Rate limiting applies strictly to POST requests (creating reports).
        After hitting the 10-report limit, GET requests to list reports must still return 200 OK.
        """
        self.client.force_authenticate(user=self.student)

        # Exhaust the 10-report limit
        for _ in range(10):
            response = self.client.post(self.url, data=self.valid_payload, format='json')
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify POST is throttled
        post_response = self.client.post(self.url, data=self.valid_payload, format='json')
        self.assertEqual(post_response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

        # GET request must not be throttled and return 200 OK
        get_response = self.client.get(self.url)
        self.assertEqual(get_response.status_code, status.HTTP_200_OK)

    def test_second_student_not_affected_when_first_student_throttled(self):
        """
        Throttle is per authenticated user (not per IP).
        When the first student is throttled, a second student is unaffected and can still POST.
        """
        # First student exhausts the throttle limit
        self.client.force_authenticate(user=self.student)
        for _ in range(10):
            response = self.client.post(self.url, data=self.valid_payload, format='json')
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # 11th request for first student is throttled
        response_student1 = self.client.post(self.url, data=self.valid_payload, format='json')
        self.assertEqual(response_student1.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

        # Second student is not affected and can create a report
        self.client.force_authenticate(user=self.other_student)
        response_student2 = self.client.post(self.url, data=self.valid_payload, format='json')
        self.assertEqual(response_student2.status_code, status.HTTP_201_CREATED)


class IncidentMediaUploadTestCase(TestCase):
    """
    Test suite for student incident media upload endpoint (/api/incidents/upload/).
    Verifies Cloudinary upload mocking, file validation, permissions, and error handling.
    """

    def setUp(self):
        # Clear cache between tests as in the other test cases
        cache.clear()
        self.client = APIClient()
        self.url = reverse('incident-media-upload')

        # Test users
        self.student = User.objects.create_user(
            username='upload_student',
            password='testpassword123',
            role='student',
        )
        self.admin_user = User.objects.create_user(
            username='upload_admin',
            password='testpassword123',
            role='admin',
        )

    def tearDown(self):
        cache.clear()
        super().tearDown()

    def test_student_uploads_valid_jpeg(self):
        """
        Student uploads a small valid JPEG file -> returns 201 and
        the returned url equals the mocked secure_url.
        """
        self.client.force_authenticate(user=self.student)
        jpeg_file = SimpleUploadedFile(
            name='photo.jpg',
            content=b'fake jpeg image bytes',
            content_type='image/jpeg',
        )
        mock_response = {
            'secure_url': 'https://res.cloudinary.com/testcloud/image/upload/v1/guardly/incidents/photo.jpg',
            'resource_type': 'image',
        }

        with patch('cloudinary.uploader.upload', return_value=mock_response) as mock_upload:
            response = self.client.post(self.url, {'file': jpeg_file}, format='multipart')

            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            self.assertEqual(response.data['url'], mock_response['secure_url'])
            self.assertEqual(response.data['resource_type'], 'image')
            mock_upload.assert_called_once()

    def test_student_uploads_valid_mp4(self):
        """
        Student uploads a small MP4 video file -> returns 201 and
        the returned url equals the mocked secure_url.
        """
        self.client.force_authenticate(user=self.student)
        mp4_file = SimpleUploadedFile(
            name='evidence.mp4',
            content=b'fake mp4 video bytes',
            content_type='video/mp4',
        )
        mock_response = {
            'secure_url': 'https://res.cloudinary.com/testcloud/video/upload/v1/guardly/incidents/evidence.mp4',
            'resource_type': 'video',
        }

        with patch('cloudinary.uploader.upload', return_value=mock_response) as mock_upload:
            response = self.client.post(self.url, {'file': mp4_file}, format='multipart')

            self.assertEqual(response.status_code, status.HTTP_201_CREATED)
            self.assertEqual(response.data['url'], mock_response['secure_url'])
            self.assertEqual(response.data['resource_type'], 'video')
            mock_upload.assert_called_once()

    def test_unauthenticated_request_denied(self):
        """
        Unauthenticated request must be denied (401 or 403).
        """
        unauthenticated_client = APIClient()
        jpeg_file = SimpleUploadedFile(
            name='photo.jpg',
            content=b'fake jpeg bytes',
            content_type='image/jpeg',
        )
        response = unauthenticated_client.post(self.url, {'file': jpeg_file}, format='multipart')
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_admin_user_denied(self):
        """
        Admin user must be denied access to student upload endpoint (401 or 403).
        """
        self.client.force_authenticate(user=self.admin_user)
        jpeg_file = SimpleUploadedFile(
            name='photo.jpg',
            content=b'fake jpeg bytes',
            content_type='image/jpeg',
        )
        response = self.client.post(self.url, {'file': jpeg_file}, format='multipart')
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_no_file_sent(self):
        """
        Request with no file sent -> returns 400 Bad Request with detail message.
        """
        self.client.force_authenticate(user=self.student)
        response = self.client.post(self.url, {}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data.get('detail'), 'No file was sent.')

    def test_disallowed_file_type(self):
        """
        Uploading a file with disallowed type (e.g. text/plain .txt) -> returns 400 Bad Request.
        """
        self.client.force_authenticate(user=self.student)
        txt_file = SimpleUploadedFile(
            name='document.txt',
            content=b'plain text content',
            content_type='text/plain',
        )
        response = self.client.post(self.url, {'file': txt_file}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(
            response.data.get('detail'),
            'Only photos (JPEG, PNG, WebP) and videos (MP4, MOV) are allowed.',
        )

    def test_file_too_large(self):
        """
        File larger than MAX_UPLOAD_BYTES -> returns 400 Bad Request.
        Patches MAX_UPLOAD_BYTES to 10 bytes and sends a larger file.
        """
        self.client.force_authenticate(user=self.student)
        large_file = SimpleUploadedFile(
            name='photo.jpg',
            content=b'A' * 25,
            content_type='image/jpeg',
        )
        with patch('incidents.uploads.MAX_UPLOAD_BYTES', 10):
            response = self.client.post(self.url, {'file': large_file}, format='multipart')
            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            self.assertEqual(
                response.data.get('detail'),
                'File is too large (50 MB maximum).',
            )

    def test_cloudinary_exception_returns_502_without_leaking_exception_text(self):
        """
        Cloudinary raising an Exception -> returns 502 Bad Gateway,
        and response body does not contain the raw exception text or secrets.
        """
        self.client.force_authenticate(user=self.student)
        jpeg_file = SimpleUploadedFile(
            name='photo.jpg',
            content=b'fake jpeg image bytes',
            content_type='image/jpeg',
        )
        sensitive_exception_message = 'Cloudinary secret api key error: 7knlfKlJhFLqeBnvQcLEKlAnd_k'

        with patch('cloudinary.uploader.upload', side_effect=Exception(sensitive_exception_message)):
            response = self.client.post(self.url, {'file': jpeg_file}, format='multipart')
            self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
            self.assertEqual(response.data.get('detail'), 'Upload failed. Please try again.')
            # Ensure the raw exception text and secrets are not leaked
            self.assertNotIn(sensitive_exception_message, str(response.data))
            self.assertNotIn('7knlfKlJhFLqeBnvQcLEKlAnd_k', str(response.data))


