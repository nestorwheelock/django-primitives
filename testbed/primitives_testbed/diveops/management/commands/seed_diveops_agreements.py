"""Seed diveops agreements with standard waiver templates.

Creates sample agreements including:
- PADI Certified Diver Liability Release and Assumption of Risk Agreement
- Vendor agreements with sample pricing terms
- Training agreements for DSD/courses

Usage:
    python manage.py seed_diveops_agreements
    python manage.py seed_diveops_agreements --clear  # Clear existing agreements first
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from django_agreements.models import Agreement
from django_parties.models import Organization, Person


# PADI Certified Diver Liability Release and Assumption of Risk Agreement
# This is a standard industry form used by dive operators worldwide
PADI_CERTIFIED_DIVER_LIABILITY_RELEASE = """
CERTIFIED DIVER LIABILITY RELEASE AND ASSUMPTION OF RISK AGREEMENT

Please read carefully and fill in all blanks before signing.

I, ______________________, hereby affirm that I am a certified diver, trained in safe
diving practices, or a student diver enrolled in a training program.

I understand and agree that neither the dive professionals conducting this program,
_________________________________ (hereinafter referred to as Dive Operator),
_________________________________ (hereinafter referred to as facility), nor
PADI Americas, Inc., nor its affiliate and subsidiary corporations, nor any of their
respective employees, officers, agents, contractors, and assigns (hereinafter referred
to as "Released Parties") may be held liable or responsible in any way for any injury,
death, or other damages to me, my family, estate, heirs, or assigns that may occur as a
result of my participation in this diving program or as a result of the negligence of
any party, including the Released Parties, whether passive or active.

In consideration of being allowed to participate in this program, I hereby personally
assume all risks of this program, whether foreseen or unforeseen, that may befall me
while I am a participant in this program including, but not limited to, the risks of
decompression sickness, embolism, or other hyperbaric/air expansion injury that may
result during the diving program.

I further release, exempt, and hold harmless said program and Released Parties from
any claim or lawsuit by me, my family, estate, heirs, or assigns, arising out of my
participation in this program including both claims arising during the program or
after I have completed the program.

I also understand that skin diving and scuba diving are physically strenuous activities
and that I will be exerting myself during this diving program, and that if I am injured
as a result of a heart attack, panic, hyperventilation, drowning or any other cause, I
expressly assume the risk of said injuries and death.

I further state that I am of lawful age and legally competent to sign this liability
release, or that I have acquired the written consent of my parent or guardian.

I understand the terms herein are contractual and not a mere recital, and that I have
signed this document as my own free act.

I HAVE FULLY INFORMED MYSELF OF THE CONTENTS OF THIS LIABILITY RELEASE AND ASSUMPTION
OF RISK AGREEMENT BY READING IT BEFORE I SIGNED IT ON BEHALF OF MYSELF AND MY HEIRS.

DIVER CERTIFICATION:
I am a certified diver, trained in safe diving practices.
Certification Agency: ________________
Certification Number: ________________
Date of Certification: ________________

PARTICIPANT INFORMATION:
Print Name: ____________________
Address: ____________________
City/State/Zip: ____________________
Phone: ____________________
Email: ____________________
Date of Birth: ____________________
Emergency Contact: ____________________
Emergency Phone: ____________________

SIGNATURE: ____________________
DATE: ____________________

WITNESS (if participant is a minor):
Print Name: ____________________
Signature: ____________________
Date: ____________________
"""

# PADI Standard Safe Diving Practices Statement of Understanding
PADI_SAFE_DIVING_PRACTICES = """
STANDARD SAFE DIVING PRACTICES STATEMENT OF UNDERSTANDING

I, ______________________, understand that as a certified diver I should:

1. Maintain good mental and physical fitness for diving. Avoid being under the
   influence of alcohol or dangerous drugs when diving. Keep proficient in diving
   skills, striving to increase them through continuing education and reviewing
   them in controlled conditions after a period of inactivity.

2. Be familiar with my dive sites. If not, obtain a formal diving orientation from
   a knowledgeable, local source. If diving conditions are worse than those in
   which I am experienced, postpone diving or select an alternate site with better
   conditions. Engage only in diving activities consistent with my training and
   experience.

