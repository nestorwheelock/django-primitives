"""Management command to seed agreement templates from standard forms."""

from django.core.management.base import BaseCommand
from django.utils import timezone

from primitives_testbed.diveops.models import AgreementTemplate, DiveShop


PADI_LIABILITY_WAIVER = """
<h2>NON-AGENCY DISCLOSURE AND ACKNOWLEDGMENT AGREEMENT</h2>

<p>I understand and agree that PADI Members ("Members"), including <strong>{{ dive_shop_name }}</strong>, and/or any individual PADI Instructors and Divemasters associated with the program in which I am participating, are licensed to use various PADI Trademarks and to conduct PADI training, but are not agents, employees or franchisees of PADI Americas, Inc., or its parent, subsidiary and affiliated corporations ("PADI").</p>

<p>I further understand that Member business activities are independent, and are neither owned nor operated by PADI, and that while PADI establishes the standards for PADI diver training programs, it is not responsible for, nor does it have the right to control, the operation of the Members' business activities and the day-to-day conduct of PADI programs and supervision of divers by the Members or their associated staff.</p>

<p>I further understand and agree on behalf of myself, my heirs and my estate that in the event of an injury or death during this activity, neither I nor my estate shall seek to hold PADI liable for the actions, inactions or negligence of the entities listed above and/or the instructors and divemasters associated with the activity.</p>

<h2>LIABILITY RELEASE AND ASSUMPTION OF RISK AGREEMENT</h2>

<p>I, <strong>{{ diver_name }}</strong>, hereby affirm that I am a certified scuba diver trained in safe dive practices, or a student diver under the control and supervision of a certified scuba instructor.</p>

<p>I know that skin diving, freediving and scuba diving have inherent risks including those risks associated with boat travel to and from the dive site (hereinafter "Excursion"), which may result in serious injury or death. I understand that scuba diving with compressed air involves certain inherent risks; including but not limited to decompression sickness, embolism or other hyperbaric/air expansion injury that require treatment in a recompression chamber.</p>

<p>If I am scuba diving with oxygen enriched air ("Enriched Air") or other gas blends including oxygen, I also understand that it involves inherent risks of oxygen toxicity and/or improper mixtures of breathing gas.</p>

<p>I acknowledge this Excursion includes risks of slipping or falling while on board the boat, being cut or struck by a boat while in the water, injuries occurring while getting on or off a boat, and other perils of the sea. I further understand that the Excursion will be conducted at a site that is remote, either by time or distance or both, from a recompression chamber. I still choose to proceed with the Excursion in spite of the absence of a recompression chamber in proximity to the dive site(s).</p>

<p>I understand and agree that neither <strong>{{ dive_shop_name }}</strong>; nor the dive professional(s) who may be present at the dive site, nor PADI Americas, Inc., nor any of their affiliate and subsidiary corporations, nor any of their respective employees, officers, agents, contractors and assigns (hereinafter "Released Parties") may be held liable or responsible in any way for any injury, death or other damages to me, my family, estate, heirs or assigns that may occur during the Excursion as a result of my participation in the Excursion or as a result of the negligence of any party, including the Released Parties, whether passive or active.</p>

<p>I affirm I am in good mental and physical fitness for the Excursion. I further state that I will not participate in the Excursion if I am under the influence of alcohol or any drugs that are contraindicated to diving. If I am taking medication, I affirm that I have seen a physician and have approval to dive while under the influence of the medication/drugs.</p>

<p>I understand that diving is a physically strenuous activity and that I will be exerting myself during the Excursion and that if I am injured as a result of heart attack, panic, hyperventilation, drowning or any other cause, that I expressly assume the risk of said injuries and that I will not hold the Released Parties responsible for the same.</p>

<p>I am aware that safe dive practices suggest diving with a buddy unless trained as a self-reliant diver. I am aware it is my responsibility to plan my dive allowing for my diving experience and limitations, and the prevailing water conditions and environment. I will not hold the Released Parties responsible for my failure to safely plan my dive, dive my plan, and follow the instructions and dive briefing of the dive professional(s).</p>

<p>If diving from a boat, I will be present at and attentive to the briefing given by the boat crew. If there is anything I do not understand I will notify the boat crew or captain immediately. I acknowledge it is my responsibility to plan my dives as no-decompression dives, and within parameters that allow me to make a safety stop before ascending to the surface, arriving on board the vessel with gas remaining in my cylinder as a measure of safety. If I become distressed on the surface I will immediately drop my weights and inflate my BCD (orally or with low pressure inflator) to establish buoyancy on the surface.</p>

<p>I am aware safe dive practices recommend a refresher or guided orientation dive following a period of diving inactivity. I understand such refresher/guided dive is available for an additional fee. If I choose not to follow this recommendation I will not hold the Released Parties responsible for my decision.</p>

<p>I acknowledge Released Parties may provide an in-water guide (hereinafter "Guide") during the Excursion. The Guide is present to assist in navigation during the dive and identifying local flora and fauna. If I choose to dive with the Guide I acknowledge it is my responsibility to stay in proximity to the Guide during the dive. I assume all risks associated with my choice whether to dive in proximity to the Guide or to dive independent of the Guide. I acknowledge my participation in diving is at my own risk and peril.</p>

<p>I affirm it is my responsibility to inspect all of the equipment I will be using prior to leaving the dock for the Excursion and that I should not dive if the equipment is not functioning properly. I will not hold the Released Parties responsible for my failure to inspect the equipment prior to diving or if I choose to dive with equipment that may not be functioning properly.</p>

<p>I acknowledge Released Parties have made no representation to me, implied or otherwise, that they or their crew can or will perform effective rescues or render first aid. In the event I show signs of distress or call for aid I would like assistance and will not hold the Released Parties, their crew, dive boats or passengers responsible for their actions in attempting the performance of rescue or first aid.</p>

<p>I hereby state and agree that this Agreement will be effective for all Excursions in which I participate for one (1) year from the date on which I sign this Agreement.</p>

<p>I further state that I am of lawful age and legally competent to sign this liability release, or that I have acquired the written consent of my parent or guardian. I understand the terms herein are contractual and not a mere recital, and that I have signed this Agreement of my own free act and with the knowledge that I hereby agree to waive my legal rights.</p>

<p>I further agree that if any provision of this Agreement is found to be unenforceable or invalid, that provision shall be severed from this Agreement. The remainder of this Agreement will then be construed as though the unenforceable provision had never been contained herein.</p>

<p>I understand and agree that I am not only giving up my right to sue the Released Parties but also any rights my heirs, assigns, or beneficiaries may have to sue the Released Parties resulting from my death. I further represent that I have the authority to do so and that my heirs, assigns, and beneficiaries will be estopped from claiming otherwise because of my representations to the Released Parties.</p>

<p><strong>I, {{ diver_name }}, BY THIS INSTRUMENT, AGREE TO EXEMPT AND RELEASE THE RELEASED PARTIES DEFINED ABOVE FROM ALL LIABILITY OR RESPONSIBILITY WHATSOEVER FOR PERSONAL INJURY, PROPERTY DAMAGE OR WRONGFUL DEATH HOWEVER CAUSED, INCLUDING BUT NOT LIMITED TO THE NEGLIGENCE OF THE RELEASED PARTIES, WHETHER PASSIVE OR ACTIVE.</strong></p>

<p><strong>I HAVE FULLY INFORMED MYSELF AND MY HEIRS OF THE CONTENTS OF THIS NON-AGENCY DISCLOSURE AND ACKNOWLEDGMENT AGREEMENT, AND LIABILITY RELEASE AND ASSUMPTION OF RISK AGREEMENT BY READING BOTH BEFORE SIGNING BELOW ON BEHALF OF MYSELF AND MY HEIRS.</strong></p>
"""

