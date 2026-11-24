from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import models
from django.db.models.deletion import ProtectedError
from django.test import SimpleTestCase, TestCase

from incidents.models import Incident
from reviews.models import AdminReview
from reviews.admin import AdminReviewAdmin

User = get_user_model()


class AdminReviewModelUnitTestCase(SimpleTestCase):
    """
    Unit test suite for the AdminReview model.
    Validates model fields, foreign key configurations, choices,
    meta options, and string representations without requiring database access.
    """

    def setUp(self):
        # Create unsaved instances for in-memory model testing
        self.admin_user = User(id=1, username='admin_alice')
        self.incident = Incident(
            id=42,
            category='Safety Hazard',
            description='Broken handrail near stairwell B.',
            location_text='Building 3, Stairwell B',
            status='Pending',
            reported_by=self.admin_user,
        )

    def test_admin_review_instantiation_and_fields(self):
        """Verify AdminReview can be instantiated with all required fields."""
        review = AdminReview(
            id=101,
            incident=self.incident,
            admin=self.admin_user,
            action_taken='approve',
            reason_given='Handrail repaired by maintenance crew.',
        )

        self.assertEqual(review.incident, self.incident)
        self.assertEqual(review.incident.id, 42)
        self.assertEqual(review.admin, self.admin_user)
        self.assertEqual(review.admin.username, 'admin_alice')
        self.assertEqual(review.action_taken, 'approve')
        self.assertEqual(review.reason_given, 'Handrail repaired by maintenance crew.')

    def test_str_representation(self):
        """Verify __str__ output matches the expected format."""
        review = AdminReview(
            id=102,
            incident=self.incident,
            admin=self.admin_user,
            action_taken='approve',
            reason_given='Looks good.',
        )

        expected_str = "Review for Incident #42 by admin_alice (approve)"
        self.assertEqual(str(review), expected_str)

    def test_foreign_key_configurations(self):
        """Verify incident and admin foreign keys have correct on_delete and related_name."""
        incident_field = AdminReview._meta.get_field('incident')
        admin_field = AdminReview._meta.get_field('admin')

        # Check model targets
        self.assertEqual(incident_field.remote_field.model, Incident)
        self.assertEqual(admin_field.remote_field.model, User)

        # Check PROTECT (not CASCADE) - records must never be silently deleted
        self.assertEqual(incident_field.remote_field.on_delete, models.PROTECT)
        self.assertEqual(admin_field.remote_field.on_delete, models.PROTECT)

        # Check reverse relationship names
        self.assertEqual(incident_field.remote_field.related_name, 'admin_reviews')
        self.assertEqual(admin_field.remote_field.related_name, 'admin_reviews')

    def test_action_taken_choices(self):
        """Verify ACTION_CHOICES contains only the three admin decision actions."""
        choices_dict = dict(AdminReview.ACTION_CHOICES)
        self.assertIn('approve', choices_dict)
        self.assertIn('request_more_info', choices_dict)
        self.assertIn('reject', choices_dict)
        # Old status-style choices must NOT be present
        self.assertNotIn('Under Review', choices_dict)
        self.assertNotIn('Pending Rejection', choices_dict)
        self.assertNotIn('Resolved', choices_dict)
        self.assertNotIn('Rejected', choices_dict)

    def test_meta_options(self):
        """Verify model ordering and verbose names in Meta."""
        self.assertEqual(AdminReview._meta.ordering, ['-reviewed_at'])
        self.assertEqual(AdminReview._meta.verbose_name, 'Admin Review')
        self.assertEqual(AdminReview._meta.verbose_name_plural, 'Admin Reviews')

    def test_reason_given_can_be_blank_or_null(self):
        """Verify reason_given field allows blank and null values."""
        reason_field = AdminReview._meta.get_field('reason_given')
        self.assertTrue(reason_field.blank)
        self.assertTrue(reason_field.null)

        review = AdminReview(
            id=103,
            incident=self.incident,
            admin=self.admin_user,
            action_taken='approve',
            reason_given=None,
        )
        self.assertIsNone(review.reason_given)

    def test_action_taken_is_required(self):
        """Verify action_taken field does not allow blank."""
        action_field = AdminReview._meta.get_field('action_taken')
        self.assertFalse(action_field.blank)

    # --- clean() validation tests (no DB needed) ---

    def test_reject_with_empty_reason_fails_validation(self):
        """Rejecting without a reason must raise ValidationError."""
        review = AdminReview(
            incident=self.incident,
            admin=self.admin_user,
            action_taken='reject',
            reason_given='',
        )
        with self.assertRaises(ValidationError):
            review.clean()

    def test_reject_with_whitespace_only_reason_fails_validation(self):
        """Rejecting with only whitespace in reason must raise ValidationError."""
        review = AdminReview(
            incident=self.incident,
            admin=self.admin_user,
            action_taken='reject',
            reason_given='   ',
        )
        with self.assertRaises(ValidationError):
            review.clean()

    def test_reject_with_none_reason_fails_validation(self):
        """Rejecting with None reason must raise ValidationError."""
        review = AdminReview(
            incident=self.incident,
            admin=self.admin_user,
            action_taken='reject',
            reason_given=None,
        )
        with self.assertRaises(ValidationError):
            review.clean()

    def test_approve_with_empty_reason_passes_validation(self):
        """Approving without a reason is allowed."""
        review = AdminReview(
            incident=self.incident,
            admin=self.admin_user,
            action_taken='approve',
            reason_given='',
        )
        # Should not raise
        review.clean()

    def test_request_more_info_with_empty_reason_passes_validation(self):
        """'request_more_info' action without a reason is allowed."""
        review = AdminReview(
            incident=self.incident,
            admin=self.admin_user,
            action_taken='request_more_info',
            reason_given=None,
        )
        # Should not raise
        review.clean()

    # --- Admin panel permission tests ---

    def test_admin_panel_has_add_permission_returns_false(self):
        admin_panel = AdminReviewAdmin(AdminReview, None)
        self.assertFalse(admin_panel.has_add_permission(request=None))

    def test_admin_panel_has_change_permission_returns_false(self):
        admin_panel = AdminReviewAdmin(AdminReview, None)
        self.assertFalse(admin_panel.has_change_permission(request=None))

    def test_admin_panel_has_delete_permission_returns_false(self):
        admin_panel = AdminReviewAdmin(AdminReview, None)
        self.assertFalse(admin_panel.has_delete_permission(request=None))

    def test_admin_panel_all_fields_readonly(self):
        """All model fields must appear in readonly_fields."""
        admin_panel = AdminReviewAdmin(AdminReview, None)
        expected = {'incident', 'admin', 'action_taken', 'reason_given', 'reviewed_at'}
        self.assertTrue(expected.issubset(set(admin_panel.readonly_fields)))


