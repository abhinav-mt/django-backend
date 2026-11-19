from django.urls import path

from .views import RegisterFaceView

urlpatterns = [
    path("<int:student_id>/face/", RegisterFaceView.as_view()),
]