You are working in an existing Django project that already contains a mature primitives
ecosystem (18 primitives). These primitives already cover core capabilities like:
parties, rbac, encounters/state, catalog, basket/invoicing, ledger/accounting,
agreements/documents, geo, audit logging, etc. Do NOT rebuild these.

We must implement a domain layer for dive operations that:
- Corrects the semantics: Dive < Excursion < Trip (package/itinerary)
- Splits the current operational "Trip" concept into:
  - Excursion (operational, single-day departure, 1..N dives)
  - Trip (commercial package/itinerary, may be multi-day, 1..N excursions, supports commissions)
- All offerings sold are already represented as Catalog items and combinations using existing primitives.

MANDATORY FIRST STEP (DO NOT SKIP)
1) Read all architecture docs in the repo and any `claude.md` guidance.
2) Identify the 18 primitives packages actually installed/used and how to use them correctly:
   - base model rules (UUIDs/timestamps/soft delete)
   - service layer style
   - audit/event logging style (append-only)
   - how catalog composition works today (bundles/components/modifiers)
   - how basket/invoice/ledger primitives represent sales and commissions
3) Summarize constraints and list the files you read.

AUTHORITATIVE SEMANTICS CONTRACT
- Dive: atomic, loggable unit; belongs to an Excursion.
- Excursion: operational fulfillment unit (single calendar day) containing 1..N dives.
- Trip: commercial wrapper/itinerary (may span days) composed of 1..N excursions.
- Excursions can exist standalone (walk-ins). Trips are optional but central to business sales.

PROJECT REALITY
- The code currently uses "Trip" to mean operational outings.
- We must split without rewriting primitives.
- We must preserve data and keep backwards compatibility where feasible.

SCOPE
A) Domain layer app (thin orchestration)
Create a new domain app/module (e.g. `diveops_domain` or `diveops_trips`) that:
- defines domain-level models ONLY when needed for joins/mappings
- orchestrates primitives using services (no fat models)
- emits audit events following the existing audit primitive

B) Trip vs Excursion split
1) Introduce `Excursion` as the operational object, using/aliasing existing data where possible.
2) Re-define `Trip` as the commercial itinerary/package container tied to basket/invoice primitives.

C) Catalog-driven offerings (already built)
- Assume catalog combinations already exist via primitives.
- Your job is to CONNECT them:
  - Trip is created from baskets/invoices referencing catalog items
  - Trip expands/derives a fulfillment plan (which items imply operational excursions)
  - Excursions are created/scheduled as fulfillment objects linked back to the originating sale line items
- Do NOT re-implement catalog composition. Use existing primitive APIs.

D) Commissions (already supported by primitives)
- Use the existing ledger/accounting primitives to compute and post commissions.
- Commission rules come from existing constructs (default rules, overrides, affiliates/providers/booth owner).
- Ensure commission posting is traceable to Trip line items and fulfillment completion.

REQUIRED DELIVERABLES
1) An explicit mapping document:
   - “Which primitive handles what” for Trips/Excursions/Dives
   - Which existing “Trip” code maps to Excursion
2) Refactor plan with file-level changes:
   - current Trip model/service/view usage inventory
   - what becomes Excursion
   - what becomes Trip (package)
   - what remains as alias for backwards compatibility
3) Implementation:
   - Domain services:
     - TripService: create trip from basket/invoice, itinerary structure, attach excursions, commission hooks
     - ExcursionService: schedule, assign staff, roster/manifest, attach dive plans/logs, status transitions
   - Minimal domain models only when necessary:
     - e.g. mapping between Trip line items and created Excursions (traceability)
     - e.g. itinerary day structure if primitives don't already represent it
4) Migration strategy:
   - Safely migrate existing operational Trip data into Excursion semantics
   - Preserve primary keys if feasible; otherwise create mapping + update FKs
   - Provide a rollback note
5) API/UI:
   - Operator UI should show “Excursions”
   - Sales UI should show “Trips” (packages)
   - Keep /trips operational endpoints working as alias or deprecate safely with /excursions replacement
6) Tests:
   - Excursion single-day constraint
   - Trip multi-day container
   - Backwards compatibility endpoints
   - Audit events emitted for mutations
   - Commission posting triggered from fulfillment completion

NON-GOALS
- Do not modify primitives packages (unless there is a clearly justified bug fix)
- Do not implement payment processors, email, or marketing automation
- Do not build dive computer profile ingestion
- Do not add new “catalog composition” logic; use the existing one

OUTPUT REQUIREMENTS
- Start by listing the architecture/docs you read.
- Then present a plan with small incremental steps.
- Then implement changes.
- End with how to run tests and verify manually.
