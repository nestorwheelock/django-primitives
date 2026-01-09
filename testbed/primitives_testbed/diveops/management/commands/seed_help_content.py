"""Management command to seed help center content.

This content is derived from actual code analysis and interface crawling,
not invented. Each section reflects the real functionality in the application.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from django_cms_core.models import ContentPage, ContentBlock, PageStatus, AccessLevel


# Help content derived from actual interface analysis and code examination
# See: docs/interface_analysis/interface_analysis.json for extracted UI elements
# See: primitives_testbed/diveops/models.py for model definitions
HELP_CONTENT = {
    "getting-started": {
        "dashboard-overview": {
            "title": "Dashboard Overview",
            "content": """
<p>The Dive Operations Dashboard is your central hub for managing daily operations.</p>

<h3>Dashboard Statistics</h3>
<p>The top of the dashboard displays key metrics:</p>
<ul>
    <li><strong>Registered Divers</strong> - Total active diver profiles in the system</li>
    <li><strong>Active Excursions</strong> - Scheduled and in-progress dive trips</li>
    <li><strong>Pending Agreements</strong> - Waivers awaiting signature</li>
</ul>

<h3>Weather Forecast</h3>
<p>The dashboard includes a weather widget showing current conditions and forecast for your dive shop location. Wind speed, direction, and conditions help with trip planning decisions.</p>

<h3>Quick Navigation</h3>
<p>The sidebar provides access to all major sections:</p>
<ul>
    <li><strong>Dive Operations</strong> - Excursions, Divers, Sites, Protected Areas, Agreements, Medical</li>
    <li><strong>Planning</strong> - Dive Plans and Dive Logs</li>
    <li><strong>System</strong> - Documents, Media, Audit Log</li>
    <li><strong>Configuration</strong> - Excursion Types, Agreement Templates, Catalog Items, AI Settings</li>
    <li><strong>Finance</strong> - Chart of Accounts, Payables</li>
</ul>
""",
        },
        "navigation-guide": {
            "title": "Navigation Guide",
            "content": """
<p>The staff portal uses a consistent navigation structure across all pages.</p>

<h3>Sidebar Navigation</h3>
<p>The left sidebar is organized into logical sections:</p>

<h4>Dive Operations</h4>
<ul>
    <li><strong>Excursions</strong> (<code>/staff/diveops/excursions/</code>) - Schedule and manage dive trips</li>
    <li><strong>Divers</strong> (<code>/staff/diveops/divers/</code>) - Diver profiles and certifications</li>
    <li><strong>Dive Sites</strong> (<code>/staff/diveops/sites/</code>) - Location details and photos</li>
    <li><strong>Protected Areas</strong> (<code>/staff/diveops/protected-areas/</code>) - Marine parks, permits, fees</li>
    <li><strong>Agreements</strong> (<code>/staff/diveops/signable-agreements/</code>) - Waivers and contracts</li>
    <li><strong>Medical Questionnaires</strong> (<code>/staff/diveops/medical/</code>) - Health screening</li>
</ul>

<h4>Planning</h4>
<ul>
    <li><strong>Dive Plans</strong> (<code>/staff/diveops/dive-plans/</code>) - Pre-dive briefings and profiles</li>
    <li><strong>Dive Logs</strong> (<code>/staff/diveops/dive-logs/</code>) - Post-dive records</li>
</ul>

<h4>Configuration</h4>
<ul>
    <li><strong>Excursion Types</strong> (<code>/staff/diveops/excursion-types/</code>) - Trip templates with pricing</li>
    <li><strong>Agreement Types</strong> (<code>/staff/diveops/agreements/templates/</code>) - Document templates</li>
    <li><strong>Catalog Items</strong> (<code>/staff/diveops/catalog/</code>) - Products and services</li>
    <li><strong>AI Settings</strong> (<code>/staff/diveops/settings/ai/</code>) - AI feature configuration</li>
</ul>

<h4>Finance</h4>
<ul>
    <li><strong>Chart of Accounts</strong> (<code>/staff/diveops/accounts/</code>) - Ledger accounts</li>
    <li><strong>Payables</strong> (<code>/staff/diveops/payables/</code>) - Vendor invoices and payments</li>
</ul>
""",
        },
        "your-account": {
            "title": "Your Account",
            "content": """
<p>Staff accounts provide access to the dive operations dashboard based on assigned roles.</p>

<h3>Account Access</h3>
<p>Your account provides access based on your staff permissions. The system tracks all actions in the audit log for accountability.</p>

<h3>Profile Link</h3>
<p>Click <strong>Profile</strong> in the sidebar to access your personal settings. Click <strong>Log out</strong> to end your session.</p>

<h3>Session Security</h3>
<p>Sessions expire after a period of inactivity. For security, always log out when using shared computers.</p>
""",
        },
    },
    "divers": {
        "creating-profiles": {
            "title": "Creating Diver Profiles",
            "content": """
<p>Diver profiles (DiverProfile model) store comprehensive information about each diver including contact details, certifications, medical status, and equipment sizing.</p>

<h3>Creating a New Diver</h3>
<ol>
    <li>Navigate to <strong>Divers</strong> in the sidebar</li>
    <li>Click <strong>Add Diver</strong></li>
    <li>Complete the form sections described below</li>
    <li>Click <strong>Create Diver</strong></li>
</ol>

