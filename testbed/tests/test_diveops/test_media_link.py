"""Tests for MediaLink model and service.

TDD: These tests are written FIRST before implementation.
Expected to fail initially until model and service are implemented.
"""

import pytest
from datetime import timedelta
from decimal import Decimal
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.utils import timezone

from django_documents.models import Document, MediaAsset, MediaKind


# =============================================================================
# Fixtures for MediaLink tests
# =============================================================================

@pytest.fixture
def document(db):
    """Create a test document."""
    test_file = SimpleUploadedFile(
        "test_photo.jpg",
        b"fake image content",
        content_type="image/jpeg"
    )
    return Document.objects.create(
        file=test_file,
        filename="test_photo.jpg",
        content_type="image/jpeg",
        file_size=18,
        document_type="photo",
        category="image",
    )


@pytest.fixture
def media_asset(db, document):
    """Create a MediaAsset for testing."""
    return MediaAsset.objects.create(
        document=document,
        kind=MediaKind.IMAGE,
        width=1920,
        height=1080,
    )


@pytest.fixture
def excursion_with_site(db, dive_shop, dive_site, encounter_definition, user):
    """Create an excursion with a dive site."""
    from primitives_testbed.diveops.models import Excursion

    tomorrow = timezone.now() + timedelta(days=1)

    return Excursion.objects.create(
        dive_shop=dive_shop,
        dive_site=dive_site,
        departure_time=tomorrow,
        return_time=tomorrow + timedelta(hours=4),
        max_divers=8,
        price_per_diver=Decimal("100.00"),
        currency="USD",
        created_by=user,
    )


@pytest.fixture
def excursion_with_roster(db, dive_shop, dive_site, encounter_definition, user, diver_profile, beginner_diver):
    """Create an excursion with divers via confirmed bookings.

    Note: ExcursionRoster requires a booking, so we use bookings here.
    The service will fall back to bookings when roster is empty.
    """
    from primitives_testbed.diveops.models import Excursion, Booking

    tomorrow = timezone.now() + timedelta(days=1)

    excursion = Excursion.objects.create(
        dive_shop=dive_shop,
        dive_site=dive_site,
        departure_time=tomorrow,
        return_time=tomorrow + timedelta(hours=4),
        max_divers=8,
        price_per_diver=Decimal("100.00"),
        currency="USD",
        created_by=user,
    )

    # Add divers via confirmed bookings (service falls back to this)
    Booking.objects.create(
        excursion=excursion,
        diver=diver_profile,
        status="confirmed",
        booked_by=user,
    )
    Booking.objects.create(
        excursion=excursion,
        diver=beginner_diver,
        status="confirmed",
        booked_by=user,
    )

    return excursion


@pytest.fixture
def diver(diver_profile):
    """Alias for diver_profile fixture."""
    return diver_profile


# =============================================================================
# Test MediaLink Model Constraints
# =============================================================================

@pytest.mark.django_db
class TestMediaLinkConstraints:
    """Test that direct and derived links can coexist."""

    def test_direct_and_derived_link_to_same_diver_allowed(self, media_asset, diver, excursion):
        """Both direct and derived links to same diver should work."""
        from primitives_testbed.diveops.models import MediaLink, MediaLinkSource, DiverProfile

        diver_ct = ContentType.objects.get_for_model(DiverProfile)

        # Create direct link
        direct_link = MediaLink.objects.create(
            media_asset=media_asset,
            content_type=diver_ct,
            object_id=str(diver.pk),
            link_source=MediaLinkSource.DIRECT,
        )

        # Create derived link from excursion - should NOT conflict
        derived_link = MediaLink.objects.create(
            media_asset=media_asset,
            content_type=diver_ct,
            object_id=str(diver.pk),
            link_source=MediaLinkSource.DERIVED_FROM_EXCURSION,
            source_excursion=excursion,
        )

        assert direct_link.pk != derived_link.pk
        assert MediaLink.objects.filter(
            media_asset=media_asset,
            object_id=str(diver.pk),
        ).count() == 2

    def test_duplicate_direct_link_rejected(self, media_asset, diver):
        """Two direct links to same target should be rejected."""
        from primitives_testbed.diveops.models import MediaLink, MediaLinkSource, DiverProfile

        diver_ct = ContentType.objects.get_for_model(DiverProfile)

        MediaLink.objects.create(
            media_asset=media_asset,
            content_type=diver_ct,
            object_id=str(diver.pk),
            link_source=MediaLinkSource.DIRECT,
        )

        with pytest.raises(IntegrityError):
            MediaLink.objects.create(
                media_asset=media_asset,
                content_type=diver_ct,
                object_id=str(diver.pk),
                link_source=MediaLinkSource.DIRECT,
            )

    def test_duplicate_derived_from_same_excursion_rejected(self, media_asset, diver, excursion):
        """Two derived links from same excursion to same target should be rejected."""
        from primitives_testbed.diveops.models import MediaLink, MediaLinkSource, DiverProfile

        diver_ct = ContentType.objects.get_for_model(DiverProfile)

        MediaLink.objects.create(
            media_asset=media_asset,
            content_type=diver_ct,
            object_id=str(diver.pk),
            link_source=MediaLinkSource.DERIVED_FROM_EXCURSION,
            source_excursion=excursion,
        )

        with pytest.raises(IntegrityError):
            MediaLink.objects.create(
                media_asset=media_asset,
                content_type=diver_ct,
                object_id=str(diver.pk),
                link_source=MediaLinkSource.DERIVED_FROM_EXCURSION,
                source_excursion=excursion,
            )


