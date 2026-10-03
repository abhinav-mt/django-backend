from django.db import models
from django.conf import settings


class AdminReview(models.Model):
    incident = models.ForeignKey(
        'incidents.Incident',
        on_delete=models.CASCADE,
        related_name='admin_reviews'
    )
    admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='admin_reviews'
    )
    action_taken = models.CharField(max_length=100)
    reason_given = models.TextField(blank=True, null=True)
    reviewed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Review for Incident #{self.incident_id} by {self.admin}"