<h3>Personal Information (Required)</h3>
<ul>
    <li><strong>First Name</strong> - Diver's first name</li>
    <li><strong>Last Name</strong> - Diver's last name</li>
    <li><strong>Email</strong> - Primary contact email</li>
</ul>

<h3>Certification Section</h3>
<ul>
    <li><strong>Agency</strong> - Certification agency (PADI, SSI, NAUI, etc.)</li>
    <li><strong>Level</strong> - Certification level (Open Water, Advanced, Rescue, Divemaster, etc.)</li>
    <li><strong>Certification Number</strong> - Card number for verification</li>
    <li><strong>Certification Date</strong> - Date certification was issued</li>
</ul>

<h3>Experience</h3>
<ul>
    <li><strong>Total Dives</strong> - Logged dive count for experience tracking</li>
</ul>

<h3>Medical Clearance</h3>
<ul>
    <li><strong>Clearance Date</strong> - When physician clearance was obtained</li>
    <li><strong>Valid Until</strong> - Expiration date of medical clearance</li>
</ul>

<h3>Diver Profile</h3>
<ul>
    <li><strong>Diver Type</strong>:
        <ul>
            <li><em>Does Diving (Activity)</em> - Diving is an activity they do</li>
            <li><em>Diver (Identity)</em> - Diving is core to their identity</li>
        </ul>
    </li>
    <li><strong>Equipment Ownership</strong>:
        <ul>
            <li><em>None - Rents All</em> - Full rental customer</li>
            <li><em>Partial - Owns Some Gear</em> - Hybrid rental</li>
            <li><em>Full - Owns All Essential Gear</em> - Brings own equipment</li>
        </ul>
    </li>
</ul>

<h3>Body Measurements</h3>
<p>Used for equipment fitting and weighting calculations:</p>
<ul>
    <li><strong>Weight (kg)</strong> - For buoyancy calculations</li>
    <li><strong>Height (cm)</strong> - For wetsuit sizing</li>
    <li><strong>Weight Required (kg)</strong> - Calculated neutral buoyancy weight</li>
</ul>

<h3>Gear Sizes</h3>
<ul>
    <li><strong>Wetsuit Size</strong> - e.g., M, L, XL</li>
    <li><strong>BCD Size</strong> - e.g., M, L, XL</li>
    <li><strong>Fin Size</strong> - e.g., M/L, 9-10</li>
    <li><strong>Mask Fit</strong> - e.g., Low volume, Standard</li>
    <li><strong>Glove Size</strong> - e.g., M, L, XL</li>
    <li><strong>Gear Notes</strong> - Additional preferences or requirements</li>
</ul>
""",
        },
        "managing-certifications": {
            "title": "Managing Certifications",
            "content": """
<p>The certification system tracks diver qualifications using a normalized model with agency-scoped certification levels.</p>

<h3>Certification Levels</h3>
<p>Certifications are ranked for eligibility checking:</p>
<ul>
    <li><strong>Scuba Diver</strong> - Entry level (rank 1)</li>
    <li><strong>Open Water Diver</strong> - Basic certification (rank 2)</li>
    <li><strong>Advanced Open Water</strong> - Intermediate (rank 3)</li>
    <li><strong>Rescue Diver</strong> - Advanced (rank 4)</li>
    <li><strong>Divemaster</strong> - Professional (rank 5)</li>
    <li><strong>Instructor</strong> - Teaching level (rank 6)</li>
</ul>

<h3>Specialty Certifications</h3>
<p>Additional certifications tracked include:</p>
<ul>
    <li>Enriched Air (Nitrox) Diver</li>
    <li>Deep Diver</li>
    <li>Night Diver</li>
    <li>Wreck Diver</li>
    <li>Cavern Diver</li>
    <li>Underwater Photographer</li>
    <li>Peak Performance Buoyancy</li>
</ul>

<h3>Verification Status</h3>
<p>Each certification tracks:</p>
<ul>
    <li><strong>Verification status</strong> - Whether card has been verified</li>
    <li><strong>Verified by</strong> - Staff member who verified</li>
    <li><strong>Verified at</strong> - Date of verification</li>
    <li><strong>Document proof</strong> - Uploaded certification card photo</li>
</ul>

<h3>Eligibility Checking</h3>
<p>When booking divers for excursions, the system automatically checks certification requirements. The <code>is_current</code> property validates expiration dates.</p>
""",
        },
        "emergency-contacts": {
            "title": "Emergency Contacts",
            "content": """
<p>The EmergencyContact model stores emergency contact information with priority ordering for each diver.</p>

<h3>Contact Information</h3>
<p>Each emergency contact includes:</p>
<ul>
    <li><strong>Name</strong> - Contact's full name</li>
    <li><strong>Relationship</strong> - Relationship to diver</li>
    <li><strong>Phone numbers</strong> - Primary and alternate contact numbers</li>
    <li><strong>Priority</strong> - Order of contact (primary, secondary, etc.)</li>
</ul>

<h3>Diver Relationships</h3>
<p>The DiverRelationship model tracks connections between divers:</p>
<ul>
    <li><strong>Spouse</strong> - Married partner</li>
    <li><strong>Buddy</strong> - Preferred dive buddy</li>
    <li><strong>Friend</strong> - Social connection</li>
    <li><strong>Family</strong> - Family member</li>
    <li><strong>Instructor/Student</strong> - Training relationship</li>
</ul>

<h3>Buddy Preferences</h3>
<p>Divers can mark preferred buddies. The system provides methods to query:</p>
<ul>
    <li><code>spouse</code> - Find spouse relationship</li>
    <li><code>preferred_buddies</code> - List marked buddy preferences</li>
    <li><code>related_divers</code> - All connected divers</li>
