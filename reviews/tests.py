from django.test import SimpleTestCase
from django.db import models

from accounts.models import User
from incidents.models import Incident
from reviews.models import AdminReview


class AdminReviewModelUnitTestCase(SimpleTestCase):
    """
    Unit test suite for the AdminReview model.
    Validates model fields, foreign key configurations, choices,
    meta options, and string representations without requiring database access.
    """

    def setUp(self):
        # Create unsaved instances for in-memory model testing
        self.admin_user = User(id=1, username='admin_alice', role='admin')
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
            action_taken='Resolved',
            reason_given='Handrail repaired by maintenance crew.',
        )

        self.assertEqual(review.incident, self.incident)
        self.assertEqual(review.incident.id, 42)
        self.assertEqual(review.admin, self.admin_user)
        self.assertEqual(review.admin.username, 'admin_alice')
        self.assertEqual(review.action_taken, 'Resolved')
        self.assertEqual(review.reason_given, 'Handrail repaired by maintenance crew.')

    def test_str_representation(self):
        """Verify __str__ output matches the expected format."""
        review = AdminReview(
            id=102,
            incident=self.incident,
            admin=self.admin_user,
            action_taken='Under Review',
            reason_given='Assigned to campus safety officer.',
        )

        expected_str = "Review for Incident #42 by admin_alice (Under Review)"
        self.assertEqual(str(review), expected_str)

    def test_foreign_key_configurations(self):
        """Verify incident and admin foreign keys have correct on_delete and related_name."""
        incident_field = AdminReview._meta.get_field('incident')
        admin_field = AdminReview._meta.get_field('admin')

        # Check model targets
        self.assertEqual(incident_field.remote_field.model, Incident)
        self.assertEqual(admin_field.remote_field.model, User)

        # Check cascading deletion
        self.assertEqual(incident_field.remote_field.on_delete, models.CASCADE)
        self.assertEqual(admin_field.remote_field.on_delete, models.CASCADE)

        # Check reverse relationship names
        self.assertEqual(incident_field.remote_field.related_name, 'admin_reviews')
        self.assertEqual(admin_field.remote_field.related_name, 'admin_reviews')

    def test_action_taken_choices(self):
        """Verify ACTION_CHOICES contains the expected Guardly review actions."""
        choices_dict = dict(AdminReview.ACTION_CHOICES)
        self.assertIn('Under Review', choices_dict)
        self.assertIn('Pending Rejection', choices_dict)
        self.assertIn('Resolved', choices_dict)
        self.assertIn('Rejected', choices_dict)

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
            action_taken='Resolved',
            reason_given=None,
        )
        self.assertIsNone(review.reason_given)
