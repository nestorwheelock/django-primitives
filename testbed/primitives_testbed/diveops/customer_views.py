"""Customer portal views (authenticated customers)."""

import json

from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
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
            from django.utils import timezone

            # Get full diver with certifications
            diver_with_certs = get_diver_with_certifications(diver.pk)
            highest_cert = get_diver_highest_certification(diver)

            # Get bookings in ONE query - split into upcoming/past in Python
            all_bookings = list_diver_bookings(diver, include_past=True, limit=10)
            now = timezone.now()
            upcoming_bookings = [b for b in all_bookings if b.excursion.departure_time > now][:5]
            past_bookings = [b for b in all_bookings if b.excursion.departure_time <= now][:3]

            # Cache expensive queries (2-minute TTL for semi-real-time data)
            from django.core.cache import cache
            cache_key = f"diver_dash:{diver.pk}"

            # Medical clearance status (cached 2 min)
            medical_status = cache.get(f"{cache_key}:medical")
            if medical_status is None:
                medical_status = get_diver_medical_status(diver)
                cache.set(f"{cache_key}:medical", medical_status, 120)

            # Agreements (waivers, medical forms, etc.)
            signed_agreements = list_diver_signed_agreements(diver, limit=10)
            pending_agreements = list_diver_pending_agreements(diver, limit=10)

            # Briefings (subset of signed agreements)
            briefings = list_diver_briefings(diver, limit=5)

            # Dive logs and stats (cached 2 min)
            dive_logs = list_diver_dive_logs(diver, limit=10)
            dive_stats = cache.get(f"{cache_key}:stats")
            if dive_stats is None:
                dive_stats = get_diver_dive_stats(diver)
                cache.set(f"{cache_key}:stats", dive_stats, 120)

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

            # Recommendations (cached for 5 minutes - expensive queries)
            cache_key_base = f"diver_recs:{diver.pk}"

            recommended_certifications = cache.get(f"{cache_key_base}:certs")
            if recommended_certifications is None:
                recommended_certifications = get_recommended_certifications(diver, limit=3)
                cache.set(f"{cache_key_base}:certs", recommended_certifications, 300)

            recommended_courseware = cache.get(f"{cache_key_base}:courseware")
            if recommended_courseware is None:
                recommended_courseware = get_recommended_courseware(diver, limit=3)
                cache.set(f"{cache_key_base}:courseware", recommended_courseware, 300)

            recommended_gear = cache.get(f"{cache_key_base}:gear")
            if recommended_gear is None:
                recommended_gear = get_recommended_gear(diver, limit=3)
                cache.set(f"{cache_key_base}:gear", recommended_gear, 300)

            # Briefings status = confirmed upcoming bookings (reuse data)
            upcoming_briefings = [b for b in upcoming_bookings if b.status == "confirmed"]

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
        # Optimized: check entitlements in Python instead of N+1 DB calls
        courseware_pages = []
        if entitlements:
            entitlement_set = set(entitlements)  # O(1) lookup
            pages = ContentPage.objects.filter(
                status=PageStatus.PUBLISHED,
                access_level=AccessLevel.ENTITLEMENT,
                deleted_at__isnull=True,
            )
            for page in pages:
                # Check if user has any required entitlement
                required = page.required_entitlements or []
                if any(ent in entitlement_set for ent in required):
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


# =============================================================================
# Messages / Conversations (Unified CRM Messaging)
# =============================================================================


class CustomerMessagesInboxView(CustomerPortalMixin, TemplateView):
    """List conversations for current customer Person."""

    template_name = "diveops/portal/messages/inbox.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        diver = get_current_diver(self.request.user)

        if diver and diver.person:
            from django_communication.services import get_customer_inbox

            context["conversations"] = get_customer_inbox(diver.person)
        else:
            context["conversations"] = []

        return context