</ul>
""",
        },
        "diver-categories": {
            "title": "Diver Categories",
            "content": """
<p>Diver categorization is used for agreement template targeting and eligibility.</p>

<h3>Category Types</h3>
<p>The DiverCategory enumeration defines:</p>
<ul>
    <li><strong>all</strong> - Applies to all divers</li>
    <li><strong>certified</strong> - Certified divers only</li>
    <li><strong>student</strong> - Divers in training</li>
    <li><strong>dsd</strong> - Discover Scuba Diving participants</li>
</ul>

<h3>Agreement Template Targeting</h3>
<p>Agreement templates can be configured for specific diver categories. When creating agreements, the system presents only templates appropriate for the diver's category.</p>

<h3>Diver Type Classification</h3>
<p>Separate from category, divers are classified by their relationship with diving:</p>
<ul>
    <li><strong>Activity</strong> - Does diving as an occasional activity</li>
    <li><strong>Identity</strong> - Diving is core to their identity</li>
</ul>
<p>This classification helps with marketing and communication targeting.</p>
""",
        },
    },
    "bookings": {
        "scheduling-excursions": {
            "title": "Scheduling Excursions",
            "content": """
<p>Excursions are single-day operational units representing scheduled dive trips.</p>

<h3>Creating an Excursion</h3>
<ol>
    <li>Navigate to <strong>Excursions</strong></li>
    <li>Click <strong>New Excursion</strong></li>
    <li>Select an <strong>Excursion Type</strong> (template with defaults)</li>
    <li>Set <strong>Date</strong> and <strong>Departure Time</strong></li>
    <li>Choose <strong>Dive Site</strong> (optional - can have multiple via dives)</li>
    <li>Set <strong>Maximum Divers</strong> capacity</li>
    <li>Set <strong>Price per Diver</strong> (pre-filled from type)</li>
    <li>Click <strong>Create</strong></li>
</ol>

<h3>Excursion Types</h3>
<p>ExcursionType models serve as templates defining:</p>
<ul>
    <li><strong>Name and description</strong></li>
    <li><strong>Dive mode</strong> - boat, shore, cenote, cavern</li>
    <li><strong>Time of day</strong> - morning, afternoon, night</li>
    <li><strong>Duration</strong> - typical_duration_minutes</li>
    <li><strong>Dives per excursion</strong> - number of dives included</li>
    <li><strong>Base price</strong> - default pricing</li>
    <li><strong>Certification requirements</strong> - minimum level required</li>
    <li><strong>Suitable sites</strong> - M2M relationship (empty = all sites)</li>
</ul>

<h3>Excursion Status Workflow</h3>
<ul>
    <li><strong>scheduled</strong> - Future trip, accepting bookings</li>
    <li><strong>boarding</strong> - Check-in in progress</li>
    <li><strong>in_progress</strong> - Trip underway</li>
    <li><strong>completed</strong> - Trip finished</li>
    <li><strong>cancelled</strong> - Trip cancelled</li>
</ul>

<h3>Capacity Management</h3>
<p>The <code>spots_available</code> property calculates remaining capacity. The <code>is_full</code> property indicates when max_divers is reached.</p>
""",
        },
        "managing-bookings": {
            "title": "Managing Bookings",
            "content": """
<p>Bookings link divers to excursions and track reservation lifecycle.</p>

<h3>Creating a Booking</h3>
<ol>
    <li>Open the excursion detail page</li>
    <li>Click <strong>Add Booking</strong></li>
    <li>Search for and select a diver</li>
    <li>System performs eligibility checks automatically</li>
    <li>Confirm the booking</li>
</ol>

<h3>Booking Status</h3>
<ul>
    <li><strong>pending</strong> - Reservation made, not confirmed</li>
    <li><strong>confirmed</strong> - Booking confirmed</li>
    <li><strong>checked_in</strong> - Diver arrived and checked in</li>
    <li><strong>cancelled</strong> - Booking cancelled</li>
    <li><strong>no_show</strong> - Diver didn't arrive</li>
</ul>

<h3>Eligibility Checking</h3>
<p>Before booking confirmation, the system validates:</p>
<ul>
    <li>Diver has required certification level for excursion type</li>
    <li>Medical clearance is current (if required)</li>
    <li>Waiver is signed and valid</li>
    <li>No scheduling conflicts</li>
</ul>

<h3>Eligibility Overrides</h3>
<p>The EligibilityOverride model allows bypassing requirements:</p>
<ul>
    <li>One override per booking only</li>
    <li>Requires <strong>approved_by</strong> staff member</li>
    <li>Requires documented <strong>reason</strong></li>
    <li>Tracks which requirement was bypassed</li>
    <li>Creates immutable audit trail</li>
</ul>

<h3>Price Snapshot</h3>
<p>The booking captures <code>price_snapshot</code> at creation time. This ensures price immutability even if the excursion price changes later.</p>
""",
        },
        "check-in-process": {
            "title": "Check-in Process",
            "content": """
<p>Check-in is managed through the ExcursionRoster model which tracks actual participants.</p>

<h3>Check-in Workflow</h3>
<ol>
    <li>Open the excursion on departure day</li>
    <li>View the booking list</li>
    <li>For each arriving diver, click to mark check-in</li>
    <li>System records <code>checked_in_at</code> timestamp and <code>checked_in_by</code> staff</li>