EQUIPMENT_RENTAL_FORM = """
<h2>Diver Intake & Equipment Rental Form</h2>

<h3>1. Diver Information</h3>
<p><strong>Full Name:</strong> {{ diver_name }}</p>
<p><strong>Email:</strong> {{ email }}</p>
<p><strong>Date:</strong> {{ date }}</p>

<h3>2. Certification Details</h3>
<p>Please provide your certification information to the dive shop staff.</p>

<h3>3. Emergency Contact</h3>
<p>Please provide emergency contact information to the dive shop staff.</p>

<h3>4. Equipment Rental & Inventory Checklist</h3>
<p>The following equipment will be inspected and recorded by staff:</p>
<ul>
    <li>Mask - Size: _____ Condition: _____</li>
    <li>Snorkel - Size: _____ Condition: _____</li>
    <li>Fins - Size: _____ Condition: _____</li>
    <li>Wetsuit - Size: _____ Condition: _____</li>
    <li>Regulator - Serial #: _____ Condition: _____</li>
    <li>BCD - Size: _____ Condition: _____</li>
    <li>Dive Computer - Serial #: _____ Condition: _____</li>
    <li>Weight Belt / Weights - Amount: _____ kg</li>
    <li>Tank - Size: _____ PSI: _____</li>
    <li>Surface Marker Buoy</li>
    <li>Flashlight / Torch</li>
    <li>Compass</li>
    <li>Other: _____</li>
</ul>

<h3>5. Equipment Use Agreement & Responsibility</h3>

<p>I, the undersigned, agree to:</p>
<ul>
    <li>Use all rented equipment responsibly and follow standard scuba practices.</li>
    <li>Immediately report any damage, malfunction, or loss.</li>
    <li>Reimburse the operator for the full cost of repair or replacement due to negligence, misuse, or loss.</li>
    <li>Return all items in the condition received.</li>
</ul>

<p><strong>I confirm that I have received all equipment listed above and inspected it for proper function.</strong></p>

<p><strong>I understand the terms and agree to be held responsible for the rental equipment.</strong></p>
"""