class CustomerConversationDetailView(CustomerPortalMixin, TemplateView):
    """Full-page chat view for a conversation."""

    template_name = "diveops/portal/messages/chat.html"

    def get_conversation(self):
        """Get conversation and verify customer is participant."""
        from django_communication.models import Conversation

        conversation_id = self.kwargs.get("conversation_id")
        diver = get_current_diver(self.request.user)

        if not diver or not diver.person:
            raise Http404("Not authenticated")

        conversation = get_object_or_404(Conversation, pk=conversation_id)

        # Verify customer is a participant
        if not conversation.participants.filter(person=diver.person).exists():
            raise Http404("Conversation not found")

        return conversation, diver.person

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        conversation, person = self.get_conversation()

        from django_communication.services import get_conversation_messages

        context["conversation"] = conversation
        context["messages_list"] = get_conversation_messages(conversation)
        context["current_person"] = person

        # Get staff participant for read status display and avatar
        staff_participant = conversation.participants.filter(role="staff").first()
        if staff_participant:
            context["staff_participant"] = staff_participant
            context["staff_person"] = staff_participant.person
            # Find the last message from customer that staff has read
            if staff_participant.last_read_at:
                last_read_outbound = conversation.messages.filter(
                    sender_person=person,
                    created_at__lte=staff_participant.last_read_at,
                ).order_by("-created_at").first()
                if last_read_outbound:
                    context["last_read_outbound_message_id"] = str(last_read_outbound.pk)

        # Get current diver for their profile photo
        diver = get_current_diver(self.request.user)
        if diver:
            context["current_diver"] = diver

        # Mark as read for this customer
        conversation.mark_read_for(person)

        return context

    def post(self, request, *args, **kwargs):
        """Handle sending a message in the conversation."""
        from django_communication.services import send_in_conversation

        conversation, person = self.get_conversation()
        body_text = request.POST.get("message", "").strip()

        if body_text:
            send_in_conversation(
                conversation=conversation,
                sender_person=person,
                body_text=body_text,
            )

        return redirect("portal:conversation", conversation_id=conversation.pk)


class CustomerSendMessageView(CustomerPortalMixin, View):
    """POST endpoint for sending a message in a conversation."""

    def post(self, request, conversation_id):
        """Send a message via POST."""
        from django_communication.models import Conversation
        from django_communication.services import send_in_conversation

        diver = get_current_diver(request.user)
        if not diver or not diver.person:
            raise Http404("Not authenticated")

        conversation = get_object_or_404(Conversation, pk=conversation_id)

        # Verify customer is participant
        if not conversation.participants.filter(person=diver.person).exists():
            raise Http404("Conversation not found")

        body_text = request.POST.get("message", "").strip()

        if body_text:
            send_in_conversation(
                conversation=conversation,
                sender_person=diver.person,
                body_text=body_text,
            )

        return redirect("portal:conversation", conversation_id=conversation.pk)


class CustomerStartConversationView(CustomerPortalMixin, TemplateView):
    """Start a new conversation (for general inquiries)."""

    template_name = "diveops/portal/messages/new_conversation.html"

    def post(self, request, *args, **kwargs):
        """Create a new conversation and redirect to it."""
        from django_communication.models import ParticipantRole
        from django_communication.services import create_conversation, send_in_conversation

        diver = get_current_diver(request.user)
        if not diver or not diver.person:
            raise Http404("Not authenticated")

        subject = request.POST.get("subject", "").strip() or "New Inquiry"
        body_text = request.POST.get("message", "").strip()

        if not body_text:
            return redirect("portal:messages")

        # Create conversation with customer as participant
        conversation = create_conversation(
            subject=subject,
            participants=[(diver.person, ParticipantRole.CUSTOMER)],
            primary_channel="in_app",
        )

        # Send initial message
        send_in_conversation(
            conversation=conversation,
            sender_person=diver.person,
            body_text=body_text,
        )

        return redirect("portal:conversation", conversation_id=conversation.pk)


# =============================================================================
# Push Notifications
# =============================================================================


class VapidPublicKeyView(View):
    """Return the VAPID public key for browser subscription.

    This endpoint is public (no auth required) so the browser can
    request the key before the service worker subscribes.
    """

    def get(self, request):
        from django_communication.models import CommunicationSettings

        settings = CommunicationSettings.objects.first()
        if settings and settings.vapid_public_key:
            return JsonResponse({"publicKey": settings.vapid_public_key})
        return JsonResponse({"publicKey": None}, status=404)


class PushSubscribeView(CustomerPortalMixin, View):
    """Store a new push subscription for the current user."""

    def post(self, request):
        from django_communication.models import PushSubscription

        diver = get_current_diver(request.user)
        if not diver or not diver.person:
            return JsonResponse({"error": "No diver profile"}, status=400)

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        endpoint = data.get("endpoint")
        keys = data.get("keys", {})
        p256dh = keys.get("p256dh")
        auth = keys.get("auth")

        if not endpoint or not p256dh or not auth:
            return JsonResponse({"error": "Missing subscription data"}, status=400)

        PushSubscription.objects.update_or_create(
            person=diver.person,
            endpoint=endpoint,
            defaults={
                "p256dh_key": p256dh,
                "auth_key": auth,
                "user_agent": request.META.get("HTTP_USER_AGENT", "")[:500],
                "is_active": True,
                "failure_count": 0,
            },
        )
        return JsonResponse({"status": "subscribed"})