</ol>

<h3>Roster Roles</h3>
<p>Each roster entry can have a role:</p>
<ul>
    <li><strong>Diver</strong> - Customer participant</li>
    <li><strong>Divemaster</strong> - Professional leading the dive</li>
    <li><strong>Instructor</strong> - Teaching role</li>
</ul>

<h3>Dive Completion</h3>
<p>After the excursion, mark <code>dive_completed</code> status for each participant. Notes can be added to individual roster entries.</p>

<h3>Excursion Status Transitions</h3>
<ul>
    <li>Use <strong>Start Excursion</strong> to change status to <code>in_progress</code></li>
    <li>Use <strong>Complete Excursion</strong> to change status to <code>completed</code></li>
</ul>
""",
        },
        "recurring-series": {
            "title": "Recurring Series",
            "content": """
<p>ExcursionSeries enables scheduling recurring excursions using RFC 5545 recurrence rules.</p>

<h3>Creating a Recurring Series</h3>
<ol>
    <li>Open an existing excursion</li>
    <li>Click <strong>Make Recurring</strong></li>
    <li>Configure the recurrence pattern</li>
    <li>Set series defaults (capacity, price, meeting place)</li>
    <li>Save the series</li>
</ol>

<h3>Recurrence Rules</h3>
<p>The RecurrenceRule model stores RFC 5545 RRULE strings:</p>
<ul>
    <li><strong>FREQ=WEEKLY;BYDAY=SA</strong> - Every Saturday</li>
    <li><strong>FREQ=DAILY</strong> - Every day</li>
    <li><strong>FREQ=WEEKLY;BYDAY=MO,WE,FR</strong> - Monday, Wednesday, Friday</li>
</ul>

<h3>Series Attributes</h3>
<ul>
    <li><strong>excursion_type</strong> - Template for generated excursions</li>
    <li><strong>dive_site</strong> - Default site</li>
    <li><strong>capacity_default</strong> - Default max divers</li>
    <li><strong>price_default</strong> - Default price</li>
    <li><strong>meeting_place</strong> - Where divers meet</li>
    <li><strong>window_days</strong> - How far ahead to generate occurrences</li>
</ul>

<h3>Series Status</h3>
<ul>
    <li><strong>draft</strong> - Not yet active</li>
    <li><strong>active</strong> - Generating occurrences</li>
    <li><strong>paused</strong> - Temporarily stopped</li>
    <li><strong>retired</strong> - Permanently ended</li>
</ul>

<h3>Exceptions</h3>
<p>RecurrenceException handles individual date modifications:</p>
<ul>
    <li><strong>cancelled</strong> - Skip this occurrence</li>
    <li><strong>rescheduled</strong> - Move to different time</li>
    <li><strong>added</strong> - Extra occurrence</li>
</ul>
""",
        },
        "cancellations-refunds": {
            "title": "Cancellations & Refunds",
            "content": """
<p>Booking cancellations and financial settlements are handled through the SettlementRecord model.</p>

<h3>Cancelling a Booking</h3>
<ol>
    <li>Open the booking</li>
    <li>Click <strong>Cancel Booking</strong></li>
    <li>Booking status changes to <code>cancelled</code></li>
    <li><code>cancelled_at</code> timestamp is recorded</li>
</ol>

<h3>Settlement Types</h3>
<p>SettlementRecord tracks financial transactions:</p>
<ul>
    <li><strong>revenue</strong> - Payment received</li>
    <li><strong>refund</strong> - Payment returned</li>
</ul>

<h3>Idempotent Settlements</h3>
<p>Each settlement has a unique <code>idempotency_key</code> preventing duplicate processing. The system generates deterministic keys based on booking and transaction type.</p>

<h3>Financial State</h3>
<p>Bookings track financial state through:</p>
<ul>
    <li><code>is_settled</code> - Whether payment is complete</li>
    <li><code>has_refund</code> - Whether refund was issued</li>
    <li><code>get_financial_state()</code> - Current state summary</li>
</ul>

<h3>Protection Against Deletion</h3>
<p>Settled bookings cannot be deleted to preserve financial records. Use soft delete (<code>deleted_at</code>) instead.</p>
""",
        },
    },
    "agreements": {
        "creating-agreements": {
            "title": "Creating Agreements",
            "content": """
<p>SignableAgreement tracks the full workflow of liability waivers and other documents from creation through signature.</p>

<h3>Creating a New Agreement</h3>
<ol>
    <li>Navigate to <strong>Agreements</strong></li>
    <li>Click <strong>New Agreement</strong></li>
    <li>Select an <strong>Agreement Template</strong> (radio buttons)</li>
    <li>Select the <strong>Diver</strong> from the dropdown</li>
    <li>Choose <strong>Delivery Method</strong>:
        <ul>
            <li><em>Link (copy signing URL)</em> - Generate shareable link</li>
            <li><em>Email (send to diver)</em> - Email the signing link</li>
            <li><em>In Person (sign on device)</em> - Sign at the shop</li>
        </ul>
    </li>
    <li>Set <strong>Expires In</strong> (7, 14, 30, 60, or 90 days)</li>
    <li>Click <strong>Create & Send</strong> or <strong>Save as Draft</strong></li>
</ol>

