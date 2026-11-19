from io import BytesIO
from unittest.mock import MagicMock, patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import User
from students.models import Student
from students.views import RegisterFaceView


def fake_photo():
    return SimpleUploadedFile("face.jpg", b"fake-bytes", content_type="image/jpeg")


class RegisterFaceViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = RegisterFaceView.as_view()
        self.management = User(username="m", role="management", is_active=True)
        self.student_user = User(username="s", role="student", is_active=True)

    def _post(self, user, data):
        request = self.factory.post("/api/students/1/face/", data, format="multipart")
        force_authenticate(request, user=user)
        return self.view(request, student_id=1)

    @patch("students.views.get_embedding", return_value=[0.1] * 192)
    @patch("students.views.Student.objects")
    def test_management_can_register_face(self, objects, _embed):
        student = MagicMock(spec=Student, id=1)
        objects.get.return_value = student
        response = self._post(self.management, {"photo": fake_photo()})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["embedding_size"], 192)
        student.save.assert_called_once()

    def test_student_role_is_denied(self):
        response = self._post(self.student_user, {"photo": fake_photo()})
        self.assertEqual(response.status_code, 403)

    @patch("students.views.Student.objects")
    def test_missing_photo_is_400(self, objects):
        objects.get.return_value = MagicMock(spec=Student, id=1)
        response = self._post(self.management, {})
        self.assertEqual(response.status_code, 400)

    @patch("students.views.Student.objects")
    def test_unknown_student_is_404(self, objects):
        objects.get.side_effect = Student.DoesNotExist
        response = self._post(self.management, {"photo": fake_photo()})
        self.assertEqual(response.status_code, 404)