class PushUnsubscribeView(CustomerPortalMixin, View):
    """Remove a push subscription."""

    def post(self, request):
        from django_communication.models import PushSubscription

        diver = get_current_diver(request.user)
        if not diver or not diver.person:
            return JsonResponse({"error": "No diver profile"}, status=400)

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        endpoint = data.get("endpoint")
        if not endpoint:
            return JsonResponse({"error": "Missing endpoint"}, status=400)

        PushSubscription.objects.filter(
            person=diver.person,
            endpoint=endpoint,
        ).update(is_active=False)

        return JsonResponse({"status": "unsubscribed"})


# =============================================================================
# Buddy Group Chat Views
# =============================================================================


class BuddyGroupChatListView(CustomerPortalMixin, TemplateView):
    """List all buddy group chats for the current diver."""

    template_name = "diveops/portal/messages/buddy_groups.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        diver = get_current_diver(self.request.user)
        if not diver or not diver.person:
            context["buddy_groups"] = []
            context["dive_teams_without_chat"] = []
            return context

        from .services import get_buddy_conversations, list_buddy_pairs, list_buddy_groups
        from .models import BuddyIdentity, DiveTeam

        person = diver.person

        # Get buddy group chats
        buddy_groups = get_buddy_conversations(person)
        context["buddy_groups"] = buddy_groups

        # Get dive teams without chats
        try:
            my_identity = BuddyIdentity.objects.get(person=person)
            all_teams = DiveTeam.objects.filter(
                members__identity=my_identity,
                deleted_at__isnull=True,
            ).prefetch_related("members__identity")

            # Filter to teams without group_chat
            teams_with_chat_ids = set(
                buddy_groups.values_list("dive_team_id", flat=True)
            )
            teams_without_chat = [
                t for t in all_teams if t.pk not in teams_with_chat_ids
            ]
            context["dive_teams_without_chat"] = teams_without_chat
        except BuddyIdentity.DoesNotExist:
            context["dive_teams_without_chat"] = []

        return context


class CreateBuddyGroupChatView(CustomerPortalMixin, View):
    """Create a group chat for an existing buddy team."""

    def post(self, request, team_id):
        from django.contrib import messages
        from .models import DiveTeam, BuddyIdentity
        from .services import create_buddy_group_chat

        diver = get_current_diver(request.user)
        if not diver or not diver.person:
            raise Http404("Not authenticated")

        # Get the team
        team = get_object_or_404(DiveTeam, pk=team_id)

        # Verify user is a team member
        try:
            my_identity = BuddyIdentity.objects.get(person=diver.person)
            if not team.members.filter(identity=my_identity).exists():
                raise Http404("Not a team member")
        except BuddyIdentity.DoesNotExist:
            raise Http404("Not a team member")

        # Create the chat
        try:
            buddy_group = create_buddy_group_chat(
                dive_team=team,
                title=request.POST.get("title") or None,
            )
            messages.success(request, "Group chat created!")
            return redirect("portal:buddy_chat", conversation_id=buddy_group.conversation.pk)
        except ValueError as e:
            messages.error(request, str(e))
            return redirect("portal:buddy_chats")


