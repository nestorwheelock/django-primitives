You are implementing invoice printing for primitives_testbed.
You must follow the existing Invoice Printing Implementation Plan exactly.

Hard constraints (non-negotiable):
- PostgreSQL only.
- Deterministic printing: render ONLY from Invoice + InvoiceLineItem snapshot fields, not live pricing/catalog.
- Printable statuses: issued, paid, voided ONLY. Draft must be rejected.
- Security: enforce org access + RBAC permission check. No IDOR.
- Keep changes minimal. No new invoice fields unless required.
- No DRF. No editing UI. No new billing features.
- Prefer DB invariants already enforced; do not move invariants into Python “just because.”

Execution order (TDD, in small commits):
1) Tests first: create tests/test_invoice_printing.py with failing tests for selector + printing service + views.
2) Implement selector: invoicing/selectors.py get_invoice_for_print(invoice_id, user) that:
   - uses select_related/prefetch_related to avoid N+1
   - enforces status rule
   - enforces org access + RBAC permission
   - returns a DTO or the loaded Invoice object ready for rendering
3) Implement InvoicePrintService in invoicing/printing.py:
   - render_html() -> str using templates/invoicing/invoice_print.html
   - render_pdf() -> bytes using WeasyPrint
   - get_filename() -> deterministic filename using invoice_number
   - uses print.css as the stylesheet
4) Implement views + urls:
   - /invoicing/<uuid>/print/ (HTML)
   - /invoicing/<uuid>/pdf/ (download)
   - /invoicing/<uuid>/pdf/view/ (inline)
   - login required
   - content types correct
   - 404 for missing invoice, 400 for draft/not printable, 403 for denied access
5) Add optional storage integration (OFF by default):
   - INVOICE_STORE_PDF = False in settings
   - invoicing/document_storage.py with store_invoice_pdf(invoice, user) that:
     - creates a Document with checksum
     - links it to invoice
     - enforces append-only: if already stored, do not overwrite
6) Update invoicing/ARCHITECTURE.md:
   - document printing contract, snapshot requirement, access control, immutability behavior
7) Run full suite and keep it green:
   - pytest -q
   - python manage.py verify_integrity --detailed

Testing requirements:
- test_draft_invoice_not_printable
- test_issued_invoice_printable
- test_render_html_contains_invoice_number_and_totals
- test_render_pdf_returns_nonempty_bytes_and_pdf_header
- test_snapshotted_prices_used_when_catalog_changes
- test_access_denied_wrong_org
- test_pdf_views_return_correct_content_type_and_headers
- storage tests only if INVOICE_STORE_PDF enabled in test settings

Performance requirement:
- selector + print should not trigger N+1.
- Add an assert on django_assert_num_queries (or equivalent) for the selector path.

Renderer requirement:
- Use WeasyPrint. Add dependency and ensure import works.
- Do not add wkhtmltopdf or system binaries.

Output:
- Provide full code for each new/modified file.
- Show commands to run:
  - docker compose up -d db
  - migrate
  - pytest tests/test_invoice_printing.py -v
  - curl example for PDF endpoint
- If any decision is ambiguous, choose the simplest option consistent with auditability and primitives rules.

Stop only when all tests pass and the feature is fully wired into urls.py.
