"""Customer portal views (authenticated customers)."""

from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView

from django_cms_core.models import AccessLevel, ContentPage, PageStatus
from django_cms_core.services import check_page_access
from django_portal_ui.mixins import CustomerPortalMixin

from primitives_testbed.store.models import StoreOrder

from .selectors import (
    get_current_diver,
    get_diver_agreement_status,
    get_diver_dive_stats,
    get_diver_highest_certification,
    get_diver_medical_status,
    get_diver_with_certifications,
    list_diver_bookings,
    list_diver_briefings,
    list_diver_dive_logs,
    list_diver_documents,
    list_diver_pending_agreements,
    list_diver_signed_agreements,
    list_upcoming_excursions,
)
from .preferences.selectors import (
    get_diver_preference_status,
    get_recommended_certifications,
    get_recommended_courseware,
    get_recommended_gear,
    list_diver_preferences_by_category,
)


class CustomerDashboardView(CustomerPortalMixin, TemplateView):
    """Customer portal dashboard showing bookings, orders, and courseware."""

    template_name = "diveops/portal/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Get diver profile for current user
        diver = get_current_diver(user)
        diver_with_certs = None
        highest_cert = None
        upcoming_bookings = []
        past_bookings = []

        # Initialize diver-related data
        medical_status = None
        signed_agreements = []
        pending_agreements = []
        briefings = []
        dive_logs = []
        dive_stats = None
        documents = []
        photo_tags = []
        emergency_contacts = []

        if diver:
            # Get full diver with certifications
            diver_with_certs = get_diver_with_certifications(diver.pk)
            highest_cert = get_diver_highest_certification(diver)
            # Get upcoming bookings (future excursions)
            upcoming_bookings = list_diver_bookings(diver, include_past=False, limit=5)
            # Get recent past bookings
            past_bookings = list_diver_bookings(diver, include_past=True, limit=5)
            # Filter to only past ones
            from django.utils import timezone
            past_bookings = [
                b for b in past_bookings
                if b.excursion.departure_time <= timezone.now()
            ][:3]

            # Medical clearance status
            medical_status = get_diver_medical_status(diver)

            # Agreements (waivers, medical forms, etc.)
            signed_agreements = list_diver_signed_agreements(diver, limit=10)
            pending_agreements = list_diver_pending_agreements(diver, limit=10)

            # Briefings (subset of signed agreements)
            briefings = list_diver_briefings(diver, limit=5)

            # Dive logs and stats
            dive_logs = list_diver_dive_logs(diver, limit=10)
            dive_stats = get_diver_dive_stats(diver)

            # Documents (medical questionnaire PDFs, photo ID, etc.)
            documents = list_diver_documents(diver, limit=20)

            # Combine documents and signed agreements for unified display
            # Each item gets a 'item_type' and 'item_date' for sorting
            combined_docs = []
            for doc in documents:
                combined_docs.append({
                    'type': 'document',
                    'item': doc,
                    'date': doc.created_at,
                })
            for agreement in signed_agreements:
                combined_docs.append({
                    'type': 'agreement',
                    'item': agreement,
                    'date': agreement.signed_at,
                })
            # Sort by date, most recent first
            combined_docs.sort(key=lambda x: x['date'] if x['date'] else timezone.now(), reverse=True)

            # Required agreements (medical, waiver based on category)
            agreement_status = get_diver_agreement_status(diver)

            # Preference status for progressive preference collection
            preference_status = get_diver_preference_status(diver)

            # Certification recommendations based on progression and preferences
            recommended_certifications = get_recommended_certifications(diver, limit=3)

            # Courseware recommendations based on certification progression
            recommended_courseware = get_recommended_courseware(diver, limit=3)

            # Gear recommendations based on diving interests
            recommended_gear = get_recommended_gear(diver, limit=3)

            # Briefings status (upcoming excursions with briefings to review)
            from .models import Booking
            from django.utils import timezone as tz

            # Upcoming bookings = briefings to review
            upcoming_briefings = Booking.objects.filter(
                diver=diver,
                status="confirmed",
                excursion__departure_time__gte=tz.now(),
                deleted_at__isnull=True,
            ).select_related("excursion", "excursion__dive_site")

            # Photos where diver is tagged (for photo gallery/store)
            from .models import PhotoTag
            photo_tags = PhotoTag.objects.filter(
                diver=diver,
                deleted_at__isnull=True,
            ).select_related("document").order_by("-created_at")[:24]

            # Emergency contacts
            emergency_contacts = diver.emergency_contacts

            # Buddy pairs and groups
            from .services import list_buddy_pairs, list_buddy_groups
            buddy_pairs = list_buddy_pairs(diver.person)
            buddy_groups = list_buddy_groups(diver.person)
        else:
            agreement_status = None
            combined_docs = []
            preference_status = None
            recommended_certifications = []
            recommended_courseware = []
            recommended_gear = []
            upcoming_briefings = []
            buddy_pairs = []
            buddy_groups = []

        # Get recent orders for this user
        orders = StoreOrder.objects.filter(user=user).order_by("-created_at")[:5]

        # Get user's entitlements
        from primitives_testbed.diveops.entitlements.services import get_user_entitlements

        entitlements = get_user_entitlements(user)

        # Find courseware pages user has access to
        courseware_pages = []
        if entitlements:
            pages = ContentPage.objects.filter(
                status=PageStatus.PUBLISHED,
                access_level=AccessLevel.ENTITLEMENT,
                deleted_at__isnull=True,
            )
            for page in pages:
                allowed, _ = check_page_access(page, user)
                if allowed:
                    courseware_pages.append(page)

        # Get recommended excursions if user has no upcoming bookings
        # Priority: actual scheduled excursions with spots > excursion types
        recommended_excursions = []
        recommended_types = []
        if not upcoming_bookings:
            recommended_excursions = list_upcoming_excursions(min_spots=1, limit=2)
            if not recommended_excursions:
                # Fall back to excursion types
                from .models import ExcursionType
                recommended_types = list(
                    ExcursionType.objects.filter(is_active=True)
                    .select_related("min_certification_level")
                    .prefetch_related("suitable_sites")[:2]
                )

        context.update({
            "diver": diver_with_certs or diver,
            "highest_cert": highest_cert,
            "upcoming_bookings": upcoming_bookings,
            "past_bookings": past_bookings,
            "orders": orders,
            "entitlements": entitlements,
            "courseware_pages": courseware_pages,
            # New dashboard sections
            "medical_status": medical_status,
            "signed_agreements": signed_agreements,
            "pending_agreements": pending_agreements,
            "briefings": briefings,
            "dive_logs": dive_logs,
            "dive_stats": dive_stats,
            "agreement_status": agreement_status,
            "preference_status": preference_status,
            "documents": documents,
            "combined_docs": combined_docs,
            "photo_tags": photo_tags,
            "emergency_contacts": emergency_contacts,
            "recommended_excursions": recommended_excursions,
            "recommended_types": recommended_types,
            "recommended_certifications": recommended_certifications,
            "recommended_courseware": recommended_courseware,
            "recommended_gear": recommended_gear,
            "upcoming_briefings": upcoming_briefings,
            "buddy_pairs": buddy_pairs,
            "buddy_groups": buddy_groups,
        })
        return context


