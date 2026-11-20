from django.urls import path

from .views import EmbeddingListView, RegisterFaceView

urlpatterns = [
    path("embeddings/", EmbeddingListView.as_view()),
    path("<int:student_id>/face/", RegisterFaceView.as_view()),
]