3. Use complete, well-maintained, reliable equipment with which I am familiar; and
   inspect it for correct fit and function prior to each dive. Have a buoyancy
   control device (BCD), low-pressure buoyancy control inflation system, submersible
   pressure gauge, and dive computer/depth gauge and timing device. Deny use of my
   equipment to uncertified divers.

4. Listen carefully to dive briefings and instructions and follow the advice of those
   supervising my diving activities.

5. Adhere to the buddy system throughout every dive. Plan dives – Loss of buddy
   underwater: search briefly, then reunite on surface.

6. Be proficient in dive planning (dive computer/tables use). Make all dives no
   decompression dives and allow a margin of safety. Have a means to monitor depth
   and time underwater. Limit maximum depth to my level of training and experience.
   Ascend at a rate of not more than 18 metres/60 feet per minute. Be a SAFE diver –
   Slowly Ascend From Every dive. Make a safety stop as an added precaution,
   usually three minutes at five metres/15 feet.

7. Maintain proper buoyancy. Adjust weighting at the surface for neutral buoyancy
   with no air in my BCD. Maintain neutral buoyancy while underwater. Be buoyant
   for surface swimming and resting. Have weights clear for easy removal, and
   establish buoyancy when in distress while diving.

8. Breathe properly for diving. Never breath-hold or skip-breathe when breathing
   compressed air, and avoid excessive hyperventilation when breath-hold diving.
   Avoid overexertion while in the water.

9. Know and obey local dive flags and float.

10. Plan for emergencies and be familiar with emergency procedures.

SIGNATURE: ____________________
DATE: ____________________
"""

# Non-Agency Disclosure Statement
PADI_NON_AGENCY_DISCLOSURE = """
NON-AGENCY DISCLOSURE STATEMENT

I understand and agree that the Released Parties are not agents, employees or servants
of, or in joint venture with PADI Americas, Inc., PADI International, Inc., or any
PADI sanctioned member dive operation. Dive professionals operating under PADI
agreements receive only approval for the purpose of teaching PADI sanctioned programs
and related activities, but are not agents, employees, servants or in joint venture
with PADI Americas, Inc., PADI International, Inc. or any PADI sanctioned member dive
operation.

SIGNATURE: ____________________
DATE: ____________________
"""

# Medical Statement
PADI_MEDICAL_STATEMENT = """
MEDICAL STATEMENT

Diving is an enjoyable and exciting activity. To scuba dive, you must meet certain
medical criteria. Please answer the following questions on your diving-related
medical history by checking YES or NO. If you are not sure how to answer a question,
check YES.

GENERAL HEALTH:
[ ] YES [ ] NO  Could you be pregnant, or are you attempting to become pregnant?
[ ] YES [ ] NO  Do you regularly take prescription or non-prescription medications?
                (with the exception of birth control or anti-malarial drugs)
[ ] YES [ ] NO  Are you over 45 years of age and have one or more of the following:
                - currently smoke a pipe, cigars or cigarettes
                - have a high cholesterol level
                - have a family history of heart attack or stroke
                - are currently receiving medical care
                - high blood pressure
                - diabetes mellitus, even controlled by diet alone

If YES to any, explain: ____________________

HAVE YOU EVER HAD OR DO YOU CURRENTLY HAVE:
[ ] YES [ ] NO  Asthma, or wheezing with breathing, or wheezing with exercise?
[ ] YES [ ] NO  Frequent or severe attacks of hayfever or allergy?
[ ] YES [ ] NO  Frequent colds, sinusitis or bronchitis?
[ ] YES [ ] NO  Any form of lung disease?
[ ] YES [ ] NO  Pneumothorax (collapsed lung)?
[ ] YES [ ] NO  Other chest disease or chest surgery?
[ ] YES [ ] NO  Behavioral health, mental or psychological problems?
[ ] YES [ ] NO  Epilepsy, seizures, convulsions or take medications to prevent them?
[ ] YES [ ] NO  Recurring complicated migraine headaches or take medications to
                prevent them?