<h3>Agreement Templates</h3>
<p>AgreementTemplate defines reusable document types:</p>
<ul>
    <li><strong>waiver</strong> - Liability release</li>
    <li><strong>medical</strong> - Medical disclosure</li>
    <li><strong>briefing</strong> - Dive briefing acknowledgment</li>
    <li><strong>code_of_conduct</strong> - Behavior agreement</li>
    <li><strong>rental</strong> - Equipment rental terms</li>
    <li><strong>training</strong> - Course enrollment</li>
</ul>

<h3>Template Targeting</h3>
<p>Templates can target specific audiences:</p>
<ul>
    <li><strong>target_party_type</strong> - diver, employee, vendor, any</li>
    <li><strong>diver_category</strong> - all, certified, student, dsd</li>
</ul>
""",
        },
        "sending-for-signature": {
            "title": "Sending for Signature",
            "content": """
<p>Agreements use secure token-based access for the signing process.</p>

<h3>Access Token Security</h3>
<p>Each agreement generates:</p>
<ul>
    <li>Cryptographically random access token</li>
    <li>SHA-256 hash stored (raw token never stored)</li>
    <li><code>token_consumed</code> flag for one-time use</li>
    <li><code>expires_at</code> enforcement at signing time</li>
</ul>

<h3>Delivery Methods</h3>
<ul>
    <li><strong>Email</strong> - System sends email with secure signing link</li>
    <li><strong>Link</strong> - Copy URL to share via text, WhatsApp, etc.</li>
    <li><strong>In Person</strong> - Diver signs on shop device</li>
</ul>

<h3>Resending</h3>
<p>For agreements in <code>sent</code> status, use <strong>Resend</strong> to generate a new token and send again. Previous tokens are invalidated.</p>

<h3>Expiration Options</h3>
<p>Signing links can expire in:</p>
<ul>
    <li>7 days (default)</li>
    <li>14 days</li>
    <li>30 days</li>
    <li>60 days</li>
    <li>90 days</li>
</ul>
""",
        },
        "tracking-status": {
            "title": "Tracking Status",
            "content": """
<p>Monitor agreement progress through the defined status workflow.</p>

<h3>Agreement Status</h3>
<ul>
    <li><strong>draft</strong> - Created but not sent, content editable</li>
    <li><strong>sent</strong> - Delivered to signer, awaiting signature</li>
    <li><strong>signed</strong> - Completed with digital signature</li>
    <li><strong>void</strong> - Cancelled before signing</li>
    <li><strong>expired</strong> - Signing link expired without signature</li>
</ul>

<h3>List Filtering</h3>
<p>The agreements list provides filters to find specific documents:</p>
<ul>
    <li>Filter by status (dropdown)</li>
    <li>Search by diver name</li>
    <li>Date range filtering</li>
</ul>

<h3>Agreement Detail View</h3>
<p>Each agreement shows:</p>
<ul>
    <li>Status badge with color coding</li>
    <li>Diver information</li>
    <li>Template used and version</li>
    <li>Timeline of status changes</li>
    <li>Digital signature details (if signed)</li>
</ul>

<h3>Content Hash</h3>
<p>Agreements maintain a SHA-256 <code>content_hash</code> for integrity verification. Any content changes create revision records.</p>
""",
        },
        "voiding-agreements": {
            "title": "Voiding Agreements",
            "content": """
<p>Voiding cancels an agreement before it is signed.</p>

<h3>When to Void</h3>
<p>Void an agreement when:</p>
<ul>
    <li>Created in error</li>
    <li>Wrong template selected</li>
    <li>Wrong diver associated</li>
    <li>Related booking cancelled</li>
</ul>

<h3>Voiding Restrictions</h3>
<p><strong>Important:</strong> Only agreements in <code>draft</code> or <code>sent</code> status can be voided.</p>
<p>Signed agreements are legal documents and cannot be voided. To nullify a signed agreement, create a <strong>Revocation Agreement</strong> that the diver must also sign.</p>

<h3>Voiding Process</h3>
<ol>
    <li>Open the agreement (must be draft or sent)</li>
    <li>Click <strong>Void Agreement</strong></li>
    <li>Enter required reason for voiding</li>
    <li>Confirm the action</li>
</ol>

<h3>Revision History</h3>
<p>SignableAgreementRevision maintains an immutable audit trail of all content changes, including voiding. Each revision records:</p>
<ul>
    <li><code>revision_number</code></li>
    <li><code>previous</code> and <code>new content_hash</code></li>
    <li><code>change_note</code> (required explanation)</li>
    <li><code>changed_by</code> staff member</li>
</ul>
""",
        },
    },
    "medical": {
        "medical-questionnaires": {
            "title": "Medical Questionnaires",
            "content": """
<p>Medical questionnaires screen divers for health conditions that may affect diving safety, based on RSTC/DAN Medical Statement guidelines.</p>

<h3>Questionnaire List</h3>
<p>The medical questionnaires page (<code>/staff/diveops/medical/</code>) displays:</p>
<ul>
    <li>All submitted questionnaires</li>
    <li>Status filters for reviewing</li>
    <li>Diver information and submission date</li>
    <li>Flagged conditions count</li>
</ul>

<h3>Sending Questionnaires</h3>
<p>Questionnaires can be sent:</p>
<ul>
    <li>From diver profile medical tab</li>
    <li>Automatically when creating first booking</li>
    <li>On annual renewal dates</li>
</ul>

<h3>Integration with django-questionnaires</h3>
<p>The medical system uses the django-questionnaires package for form rendering and response collection.</p>
""",
        },
        "reviewing-responses": {
            "title": "Reviewing Responses",
            "content": """