# =============================================================================
# Test link_media_to_excursion Service
# =============================================================================

@pytest.mark.django_db
class TestLinkMediaToExcursion:
    """Test excursion linking with cascade."""

    def test_creates_excursion_link(self, media_asset, excursion):
        """Should create direct link to excursion."""
        from primitives_testbed.diveops.media_link_service import link_media_to_excursion
        from primitives_testbed.diveops.models import MediaLink, MediaLinkSource, Excursion

        link = link_media_to_excursion(media_asset, excursion, cascade=False)

        assert link.link_source == MediaLinkSource.DIRECT
        excursion_ct = ContentType.objects.get_for_model(Excursion)
        assert link.content_type == excursion_ct
        assert link.object_id == str(excursion.pk)

    def test_creates_derived_diver_links(self, media_asset, excursion_with_roster):
        """Should create derived links to all divers from bookings."""
        from primitives_testbed.diveops.media_link_service import link_media_to_excursion
        from primitives_testbed.diveops.models import MediaLink, MediaLinkSource, DiverProfile

        link_media_to_excursion(media_asset, excursion_with_roster)

        diver_ct = ContentType.objects.get_for_model(DiverProfile)
        diver_links = MediaLink.objects.filter(
            media_asset=media_asset,
            content_type=diver_ct,
            link_source=MediaLinkSource.DERIVED_FROM_EXCURSION,
            source_excursion=excursion_with_roster,
        )

        # Service falls back to confirmed bookings when roster is empty
        booking_count = excursion_with_roster.bookings.filter(
            status__in=['confirmed', 'checked_in']
        ).count()
        assert diver_links.count() == booking_count
        assert booking_count == 2  # From fixture setup

    def test_creates_derived_dive_site_link(self, media_asset, excursion_with_site):
        """Should create derived link to dive site."""
        from primitives_testbed.diveops.media_link_service import link_media_to_excursion
        from primitives_testbed.diveops.models import MediaLink, MediaLinkSource, DiveSite

        link_media_to_excursion(media_asset, excursion_with_site)

        site_ct = ContentType.objects.get_for_model(DiveSite)
        site_link = MediaLink.objects.filter(
            media_asset=media_asset,
            content_type=site_ct,
            link_source=MediaLinkSource.DERIVED_FROM_EXCURSION,
            source_excursion=excursion_with_site,
        ).first()

        assert site_link is not None
        assert site_link.object_id == str(excursion_with_site.dive_site_id)

    def test_sets_captured_at_from_excursion(self, media_asset, excursion_with_site):
        """Should set captured_at from excursion departure_time if not set."""
        from primitives_testbed.diveops.media_link_service import link_media_to_excursion

        assert media_asset.captured_at is None

        link_media_to_excursion(media_asset, excursion_with_site)

        media_asset.refresh_from_db()
        assert media_asset.captured_at is not None
        assert media_asset.captured_at == excursion_with_site.departure_time

    def test_idempotent_linking(self, media_asset, excursion_with_site):
        """Linking same media to same excursion twice should not create duplicates."""
        from primitives_testbed.diveops.media_link_service import link_media_to_excursion
        from primitives_testbed.diveops.models import MediaLink

        link1 = link_media_to_excursion(media_asset, excursion_with_site)
        link2 = link_media_to_excursion(media_asset, excursion_with_site)

        assert link1.pk == link2.pk
        assert MediaLink.objects.filter(media_asset=media_asset).count() == 2  # Excursion + site


# =============================================================================
# Test unlink_media_from_excursion Service
# =============================================================================

