from django.db import models
from django.conf import settings


class Incident(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Under Review', 'Under Review'),
        ('Pending Rejection', 'Pending Rejection'),
        ('Resolved', 'Resolved'),
        ('Rejected', 'Rejected'),
    ]

    category = models.CharField(max_length=100)
    description = models.TextField()
    location_text = models.CharField(max_length=255)
    image_url = models.URLField(max_length=500, blank=True, null=True)
    is_anonymous = models.BooleanField(default=False)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='Pending')
    rejection_reason = models.TextField(blank=True, null=True)
    first_rejected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='first_rejected_incidents'
    )
    second_rejected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='second_rejected_incidents'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='reported_incidents'
    )

    def __str__(self):
        return f"Incident #{self.id} - {self.category} ({self.status})"
