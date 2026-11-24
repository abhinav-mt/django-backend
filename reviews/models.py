from django.core.exceptions import ValidationError, PermissionDenied
from django.db import models
from django.conf import settings


class AdminReview(models.Model):
    ACTION_CHOICES = [
        ('approve', 'Approve'),
        ('request_more_info', 'Request More Info'),
        ('reject', 'Reject'),
    ]

    incident = models.ForeignKey(
        'incidents.Incident',
        on_delete=models.PROTECT,
        related_name='admin_reviews'
    )
    admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='admin_reviews'
    )
    action_taken = models.CharField(max_length=100, choices=ACTION_CHOICES)
    reason_given = models.TextField(blank=True, null=True)
    reviewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-reviewed_at']
        verbose_name = 'Admin Review'
        verbose_name_plural = 'Admin Reviews'

    def __str__(self):
        return f"Review for Incident #{self.incident_id} by {self.admin} ({self.action_taken})"

    def clean(self):
        if self.action_taken == 'reject' and not (self.reason_given or '').strip():
            raise ValidationError(
                {'reason_given': 'A rejection reason is mandatory when action is "reject".'}
            )

    def save(self, *args, **kwargs):
        if self.pk is not None and not self._state.adding:
            raise PermissionDenied("AdminReview records are insert-only")
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise PermissionDenied("AdminReview records are insert-only")