class CustomerOrdersView(CustomerPortalMixin, TemplateView):
    """Customer view of their orders."""

    template_name = "diveops/portal/orders.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Get all orders for this user
        orders = StoreOrder.objects.filter(user=user).order_by("-created_at")

        context["orders"] = orders
        return context


class UpdateGearSizingView(CustomerPortalMixin, View):
    """Update diver gear sizing from dashboard modal."""

    def post(self, request, *args, **kwargs):
        diver = get_current_diver(request.user)
        if not diver:
            return redirect("portal:dashboard")

        # Update gear sizing fields
        diver.height_cm = request.POST.get("height_cm") or None
        diver.weight_kg = request.POST.get("weight_kg") or None
        diver.wetsuit_size = request.POST.get("wetsuit_size", "")
        diver.bcd_size = request.POST.get("bcd_size", "")
        diver.fin_size = request.POST.get("fin_size", "")
        diver.glove_size = request.POST.get("glove_size", "")
        diver.mask_fit = request.POST.get("mask_fit", "")
        diver.weight_required_kg = request.POST.get("weight_required_kg") or None
        diver.gear_notes = request.POST.get("gear_notes", "")

        diver.save(update_fields=[
            "height_cm", "weight_kg", "wetsuit_size", "bcd_size",
            "fin_size", "glove_size", "mask_fit", "weight_required_kg",
            "gear_notes", "updated_at"
        ])

        return redirect("portal:dashboard")


