You are working in an existing Django project built on a primitives ecosystem (18 primitives).
We are building a diving-domain thin overlay that composes primitives rather than rewriting them.

We need to manage VENDORS (tour providers, boat operators, transport, photographers, cenote operators, etc.)
using the same thin overlay approach as the Trip/Excursion split:
- Vendors are Parties/Organizations in primitives
- Vendor offerings are Catalog items
- Vendor contracts/policies are Agreements/Documents
- Vendor payouts/commissions use Accounting/Ledger primitives
- All vendor-facing changes must be audited (append-only audit events)

MANDATORY FIRST STEP (DO NOT SKIP)
1) Read repo architecture docs and any `claude.md` guidance.
2) Identify the primitives for: parties, rbac, catalog, agreements/documents, accounting/ledger, audit, geo.
3) Summarize constraints (base models, UUID rules, services pattern, audit pattern).

AUTHORITATIVE DOMAIN DEFINITIONS
- Vendor: an external provider organization (Party/Org) supplying excursions/services/products.
- Vendor Offering: a Catalog item owned by or fulfilled by a vendor.
- Vendor Agreement: contract terms, commission rules, cancellation policy, payment timing.
- Vendor Fulfillment: excursions (operational units) that are executed by a vendor.
- Vendor Settlement: accounting actions that pay vendor and booth-owner commissions tied to fulfilled items.

SCOPE
Build a thin domain app/module (e.g. `diveops_vendors` or inside `diveops_domain`) that:
A) Adds minimal domain models ONLY for joins/mappings not representable in primitives.
B) Adds domain services that orchestrate primitives to support vendor workflows.
C) Adds admin/staff UI and API endpoints for vendor ops.
D) Integrates with Trip/Excursion semantics:
   - Trips may contain excursions from multiple vendors.
   - Excursions can be fulfilled by a vendor.
   - Commissions/payouts are calculated from sold items and fulfillment status.

REQUIRED CAPABILITIES (V0.1)
1) Vendor registry
- Create vendors as Party/Organization using primitives.
- Store vendor classification and metadata (type, contact, operating area).
- Vendor status lifecycle (onboarding -> active -> suspended) using existing primitives patterns
  (use encounters/state machine if available; otherwise simple status field in overlay).

2) Vendor offerings mapping (Catalog ownership/fulfillment)
- Associate Catalog items with:
  - owner_vendor (who provides the service)
  - fulfillment_kind (excursion/transport/photo/etc) if already supported
- Do NOT re-implement catalog composition; use the existing catalog primitives.
- Provide views to list vendor offerings and their pricing rules.

3) Vendor agreements and policies
- Attach agreement documents (waivers, provider contract, cancellation rules) using agreements/documents primitives.
- Store commission terms and settlement timing in a structured way:
  - default commission rates
  - overrides per offering
  - booth-owner cut
  - affiliate/reseller cuts if applicable
Use existing accounting primitives for rule storage if they exist; otherwise store minimal structured config
in the overlay and translate into ledger postings.

4) Fulfillment tracking linkage
- Ensure each Excursion has a vendor/provider party reference.
- Ensure traceability: sold Trip line items -> generated Excursions -> vendor fulfillment.
If needed, add a join table in the overlay:
  - TripLineItem <-> Excursion mappings for settlement and reporting.

5) Settlement and payouts (using primitives)
- Implement a `VendorSettlementService` that:
  - finds fulfilled excursions in a period
  - aggregates owed amounts per vendor and booth owner
  - posts ledger entries using accounting primitives
  - marks settlements as posted (idempotent)
- Support partial fulfillment, cancellations, refunds, no-shows (at least as placeholders in v0.1).

6) Audit everything
- Every vendor mutation (create/update/status change/offer mapping/agreement attach/settlement post)
  must emit append-only audit events using the audit primitive.

DELIVERABLES
1) Mapping doc: which primitive is used for which vendor concept.
2) Domain models (minimal) and migrations if required (only for missing joins/mappings).
3) Domain services:
   - VendorService (create/update/status, contacts, compliance flags)
   - VendorOfferingService (associate catalog items, pricing hooks, availability flags)
   - VendorAgreementService (attach/retrieve agreements, policy summaries)
   - VendorSettlementService (compute/post payouts, idempotent)
4) Admin/staff UI screens:
   - Vendor list/detail, status, agreements, offerings
   - Settlement run/report (by date range)
5) Tests:
   - Vendor creation via parties primitive
   - Offering mapping works
   - Settlement posting is idempotent and auditable
   - Excursions linked to vendors produce correct settlement aggregates

NON-GOALS
- No payment processor integration
- No vendor portal UI (internal staff only)
- No rewriting primitives
- No deep scheduling/availability engine unless primitives already provide it

OUTPUT REQUIREMENTS
- Start by listing files read (architecture docs, claude.md) and summarizing constraints.
- Provide plan with incremental steps.
- Implement code changes.
- Provide verification steps and tests to run.