<p>Staff review completed questionnaires to determine diving eligibility.</p>

<h3>Review Workflow</h3>
<ol>
    <li>Navigate to <strong>Medical Questionnaires</strong></li>
    <li>Filter for pending review status</li>
    <li>Open questionnaire to see all responses</li>
    <li>Review flagged conditions</li>
    <li>Make clearance decision</li>
</ol>

<h3>Flagged Conditions</h3>
<p>Certain "Yes" answers automatically flag for review:</p>
<ul>
    <li>Cardiovascular conditions</li>
    <li>Respiratory conditions</li>
    <li>Neurological conditions (seizures, blackouts)</li>
    <li>Diabetes requiring medication</li>
    <li>Recent surgery or illness</li>
    <li>Current medications</li>
</ul>

<h3>Medical Status Determination</h3>
<p>The <code>get_diver_medical_status()</code> service returns:</p>
<ul>
    <li><strong>cleared</strong> - Approved for diving</li>
    <li><strong>restricted</strong> - Approved with limitations</li>
    <li><strong>needs_review</strong> - Requires staff evaluation</li>
    <li><strong>denied</strong> - Not approved for diving</li>
</ul>
""",
        },
        "clearance-process": {
            "title": "Clearance Process",
            "content": """
<p>Physician clearance is required when questionnaire responses indicate potential health concerns.</p>

<h3>When Clearance Required</h3>
<ul>
    <li>Questionnaire has flagged responses</li>
    <li>Diver reports significant medical conditions</li>
    <li>Previous clearance has expired</li>
</ul>

<h3>Clearance Workflow</h3>
<ol>
    <li>System generates PDF with flagged conditions</li>
    <li>Diver takes form to physician</li>
    <li>Physician examines and signs clearance</li>
    <li>Diver returns signed form</li>
    <li>Staff uploads and records clearance</li>
</ol>

<h3>Recording Clearance</h3>
<p>The DiverProfile stores:</p>
<ul>
    <li><code>medical_clearance_date</code> - When obtained</li>
    <li><code>medical_clearance_valid_until</code> - Expiration</li>
</ul>

<h3>Medical Provider Integration</h3>
<p>The MedicalProviderProfile and MedicalProviderRelationship models track relationships between divers and their healthcare providers.</p>
""",
        },
        "retention-policies": {
            "title": "Retention Policies",
            "content": """
<p>Medical records are subject to retention policies and privacy requirements.</p>

<h3>Document Retention</h3>
<p>The DocumentRetentionPolicy model manages automatic document lifecycle:</p>
<ul>
    <li>Retention period definition</li>
    <li>Automatic purge scheduling</li>
    <li>Legal hold capability (DocumentLegalHold)</li>
</ul>

<h3>Privacy Considerations</h3>
<p>Medical information is protected:</p>
<ul>
    <li>Access limited to authorized staff</li>
    <li>Audit logging of all access</li>
    <li>Secure storage and transmission</li>
</ul>

<h3>Retention Administration</h3>
<p>Staff can manage retention policies through:</p>
<ul>
    <li>RetentionPolicyListView</li>
    <li>RetentionPolicyCreateView</li>
    <li>RetentionPolicyUpdateView</li>
    <li>RetentionPolicyDeleteView</li>
</ul>
""",
        },
    },
    "protected-areas": {
        "managing-permits": {
            "title": "Managing Permits",
            "content": """
<p>ProtectedArea models represent marine parks, reserves, and other regulated diving areas.</p>

<h3>Protected Area Types</h3>
<ul>
    <li><strong>national_park</strong></li>
    <li><strong>marine_park</strong></li>
    <li><strong>reserve</strong></li>
    <li><strong>biosphere_reserve</strong></li>
    <li><strong>protected_area</strong></li>
    <li><strong>sanctuary</strong></li>
</ul>

<h3>Hierarchical Structure</h3>
<p>Protected areas support hierarchy through self-referential parent relationships. The <code>get_ancestors()</code> method returns the parent chain.</p>

<h3>Unified Permit System</h3>
<p>ProtectedAreaPermit handles all permit types:</p>
<ul>
    <li><strong>guide</strong> - Guide credential (requires diver)</li>
    <li><strong>vessel</strong> - Boat permit (requires vessel_name, vessel_registration)</li>
    <li><strong>photography</strong> - Commercial photography permit</li>
    <li><strong>diving</strong> - Operator diving permit</li>
</ul>

<h3>Permit Attributes</h3>
<ul>
    <li><code>permit_number</code> - Unique per area+type</li>
    <li><code>issued_at</code>, <code>expires_at</code> - Validity period</li>
    <li><code>authorized_zones</code> - M2M (empty = all zones)</li>
</ul>
""",
        },
        "fee-schedules": {
            "title": "Fee Schedules",
            "content": """
<p>ProtectedAreaFeeSchedule configures fees for diving activities in protected areas.</p>

<h3>Fee Types</h3>
<ul>
    <li><strong>per_person</strong> - Charged per diver</li>
    <li><strong>per_boat</strong> - Charged per vessel</li>
    <li><strong>per_trip</strong> - Charged per excursion</li>
    <li><strong>per_day</strong> - Daily fee</li>
    <li><strong>per_activity</strong> - Activity-specific fee</li>
</ul>

<h3>Activity Scope</h3>
<p>Fees can apply to:</p>
<ul>
    <li>diving</li>
    <li>snorkeling</li>
    <li>kayaking</li>
    <li>fishing</li>
    <li>all activities</li>