class AddEmergencyContactView(CustomerPortalMixin, View):
    """Add an emergency contact from dashboard modal.

    Uses the new PartyRelationship + DiverRelationshipMeta (canonical model)
    instead of the legacy EmergencyContact model.
    """

    def post(self, request, *args, **kwargs):
        from django_parties.models import PartyRelationship

        from .services import add_emergency_contact_via_party_relationship

        diver = get_current_diver(request.user)
        if not diver:
            return redirect("portal:dashboard")

        # Get next priority based on existing PartyRelationship contacts
        existing_count = PartyRelationship.objects.filter(
            from_person=diver.person,
            relationship_type="emergency_contact",
            deleted_at__isnull=True,
        ).count()

        # Create emergency contact via PartyRelationship
        add_emergency_contact_via_party_relationship(
            diver=diver,
            existing_person=None,  # Always creating new Person from customer portal
            first_name=request.POST.get("first_name", "").strip(),
            last_name=request.POST.get("last_name", "").strip(),
            phone=request.POST.get("phone", "").strip(),
            email=request.POST.get("email", "").strip() or "",
            date_of_birth=None,  # Not collected in customer portal
            phone_is_mobile=True,  # Default
            phone_has_whatsapp=False,  # Default
            phone_can_receive_sms=True,  # Default
            relationship=request.POST.get("relationship", "other"),
            priority=existing_count + 1,
            notes=request.POST.get("notes", "").strip(),
            actor=request.user,
        )

        return redirect("portal:dashboard")


class StartFormView(CustomerPortalMixin, View):
    """Start a required form (questionnaire or agreement) and redirect to it."""

    def get(self, request, template_id, *args, **kwargs):
        import uuid
        from django.contrib.contenttypes.models import ContentType
        from django.urls import reverse

        from .models import AgreementTemplate, DiverProfile

        diver = get_current_diver(request.user)
        if not diver:
            return redirect("portal:dashboard")

        # Get the template
        template = get_object_or_404(AgreementTemplate, pk=template_id)

        # Handle based on template type
        if template.template_type == AgreementTemplate.TemplateType.MEDICAL:
            # Create a questionnaire instance
            from django_questionnaires.models import QuestionnaireInstance

            diver_ct = ContentType.objects.get_for_model(DiverProfile)

            # Check for existing pending instance
            existing = QuestionnaireInstance.objects.filter(
                respondent_content_type=diver_ct,
                respondent_object_id=str(diver.pk),
                status__in=["pending", "in_progress"],
                deleted_at__isnull=True,
            ).first()

            if existing:
                instance = existing
            else:
                # Create new questionnaire instance
                instance = QuestionnaireInstance.objects.create(
                    questionnaire=template.questionnaire,
                    respondent_content_type=diver_ct,
                    respondent_object_id=str(diver.pk),
                    status="pending",
                )

            # Redirect to the public questionnaire URL
            return redirect(reverse("diveops_public:medical-questionnaire", args=[instance.pk]))

        else:
            # Create a signable agreement
            from django_parties.models import Person

            from .models import SignableAgreement

            person_ct = ContentType.objects.get_for_model(Person)

            # Check for existing pending agreement
            existing = SignableAgreement.objects.filter(
                template=template,
                party_a_content_type=person_ct,
                party_a_object_id=str(diver.person_id),
                status=SignableAgreement.Status.PENDING,
            ).first()

            if existing:
                agreement = existing
            else:
                # Create new signable agreement with token
                agreement = SignableAgreement.objects.create(
                    template=template,
                    party_a_content_type=person_ct,
                    party_a_object_id=str(diver.person_id),
                    access_token=uuid.uuid4().hex[:32],
                    status=SignableAgreement.Status.PENDING,
                )

            # Redirect to the public signing URL
            return redirect(reverse("diveops_public:sign", args=[agreement.access_token]))