@pytest.mark.django_db
class TestUnlinkMediaFromExcursion:
    """Test excursion unlinking with cascade."""

    def test_unlink_cascades_derived_but_not_direct(self, media_asset, excursion_with_roster, diver):
        """Unlink should remove derived links but leave direct links intact."""
        from primitives_testbed.diveops.media_link_service import (
            link_media_to_excursion,
            unlink_media_from_excursion,
            link_media_direct,
        )
        from primitives_testbed.diveops.models import MediaLink, MediaLinkSource

        # Link to excursion (creates derived links)
        link_media_to_excursion(media_asset, excursion_with_roster)

        # Also create a direct link to same diver
        direct_link = link_media_direct(media_asset, diver)

        # Verify both exist
        assert MediaLink.objects.filter(
            media_asset=media_asset,
            link_source=MediaLinkSource.DERIVED_FROM_EXCURSION,
        ).exists()

        # Unlink excursion
        deleted = unlink_media_from_excursion(media_asset, excursion_with_roster, cascade_derived=True)

        # Should have deleted: 1 excursion link + 2 diver links + 1 site link = 4
        assert deleted >= 3

        # Direct link should still exist
        assert MediaLink.objects.filter(pk=direct_link.pk).exists()

        # Derived links should be gone
        assert not MediaLink.objects.filter(
            media_asset=media_asset,
            link_source=MediaLinkSource.DERIVED_FROM_EXCURSION,
            source_excursion=excursion_with_roster,
        ).exists()

    def test_unlink_without_cascade_preserves_derived(self, media_asset, excursion_with_roster):
        """Unlink without cascade should only remove excursion link."""
        from primitives_testbed.diveops.media_link_service import (
            link_media_to_excursion,
            unlink_media_from_excursion,
        )
        from primitives_testbed.diveops.models import MediaLink, MediaLinkSource

        link_media_to_excursion(media_asset, excursion_with_roster)

        # Count derived links before
        derived_count = MediaLink.objects.filter(
            media_asset=media_asset,
            link_source=MediaLinkSource.DERIVED_FROM_EXCURSION,
        ).count()

        # Unlink without cascade
        unlink_media_from_excursion(media_asset, excursion_with_roster, cascade_derived=False)

        # Derived links should still exist
        assert MediaLink.objects.filter(
            media_asset=media_asset,
            link_source=MediaLinkSource.DERIVED_FROM_EXCURSION,
        ).count() == derived_count


# =============================================================================
# Test Virtual Folder Query Helpers
# =============================================================================

@pytest.mark.django_db
class TestVirtualFolderQueries:
    """Test query helpers for virtual folders."""

    def test_get_media_by_excursion_returns_correct_assets(self, media_asset, excursion):
        """Should return media linked to excursion."""
        from primitives_testbed.diveops.media_link_service import (
            link_media_to_excursion,
            get_media_by_excursion,
        )

        link_media_to_excursion(media_asset, excursion, cascade=False)

        result = list(get_media_by_excursion(excursion))

        assert media_asset in result

    def test_get_media_by_diver_returns_correct_assets(self, media_asset, diver):
        """Should return media linked to diver."""
        from primitives_testbed.diveops.media_link_service import (
            link_media_direct,
            get_media_by_diver,
        )

        link_media_direct(media_asset, diver)

        result = list(get_media_by_diver(diver))

        assert media_asset in result

    def test_get_media_by_dive_site_returns_correct_assets(self, media_asset, dive_site):
        """Should return media linked to dive site."""
        from primitives_testbed.diveops.media_link_service import (
            link_media_direct,
            get_media_by_dive_site,
        )

        link_media_direct(media_asset, dive_site)

        result = list(get_media_by_dive_site(dive_site))

        assert media_asset in result

    def test_get_unused_media_excludes_linked(self, media_asset, excursion):
        """Unused media should exclude anything with links."""
        from primitives_testbed.diveops.media_link_service import (
            link_media_to_excursion,
            get_unused_media,
        )

        # Initially no links
        assert media_asset in list(get_unused_media())

        # After linking
        link_media_to_excursion(media_asset, excursion)
        assert media_asset not in list(get_unused_media())

    def test_get_media_by_date_returns_correct_assets(self, media_asset, excursion):
        """Should return media for a specific date."""
        from primitives_testbed.diveops.media_link_service import (
            link_media_to_excursion,
            get_media_by_date,
        )

        # Link to set captured_at
        link_media_to_excursion(media_asset, excursion)
        media_asset.refresh_from_db()

        # Query by date
        result = list(get_media_by_date(media_asset.captured_at.date()))

        assert media_asset in result


# =============================================================================
# Test MediaAsset New Fields
# =============================================================================

@pytest.mark.django_db
class TestMediaAssetNewFields:
    """Test the new captured_at and visibility fields on MediaAsset."""

    def test_captured_at_nullable(self, document):
        """captured_at should be nullable."""
        asset = MediaAsset.objects.create(
            document=document,
            kind=MediaKind.IMAGE,
        )
        assert asset.captured_at is None

    def test_captured_at_can_be_set(self, media_asset):
        """captured_at should be settable."""
        now = timezone.now()
        media_asset.captured_at = now
        media_asset.save()

        media_asset.refresh_from_db()
        assert media_asset.captured_at == now

    def test_visibility_default_is_private(self, document):
        """visibility should default to private."""
        asset = MediaAsset.objects.create(
            document=document,
            kind=MediaKind.IMAGE,
        )
        assert asset.visibility == "private"

    def test_visibility_can_be_set(self, media_asset):
        """visibility should be settable to internal or public."""
        media_asset.visibility = "public"
        media_asset.save()

        media_asset.refresh_from_db()
        assert media_asset.visibility == "public"

        media_asset.visibility = "internal"
        media_asset.save()

        media_asset.refresh_from_db()
        assert media_asset.visibility == "internal"
