from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdminOrManagement, IsManagement

from .ml.embedder import get_embedding
from .models import Student


class RegisterFaceView(APIView):
    """Management uploads a tightly cropped face photo for one student."""

    permission_classes = [IsManagement]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, student_id):
        try:
            student = Student.objects.get(pk=student_id)
        except Student.DoesNotExist:
            return Response(
                {"detail": "Student not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        photo = request.FILES.get("photo")
        if photo is None:
            return Response(
                {"detail": "Upload a face photo in the 'photo' field."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            embedding = get_embedding(photo)
        except OSError:
            return Response(
                {"detail": "Could not read the image."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        student.face_embedding = embedding
        student.save(update_fields=["face_embedding"])
        return Response(
            {"student_id": student.id, "embedding_size": len(embedding)},
            status=status.HTTP_200_OK,
        )

class EmbeddingListView(APIView):
    """Admin or management downloads all registered face embeddings."""

    permission_classes = [IsAdminOrManagement]

    def get(self, request):
        students = Student.objects.exclude(face_embedding=[]).order_by("id")
        data = [
            {
                "id": s.id,
                "name": s.name,
                "register_number": s.register_number,
                "face_embedding": s.face_embedding,
            }
            for s in students
        ]
        return Response(data, status=status.HTTP_200_OK)
