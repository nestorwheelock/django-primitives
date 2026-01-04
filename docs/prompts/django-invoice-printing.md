You are implementing invoice printing for our Django primitives-based system.

MANDATORY CONTEXT:
- PostgreSQL is the only supported database.
- We use django-primitives packages (parties, catalog, pricing, invoicing, documents, notes, sequence, ledger, agreements, rbac, geo, worklog, encounters).
- Data integrity invariants are enforced in Postgres wherever possible.
- Invoicing is audit-sensitive: invoices should not be edited after issuing; void/refund are separate actions (do not implement those unless required).
- Pricing is snapshotted: invoice line items store unit_price + line_total at invoice time.
- We have architecture files for modules and repo rules; you MUST read and follow them before coding.

STEP 0: READ FIRST (no coding yet)
- Locate and read:
  - repo-level ARCHITECTURE.md
  - invoicing module ARCHITECTURE.md (if present)
  - pricing module ARCHITECTURE.md (if present)
  - documents/notes architecture docs (if present)
  - any rules in docs/ (including integrity sweep docs)
Summarize the constraints and rules you discovered in 10 bullets max.
Only then proceed.

GOAL:
Implement printable invoices:
1) HTML view for browser printing
2) PDF output suitable for emailing/downloading/archiving
3) Optional “store rendered PDF” hook via django-documents (but keep it off by default)

NON-GOALS:
- No DRF API
- No external SaaS for rendering
- No full billing UI
- No “edit invoice” screens

FUNCTIONAL REQUIREMENTS:
A) Print Inputs
- Invoice is identified by UUID primary key
- Only allow printing invoices with status in {"issued", "paid", "voided"} (draft not printable)
- The print view must be deterministic: always renders from snapshotted invoice + line items (NOT from current pricing/catalog)

B) Rendered Content (minimum fields)
- Invoice number (from sequence)
- Issue date, due date (if present)
- Billed-to party details (name + address + contact)
- Issued-by org details (name + address + contact)
- Line items:
  - display_name/description
  - quantity
  - unit price (Money formatted)
  - line total
- Subtotal, tax (if present), total, amount paid (if present), balance due
- Optional metadata:
  - agreement reference (if present)
  - encounter reference (if present)

C) Formatting Rules
- Print-safe CSS
- Pagination: line items should not break mid-row
- Handle long descriptions gracefully
- Locale/currency formatting must be explicit and deterministic

D) PDF Implementation
- Use a reliable local renderer (choose ONE):
  - WeasyPrint OR
  - wkhtmltopdf OR
  - ReportLab
Pick the simplest for Django integration with good Unicode support.
Explain the tradeoff and why you chose it.
No network calls.

E) Storage Integration (optional)
- If enabled, store generated PDF as a Document in django-documents
- Include checksum immutability expectations
- Store a reference from Invoice to Document (optional FK) OR store via generic relation
- Must not regenerate/overwrite stored PDFs once saved (append-only behavior)

F) Security / Access Control
- Only authenticated users with appropriate role may print (integrate with django-rbac if available)
- Prevent IDOR: user must have access to the invoice’s org

G) Performance
- Avoid N+1 queries: use select_related/prefetch_related for party/org/address/line items
- Provide a selector function get_invoice_for_print(invoice_id, user_context)

TEST REQUIREMENTS:
- Unit tests for:
  - draft invoices cannot be printed
  - render uses snapshotted fields (changing catalog price does not change output)
  - PDF generation returns bytes and is non-empty
  - access control denies unauthorized users
- If storage enabled, test immutability behavior (re-render doesn’t overwrite existing stored PDF)

DELIVERABLES:
1) invoicing/printing.py (rendering service)
2) invoicing/selectors.py updates for print query
3) invoicing/views.py for:
   - HTML print view
   - PDF download view
4) templates/invoicing/invoice_print.html
5) static CSS (print stylesheet)
6) Optional documents integration module or feature flag
7) Tests
8) Short docs update:
   - “Invoice Printing” section in invoicing README/ARCHITECTURE
   - How it respects primitives and immutability

OUTPUT FORMAT:
- Provide the file tree and full code for each new/modified file.
- Provide exact commands to run tests and generate a sample PDF locally.

IMPORTANT CONSTRAINTS:
- Do NOT introduce new invoice fields unless strictly required for printing.
- Do NOT implement payment UI.
- Keep changes minimal and aligned with architecture rules.
