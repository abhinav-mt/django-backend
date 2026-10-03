from django.db import models


class Student(models.Model):
    name = models.CharField(max_length=255)
    department = models.CharField(max_length=100)
    register_number = models.CharField(max_length=50, unique=True)
    face_embedding = models.JSONField(default=list, blank=True)
    reference_photo_url = models.URLField(max_length=500, blank=True, null=True)

    def __str__(self):
        return f"{self.name} ({self.register_number})"