class CustomerOrderDetailView(CustomerPortalMixin, TemplateView):
    """Customer view of a single order detail."""

    template_name = "diveops/portal/order_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        order_number = self.kwargs.get("order_number")

        # Get the order for this user only
        order = get_object_or_404(
            StoreOrder.objects.prefetch_related("items__catalog_item"),
            order_number=order_number,
            user=user,
        )

        context["order"] = order
        return context


class PortalCMSPageView(CustomerPortalMixin, TemplateView):
    """Render CMS pages within the portal context.

    This view wraps CMS pages inside the portal layout,
    enforcing at minimum AUTHENTICATED access.
    """

    template_name = "diveops/portal/content_page.html"

    def get(self, request, path, *args, **kwargs):
        # Normalize path (remove leading/trailing slashes)
        slug = path.strip("/") or "home"

        # Get the page
        try:
            page = ContentPage.objects.get(
                slug=slug,
                status=PageStatus.PUBLISHED,
                deleted_at__isnull=True,
            )
        except ContentPage.DoesNotExist:
            raise Http404("Page not found")

        # Check access (portal forces minimum AUTHENTICATED)
        allowed, reason = check_page_access(page, request.user)
        if not allowed:
            raise Http404(reason)

        # Store page for context
        self.page = page
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        page = self.page
        snapshot = page.published_snapshot or {}

        context.update({
            "page": page,
            "page_title": page.title,
            "blocks": snapshot.get("blocks", []),
            "meta": snapshot.get("meta", {}),
        })
        return context


class CustomerPreferencesView(CustomerPortalMixin, TemplateView):
    """Customer view for viewing and managing preferences."""

    template_name = "diveops/portal/preferences.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        diver = get_current_diver(user)

        preferences_by_category = {}
        preference_status = None

        if diver:
            preference_status = get_diver_preference_status(diver)
            preferences_by_category = list_diver_preferences_by_category(diver)

        context.update({
            "diver": diver,
            "preference_status": preference_status,
            "preferences_by_category": preferences_by_category,
        })
        return context


class PreferencesSurveyView(CustomerPortalMixin, TemplateView):
    """Survey form for collecting diver preferences."""

    template_name = "diveops/portal/preferences_survey.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        diver = get_current_diver(user)

        # Get all preference definitions grouped by category
        from .preferences.models import PreferenceDefinition, PartyPreference

        definitions = PreferenceDefinition.objects.filter(
            deleted_at__isnull=True
        ).order_by("category", "key")

        # Group by category
        definitions_by_category = {}
        for defn in definitions:
            if defn.category not in definitions_by_category:
                definitions_by_category[defn.category] = []
            definitions_by_category[defn.category].append(defn)

        # Get existing preferences for this diver
        existing_prefs = {}
        if diver:
            prefs = PartyPreference.objects.filter(
                person=diver.person,
                deleted_at__isnull=True,
            ).select_related("definition")
            for pref in prefs:
                existing_prefs[pref.definition.key] = pref.value_json

        context.update({
            "diver": diver,
            "definitions_by_category": definitions_by_category,
            "existing_prefs": existing_prefs,
        })
        return context

    def post(self, request, *args, **kwargs):
        from django.http import HttpResponseRedirect
        from django.urls import reverse
        from django.contrib import messages
        from .preferences.models import PreferenceDefinition, PartyPreference

        diver = get_current_diver(request.user)
        if not diver:
            messages.error(request, "Diver profile not found.")
            return HttpResponseRedirect(reverse("portal:dashboard"))

        # Get all definitions to know what fields to expect
        definitions = PreferenceDefinition.objects.filter(deleted_at__isnull=True)

        saved_count = 0
        for defn in definitions:
            field_name = f"pref_{defn.key.replace('.', '_')}"

            if defn.value_type == "multi_choice":
                # Checkboxes - get list of values
                values = request.POST.getlist(field_name)
                if values:
                    PartyPreference.objects.update_or_create(
                        person=diver.person,
                        definition=defn,
                        defaults={"value_json": values},
                    )
                    saved_count += 1
            elif defn.value_type == "bool":
                # Checkbox - presence means True
                value = field_name in request.POST
                PartyPreference.objects.update_or_create(
                    person=diver.person,
                    definition=defn,
                    defaults={"value_json": value},
                )
                saved_count += 1
            elif defn.value_type == "choice":
                # Select - single value
                value = request.POST.get(field_name)
                if value:
                    PartyPreference.objects.update_or_create(
                        person=diver.person,
                        definition=defn,
                        defaults={"value_json": value},
                    )
                    saved_count += 1
            else:
                # Text, number, date - string value
                value = request.POST.get(field_name)
                if value:
                    PartyPreference.objects.update_or_create(
                        person=diver.person,
                        definition=defn,
                        defaults={"value_json": value},
                    )
                    saved_count += 1

        messages.success(request, f"Saved {saved_count} preferences.")
        return HttpResponseRedirect(reverse("portal:preferences"))