class BuddyGroupChatDetailView(CustomerConversationDetailView):
    """Detail view for a buddy group chat (extends conversation detail)."""

    template_name = "diveops/portal/messages/buddy_chat.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        conversation = context.get("conversation")
        current_person = context.get("current_person")

        if not conversation:
            return context

        from django_communication.models import (
            ConversationParticipant,
            ParticipantRole,
            ParticipantState,
        )
        from django_communication.services.conversations import (
            can_send_message,
            get_active_participants,
        )

        # Add buddy group info
        if hasattr(conversation, "buddy_group"):
            context["buddy_group"] = conversation.buddy_group
            context["dive_team"] = conversation.buddy_group.dive_team

        # Get active participants
        context["active_participants"] = get_active_participants(conversation)

        # Get pending invitations
        context["pending_invitations"] = ConversationParticipant.objects.filter(
            conversation=conversation,
            state=ParticipantState.INVITED,
        ).select_related("person")

        # Get current user's participant record
        user_participant = ConversationParticipant.objects.filter(
            conversation=conversation,
            person=current_person,
        ).first()
        context["user_participant"] = user_participant

        # Check if current user is admin (owner or admin role)
        is_admin = user_participant and user_participant.role in [
            ParticipantRole.OWNER,
            ParticipantRole.ADMIN,
        ]
        context["is_admin"] = is_admin

        # Check if user can send messages
        context["can_send"] = can_send_message(conversation, current_person)

        # Get available buddies to invite (if admin)
        if is_admin and hasattr(conversation, "buddy_group"):
            from .models import BuddyIdentity

            # Get all people from user's buddy teams who aren't already participants
            diver = get_current_diver(self.request.user)
            available_buddies = []

            if diver and diver.person:
                try:
                    my_identity = BuddyIdentity.objects.get(person=diver.person)
                    # Get all members from all my teams
                    all_buddy_people = set()
                    for membership in my_identity.team_memberships.select_related(
                        "team"
                    ).prefetch_related("team__members__identity__person"):
                        for member in membership.team.members.all():
                            if member.identity.person:
                                all_buddy_people.add(member.identity.person)

                    # Filter out people already in this conversation
                    existing_participant_ids = set(
                        ConversationParticipant.objects.filter(
                            conversation=conversation
                        ).values_list("person_id", flat=True)
                    )

                    available_buddies = [
                        p for p in all_buddy_people if p.pk not in existing_participant_ids
                    ]
                except BuddyIdentity.DoesNotExist:
                    pass

            context["available_buddies"] = available_buddies

        return context


class InviteBuddyToChatView(CustomerPortalMixin, View):
    """Invite a buddy to an existing group chat."""

    def post(self, request, conversation_id):
        from django.contrib import messages
        from django_communication.models import Conversation
        from django_communication.services.conversations import invite_participant
        from django_parties.models import Person

        diver = get_current_diver(request.user)
        if not diver or not diver.person:
            raise Http404("Not authenticated")

        conversation = get_object_or_404(Conversation, pk=conversation_id)

        # Verify user is participant with invite permission
        from django_communication.models import ConversationParticipant, ParticipantRole

        participant = ConversationParticipant.objects.filter(
            conversation=conversation,
            person=diver.person,
            role__in=[ParticipantRole.OWNER, ParticipantRole.ADMIN],
        ).first()

        if not participant:
            messages.error(request, "You don't have permission to invite members.")
            return redirect("portal:buddy_chat", conversation_id=conversation_id)

        # Get person to invite
        person_id = request.POST.get("buddy_person_id")
        if not person_id:
            messages.error(request, "No person selected.")
            return redirect("portal:buddy_chat", conversation_id=conversation_id)

        try:
            person_to_invite = Person.objects.get(pk=person_id)
            invite_participant(
                conversation=conversation,
                person=person_to_invite,
                invited_by=diver.person,
            )
            messages.success(request, f"Invited {person_to_invite.full_name}!")
        except Person.DoesNotExist:
            messages.error(request, "Person not found.")
        except (PermissionError, ValueError) as e:
            messages.error(request, str(e))

        return redirect("portal:buddy_chat", conversation_id=conversation_id)


class LeaveBuddyChatView(CustomerPortalMixin, View):
    """Leave a buddy group chat."""

    def post(self, request, conversation_id):
        from django.contrib import messages
        from django_communication.models import Conversation
        from django_communication.services.conversations import leave_conversation

        diver = get_current_diver(request.user)
        if not diver or not diver.person:
            raise Http404("Not authenticated")

        conversation = get_object_or_404(Conversation, pk=conversation_id)

        try:
            leave_conversation(conversation, diver.person)
            messages.success(request, "You have left the group chat.")
        except ValueError as e:
            messages.error(request, str(e))
            return redirect("portal:buddy_chat", conversation_id=conversation_id)

        return redirect("portal:buddy_chats")


class AcceptBuddyChatInviteView(CustomerPortalMixin, View):
    """Accept an invitation to a buddy group chat."""

    def post(self, request, conversation_id):
        from django.contrib import messages
        from django_communication.models import Conversation
        from django_communication.services.conversations import accept_invite

        diver = get_current_diver(request.user)
        if not diver or not diver.person:
            raise Http404("Not authenticated")

        conversation = get_object_or_404(Conversation, pk=conversation_id)

        try:
            accept_invite(conversation, diver.person)
            messages.success(request, "You have joined the group chat!")
        except ValueError as e:
            messages.error(request, str(e))

        return redirect("portal:buddy_chat", conversation_id=conversation_id)