[ ] YES [ ] NO  Blackouts or fainting (full/partial loss of consciousness)?
[ ] YES [ ] NO  Do you frequently suffer from motion sickness?
[ ] YES [ ] NO  Dysentery or dehydration requiring medical intervention?
[ ] YES [ ] NO  Any diving accidents or decompression sickness?
[ ] YES [ ] NO  Inability to perform moderate exercise?
[ ] YES [ ] NO  Head injury with loss of consciousness in the past five years?
[ ] YES [ ] NO  Recurrent back problems?
[ ] YES [ ] NO  Back or spinal surgery?
[ ] YES [ ] NO  Diabetes?
[ ] YES [ ] NO  Back, arm or leg problems following surgery, injury or fracture?
[ ] YES [ ] NO  High blood pressure or take medicine to control blood pressure?
[ ] YES [ ] NO  Heart disease?
[ ] YES [ ] NO  Heart attack?
[ ] YES [ ] NO  Angina, heart surgery or blood vessel surgery?
[ ] YES [ ] NO  Sinus surgery?
[ ] YES [ ] NO  Ear disease or surgery, hearing loss or problems with balance?
[ ] YES [ ] NO  Recurrent ear problems?
[ ] YES [ ] NO  Bleeding or other blood disorders?
[ ] YES [ ] NO  Hernia?
[ ] YES [ ] NO  Ulcers or ulcer surgery?
[ ] YES [ ] NO  A colostomy or ileostomy?
[ ] YES [ ] NO  Recreational drug use or treatment for, or alcoholism in the past
                five years?

If YES to any, explain and provide physician clearance: ____________________

I certify that the above information is accurate and I have not withheld any
pertinent medical information. I agree to accept responsibility for omissions
regarding my failure to disclose any existing or past health conditions.

SIGNATURE: ____________________
DATE: ____________________
WITNESS: ____________________
"""

# Vendor Agreement Template
VENDOR_AGREEMENT_TEMPLATE = """
VENDOR SERVICES AGREEMENT

This Agreement is entered into between:

PARTY A (Dive Operator): ____________________
PARTY B (Vendor/Service Provider): ____________________

EFFECTIVE DATE: ____________________

TERMS AND CONDITIONS:

1. SERVICES
The Vendor agrees to provide the following services:
- Equipment rental and maintenance
- Transportation services
- Guide services
- Other services as agreed in writing

2. PRICING
The parties agree to the following pricing structure:
- Base rates as per attached price schedule
- Volume discounts may apply for bookings exceeding [X] divers/month
- Special rates for exclusive arrangements
- Annual rate reviews with 30 days notice

3. PAYMENT TERMS
- Net 30 days from invoice date
- Late payments subject to 1.5% monthly interest
- Disputes must be raised within 7 days of invoice

4. QUALITY STANDARDS
The Vendor agrees to:
- Maintain all required licenses and certifications
- Provide equipment meeting industry safety standards
- Carry appropriate liability insurance (minimum $1,000,000)
- Report any incidents or safety concerns immediately

5. TERM AND TERMINATION
- Initial term: 12 months from effective date
- Automatic renewal for successive 12-month periods
- Either party may terminate with 30 days written notice
- Immediate termination for material breach

6. CONFIDENTIALITY
Both parties agree to keep all pricing and business information confidential.

7. INDEMNIFICATION
Each party shall indemnify the other against claims arising from their own
negligence or breach of this Agreement.

SIGNATURES:

PARTY A: ____________________
Name: ____________________
Title: ____________________
Date: ____________________

