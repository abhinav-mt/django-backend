import secrets
from django.conf import settings
from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    ROLE_CHOICES = [
        ('student', 'Student'),
        ('admin', 'Admin'),
        ('management', 'Management'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='student')


class UserToken(models.Model):
    key = models.CharField(max_length=64, unique=True, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name='auth_tokens',
        on_delete=models.CASCADE,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = secrets.token_hex(32)
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"UserToken({self.user_id}, {self.key[:8]}...)"