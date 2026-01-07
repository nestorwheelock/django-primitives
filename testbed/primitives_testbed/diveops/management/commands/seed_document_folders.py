"""Management command to seed default document folders."""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from django_documents.models import Document, DocumentFolder


DEFAULT_FOLDERS = [
    {
        "name": "Agreements",
        "description": "Signed agreements, waivers, and legal documents",
        "children": [
            {"name": "Signatures", "description": "Signature images from signed agreements"},
            {"name": "Signed PDFs", "description": "Final signed agreement PDFs"},
        ],
    },
    {
        "name": "Certifications",
        "description": "Diver certification cards and training records",
    },
    {
        "name": "Medical",
        "description": "Medical forms, fitness declarations, and health records",
    },
    {
        "name": "Dive Logs",
        "description": "Dive log exports and dive records",
    },
    {
        "name": "Operations",
        "description": "Operational documents and procedures",
        "children": [
            {"name": "Emergency Procedures", "description": "Emergency action plans and protocols"},
            {"name": "Equipment", "description": "Equipment manuals and maintenance records"},
        ],
    },
    {
        "name": "Pictures",
        "description": "Photos from dive excursions and events",
        "children": [
            {"name": "Originals", "description": "Original uploaded photos (full resolution)"},
            {"name": ".processed", "description": "Web-optimized versions (system managed)", "children": [
                {"name": "thumbnails", "description": "Small thumbnails (150px)"},
                {"name": "previews", "description": "Medium previews (800px)"},
                {"name": "web", "description": "Web-optimized full size (1920px)"},
            ]},
        ],
    },
    {
        "name": "Videos",
        "description": "Video footage from dive excursions",
        "children": [
            {"name": "Originals", "description": "Original uploaded videos (full quality)"},
            {"name": ".processed", "description": "Transcoded versions (system managed)", "children": [
                {"name": "thumbnails", "description": "Video thumbnail frames"},
                {"name": "web-720p", "description": "Web streaming 720p"},
                {"name": "web-1080p", "description": "Web streaming 1080p"},
                {"name": "mobile", "description": "Mobile-optimized versions"},
            ]},
        ],
    },
    {
        "name": "Branding",
        "description": "Brand assets and marketing materials",
        "children": [
            {"name": "Logos", "description": "Logo files in various formats", "children": [
                {"name": "Primary", "description": "Main logo variants (color, mono, reversed)"},
                {"name": "Marks", "description": "Icon/symbol versions without text"},
                {"name": "Partners", "description": "Partner and certification body logos"},
            ]},
            {"name": "Watermarks", "description": "Watermark overlays for photos/videos"},
            {"name": "Templates", "description": "Document and email templates", "children": [
                {"name": "Email", "description": "Email signature and newsletter templates"},
                {"name": "Documents", "description": "Letterhead, invoice, receipt templates"},
                {"name": "Social", "description": "Social media post templates"},
            ]},
            {"name": "Marketing", "description": "Promotional materials", "children": [
                {"name": "Brochures", "description": "Digital brochures and flyers"},
                {"name": "Banners", "description": "Web banners and ads"},
            ]},
        ],
    },
    {
        "name": "Staff",
        "description": "Employee and HR documents",
        "children": [
            {"name": "Personnel Files", "description": "Individual employee files (by person)"},
            {"name": "Recruiting", "description": "Job postings, applications, resumes"},
            {"name": "Onboarding", "description": "I-9s, W-4s, direct deposit forms"},
            {"name": "Performance", "description": "Reviews, evaluations, disciplinary"},
            {"name": "Training Records", "description": "Staff training completions and certs"},
            {"name": "Benefits", "description": "Benefits enrollment, 401k, health insurance"},
            {"name": "Policies", "description": "Employee handbook, HR policies"},
        ],
    },
    {
        "name": "Training",
        "description": "Training and educational materials",
        "children": [
            {"name": "Courses", "description": "Course curricula and lesson plans", "children": [
                {"name": "Open Water", "description": "Open water certification materials"},
                {"name": "Advanced", "description": "Advanced and specialty courses"},
                {"name": "Rescue", "description": "Rescue diver materials"},
                {"name": "Professional", "description": "Divemaster and instructor materials"},
            ]},
            {"name": "Manuals", "description": "Reference manuals and guides"},
            {"name": "Presentations", "description": "Classroom presentations and slides"},
            {"name": "Exams", "description": "Tests, quizzes, answer keys"},
            {"name": "Videos", "description": "Training videos and demonstrations"},
        ],
    },
    {
        "name": "Vendors",
        "description": "Supplier and vendor information",
        "children": [
            {"name": "Contacts", "description": "Vendor contact info and accounts"},
            {"name": "Catalogs", "description": "Product catalogs and price lists"},
            {"name": "Agreements", "description": "Dealer agreements, terms"},
            {"name": "Orders", "description": "Purchase orders and confirmations"},
        ],
    },
    {
        "name": "Archive",
        "description": "Historical documents by year",
        "children": [
            {"name": "2024", "description": "Archived documents from 2024"},
            {"name": "2023", "description": "Archived documents from 2023"},
            {"name": "2022", "description": "Archived documents from 2022"},
        ],
    },
    {
        "name": "Inbox",
        "description": "Unsorted incoming documents for triage",
    },
    {
        "name": "Trash",
        "description": "Deleted documents awaiting permanent removal",
    },
    {
        "name": "Business",
        "description": "Business registration and compliance documents",
        "children": [
            {"name": "Licenses", "description": "Business and professional licenses", "children": [
                {"name": "Business", "description": "Business license, DBA, LLC/Corp docs"},
                {"name": "Professional", "description": "Instructor certifications, dive pro credentials"},
                {"name": "Retail", "description": "Retail permits, sales tax certificates"},
            ]},
            {"name": "Permits", "description": "Operating permits and authorizations", "children": [
                {"name": "Marine", "description": "Marine sanctuary, coastal access permits"},
                {"name": "Environmental", "description": "Environmental impact, wildlife permits"},
                {"name": "Vessel", "description": "Boat registration, USCG documentation"},
                {"name": "Local", "description": "City/county operating permits"},
            ]},
            {"name": "Compliance", "description": "Regulatory compliance documents", "children": [
                {"name": "Safety", "description": "OSHA, safety inspections, incident reports"},
                {"name": "Health", "description": "Health department permits and inspections"},
                {"name": "Fire", "description": "Fire marshal inspections, suppression certs"},
            ]},
            {"name": "Corporate", "description": "Corporate governance documents", "children": [
                {"name": "Formation", "description": "Articles, bylaws, operating agreements"},
                {"name": "Annual Filings", "description": "Annual reports, franchise tax"},
                {"name": "Minutes", "description": "Board/member meeting minutes"},
            ]},
            {"name": "Leases", "description": "Property and equipment leases"},
        ],
    },
    {
        "name": "Finance",
        "description": "Financial records and accounting documents",
        "children": [
            {"name": "Invoices", "description": "Issued invoices", "children": [
                {"name": "Customers", "description": "Invoices issued to customers"},
                {"name": "Vendors", "description": "Invoices received from vendors/suppliers"},
            ]},
            {"name": "Receipts", "description": "Payment receipts and proof of payment"},
            {"name": "Bank Statements", "description": "Monthly bank and credit card statements"},
            {"name": "Tax", "description": "Tax-related documents", "children": [
                {"name": "Returns", "description": "Filed tax returns"},
                {"name": "Forms", "description": "W-9s, 1099s, and other tax forms"},
                {"name": "Correspondence", "description": "IRS and state tax correspondence"},
            ]},
            {"name": "Payroll", "description": "Payroll records and employee compensation"},
            {"name": "Insurance", "description": "Insurance policies and claims", "children": [
                {"name": "Policies", "description": "Active and historical insurance policies"},
                {"name": "Claims", "description": "Insurance claims and documentation"},
                {"name": "Certificates", "description": "Certificates of insurance"},
            ]},
            {"name": "Contracts", "description": "Vendor and supplier contracts"},
            {"name": "Reports", "description": "Financial reports and statements", "children": [
                {"name": "Monthly", "description": "Monthly P&L and balance sheets"},
                {"name": "Annual", "description": "Year-end financial statements"},
                {"name": "Audits", "description": "Audit reports and working papers"},
            ]},
        ],
    },
]


