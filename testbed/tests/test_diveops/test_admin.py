"""Tests for diveops admin configuration."""

from datetime import date, timedelta

import pytest
from django.contrib.admin.sites import AdminSite

from primitives_testbed.diveops.models import (
    CertificationLevel,
    DiverCertification,
    TripRequirement,
)


@pytest.mark.django_db
class TestCertificationLevelAdmin:
    """Tests for CertificationLevel admin."""

    def test_admin_registered(self):
        """CertificationLevel is registered in admin."""
        from django.contrib import admin
        assert CertificationLevel in admin.site._registry

    def test_list_display(self):
        """Admin shows code, name, agency, rank, is_active."""
        from django.contrib import admin
        model_admin = admin.site._registry[CertificationLevel]
        assert "code" in model_admin.list_display
        assert "name" in model_admin.list_display
        assert "agency" in model_admin.list_display  # Agency FK
        assert "rank" in model_admin.list_display
        assert "is_active" in model_admin.list_display

    def test_search_fields(self):
        """Admin can search by code and name."""
        from django.contrib import admin
        model_admin = admin.site._registry[CertificationLevel]
        assert "code" in model_admin.search_fields
        assert "name" in model_admin.search_fields


@pytest.mark.django_db
class TestDiverCertificationAdmin:
    """Tests for DiverCertification admin."""

    def test_admin_registered(self):
        """DiverCertification is registered in admin."""
        from django.contrib import admin
        assert DiverCertification in admin.site._registry

    def test_list_display(self):
        """Admin shows diver, level, get_agency, is_verified."""
        from django.contrib import admin
        model_admin = admin.site._registry[DiverCertification]
        assert "diver" in model_admin.list_display
        assert "level" in model_admin.list_display
        assert "get_agency" in model_admin.list_display  # Agency derived from level.agency
        assert "is_verified" in model_admin.list_display

    def test_list_filter(self):
        """Admin can filter by level__agency and is_verified."""
        from django.contrib import admin
        model_admin = admin.site._registry[DiverCertification]
        # Filter by agency (derived from level.agency) instead of level directly
        assert "level__agency" in model_admin.list_filter
        assert "is_verified" in model_admin.list_filter


@pytest.mark.django_db
class TestTripRequirementAdmin:
    """Tests for TripRequirement admin."""

    def test_admin_registered(self):
        """TripRequirement is registered in admin."""
        from django.contrib import admin
        assert TripRequirement in admin.site._registry

    def test_list_display(self):
        """Admin shows trip, requirement_type, is_mandatory."""
        from django.contrib import admin
        model_admin = admin.site._registry[TripRequirement]
        assert "trip" in model_admin.list_display
        assert "requirement_type" in model_admin.list_display
        assert "is_mandatory" in model_admin.list_display

    def test_list_filter(self):
        """Admin can filter by requirement_type and is_mandatory."""
        from django.contrib import admin
        model_admin = admin.site._registry[TripRequirement]
        assert "requirement_type" in model_admin.list_filter
        assert "is_mandatory" in model_admin.list_filter
