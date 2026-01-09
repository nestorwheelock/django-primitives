"""Management command to seed help center content."""

from django.core.management.base import BaseCommand
from django.utils import timezone

from django_cms_core.models import ContentPage, ContentBlock, PageStatus, AccessLevel


HELP_CONTENT = {
    "getting-started": {
        "dashboard-overview": {
            "title": "Dashboard Overview",
            "content": """
<p>Welcome to the DiveOps Staff Dashboard! This guide will help you navigate and use the dashboard effectively.</p>

<h3>Main Dashboard</h3>
<p>When you first log in, you'll see the main dashboard with key metrics and quick actions:</p>
<ul>
    <li><strong>Today's Excursions</strong> - View upcoming trips for today with participant counts</li>
    <li><strong>Recent Bookings</strong> - New bookings that may need attention</li>
    <li><strong>Pending Medical</strong> - Medical questionnaires awaiting review</li>
    <li><strong>Unsigned Agreements</strong> - Agreements sent but not yet signed</li>
</ul>

<h3>Quick Actions</h3>
<p>The dashboard provides quick access to common tasks:</p>
<ul>
    <li>Schedule a new excursion</li>
    <li>Add a new diver</li>
    <li>Send an agreement for signature</li>
    <li>View today's manifest</li>
</ul>

<h3>Getting Help</h3>
<p>You can access this Help Center anytime by clicking the Help link in the navigation sidebar.</p>
""",
        },
        "navigation-guide": {
            "title": "Navigation Guide",
            "content": """
<p>The staff dashboard is organized into logical sections to help you find what you need quickly.</p>

<h3>Navigation Sections</h3>

<h4>Dive Operations</h4>
<ul>
    <li><strong>Excursions</strong> - Manage dive trips, schedules, and manifests</li>
    <li><strong>Divers</strong> - Diver profiles, certifications, and history</li>
    <li><strong>Dive Sites</strong> - Location information and site details</li>
    <li><strong>Protected Areas</strong> - Marine park permits and fees</li>
    <li><strong>Agreements</strong> - Liability waivers and rental forms</li>
    <li><strong>Medical Questionnaires</strong> - Health screening forms</li>
</ul>

<h4>Planning</h4>
<ul>
    <li><strong>Dive Plans</strong> - Pre-dive planning documents</li>
    <li><strong>Dive Logs</strong> - Post-dive records</li>
</ul>

<h4>System</h4>
<ul>
    <li><strong>Documents</strong> - File storage and organization</li>
    <li><strong>Media</strong> - Photo and video library</li>
    <li><strong>Audit Log</strong> - Activity history</li>
</ul>

<h4>Configuration</h4>
<ul>
    <li><strong>Excursion Types</strong> - Trip templates and pricing</li>
    <li><strong>Agreement Types</strong> - Document templates</li>
    <li><strong>Catalog Items</strong> - Products and services</li>
    <li><strong>AI Settings</strong> - Configure AI assistance</li>
</ul>
""",
        },
        "your-account": {
            "title": "Your Account",
            "content": """
<p>Manage your staff account settings and preferences.</p>

<h3>Profile Settings</h3>
<p>Your profile includes:</p>
<ul>
    <li>Name and contact information</li>
    <li>Profile photo</li>
    <li>Notification preferences</li>
    <li>Dashboard layout preferences</li>
</ul>

<h3>Security</h3>
<p>Keep your account secure by:</p>
<ul>
    <li>Using a strong, unique password</li>
    <li>Enabling two-factor authentication if available</li>
    <li>Logging out when using shared computers</li>
    <li>Reporting suspicious activity to your administrator</li>
</ul>

<h3>Support</h3>
<p>If you need help with your account, contact your system administrator.</p>
""",
        },
    },
    "divers": {
        "creating-profiles": {
            "title": "Creating Diver Profiles",
            "content": """
<p>Diver profiles store all information about your customers, including contact details, certifications, and dive history.</p>

<h3>Creating a New Diver</h3>
<ol>
    <li>Navigate to <strong>Divers</strong> in the sidebar</li>
    <li>Click the <strong>Add Diver</strong> button</li>
    <li>Fill in the required information:
        <ul>
            <li>Full name</li>
            <li>Email address</li>
            <li>Phone number</li>
            <li>Date of birth</li>
        </ul>
    </li>
    <li>Add optional information as available (certifications, emergency contacts)</li>
    <li>Click <strong>Save</strong> to create the profile</li>
</ol>

<h3>Required vs Optional Fields</h3>
<p>Only basic contact information is required initially. Certifications, medical information, and documents can be added later or by the diver themselves.</p>

<h3>Photo ID</h3>
<p>For verification purposes, you can upload a photo of the diver's ID. This is stored securely and helps prevent identity issues.</p>
""",
        },
        "managing-certifications": {
            "title": "Managing Certifications",
            "content": """
<p>Track and verify diver certifications to ensure safety and compliance.</p>

<h3>Adding a Certification</h3>
<ol>
    <li>Open the diver's profile</li>
    <li>Go to the <strong>Certifications</strong> tab</li>
    <li>Click <strong>Add Certification</strong></li>
    <li>Select the certification agency (PADI, SSI, NAUI, etc.)</li>
    <li>Choose the certification level</li>
    <li>Enter the certification number and date</li>
    <li>Upload a photo of the certification card if available</li>
</ol>

<h3>Verification</h3>
<p>Certifications can be marked as:</p>
<ul>
    <li><strong>Unverified</strong> - Not yet checked</li>
    <li><strong>Verified</strong> - Confirmed with agency or card photo</li>
    <li><strong>Expired</strong> - Past expiration date</li>
</ul>

<h3>Eligibility</h3>
<p>When booking divers for excursions, the system will check that they have appropriate certifications for the dive type.</p>
""",
        },
        "emergency-contacts": {
            "title": "Emergency Contacts",
            "content": """
<p>Every diver should have at least one emergency contact on file.</p>

<h3>Adding an Emergency Contact</h3>
<ol>
    <li>Open the diver's profile</li>
    <li>Go to the <strong>Emergency Contacts</strong> tab</li>
    <li>Click <strong>Add Contact</strong></li>
    <li>Enter:
        <ul>
            <li>Contact name</li>
            <li>Relationship to diver</li>
            <li>Phone number(s)</li>
            <li>Email (optional)</li>
        </ul>
    </li>
    <li>Mark as primary contact if this is the first person to call</li>
</ol>

<h3>Best Practices</h3>
<ul>
    <li>Encourage divers to provide at least two contacts</li>
    <li>Verify phone numbers are correct and reachable</li>
    <li>Update contacts annually or when information changes</li>
</ul>
""",
        },
        "diver-categories": {
            "title": "Diver Categories",
            "content": """
<p>Categorize divers for easier management and targeted communications.</p>

<h3>Default Categories</h3>
<ul>
    <li><strong>Regular</strong> - Standard customers</li>
    <li><strong>VIP</strong> - High-value or frequent customers</li>
    <li><strong>Instructor</strong> - Certified instructors</li>
    <li><strong>Student</strong> - Currently in training</li>
    <li><strong>Staff</strong> - Shop employees</li>
</ul>

<h3>Custom Categories</h3>
<p>Create custom categories for your specific needs, such as:</p>
<ul>
    <li>Resort guests</li>
    <li>Club members</li>
    <li>Group tour participants</li>
</ul>

<h3>Using Categories</h3>
<p>Categories can be used to:</p>
<ul>
    <li>Filter diver lists</li>
    <li>Apply special pricing</li>
    <li>Send targeted communications</li>
    <li>Generate reports</li>
</ul>
""",
        },
    },
    "bookings": {
        "scheduling-excursions": {
            "title": "Scheduling Excursions",
            "content": """
<p>Create and manage dive excursions for your customers.</p>

<h3>Creating an Excursion</h3>
<ol>
    <li>Navigate to <strong>Excursions</strong> in the sidebar</li>
    <li>Click <strong>New Excursion</strong></li>
    <li>Select an excursion type (2-tank morning dive, night dive, etc.)</li>
    <li>Choose the date and time</li>
    <li>Select dive sites (primary and backup)</li>
    <li>Set capacity limits</li>
    <li>Add any special notes</li>
    <li>Click <strong>Create</strong></li>
</ol>

<h3>Excursion Types</h3>
<p>Excursion types are templates that pre-fill common settings:</p>
<ul>
    <li>Default pricing</li>
    <li>Duration</li>
    <li>Equipment requirements</li>
    <li>Certification requirements</li>
</ul>

<h3>Capacity Management</h3>
<p>Set maximum capacity based on:</p>
<ul>
    <li>Boat capacity</li>
    <li>Guide-to-diver ratios</li>
    <li>Site limitations</li>
</ul>
""",
        },
        "managing-bookings": {
            "title": "Managing Bookings",
            "content": """
<p>Add divers to excursions and manage their bookings.</p>

<h3>Adding a Booking</h3>
<ol>
    <li>Open the excursion</li>
    <li>Click <strong>Add Booking</strong></li>
    <li>Search for the diver by name or email</li>
    <li>Select the diver from results</li>
    <li>The system checks eligibility automatically</li>
    <li>Confirm the booking</li>
</ol>

<h3>Eligibility Checks</h3>
<p>Before a booking is confirmed, the system verifies:</p>
<ul>
    <li>Valid certification for the dive type</li>
    <li>Current medical clearance</li>
    <li>Signed liability waiver</li>
    <li>No scheduling conflicts</li>
</ul>

<h3>Price Adjustments</h3>
<p>You can override the default price for:</p>
<ul>
    <li>Group discounts</li>
    <li>VIP customers</li>
    <li>Package deals</li>
    <li>Promotional offers</li>
</ul>
""",
        },
        "check-in-process": {
            "title": "Check-in Process",
            "content": """
<p>Manage the check-in process on dive day.</p>

<h3>Pre-Dive Checklist</h3>
<p>Before departure, verify each diver has:</p>
<ul>
    <li>Signed liability waiver (current)</li>
    <li>Medical clearance (if required)</li>
    <li>Valid certification card</li>
    <li>Paid or payment arranged</li>
</ul>

<h3>Marking Check-in</h3>
<ol>
    <li>Open the excursion manifest</li>
    <li>Find the diver in the list</li>
    <li>Click the check-in checkbox</li>
    <li>Note any equipment rentals</li>
</ol>

<h3>No-Shows</h3>
<p>If a diver doesn't arrive:</p>
<ol>
    <li>Attempt to contact them</li>
    <li>Wait until departure time</li>
    <li>Mark as no-show in the system</li>
    <li>Apply cancellation policy as appropriate</li>
</ol>
""",
        },
        "recurring-series": {
            "title": "Recurring Series",
            "content": """
<p>Set up excursions that repeat on a regular schedule.</p>

<h3>Creating a Recurring Series</h3>
<ol>
    <li>Create a new excursion</li>
    <li>Enable <strong>Recurring</strong> option</li>
    <li>Choose the recurrence pattern:
        <ul>
            <li>Daily</li>
            <li>Weekly (select days)</li>
            <li>Bi-weekly</li>
            <li>Monthly</li>
        </ul>
    </li>
    <li>Set the end date or number of occurrences</li>
    <li>Click <strong>Create Series</strong></li>
</ol>

<h3>Editing Series</h3>
<p>When editing a recurring excursion, you can:</p>
<ul>
    <li><strong>Edit this occurrence only</strong> - Changes apply to this date only</li>
    <li><strong>Edit all future occurrences</strong> - Changes apply from this date forward</li>
    <li><strong>Edit entire series</strong> - Changes apply to all occurrences</li>
</ul>

<h3>Syncing Occurrences</h3>
<p>Use the sync feature to generate or update occurrences based on the series pattern.</p>
""",
        },
        "cancellations-refunds": {
            "title": "Cancellations & Refunds",
            "content": """
<p>Handle booking cancellations and process refunds.</p>

<h3>Cancellation Policy</h3>
<p>Review your shop's cancellation policy before processing:</p>
<ul>
    <li>Full refund period (e.g., 48+ hours before)</li>
    <li>Partial refund period (e.g., 24-48 hours)</li>
    <li>No refund period (e.g., less than 24 hours)</li>
</ul>

<h3>Processing a Cancellation</h3>
<ol>
    <li>Open the booking</li>
    <li>Click <strong>Cancel Booking</strong></li>
    <li>Select the reason for cancellation</li>
    <li>Choose refund amount based on policy</li>
    <li>Add any notes</li>
    <li>Confirm the cancellation</li>
</ol>

<h3>Weather Cancellations</h3>
<p>If an excursion is cancelled due to weather:</p>
<ul>
    <li>Notify all booked divers</li>
    <li>Offer rescheduling options</li>
    <li>Process refunds for those who can't reschedule</li>
    <li>Document the cancellation reason</li>
</ul>
""",
        },
    },
    "agreements": {
        "creating-agreements": {
            "title": "Creating Agreements",
            "content": """
<p>Generate liability waivers and other agreements for divers to sign.</p>

<h3>Creating from Template</h3>
<ol>
    <li>Navigate to <strong>Agreements</strong></li>
    <li>Click <strong>New Agreement</strong></li>
    <li>Select the agreement template (e.g., PADI Liability Release)</li>
    <li>Search for and select the diver</li>
    <li>The system populates the agreement with diver information</li>
    <li>Review the agreement</li>
    <li>Click <strong>Create</strong></li>
</ol>

<h3>Agreement Templates</h3>
<p>Common templates include:</p>
<ul>
    <li>PADI Liability Release (standard diving)</li>
    <li>Equipment Rental Agreement</li>
    <li>Minor Consent Form</li>
    <li>Nitrox/Enriched Air Acknowledgment</li>
</ul>

<h3>Validity Period</h3>
<p>Most agreements are valid for one year from signing. The system tracks expiration dates automatically.</p>
""",
        },
        "sending-for-signature": {
            "title": "Sending for Signature",
            "content": """
<p>Deliver agreements to divers for electronic signature.</p>

<h3>Delivery Methods</h3>
<ul>
    <li><strong>Email</strong> - Send a link to the diver's email</li>
    <li><strong>Direct Link</strong> - Copy a signing link to share via any method</li>
    <li><strong>In-Person</strong> - Have diver sign on a tablet or computer at the shop</li>
</ul>

<h3>Sending via Email</h3>
<ol>
    <li>Open the agreement</li>
    <li>Click <strong>Send for Signature</strong></li>
    <li>Verify the email address</li>
    <li>Add a personal message (optional)</li>
    <li>Click <strong>Send</strong></li>
</ol>

<h3>Setting Expiration</h3>
<p>You can set when the signing link expires:</p>
<ul>
    <li>7 days (default)</li>
    <li>14 days</li>
    <li>30 days</li>
    <li>Custom date</li>
</ul>

<h3>Copying the Signing Link</h3>
<p>Use the <strong>Copy Link</strong> button to share the signing URL via text message, WhatsApp, or other channels.</p>
""",
        },
        "tracking-status": {
            "title": "Tracking Status",
            "content": """
<p>Monitor agreement status and follow up on unsigned documents.</p>

<h3>Agreement Statuses</h3>
<ul>
    <li><strong>Draft</strong> - Created but not sent</li>
    <li><strong>Sent</strong> - Delivered, awaiting signature</li>
    <li><strong>Signed</strong> - Completed and valid</li>
    <li><strong>Voided</strong> - Cancelled before signing</li>
    <li><strong>Expired</strong> - Signing link has expired</li>
</ul>

<h3>Filtering Agreements</h3>
<p>Use filters to find specific agreements:</p>
<ul>
    <li>By status</li>
    <li>By diver name</li>
    <li>By date range</li>
    <li>By agreement type</li>
</ul>

<h3>Follow-up Actions</h3>
<p>For unsigned agreements:</p>
<ul>
    <li>Resend the email</li>
    <li>Generate a new link</li>
    <li>Call the diver to remind them</li>
    <li>Void and create a new agreement if needed</li>
</ul>
""",
        },
        "voiding-agreements": {
            "title": "Voiding Agreements",
            "content": """
<p>Cancel agreements that are no longer needed.</p>

<h3>When to Void</h3>
<p>Void an agreement when:</p>
<ul>
    <li>Created by mistake</li>
    <li>Wrong template was used</li>
    <li>Diver information was incorrect</li>
    <li>Booking was cancelled</li>
</ul>

<h3>Important: Signed Agreements Cannot Be Voided</h3>
<p>Once an agreement is signed, it becomes a legal document and cannot be voided. If you need to nullify a signed agreement, you must create a <strong>Revocation Agreement</strong> that the diver also signs.</p>

<h3>Voiding Process</h3>
<ol>
    <li>Open the agreement (must be Draft or Sent status)</li>
    <li>Click <strong>Void Agreement</strong></li>
    <li>Enter a reason for voiding</li>
    <li>Confirm the action</li>
</ol>

<h3>After Voiding</h3>
<p>Voided agreements remain in the system for record-keeping but are clearly marked. You can create a new agreement to replace a voided one.</p>
""",
        },
    },
    "medical": {
        "medical-questionnaires": {
            "title": "Medical Questionnaires",
            "content": """
<p>Manage health screening questionnaires for divers.</p>

<h3>Purpose</h3>
<p>Medical questionnaires identify health conditions that may affect diving safety. They are based on the RSTC/DAN Medical Statement.</p>

<h3>Sending a Questionnaire</h3>
<ol>
    <li>Open the diver's profile</li>
    <li>Go to the <strong>Medical</strong> tab</li>
    <li>Click <strong>Send Questionnaire</strong></li>
    <li>The diver receives an email with the link</li>
    <li>They complete it online</li>
</ol>

<h3>Automatic Triggers</h3>
<p>Questionnaires can be sent automatically:</p>
<ul>
    <li>When creating a first booking</li>
    <li>On annual renewal dates</li>
    <li>When previous clearance expires</li>
</ul>
""",
        },
        "reviewing-responses": {
            "title": "Reviewing Responses",
            "content": """
<p>Review and process medical questionnaire responses.</p>

<h3>Response Review</h3>
<ol>
    <li>Navigate to <strong>Medical Questionnaires</strong></li>
    <li>Filter for <strong>Pending Review</strong> status</li>
    <li>Open a questionnaire</li>
    <li>Review all answers</li>
    <li>Note any flagged conditions</li>
</ol>

<h3>Flagged Conditions</h3>
<p>Certain "Yes" answers automatically flag the questionnaire:</p>
<ul>
    <li>Heart conditions</li>
    <li>Lung conditions</li>
    <li>Seizure disorders</li>
    <li>Diabetes requiring medication</li>
    <li>Recent surgery</li>
</ul>

<h3>Actions After Review</h3>
<ul>
    <li><strong>Clear to Dive</strong> - No concerns, approved for diving</li>
    <li><strong>Require Physician Clearance</strong> - Must get doctor approval</li>
    <li><strong>Deny Diving</strong> - Cannot dive safely</li>
</ul>
""",
        },
        "clearance-process": {
            "title": "Clearance Process",
            "content": """
<p>Handle physician clearance requirements for flagged questionnaires.</p>

<h3>When Clearance is Required</h3>
<p>A physician clearance is needed when:</p>
<ul>
    <li>Questionnaire has flagged responses</li>
    <li>Diver is over 45 years old (first time)</li>
    <li>Significant health changes since last questionnaire</li>
</ul>

<h3>Clearance Process</h3>
<ol>
    <li>Print the clearance form with flagged conditions</li>
    <li>Diver takes form to their physician</li>
    <li>Physician examines and signs the form</li>
    <li>Diver returns signed form</li>
    <li>Staff uploads and verifies clearance</li>
</ol>

<h3>Recording Clearance</h3>
<ol>
    <li>Open the medical questionnaire</li>
    <li>Click <strong>Record Physician Clearance</strong></li>
    <li>Upload the signed form</li>
    <li>Enter physician name and date</li>
    <li>Set clearance expiration (typically 1 year)</li>
</ol>
""",
        },
        "retention-policies": {
            "title": "Retention Policies",
            "content": """
<p>Understand medical record retention and privacy requirements.</p>

<h3>Retention Periods</h3>
<ul>
    <li><strong>Active Divers</strong> - Retain all medical records</li>
    <li><strong>Inactive Divers</strong> - Retain for 7 years after last activity</li>
    <li><strong>Minors</strong> - Retain until 7 years after 18th birthday</li>
</ul>

<h3>Data Privacy</h3>
<p>Medical information is sensitive and protected:</p>
<ul>
    <li>Access limited to authorized staff</li>
    <li>Never share with third parties without consent</li>
    <li>Secure storage and transmission</li>
    <li>Right to deletion upon request (after retention period)</li>
</ul>

<h3>Record Requests</h3>
<p>Divers can request copies of their medical records. Verify identity before providing any records.</p>
""",
        },
    },
    "protected-areas": {
        "managing-permits": {
            "title": "Managing Permits",
            "content": """
<p>Track permits for diving in marine protected areas.</p>

<h3>Permit Types</h3>
<ul>
    <li><strong>Operator Permit</strong> - Annual license to operate in the area</li>
    <li><strong>Diver Fee</strong> - Per-diver daily or weekly fee</li>
    <li><strong>Mooring Fee</strong> - Fee for using park moorings</li>
</ul>

<h3>Adding a Protected Area</h3>
<ol>
    <li>Navigate to <strong>Protected Areas</strong></li>
    <li>Click <strong>Add Protected Area</strong></li>
    <li>Enter area name and managing authority</li>
    <li>Add permit requirements and fees</li>
    <li>Link associated dive sites</li>
</ol>

<h3>Automatic Fee Calculation</h3>
<p>When booking excursions to protected areas, the system automatically:</p>
<ul>
    <li>Calculates required fees</li>
    <li>Adds fees to booking price</li>
    <li>Tracks fee collection</li>
</ul>
""",
        },
        "fee-schedules": {
            "title": "Fee Schedules",
            "content": """
<p>Configure fee schedules for protected areas.</p>

<h3>Fee Types</h3>
<ul>
    <li><strong>Daily Fee</strong> - Charged per day per diver</li>
    <li><strong>Weekly Fee</strong> - Week pass option</li>
    <li><strong>Annual Fee</strong> - Year pass option</li>
    <li><strong>Mooring Fee</strong> - Per mooring use</li>
</ul>

<h3>Setting Up Fees</h3>
<ol>
    <li>Open the protected area</li>
    <li>Go to <strong>Fee Schedule</strong></li>
    <li>Add fee types and amounts</li>
    <li>Set effective dates</li>
    <li>Configure any discounts</li>
</ol>

<h3>Fee Changes</h3>
<p>When fees change, create a new fee schedule with a future effective date. The system will automatically apply the correct fees based on booking dates.</p>
""",
        },
        "zone-rules": {
            "title": "Zone Rules",
            "content": """
<p>Configure diving rules for different zones within protected areas.</p>

<h3>Zone Types</h3>
<ul>
    <li><strong>General Use</strong> - Standard diving allowed</li>
    <li><strong>No-Take</strong> - No fishing or collecting</li>
    <li><strong>Research Only</strong> - Limited access for research</li>
    <li><strong>No-Entry</strong> - Closed to all diving</li>
</ul>

<h3>Zone Restrictions</h3>
<p>Configure restrictions per zone:</p>
<ul>
    <li>Maximum divers per day</li>
    <li>Required certifications</li>
    <li>Seasonal closures</li>
    <li>Special equipment requirements</li>
</ul>

<h3>Compliance</h3>
<p>The system helps ensure compliance by:</p>
<ul>
    <li>Warning when booking exceeds limits</li>
    <li>Blocking bookings in closed zones</li>
    <li>Tracking daily diver counts</li>
</ul>
""",
        },
    },
    "system": {
        "document-management": {
            "title": "Document Management",
            "content": """
<p>Organize and manage files in the document system.</p>

<h3>Document Browser</h3>
<p>The document browser provides:</p>
<ul>
    <li>Folder-based organization</li>
    <li>File upload and download</li>
    <li>Preview for common file types</li>
    <li>Search functionality</li>
</ul>

<h3>Uploading Documents</h3>
<ol>
    <li>Navigate to <strong>Documents</strong></li>
    <li>Select the target folder</li>
    <li>Click <strong>Upload</strong></li>
    <li>Select files from your computer</li>
    <li>Add descriptions (optional)</li>
</ol>

<h3>File Organization</h3>
<p>Common folder structure:</p>
<ul>
    <li><strong>Templates</strong> - Document templates</li>
    <li><strong>Signed Agreements</strong> - Completed waivers</li>
    <li><strong>Certifications</strong> - Certification card photos</li>
    <li><strong>Medical</strong> - Medical clearance forms</li>
</ul>
""",
        },
        "audit-log": {
            "title": "Audit Log",
            "content": """
<p>Track all activity in the system for accountability and troubleshooting.</p>

<h3>What's Logged</h3>
<p>The audit log records:</p>
<ul>
    <li>User logins and logouts</li>
    <li>Record creation, updates, and deletions</li>
    <li>Status changes (e.g., agreement signed)</li>
    <li>Permission changes</li>
    <li>System events</li>
</ul>

<h3>Viewing the Log</h3>
<ol>
    <li>Navigate to <strong>Audit Log</strong></li>
    <li>Use filters to narrow results:
        <ul>
            <li>Date range</li>
            <li>User</li>
            <li>Action type</li>
            <li>Record type</li>
        </ul>
    </li>
    <li>Click an entry to see details</li>
</ol>

<h3>Use Cases</h3>
<ul>
    <li>Investigate who made a change</li>
    <li>Track workflow progression</li>
    <li>Verify compliance actions</li>
    <li>Troubleshoot issues</li>
</ul>
""",
        },
        "ai-settings": {
            "title": "AI Settings",
            "content": """
<p>Configure AI assistance features in the dashboard.</p>

<h3>AI Features</h3>
<ul>
    <li><strong>Smart Suggestions</strong> - Recommendations for common actions</li>
    <li><strong>Natural Language Search</strong> - Search using plain English</li>
    <li><strong>Automated Summaries</strong> - Generate activity summaries</li>
</ul>

<h3>Configuration Options</h3>
<ul>
    <li>Enable/disable AI features</li>
    <li>Set suggestion sensitivity</li>
    <li>Configure which data AI can access</li>
    <li>Set rate limits</li>
</ul>

<h3>Privacy</h3>
<p>AI features are designed with privacy in mind:</p>
<ul>
    <li>Data processed locally when possible</li>
    <li>Sensitive information excluded from AI processing</li>
    <li>Configurable opt-out options</li>
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