class Command(BaseCommand):
    help = "Seed default document folders for dive operations"

    def add_arguments(self, parser):
        parser.add_argument(
            "--migrate-orphans",
            action="store_true",
            help="Move orphan documents to appropriate folders based on document_type",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        created_count = 0

        def create_folder(folder_data, parent=None):
            nonlocal created_count
            name = folder_data["name"]
            slug = slugify(name)

            # Compute depth and path based on parent
            if parent is None:
                depth = 0
                path = ""
            else:
                depth = parent.depth + 1
                path = parent.path

            # Check if folder exists
            existing = DocumentFolder.objects.filter(slug=slug, parent=parent).first()
            if existing:
                self.stdout.write(f"  Exists: {existing.name} (depth={existing.depth})")
                folder = existing
            else:
                # Create new folder with correct depth
                folder = DocumentFolder(
                    name=name,
                    slug=slug,
                    description=folder_data.get("description", ""),
                    parent=parent,
                    depth=depth,
                    path=path,  # Will update after save
                )
                folder.save()
                # Update path to include this folder's ID
                folder.path = f"{path}{folder.pk}/"
                folder.save(update_fields=["path"])
                created_count += 1
                self.stdout.write(f"  Created: {folder.name} (depth={folder.depth})")

            for child_data in folder_data.get("children", []):
                create_folder(child_data, parent=folder)

            return folder

        self.stdout.write("Seeding document folders...")
        folders = {}
        for folder_data in DEFAULT_FOLDERS:
            folder = create_folder(folder_data)
            folders[folder_data["name"]] = folder

        self.stdout.write(self.style.SUCCESS(f"\nCreated {created_count} new folders"))

        if options["migrate_orphans"]:
            self._migrate_orphan_documents(folders)

    def _migrate_orphan_documents(self, folders):
        """Move orphan documents to appropriate folders based on document_type."""
        orphans = Document.objects.filter(folder__isnull=True)
        orphan_count = orphans.count()

        if orphan_count == 0:
            self.stdout.write("No orphan documents to migrate.")
            return

        self.stdout.write(f"\nMigrating {orphan_count} orphan documents...")

        # Get or create subfolders
        agreements_folder = folders.get("Agreements")
        signatures_folder = DocumentFolder.objects.filter(
            name="Signatures", parent=agreements_folder
        ).first()
        signed_pdfs_folder = DocumentFolder.objects.filter(
            name="Signed PDFs", parent=agreements_folder
        ).first()
        certifications_folder = folders.get("Certifications")

        # Map document_type to folder
        type_to_folder = {
            "signature": signatures_folder,
            "signed_agreement": signed_pdfs_folder,
            "certification": certifications_folder,
            "certification_card": certifications_folder,
        }

        migrated = 0
        for doc in orphans:
            target_folder = type_to_folder.get(doc.document_type)
            if target_folder:
                doc.folder = target_folder
                doc.save(update_fields=["folder", "updated_at"])
                migrated += 1
                self.stdout.write(f"  Moved '{doc.filename}' to {target_folder.path}")

        self.stdout.write(self.style.SUCCESS(f"\nMigrated {migrated} documents"))
        remaining = orphan_count - migrated
        if remaining > 0:
            self.stdout.write(self.style.WARNING(
                f"{remaining} documents remain without folder (unknown document_type)"
            ))