</ul>

<h3>Fee Tiers</h3>
<p>ProtectedAreaFeeTier allows tiered pricing:</p>
<ul>
    <li><strong>tourist</strong> - Standard tourist rate</li>
    <li><strong>national</strong> - National citizen rate</li>
    <li><strong>local</strong> - Local resident rate</li>
    <li><strong>student</strong> - Student discount</li>
    <li><strong>senior</strong> - Senior discount</li>
    <li><strong>child</strong> - Child rate (age_min, age_max)</li>
    <li><strong>infant</strong> - Infant (usually free)</li>
</ul>

<h3>Eligibility Proof</h3>
<p>DiverEligibilityProof tracks documentation for tier qualification:</p>
<ul>
    <li>Proof types: student_id, national_id, resident_card, passport, birth_cert</li>
    <li>Status: pending, verified, rejected</li>
    <li>Expiration tracking for time-limited proofs</li>
</ul>
""",
        },
        "zone-rules": {
            "title": "Zone Rules",
            "content": """
<p>ProtectedAreaZone divides protected areas into zones with specific regulations.</p>

<h3>Zone Types</h3>
<ul>
    <li><strong>core</strong> - No-take zone, highest protection</li>
    <li><strong>buffer</strong> - Buffer zone around core</li>
    <li><strong>use</strong> - Recreational use zone</li>
    <li><strong>restoration</strong> - Restoration area</li>
    <li><strong>research</strong> - Research-only access</li>
</ul>

<h3>Zone Permissions</h3>
<p>Each zone defines:</p>
<ul>
    <li><code>diving_allowed</code></li>
    <li><code>anchoring_allowed</code></li>
    <li><code>fishing_allowed</code></li>
    <li><code>requires_guide</code></li>
    <li><code>requires_permit</code></li>
    <li><code>max_divers</code> - Capacity limit</li>
</ul>

<h3>Zone Rules</h3>
<p>ProtectedAreaRule enforces specific regulations:</p>
<ul>
    <li><strong>Rule types</strong>: max_depth, max_divers, certification, equipment, time, activity, conduct</li>
    <li><strong>Applies to</strong>: diver, group, vessel, operator</li>
    <li><strong>Enforcement levels</strong>: info, warn, block</li>
    <li><strong>Effective dating</strong>: effective_start, effective_end</li>
</ul>

<h3>Compliance Checking</h3>
<p>Rules use comparison operators (lte, gte, eq, in, contains, required_true) against values. The system can block bookings that violate blocking-level rules.</p>
""",
        },
    },
    "system": {
        "document-management": {
            "title": "Document Management",
            "content": """
<p>The document browser (<code>/staff/diveops/documents/</code>) provides file storage and organization.</p>

<h3>Document Browser Features</h3>
<ul>
    <li>Folder-based organization</li>
    <li>File upload and download</li>
    <li>Preview for common file types</li>
    <li>Search functionality</li>
</ul>

<h3>Document Types Used</h3>
<ul>
    <li><strong>Certification cards</strong> - Proof of diver certification</li>
    <li><strong>Profile photos</strong> - Diver identification</li>
    <li><strong>Dive site photos</strong> - Site documentation and marketing</li>
    <li><strong>Signature documents</strong> - Captured signatures</li>
    <li><strong>Signed agreement PDFs</strong> - Completed waivers</li>
    <li><strong>Medical clearances</strong> - Physician letters</li>
    <li><strong>Eligibility proofs</strong> - ID documents for fee tiers</li>
</ul>

<h3>Folder Management</h3>
<p>Views for folder organization:</p>
<ul>
    <li>FolderCreateView, FolderUpdateView, FolderDeleteView</li>
    <li>FolderPermissionListView for access control</li>
</ul>

<h3>Soft Delete</h3>
<p>Documents use soft delete with a trash feature:</p>
<ul>
    <li>DocumentDeleteView moves to trash</li>
    <li>DocumentRestoreView recovers from trash</li>
    <li>DocumentPermanentDeleteView for final deletion</li>
    <li>EmptyTrashView clears all trashed documents</li>
</ul>
""",
        },
        "audit-log": {
            "title": "Audit Log",
            "content": """
<p>The audit log (<code>/staff/diveops/audit-log/</code>) tracks all system activity for accountability and troubleshooting.</p>

<h3>What's Logged</h3>
<p>The django-audit-log package records:</p>
<ul>
    <li>Record creation, updates, and deletions</li>
    <li>Status changes (booking confirmed, agreement signed, etc.)</li>
    <li>User actions with timestamps</li>
    <li>IP addresses and user agents</li>
</ul>

<h3>Viewing the Log</h3>
<p>The AuditLogView displays entries with filtering:</p>
<ul>
    <li>Date range</li>
    <li>User who performed action</li>
    <li>Action type</li>
    <li>Record type (model)</li>
</ul>

<h3>Entry Details</h3>
<p>Each audit entry includes:</p>
<ul>
    <li>Timestamp</li>
    <li>Actor (user who performed action)</li>
    <li>Action description</li>
    <li>Affected record</li>
    <li>Before/after values for changes</li>
</ul>

<h3>Use Cases</h3>
<ul>
    <li>Investigate who made a change</li>
    <li>Track workflow progression</li>
    <li>Verify compliance actions</li>
    <li>Debug issues</li>
    <li>Security monitoring</li>