class Command(BaseCommand):
    """Seed agreement templates from standard diving forms."""

    help = "Import standard diving agreement templates (PADI liability waiver, equipment rental)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--shop",
            type=str,
            help="Dive shop name to associate templates with (uses first shop if not specified)",
        )
        parser.add_argument(
            "--publish",
            action="store_true",
            help="Publish templates immediately after creation",
        )

    def handle(self, *args, **options):
        """Create agreement templates."""
        shop_name = options.get("shop")
        publish = options.get("publish", False)

        # Get or find dive shop
        if shop_name:
            try:
                dive_shop = DiveShop.objects.get(name__icontains=shop_name)
            except DiveShop.DoesNotExist:
                self.stderr.write(self.style.ERROR(f"Dive shop '{shop_name}' not found"))
                return
            except DiveShop.MultipleObjectsReturned:
                dive_shop = DiveShop.objects.filter(name__icontains=shop_name).first()
        else:
            dive_shop = DiveShop.objects.first()
            if not dive_shop:
                self.stderr.write(self.style.ERROR("No dive shops found. Create a dive shop first."))
                return

        self.stdout.write(f"Using dive shop: {dive_shop.name}")

        templates_created = 0

        # 1. PADI Liability Waiver
        template, created = AgreementTemplate.objects.get_or_create(
            dive_shop=dive_shop,
            name="PADI Diver Activities Liability Release",
            defaults={
                "template_type": "waiver",
                "content": PADI_LIABILITY_WAIVER.strip(),
                "description": "Standard PADI Release of Liability/Assumption of Risk/Non-agency Acknowledgment Form (Product No. 10086)",
                "requires_signature": True,
                "requires_initials": False,
                "is_required_for_booking": True,
                "validity_days": 365,  # Valid for 1 year per the form
                "version": "3.0",
                "status": "published" if publish else "draft",
                "published_at": timezone.now() if publish else None,
            },
        )
        if created:
            templates_created += 1
            self.stdout.write(self.style.SUCCESS(f"  Created: {template.name}"))
        else:
            self.stdout.write(f"  Already exists: {template.name}")

        # 2. Equipment Rental Form
        template, created = AgreementTemplate.objects.get_or_create(
            dive_shop=dive_shop,
            name="Equipment Rental Agreement",
            defaults={
                "template_type": "rental",
                "content": EQUIPMENT_RENTAL_FORM.strip(),
                "description": "Diver intake form and equipment rental checklist with responsibility agreement",
                "requires_signature": True,
                "requires_initials": False,
                "is_required_for_booking": False,
                "validity_days": None,  # Per rental
                "version": "1.0",
                "status": "published" if publish else "draft",
                "published_at": timezone.now() if publish else None,
            },
        )
        if created:
            templates_created += 1
            self.stdout.write(self.style.SUCCESS(f"  Created: {template.name}"))
        else:
            self.stdout.write(f"  Already exists: {template.name}")

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(f"Done! Created {templates_created} new template(s)")
        )
        if not publish:
            self.stdout.write(
                self.style.WARNING("Templates created as drafts. Use --publish to publish immediately.")
            )
