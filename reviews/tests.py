from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import models
from django.db.models.deletion import ProtectedError
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from incidents.models import Incident
from reviews.admin import AdminReviewAdmin
from reviews.audit import GENESIS_HASH, append_review, compute_entry_hash
from reviews.models import AdminReview

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
            prev_hash='0' * 64,
            entry_hash='a' * 64,
        )

        self.assertEqual(review.incident, self.incident)
        self.assertEqual(review.incident.id, 42)
        self.assertEqual(review.admin, self.admin_user)
        self.assertEqual(review.admin.username, 'admin_alice')
        self.assertEqual(review.action_taken, 'approve')
        self.assertEqual(review.reason_given, 'Handrail repaired by maintenance crew.')
        self.assertEqual(review.prev_hash, '0' * 64)
        self.assertEqual(review.entry_hash, 'a' * 64)

    def test_str_representation(self):
        """Verify __str__ output matches the expected format."""
        review = AdminReview(
            id=102,
            incident=self.incident,
            admin=self.admin_user,
            action_taken='approve',
            reason_given='Looks good.',
            prev_hash='0' * 64,
            entry_hash='b' * 64,
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
            prev_hash='0' * 64,
            entry_hash='c' * 64,
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
            prev_hash='0' * 64,
            entry_hash='d' * 64,
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
            prev_hash='0' * 64,
            entry_hash='e' * 64,
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
            prev_hash='0' * 64,
            entry_hash='f' * 64,
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
            prev_hash='0' * 64,
            entry_hash='g' * 64,
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
            prev_hash='0' * 64,
            entry_hash='h' * 64,
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
        """Helper: create an AdminReview using append_review from reviews.audit."""
        defaults = dict(
            incident=self.incident,
            admin=self.admin_user,
            action_taken='approve',
            reason_given='Looks fine.',
        )
        defaults.update(kwargs)
        return append_review(**defaults)

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
            prev_hash='0' * 64,
            entry_hash='1' * 64,
        )
        with self.assertRaises(ValidationError):
            review.save()

    def test_approve_with_empty_reason_saves_successfully(self):
        """Creating a new 'approve' review with no reason must succeed using append_review."""
        review = append_review(
            incident=self.incident,
            admin=self.admin_user,
            action_taken='approve',
            reason_given='',
        )
        self.assertIsNotNone(review.pk)
        self.assertEqual(review.action_taken, 'approve')
        self.assertEqual(review.reason_given, '')

    def test_invalid_action_taken_fails_validation(self):
        """An action_taken value not in ACTION_CHOICES must fail validation."""
        review = AdminReview(
            incident=self.incident,
            admin=self.admin_user,
            action_taken='invalid_action',
            reason_given='Some reason.',
            prev_hash='0' * 64,
            entry_hash='1' * 64,
        )
        with self.assertRaises(ValidationError):
            review.full_clean()


