# Vibe Coding an ERP: Building Serious Business Systems with Django and LLMs

## Book Overview

**Working Title**: Vibe Coding an ERP: How to Build Correct Business Systems Fast with Django and LLMs

**Tagline**: Move fast inside hard constraints. Ship systems that survive audits, explain themselves, and don't lie.

**Target Audience**:
- Django developers building business/financial applications
- Developers using LLMs for code generation who want better results
- Technical founders building MVPs that won't require rewrites
- Engineers rescuing systems with audit/reconciliation problems

**Unique Value Proposition**:
This is the only book that combines:
1. Historical grounding in proven patterns (Pacioli, Snodgrass, Lamport)
2. Practical Django implementation
3. LLM-assisted development methodology
4. Real case studies from production systems

---

## Book Structure

### Part I: The Constraints
*What you must not violate*

**Chapter 1: Vibe Coding With Constraints**
- The two ways to fail
- What vibe coding actually means
- Why ERP is the hardest test
- Why Django
- The role of the LLM
- The VetFriendly origin story

**Chapter 2: Why ERP Systems Fail**
- Identity duplication
- Permission drift
- Mutable history
- Fuzzy time
- Retry duplicates
- Mutation instead of facts
- (Condensed from the article's Part I)

**Chapter 3: The Primitives and Their Origins**
- Identity graphs (Fellegi-Sunter, MDM)
- Ledgers (Pacioli, Cotrugli)
- Bitemporality (Snodgrass, SQL:2011)
- Immutability (archival science, event sourcing)
- Idempotency (Two Generals, Stripe)
- Events and decisions (DDD, CQRS)
- Reversals (Sagas, Garcia-Molina)
- (Historical grounding from the article)

**Chapter 4: Defining Your Constitution**
- How to identify which primitives you need
- Writing constraint documents
- The 26-step development cycle
- When to reject LLM output

---

### Part II: The Django Implementation
*How to build each primitive*

**Chapter 5: Identity - The Party Pattern**
- Models: Party, Person, Organization
- Relationships and roles
- Identifier resolution
- Django implementation with polymorphic models or manual inheritance
- Tests for merge/unmerge scenarios

**Chapter 6: Ledgers - Double-Entry in Django**
- Models: Account, Transaction, Entry
- Computed balances vs. stored balances
- Database constraints for balance verification
- Sub-ledgers and control accounts
- The ledger app as a reusable Django package

**Chapter 7: Bitemporality - Two Kinds of Time**
- Valid time vs. transaction time
- Options: django-simple-history, manual versioning, temporal tables
- Query patterns: as-of, as-known-at
- Retroactive processing
- Period close implementation

**Chapter 8: Immutability - Append-Only Models**
- Making models truly immutable (no UPDATE/DELETE)
- Database permission enforcement
- Soft deletes vs. supersession
- Hash chains for tamper evidence
- Django admin for immutable models

**Chapter 9: Idempotency - Safe Retries**
- Idempotency key middleware
- Database-backed key storage
- Handling concurrent duplicates
- Idempotent Celery tasks
- Testing retry scenarios

**Chapter 10: Events - Decisions as Facts**
- Event store models
- Publishing events from Django signals
- Building projections
- Snapshots for performance
- The outbox pattern for reliability

**Chapter 11: Reversals - Undo Without Erasing**
- Compensation patterns
- State machines with django-fsm
- Linking reversals to originals
- Partial reversals
- Saga orchestration for distributed operations

**Chapter 12: Agreements - Terms Over Time**
- Agreement and version models
- Terms modeling (pricing, SLAs, obligations)
- Temporal foreign keys
- Evaluating terms as-of a date
- Amendment workflows

**Chapter 13: Sequences - Gapless Numbering**
- Sequence service design
- Gap tracking and explanation
- Human-readable ID patterns
- Django implementation with SELECT FOR UPDATE
- Multi-tenant sequences

**Chapter 14: Permissions - Access Control That Audits**
- Beyond Django's built-in permissions
- RBAC implementation
- Permission change audit trail
- Certification campaigns
- Service account controls

---

### Part III: The Workflow
*How to actually build with LLMs*

**Chapter 15: Constraint-First Prompting**
- Why feature-first prompts fail
- Invoking patterns by name
- The prompt library structure
- Tiered prompts: foundation → contracts → TDD → production

**Chapter 16: The Development Cycle**
- The 26-step methodology (or whatever Nestor's actual process is)
- When to prompt vs. when to write
- Code review prompts
- Verification prompts

**Chapter 17: Testing Primitive Compliance**
- Test categories: invariants, edge cases, failure modes
- Generating tests with LLMs
- Property-based testing for constraints
- Integration tests for primitive interactions

**Chapter 18: When Things Go Wrong**
- Recognizing LLM errors
- Common failure patterns
- Rollback and recovery
- Post-incident primitive review

---

### Part IV: Case Studies
*The primitives in production*

**Chapter 19: VetFriendly - Veterinary Practice Management**
- Domain model
- Which primitives and why
- Implementation highlights
- What survived, what was refactored

**Chapter 20: Property Management - Leases and Payments**
- Domain model
- Mapping lease concepts to agreements
- Rent as ledger entries
- Tenant identity resolution

**Chapter 21: Dive Operations - Equipment and Certifications**
- Domain model
- Tank tracking as inventory ledger
- Certifications as temporal records
- Booking as events

**Chapter 22: What Transfers, What Doesn't**
- The reusable primitive core
- Domain-specific adaptations
- Knowing when to diverge
- Building your primitive library

---

### Appendices

**Appendix A: The Prompt Library**
- Complete tiered prompts for all primitives
- Django-specific variants
- (Expanded from the article's addendum)

**Appendix B: Django Package Recommendations**
- django-simple-history vs. alternatives
- django-fsm for state machines
- django-polymorphic for party pattern
- Testing packages

**Appendix C: Database Considerations**
- PostgreSQL features for primitives
- Constraints, triggers, functions
- Performance for temporal queries
- Migration strategies

**Appendix D: References**
- Historical sources (Pacioli, Snodgrass, Lamport, etc.)
- Django documentation
- Further reading by primitive

---

## Chapter Word Counts (Estimated)

| Chapter | Words |
|---------|-------|
| Part I: Constraints (Ch 1-4) | 20,000 |
| Part II: Implementation (Ch 5-14) | 50,000 |
| Part III: Workflow (Ch 15-18) | 15,000 |
| Part IV: Case Studies (Ch 19-22) | 20,000 |
| Appendices | 10,000 |
| **Total** | **~115,000** |

This is roughly 350-400 pages in print.

---

## Code Repository Structure

```
vibe-erp/
├── primitives/
│   ├── identity/          # Party pattern, resolution
│   ├── ledger/            # Double-entry accounting
│   ├── temporal/          # Bitemporal support
│   ├── events/            # Event store, projections
│   ├── idempotency/       # Key middleware
│   ├── sequences/         # Gapless numbering
│   └── agreements/        # Terms, versions
├── examples/
│   ├── vetfriendly/       # Veterinary case study
│   ├── property/          # Property management
│   └── diveops/           # Dive operations
├── tests/
│   ├── invariants/        # Constraint verification
│   ├── edge_cases/        # Boundary conditions
│   └── integration/       # Cross-primitive tests
└── prompts/
    ├── foundation/        # Tier 1 prompts
    ├── contracts/         # Tier 2 prompts
    ├── tdd/               # Tier 3 prompts
    └── production/        # Tier 4 prompts
```

---

## Development Plan

### Phase 1: Foundation (Chapters 1-4)
- Complete Part I establishing the thesis
- Finalize the constraint documentation format
- Verify all historical claims

### Phase 2: Core Implementation (Chapters 5-10)
- Build the primitive Django packages
- Write implementation chapters alongside code
- Ensure code compiles and tests pass at each chapter

### Phase 3: Advanced Implementation (Chapters 11-14)
- Complete remaining primitive chapters
- Integration between primitives
- Performance considerations

### Phase 4: Workflow (Chapters 15-18)
- Document the actual development process
- Refine prompt library based on book-writing experience
- Testing methodology

### Phase 5: Case Studies (Chapters 19-22)
- Extract and sanitize VetFriendly examples
- Document other domain applications
- Synthesis chapter on reuse

### Phase 6: Polish
- Appendices
- Code review and cleanup
- Technical review
- Copy editing

---

## Questions to Resolve

1. **The 26-step cycle**: What is the actual methodology? Need to document Nestor's real process.

2. **Code licensing**: Will the primitive packages be open source? MIT? 

3. **VetFriendly sanitization**: How much real code can be shown? What needs to be genericized?

4. **Django version**: Target Django 4.2 LTS? 5.0?

5. **Database**: PostgreSQL-only, or support SQLite for development?

6. **Publication path**: Traditional publisher, self-published, or living document?

---

## Next Steps

1. Review and refine Chapter 1 outline
2. Draft Chapter 1 prose
3. Document the actual development cycle (the "26 steps" or equivalent)
4. Begin primitives package structure
5. Outline Chapter 2 (Why Systems Fail)
