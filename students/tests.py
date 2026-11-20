from types import SimpleNamespace
from io import BytesIO
from unittest.mock import MagicMock, patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory, force_authenticate

from accounts.models import User
from students.models import Student
from students.views import EmbeddingListView, RegisterFaceView


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

class EmbeddingListViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.view = EmbeddingListView.as_view()
        self.admin = User(username="a", role="admin", is_active=True)
        self.management = User(username="m", role="management", is_active=True)
        self.student_user = User(username="s", role="student", is_active=True)

    def _get(self, user):
        request = self.factory.get("/api/students/embeddings/")
        force_authenticate(request, user=user)
        return self.view(request)

    @patch("students.views.Student.objects")
    def test_admin_gets_embeddings(self, objects):
        row = SimpleNamespace(
            id=1, name="Nicto", register_number="R1", face_embedding=[0.1] * 192
        )
        objects.exclude.return_value.order_by.return_value = [row]
        response = self._get(self.admin)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(len(response.data[0]["face_embedding"]), 192)

    @patch("students.views.Student.objects")
    def test_management_is_allowed(self, objects):
        objects.exclude.return_value.order_by.return_value = []
        response = self._get(self.management)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])

    def test_student_role_is_denied(self):
        response = self._get(self.student_user)
        self.assertEqual(response.status_code, 403)
