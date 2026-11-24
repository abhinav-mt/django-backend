from django.contrib import admin
from .models import AdminReview


@admin.register(AdminReview)
class AdminReviewAdmin(admin.ModelAdmin):
    list_display = ('id', 'incident', 'admin', 'action_taken', 'reviewed_at')
    list_filter = ('action_taken', 'reviewed_at')
    search_fields = ('incident__id', 'incident__category', 'admin__username', 'reason_given')
    readonly_fields = ('reviewed_at',)