class AuditLogTestCase(TestCase):
    """
    Test suite for hash-chain audit logging in reviews/audit.py.
    """

    def setUp(self):
        self.admin_user = User.objects.create_user(
            username='audit_admin',
            password='testpass123',
        )
        self.incident = Incident.objects.create(
            category='Security',
            description='Unauthorized access attempt.',
            location_text='Server Room B',
            status='Pending',
            reported_by=self.admin_user,
        )

    def test_compute_entry_hash_deterministic_and_input_sensitive(self):
        """
        2.a: compute_entry_hash returns the same value for the same inputs,
        and a different value if any one of prev_hash, incident_id, admin_id,
        action_taken, reason_given or reviewed_at changes.
        """
        base_time = timezone.now()
        base_hash = compute_entry_hash(
            prev_hash=GENESIS_HASH,
            incident_id=self.incident.id,
            admin_id=self.admin_user.id,
            action_taken='approve',
            reason_given='All verified',
            reviewed_at=base_time,
        )

        # Same inputs produce same hash
        same_hash = compute_entry_hash(
            prev_hash=GENESIS_HASH,
            incident_id=self.incident.id,
            admin_id=self.admin_user.id,
            action_taken='approve',
            reason_given='All verified',
            reviewed_at=base_time,
        )
        self.assertEqual(base_hash, same_hash)

        # Different prev_hash
        diff_prev = compute_entry_hash(
            prev_hash='1' * 64,
            incident_id=self.incident.id,
            admin_id=self.admin_user.id,
            action_taken='approve',
            reason_given='All verified',
            reviewed_at=base_time,
        )
        self.assertNotEqual(base_hash, diff_prev)

        # Different incident_id
        diff_incident = compute_entry_hash(
            prev_hash=GENESIS_HASH,
            incident_id=self.incident.id + 999,
            admin_id=self.admin_user.id,
            action_taken='approve',
            reason_given='All verified',
            reviewed_at=base_time,
        )
        self.assertNotEqual(base_hash, diff_incident)

        # Different admin_id
        diff_admin = compute_entry_hash(
            prev_hash=GENESIS_HASH,
            incident_id=self.incident.id,
            admin_id=self.admin_user.id + 999,
            action_taken='approve',
            reason_given='All verified',
            reviewed_at=base_time,
        )
        self.assertNotEqual(base_hash, diff_admin)

        # Different action_taken
        diff_action = compute_entry_hash(
            prev_hash=GENESIS_HASH,
            incident_id=self.incident.id,
            admin_id=self.admin_user.id,
            action_taken='reject',
            reason_given='All verified',
            reviewed_at=base_time,
        )
        self.assertNotEqual(base_hash, diff_action)

        # Different reason_given
        diff_reason = compute_entry_hash(
            prev_hash=GENESIS_HASH,
            incident_id=self.incident.id,
            admin_id=self.admin_user.id,
            action_taken='approve',
            reason_given='Completely different reason',
            reviewed_at=base_time,
        )
        self.assertNotEqual(base_hash, diff_reason)

        # Different reviewed_at
        diff_time = compute_entry_hash(
            prev_hash=GENESIS_HASH,
            incident_id=self.incident.id,
            admin_id=self.admin_user.id,
            action_taken='approve',
            reason_given='All verified',
            reviewed_at=base_time + timedelta(seconds=10),
        )
        self.assertNotEqual(base_hash, diff_time)

        # reason_given None is treated as empty string
        none_reason_hash = compute_entry_hash(
            prev_hash=GENESIS_HASH,
            incident_id=self.incident.id,
            admin_id=self.admin_user.id,
            action_taken='approve',
            reason_given=None,
            reviewed_at=base_time,
        )
        empty_reason_hash = compute_entry_hash(
            prev_hash=GENESIS_HASH,
            incident_id=self.incident.id,
            admin_id=self.admin_user.id,
            action_taken='approve',
            reason_given='',
            reviewed_at=base_time,
        )
        self.assertEqual(none_reason_hash, empty_reason_hash)

    def test_first_append_review_uses_genesis_hash(self):
        """
        2.b: The first append_review on an empty table uses prev_hash == GENESIS_HASH.
        """
        self.assertEqual(AdminReview.objects.count(), 0)
        review1 = append_review(
            incident=self.incident,
            admin=self.admin_user,
            action_taken='approve',
            reason_given='Initial approval',
        )
        self.assertEqual(review1.prev_hash, GENESIS_HASH)
        self.assertIsNotNone(review1.entry_hash)
        self.assertEqual(len(review1.entry_hash), 64)

    def test_second_append_review_prev_hash_equals_first_entry_hash(self):
        """
        2.c: The second append_review's prev_hash equals the first entry's entry_hash.
        """
        review1 = append_review(
            incident=self.incident,
            admin=self.admin_user,
            action_taken='approve',
            reason_given='First entry',
        )
        review2 = append_review(
            incident=self.incident,
            admin=self.admin_user,
            action_taken='request_more_info',
            reason_given='Second entry asking details',
        )
        self.assertEqual(review2.prev_hash, review1.entry_hash)

        # Also verify a third entry links to the second entry
        review3 = append_review(
            incident=self.incident,
            admin=self.admin_user,
            action_taken='approve',
            reason_given='Third entry',
        )
        self.assertEqual(review3.prev_hash, review2.entry_hash)

    def test_recomputing_hash_from_stored_fields_equals_entry_hash(self):
        """
        2.d: Recomputing compute_entry_hash from the stored fields of any saved row equals its stored entry_hash.
        """
        review = append_review(
            incident=self.incident,
            admin=self.admin_user,
            action_taken='approve',
            reason_given='Audited review',
        )
        # Fetch fresh instance from DB
        db_review = AdminReview.objects.get(pk=review.pk)
        recomputed = compute_entry_hash(
            prev_hash=db_review.prev_hash,
            incident_id=db_review.incident_id,
            admin_id=db_review.admin_id,
            action_taken=db_review.action_taken,
            reason_given=db_review.reason_given,
            reviewed_at=db_review.reviewed_at,
        )
        self.assertEqual(recomputed, db_review.entry_hash)

    def test_append_review_reject_with_empty_reason_raises_validation_error_and_creates_no_row(self):
        """
        2.e: append_review with action 'reject' and an empty reason raises a validation error and creates no row.
        """
        initial_count = AdminReview.objects.count()

        # Test empty string reason
        with self.assertRaises(ValidationError):
            append_review(
                incident=self.incident,
                admin=self.admin_user,
                action_taken='reject',
                reason_given='',
            )
        self.assertEqual(AdminReview.objects.count(), initial_count)

        # Test whitespace-only reason
        with self.assertRaises(ValidationError):
            append_review(
                incident=self.incident,
                admin=self.admin_user,
                action_taken='reject',
                reason_given='   ',
            )
        self.assertEqual(AdminReview.objects.count(), initial_count)

        # Test None reason
        with self.assertRaises(ValidationError):
            append_review(
                incident=self.incident,
                admin=self.admin_user,
                action_taken='reject',
                reason_given=None,
            )
        self.assertEqual(AdminReview.objects.count(), initial_count)

    def test_creating_admin_review_directly_with_empty_hashes_fails_validation(self):
        """
        2.f: Creating an AdminReview directly with empty prev_hash/entry_hash fails validation.
        """
        # Empty string prev_hash and entry_hash
        review_empty = AdminReview(
            incident=self.incident,
            admin=self.admin_user,
            action_taken='approve',
            reason_given='Valid reason',
            prev_hash='',
            entry_hash='',
        )
        with self.assertRaises(ValidationError) as cm:
            review_empty.full_clean()
        self.assertIn('prev_hash', cm.exception.message_dict)
        self.assertIn('entry_hash', cm.exception.message_dict)

        # Omitted (empty) prev_hash and entry_hash
        review_omitted = AdminReview(
            incident=self.incident,
            admin=self.admin_user,
            action_taken='approve',
            reason_given='Valid reason',
        )
        with self.assertRaises(ValidationError) as cm:
            review_omitted.full_clean()
        self.assertIn('prev_hash', cm.exception.message_dict)
        self.assertIn('entry_hash', cm.exception.message_dict)