</ul>
""",
        },
        "ai-settings": {
            "title": "AI Settings",
            "content": """
<p>Configure AI-assisted features through the AI Settings page (<code>/staff/diveops/settings/ai/</code>).</p>

<h3>AI Features</h3>
<p>The AISettings model configures:</p>
<ul>
    <li>Feature flags for AI capabilities</li>
    <li>Parameters for AI behavior</li>
    <li>Data access permissions</li>
</ul>

<h3>Configuration Options</h3>
<p>Settings may include:</p>
<ul>
    <li>Enable/disable AI assistance</li>
    <li>Configure which data AI can access</li>
    <li>Set processing limits</li>
</ul>

<h3>Privacy Considerations</h3>
<p>AI features are designed with privacy in mind:</p>
<ul>
    <li>Configurable data access</li>
    <li>Audit logging of AI operations</li>
    <li>Opt-out options available</li>
</ul>
""",
        },
        "automated-documentation": {
            "title": "Automated Documentation",
            "content": """
<p>DiveOps includes tools for automated documentation with screenshots.</p>

<h3>Screenshot Capture</h3>
<p>The <code>scripts/capture_help_screenshots.py</code> script uses Playwright to:</p>
<ul>
    <li>Navigate to application pages</li>
    <li>Capture full-page screenshots</li>
    <li>Capture cropped component screenshots</li>
    <li>Organize by page type (lists, details, forms, system)</li>
</ul>

<h3>Interface Crawler</h3>
<p>The <code>scripts/crawl_interface.py</code> extracts UI elements:</p>
<ul>
    <li>Form fields with labels and types</li>
    <li>Buttons and actions</li>
    <li>Table structures</li>
    <li>Navigation links</li>
</ul>

<h3>Running the Tools</h3>
<pre>
# Capture screenshots
python scripts/capture_help_screenshots.py --headed

# Crawl interface
python scripts/crawl_interface.py

# Embed screenshots in CMS
python manage.py embed_help_screenshots
</pre>

<h3>Output Locations</h3>
<ul>
    <li><code>media/help/screenshots/</code> - Screenshot images</li>
    <li><code>docs/interface_analysis/</code> - Interface analysis JSON</li>
</ul>
""",
        },
    },
}


class Command(BaseCommand):
    """Seed help center content from predefined content."""

    help = "Create help center articles in the CMS"

    def add_arguments(self, parser):
        parser.add_argument(
            "--publish",
            action="store_true",
            help="Publish articles immediately after creation",
        )
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Overwrite existing articles with the same slug",
        )

    def handle(self, *args, **options):
        """Create help content pages."""
        publish = options.get("publish", False)
        overwrite = options.get("overwrite", False)

        created_count = 0
        updated_count = 0
        skipped_count = 0

        for section_slug, articles in HELP_CONTENT.items():
            self.stdout.write(f"\nSection: {section_slug}")

            for article_slug, article_data in articles.items():
                cms_slug = f"help-{section_slug}-{article_slug}"

                # Check if page exists
                existing = ContentPage.objects.filter(
                    slug=cms_slug,
                    deleted_at__isnull=True,
                ).first()

                if existing and not overwrite:
                    self.stdout.write(f"  Skipped: {article_data['title']} (exists)")
                    skipped_count += 1
                    continue

                if existing and overwrite:
                    # Update existing page
                    existing.title = article_data["title"]
                    existing.access_level = AccessLevel.ROLE
                    existing.required_roles = ["staff"]

                    if publish:
                        existing.status = PageStatus.PUBLISHED
                        existing.published_at = timezone.now()
                        # Create snapshot
                        blocks_data = [
                            {
                                "type": "rich_text",
                                "data": {"content": article_data["content"].strip()},
                            }
                        ]
                        existing.published_snapshot = {"blocks": blocks_data}

                    existing.save()

                    # Update or create content block
                    ContentBlock.objects.filter(page=existing).delete()
                    ContentBlock.objects.create(
                        page=existing,
                        block_type="rich_text",
                        data={"content": article_data["content"].strip()},
                        sequence=0,
                    )

                    self.stdout.write(
                        self.style.WARNING(f"  Updated: {article_data['title']}")
                    )
                    updated_count += 1
                else:
                    # Create new page
                    page = ContentPage.objects.create(
                        slug=cms_slug,
                        title=article_data["title"],
                        status=PageStatus.PUBLISHED if publish else PageStatus.DRAFT,
                        access_level=AccessLevel.ROLE,
                        required_roles=["staff"],
                        published_at=timezone.now() if publish else None,
                        template_key="help-article",
                    )

                    # Create content block
                    ContentBlock.objects.create(
                        page=page,
                        block_type="rich_text",
                        data={"content": article_data["content"].strip()},
                        sequence=0,
                    )

                    # Set published snapshot if publishing
                    if publish:
                        blocks_data = [
                            {
                                "type": "rich_text",
                                "data": {"content": article_data["content"].strip()},
                            }
                        ]
                        page.published_snapshot = {"blocks": blocks_data}
                        page.save(update_fields=["published_snapshot"])

                    self.stdout.write(
                        self.style.SUCCESS(f"  Created: {article_data['title']}")
                    )
                    created_count += 1

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Done! Created: {created_count}, Updated: {updated_count}, Skipped: {skipped_count}"
            )
        )
        if not publish:
            self.stdout.write(
                self.style.WARNING(
                    "Articles created as drafts. Use --publish to publish immediately."
                )
            )