class AdminReviewIntegrationTestCase(TestCase):
    """
    Integration tests that require a real database.
    Tests PROTECT behaviour, insert-only enforcement, and validation via save().
    """

    def setUp(self):
        self.admin_user = User.objects.create_user(
            username='admin_bob',
            password='testpass123',
        )
        self.incident = Incident.objects.create(
            category='Fire Hazard',
            description='Blocked emergency exit.',
            location_text='Block A, Floor 2',
            status='Pending',
            reported_by=self.admin_user,
        )

    def _make_review(self, **kwargs):
        """Helper: create an AdminReview using direct super().save() to bypass our guard."""
        defaults = dict(
            incident=self.incident,
            admin=self.admin_user,
            action_taken='approve',
            reason_given='Looks fine.',
        )
        defaults.update(kwargs)
        review = AdminReview(**defaults)
        # Bypass the custom save() so we can create a saved record for update/delete tests
        super(AdminReview, review).save()
        return review

    # --- PROTECT tests ---

    def test_delete_incident_with_review_raises_protected_error(self):
        """Deleting an Incident that has an AdminReview must raise ProtectedError."""
        self._make_review()
        with self.assertRaises(ProtectedError):
            self.incident.delete()

    def test_delete_admin_user_with_review_raises_protected_error(self):
        """Deleting the admin User that has an AdminReview must raise ProtectedError."""
        self._make_review()
        with self.assertRaises(ProtectedError):
            self.admin_user.delete()

    # --- Insert-only enforcement tests ---

    def test_saving_existing_review_raises_permission_denied(self):
        """Calling save() on an already-saved AdminReview must raise PermissionDenied."""
        review = self._make_review()
        self.assertIsNotNone(review.pk)
        with self.assertRaises(PermissionDenied):
            review.save()

    def test_delete_on_review_instance_raises_permission_denied(self):
        """Calling delete() on an AdminReview instance must raise PermissionDenied."""
        review = self._make_review()
        with self.assertRaises(PermissionDenied):
            review.delete()

    # --- Validation via save() on new record ---

    def test_reject_with_empty_reason_fails_on_save(self):
        """Creating a new 'reject' review with no reason must fail via full_clean() in save()."""
        review = AdminReview(
            incident=self.incident,
            admin=self.admin_user,
            action_taken='reject',
            reason_given='',
        )
        with self.assertRaises(ValidationError):
            review.save()

    def test_approve_with_empty_reason_saves_successfully(self):
        """Creating a new 'approve' review with no reason must succeed."""
        review = AdminReview(
            incident=self.incident,
            admin=self.admin_user,
            action_taken='approve',
            reason_given='',
        )
        review.save()  # Should not raise
        self.assertIsNotNone(review.pk)

    def test_invalid_action_taken_fails_validation(self):
        """An action_taken value not in ACTION_CHOICES must fail validation."""
        review = AdminReview(
            incident=self.incident,
            admin=self.admin_user,
            action_taken='invalid_action',
            reason_given='Some reason.',
        )
        with self.assertRaises(ValidationError):
            review.full_clean()