PARTY B: ____________________
Name: ____________________
Title: ____________________
Date: ____________________
"""

# Sample agreement templates for seeding
AGREEMENT_TEMPLATES = [
    {
        "scope_type": "waiver",
        "name": "PADI Certified Diver Liability Release",
        "terms": {
            "description": "PADI Certified Diver Liability Release and Assumption of Risk Agreement",
            "template_version": "2024.1",
            "form_content": PADI_CERTIFIED_DIVER_LIABILITY_RELEASE,
            "safe_diving_practices": PADI_SAFE_DIVING_PRACTICES,
            "non_agency_disclosure": PADI_NON_AGENCY_DISCLOSURE,
            "requires_witness_if_minor": True,
            "requires_medical_clearance_if_yes": True,
        },
    },
    {
        "scope_type": "waiver",
        "name": "PADI Medical Statement and Questionnaire",
        "terms": {
            "description": "PADI Medical Statement for diving fitness assessment",
            "template_version": "2024.1",
            "form_content": PADI_MEDICAL_STATEMENT,
            "requires_physician_clearance_if_yes": True,
        },
    },
    {
        "scope_type": "training_agreement",
        "name": "Discover Scuba Diving Participant Agreement",
        "terms": {
            "description": "Agreement for Discover Scuba Diving (DSD) non-certified participants",
            "template_version": "2024.1",
            "includes_liability_release": True,
            "includes_medical_statement": True,
            "minimum_age": 10,
            "requires_guardian_consent_if_minor": True,
            "form_content": PADI_CERTIFIED_DIVER_LIABILITY_RELEASE,
        },
    },
    {
        "scope_type": "vendor_agreement",
        "name": "Equipment Rental Vendor Agreement",
        "terms": {
            "description": "Standard vendor agreement for equipment rental services",
            "template_version": "2024.1",
            "form_content": VENDOR_AGREEMENT_TEMPLATE,
            "payment_terms_days": 30,
            "late_payment_interest_monthly": "1.5%",
            "minimum_liability_coverage": "1000000",
            "initial_term_months": 12,
            "notice_period_days": 30,
        },
    },
    {
        "scope_type": "vendor_agreement",
        "name": "Boat Charter Vendor Agreement",
        "terms": {
            "description": "Vendor agreement for boat charter services",
            "template_version": "2024.1",
            "form_content": VENDOR_AGREEMENT_TEMPLATE,
            "payment_terms_days": 15,
            "requires_captain_certification": True,
            "requires_vessel_insurance": True,
            "requires_coast_guard_compliance": True,
            "cancellation_policy": "24 hours notice required",
        },
    },
]


class Command(BaseCommand):
    help = "Seed diveops agreements with standard waiver and vendor agreement templates"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing agreements before seeding",
        )
        parser.add_argument(
            "--with-samples",
            action="store_true",
            help="Create sample signed agreements (requires existing parties)",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options["clear"]:
            count = Agreement.objects.count()
            Agreement.objects.all().delete()
            self.stdout.write(
                self.style.WARNING(f"Cleared {count} existing agreements")
            )

        # Get or create default parties for sample agreements
        dive_shop = Organization.objects.filter(org_type="dive_shop").first()
        vendor = Organization.objects.filter(org_type="vendor").first()
        diver = Person.objects.first()

        if options["with_samples"] and (dive_shop and diver):
            self._create_sample_agreements(dive_shop, vendor, diver)
        else:
            self.stdout.write(
                "\nNo sample agreements created. Use --with-samples with existing "
                "Organization and Person records to create signed sample agreements."
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"\nAgreement templates available:\n"
                f"  - {len(AGREEMENT_TEMPLATES)} standard templates\n"
                f"\nTemplates include:\n"
                f"  - PADI Certified Diver Liability Release\n"
                f"  - PADI Medical Statement\n"
                f"  - DSD Participant Agreement\n"
                f"  - Equipment Rental Vendor Agreement\n"
                f"  - Boat Charter Vendor Agreement\n"
            )
        )

    def _create_sample_agreements(self, dive_shop, vendor, diver):
        """Create sample signed agreements."""
        from django_agreements.services import create_agreement

        created_count = 0

        # Create a sample waiver for the diver
        waiver_terms = AGREEMENT_TEMPLATES[0]["terms"].copy()
        waiver_terms["notes"] = "Sample agreement for demonstration"

        waiver = create_agreement(
            party_a=dive_shop,
            party_b=diver,
            scope_type="waiver",
            terms=waiver_terms,
            valid_from=timezone.now(),
        )
        self.stdout.write(f"  Created: Waiver for {diver.first_name} {diver.last_name}")
        created_count += 1

        # Create a vendor agreement if vendor exists
        if vendor:
            vendor_terms = AGREEMENT_TEMPLATES[3]["terms"].copy()
            vendor_terms["notes"] = "Sample vendor agreement for demonstration"

            vendor_agreement = create_agreement(
                party_a=dive_shop,
                party_b=vendor,
                scope_type="vendor_agreement",
                terms=vendor_terms,
                valid_from=timezone.now(),
            )
            self.stdout.write(f"  Created: Vendor agreement with {vendor.name}")
            created_count += 1

        self.stdout.write(
            self.style.SUCCESS(f"\nCreated {created_count} sample agreements.")
        )