class AddBuddyView(CustomerPortalMixin, TemplateView):
    """Form to add a new buddy."""

    template_name = "diveops/portal/add_buddy.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        diver = get_current_diver(self.request.user)
        context["diver"] = diver
        return context

    def post(self, request, *args, **kwargs):
        from django.http import HttpResponseRedirect
        from django.urls import reverse
        from django.contrib import messages
        from django_parties.models import Person
        from .services import add_buddy_pair

        diver = get_current_diver(request.user)
        if not diver:
            messages.error(request, "Diver profile not found.")
            return HttpResponseRedirect(reverse("portal:dashboard"))

        # Get form data
        buddy_type = request.POST.get("buddy_type", "new")

        try:
            if buddy_type == "existing":
                # Adding an existing person by email
                email = request.POST.get("email", "").strip()
                if not email:
                    messages.error(request, "Please enter an email address.")
                    return HttpResponseRedirect(reverse("portal:add_buddy"))

                # Find person by email (through their user account)
                from django.contrib.auth import get_user_model
                User = get_user_model()
                try:
                    user = User.objects.get(email=email)
                    friend_person = Person.objects.filter(
                        partycontactinfo__contact_type="email",
                        partycontactinfo__contact_value=email,
                    ).first()
                    if not friend_person:
                        # Try to get person linked to user
                        friend_person = Person.objects.filter(user=user).first()
                    if not friend_person:
                        messages.error(request, f"No diver profile found for {email}.")
                        return HttpResponseRedirect(reverse("portal:add_buddy"))

                    team = add_buddy_pair(me_person=diver.person, friend_person=friend_person)
                    messages.success(request, f"Added {friend_person.first_name} {friend_person.last_name} as your buddy!")
                except User.DoesNotExist:
                    messages.error(request, f"No user found with email {email}.")
                    return HttpResponseRedirect(reverse("portal:add_buddy"))
            else:
                # Adding a new contact (not on platform yet)
                display_name = request.POST.get("display_name", "").strip()
                email = request.POST.get("contact_email", "").strip()
                phone = request.POST.get("phone", "").strip()

                if not display_name:
                    messages.error(request, "Please enter your buddy's name.")
                    return HttpResponseRedirect(reverse("portal:add_buddy"))

                if not email and not phone:
                    messages.error(request, "Please enter either an email or phone number.")
                    return HttpResponseRedirect(reverse("portal:add_buddy"))

                friend_data = {
                    "display_name": display_name,
                    "email": email or None,
                    "phone": phone or None,
                }
                team = add_buddy_pair(me_person=diver.person, friend_data=friend_data)
                messages.success(request, f"Added {display_name} as your buddy!")

        except ValueError as e:
            messages.error(request, str(e))
            return HttpResponseRedirect(reverse("portal:add_buddy"))

        return HttpResponseRedirect(reverse("portal:dashboard"))


class RemoveBuddyView(CustomerPortalMixin, View):
    """Remove a buddy relationship."""

    def post(self, request, team_id, *args, **kwargs):
        from django.http import HttpResponseRedirect
        from django.urls import reverse
        from django.contrib import messages
        from .services import remove_buddy

        diver = get_current_diver(request.user)
        if not diver:
            messages.error(request, "Diver profile not found.")
            return HttpResponseRedirect(reverse("portal:dashboard"))

        try:
            remove_buddy(me_person=diver.person, team_id=team_id)
            messages.success(request, "Buddy removed.")
        except Exception as e:
            messages.error(request, f"Error removing buddy: {e}")

        return HttpResponseRedirect(reverse("portal:dashboard"))
