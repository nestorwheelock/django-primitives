# Chapter 6: Identity

> Who is this, really? The same person can appear as customer, vendor, and employee. The same company can have five names. Identity is a graph, not a row.

---

**Core idea:** Identity is the foundation of every business system. Get it wrong and every other primitive fails. Get it right and the rest becomes composable.

**Failure mode:** Treating identity as a simple database row. Conflating the person with their login account. Assuming names are unique, emails are permanent, and people only play one role.

**What to stop doing:** Creating separate tables for customers, vendors, and employees. Storing identity data without relationships. Assuming the person in front of you is exactly who the database says they are.

---

## The Cost of Getting It Wrong

Identity seems simple. A person has a name. An organization has a tax ID. Store them in a table. Move on.

This assumption has cost businesses billions.

According to industry research, poor data quality costs U.S. businesses $3.1 trillion annually, with the average organization losing $13 million per year. A significant portion of this is identity duplication—the same customer appearing multiple times in different systems, with different names, different contact information, and different transaction histories.

The duplicate problem compounds. In organizations without formal data governance, duplication rates of 10-30% are common. In healthcare, where identity errors can be life-threatening, large systems face duplication rates of 15-16%, translating to 120,000 duplicate records in a database of one million patients. Each duplicate costs between $20 and $1,950 to resolve, depending on the complexity and the consequences of the error.

Children's Medical Center Dallas hired an outside firm to address their duplicate problem. Their initial duplication rate was 22%—meaning more than one in five patient records was a duplicate of another. After cleanup, the rate dropped to 0.2%, and they reduced their duplicate-resolution staff from five full-time employees to less than one. Five years later, the rate remained at 0.14%.

Emerson Process Management faced a different scale of the same problem: potentially 400 different master records for each customer. They eliminated a 75% duplication rate through systematic identity management.

These aren't edge cases. They're what happens when identity is treated as a simple column in a table instead of a graph of relationships.

---

## The Person Is Not the User

The first identity mistake is conflating two different concepts: the person and the login account.

A **Person** is a human being who exists in the real world. They have a name, a birthday, contact information, and relationships to other people and organizations. The person exists whether or not they've ever touched your software.

A **User** is a login account. It's a set of credentials that grants access to a system. It has a username, a password (or OAuth token), and permissions.

These are not the same thing.

One person can have multiple user accounts. An employee might log in with their work email during business hours and with their personal email when accessing the customer portal. A user might have separate accounts for different departments or subsidiaries.

A user account can exist without a person. Service accounts, API keys, and integration accounts are users without corresponding human beings. They need permissions. They don't need birthdays.

A person can exist without any user accounts. A contact in your CRM who has never logged in. A patient who exists in medical records but has never created an account. A vendor representative who calls on the phone but doesn't use your portal.

When you conflate person and user, you lose the ability to answer basic questions:

- How many unique customers do we actually have? (If you count user accounts, you're wrong.)
- Which person approved this transaction? (If you only stored the user ID, you might not know.)
- What happens when an employee leaves? (If their person record is tied to their user account, you might lose their history.)

The fix is separation. Person is an identity primitive. User is an authentication primitive. Link them, but don't merge them.

---

## The Party Pattern

Enterprise software solved this problem decades ago with the **Party Pattern**.

A Party is an entity that can participate in business transactions. The same pattern applies whether the party is a person, an organization, or a group of people acting together.

```
Party (abstract concept)
├── Person - A human being
├── Organization - A legal entity (company, clinic, government agency)
└── Group - A collection of parties acting together (household, team, department)
```

The power of this pattern is that it treats all parties uniformly at the relationship level. A customer can be a person (individual consumer) or an organization (B2B client). A vendor can be a person (freelancer) or an organization (supplier). The invoicing system doesn't need to know which—it just deals with parties.

This pattern appears in every major ERP system. SAP's S_PARTY table stores all parties with a PARTY_TYPE_CD column. Oracle's party data model similarly unifies individuals and organizations. The pattern isn't new. It's been proven in production systems for over forty years.

But the pattern is more than just inheritance. It's a graph.

A Party Relationship connects two parties with a relationship type. The same person can be:

- An employee of Organization A
- A contractor for Organization B
- A customer of both
- The emergency contact for Person C
- A member of Group D (the household)
- The head of Group E (the family)

This is reality. People don't have single roles. They exist in webs of relationships that your system either models correctly or models wrong.

---

## Names Are Not Unique

A deeper identity assumption trips up almost every system: that names identify people.

They don't.

The Social Security Administration reports that millions of Americans share common names—there are thousands of "John Smiths" and "Maria Garcias" in any large database. In countries with patronymic naming conventions, name collisions are even more common.

Names change. People get married, divorced, or simply decide to use a different name. In many cultures, people have multiple names for different contexts—a formal name, a business name, a family name. Immigrants often adopt anglicized names while retaining their legal names for official documents.

A person's name at registration is not necessarily the same name they'll use for the next transaction. Your system must handle this.

This is why identity primitives separate:

- **Legal name:** What appears on official documents
- **Display name:** What the person wants to be called
- **Search variations:** Different spellings, transliterations, nicknames

The same applies to organizations. A company has:

- **Legal name:** What's filed with the government
- **Trade name / DBA:** What customers know them by
- **Former names:** What they were called before a merger or rebrand

Costco's legal name is Costco Wholesale Corporation. But in your database, they might also appear as Costco, Costco Wholesale, Price Club (the company they merged with), or any of their subsidiary names in different countries.

When someone searches for a customer, which name should match? All of them.

---

## The Matching Problem

This is where identity becomes genuinely hard.

Record linkage—determining whether two records refer to the same real-world entity—has been a computer science research problem since the 1940s. Census bureaus faced this first: how do you match records from different surveys to ensure you're not counting the same person twice?

In 1969, Ivan Fellegi and Alan Sunter published "A Theory For Record Linkage," formalizing the probabilistic approach that remains foundational today. Their insight was that you can't be certain two records match—but you can quantify the probability based on how their attributes compare.

Two records with the same Social Security Number are almost certainly the same person. (Almost—SSN fraud exists.) Two records with the same first name and birth year might be the same person—or might be completely different people. Two records with the same last name and city might be the same family—or might be strangers.

Probabilistic matching assigns weights to each comparison and calculates a combined score. Above a threshold, the records are considered a match. Below a threshold, they're considered distinct. In the middle? Human review.

This matters for fraud detection. Fraudsters open multiple accounts with slight variations: John Smith, Jon Smith, J. Smith—all with the same address but different email addresses. Without identity resolution, each application looks legitimate. With proper matching, the pattern becomes visible.

Financial institutions, healthcare systems, and government agencies spend enormous resources on identity resolution. They have to. The alternative is losing track of who's who—which means losing track of money, health records, and legal obligations.

Your system probably can't afford a full probabilistic matching engine. But your system needs to be designed so that identity resolution is possible. That means:

- Storing normalized data that can be compared
- Maintaining relationship links between records
- Never assuming that two different records are definitely different entities
- Supporting the eventual merging of records discovered to be duplicates

---

## Contacts Are Relationships, Not Columns

Another common mistake: storing contact information as columns on the party record.

```
Person:
  - email: "john@example.com"
  - phone: "555-1234"
  - address: "123 Main St"
```

This breaks immediately in production.

People have multiple email addresses—personal and work, at minimum. Which one is "the" email? The one for marketing? The one for invoices? The one they check daily?

People have multiple phone numbers—mobile and landline, plus work numbers, plus the number they prefer for text messages but not calls.

People have multiple addresses—billing address, shipping address, mailing address, plus vacation addresses, plus the address they had before they moved.

The fix is to model contacts as related entities:

```
Person:
  - emails: [
      { address: "john@work.com", type: "work", is_primary: true },
      { address: "john.personal@gmail.com", type: "personal" }
    ]
  - phones: [
      { number: "555-1234", type: "mobile", is_sms_capable: true },
      { number: "555-5678", type: "work" }
    ]
  - addresses: [
      { type: "billing", line1: "123 Main St", ... },
      { type: "shipping", line1: "456 Oak Ave", ... }
    ]
```

This adds complexity. But the complexity exists in reality. Your data model either reflects it or lies about it.

For convenience, many systems provide "inline" contact fields on the party record for quick data entry—a single email and phone for simple cases. But behind the scenes, the full normalized structure exists for cases that need it.

---

## Access Is Not Identity

The second primitive in identity is not about who someone *is*—it's about what they're *allowed to do*.

Role-Based Access Control (RBAC) has been the standard approach since the 1990s. Instead of assigning permissions directly to users, you define roles (Admin, Manager, Staff, Customer), assign permissions to roles, and assign roles to users.

But RBAC has a critical failure mode: **privilege escalation**.

If an Admin can assign any role to any user, what stops a Manager from asking a friendly Admin to upgrade them? What stops a Staff member who knows the Admin's password from promoting themselves?

The solution is **hierarchical RBAC**, which enforces a simple rule: **users can only manage users with lower authority than themselves**.

This is not a convenience feature. It's a security invariant.

Consider a system with these hierarchy levels:

- Superuser (100): System administrators
- Administrator (80): Full business access
- Manager (60): Team leads
- Staff (20): Front-line employees
- Customer (10): External users

A Manager at level 60 can assign roles to Staff (20) and Customers (10). They cannot assign roles to other Managers, Administrators, or Superusers. They cannot promote themselves.

An Administrator at level 80 can assign any role below their level—but cannot create new Superusers. Only existing Superusers can create other Superusers.

This hierarchy enforcement must be implemented at the application level, not just the UI. A clever attacker who bypasses the UI (by sending direct API requests or manipulating the database) must still hit the same walls. The constraint is enforced in code, not just in interface design.

---

## Temporal Identity

People's identities change over time. Names, addresses, roles, and relationships all have temporal dimensions.

When did this employee join the company? When did they leave? During their employment, what roles did they hold, and when? If you need to reconstruct the org chart as of last January, can you?

This requires treating identity assignments as **temporal records**:

```
UserRole:
  - user: "alice"
  - role: "Manager"
  - valid_from: "2023-01-15"
  - valid_to: null  # current

UserRole:
  - user: "alice"
  - role: "Staff"
  - valid_from: "2021-06-01"
  - valid_to: "2023-01-14"  # ended when promoted
```

With temporal records, you can query:

- What roles does Alice have **right now**? (current assignments)
- What roles did Alice have on **2022-07-01**? (as-of query)
- When did Alice become a Manager? (history query)

This matters for audits. "Who had access to the financial records during Q3?" requires temporal identity data. If you only store current roles, you can't answer the question.

It also matters for access revocation. When an employee leaves, you don't delete their identity—you end-date their roles. The history of who they were and what they could do remains for audit purposes. They simply can no longer log in or access anything.

---

## The Identity Stack

The primitives compose into layers:

**Layer 1: Party (Who exists)**
- Person, Organization, Group models
- Names, identifiers, demographic data
- Contact information (addresses, phones, emails)
- Relationships between parties

**Layer 2: User (Who can log in)**
- Authentication credentials
- Link to Person (optional—service accounts don't need one)
- Session management

**Layer 3: Role (What can they do)**
- Role definitions with hierarchy levels
- Role assignments with temporal validity
- Permission inheritance

**Layer 4: Permission (What actions exist)**
- Module/action pairs (e.g., "invoices.create", "patients.view")
- Assigned to roles, not directly to users
- Enforced in views, decorators, and mixins

Each layer depends only on the layers below it. The party layer knows nothing about authentication. The role layer doesn't know what a customer record looks like. This separation means you can change the authentication system without touching identity data. You can add new permissions without restructuring parties.

---

## Soft Delete, Never Hard Delete

Identity records must never be physically deleted.

When a person "leaves" your system—a customer closes their account, an employee resigns, a vendor is terminated—the record must remain. Other records reference it. Audit trails point to it. Historical reports include it.

Physical deletion breaks these references. Foreign keys fail. Audit logs become inexplicable ("Who approved this invoice?" "User ID 47." "Who was that?" "Record not found.").

The solution is **soft delete**: a `deleted_at` timestamp that marks a record as removed without destroying it.

```
Person:
  - id: 1234
  - name: "Jane Doe"
  - deleted_at: "2024-03-15T10:30:00Z"
```

Default queries exclude soft-deleted records. Special admin queries can include them. Historical queries always include them.

This creates a compliance complexity: under regulations like GDPR and CCPA, individuals can request deletion of their personal data. Soft delete may not satisfy this requirement. The solution is **anonymization**: replace personally identifiable fields with placeholders ("Deleted User #1234") while preserving the record for referential integrity.

Duplicate or incorrect customer records can violate privacy regulations. Under CCPA in California, penalties can reach $2,500–$7,500 per consumer record. Proper identity management isn't just about data quality—it's about regulatory compliance.

---

## What AI Gets Wrong

Ask an AI to build a user management system. It will produce:

- A User model with email, password, and role
- A simple role field or maybe a many-to-many with Role
- No party separation
- No temporal validity
- Hard delete by default
- Email and phone as columns, not relationships

This is what user management looks like in tutorials. It's what most applications start with. It's also what fails at scale.

The AI doesn't know that:
- The same person might need multiple login methods
- Roles need hierarchy to prevent privilege escalation
- Access assignments need timestamps for auditing
- Delete operations in identity systems are almost never physical

These are your constraints. The AI will follow them if you specify them. But if you don't specify them, it will generate the statistically likely pattern—which is the pattern from tutorials, which is wrong.

---

## Building It Correctly: A Preview

This chapter describes what identity primitives must do. Part III of this book describes *how* to make AI build them correctly.

The short version: you don't trust the AI to invent. You constrain it to compose.

**Constraints in prompts.** Before generating any identity code, you specify the invariants: "Party records are never deleted, only soft-deleted. Roles have hierarchy levels. Role assignments are temporal with valid_from and valid_to dates. Contact information is normalized into separate tables."

**Tests before implementation.** You write (or have AI write) tests that verify the constraints before writing implementation code. "Test that deleting a Person raises an error or sets deleted_at. Test that a Manager cannot assign Admin role to another user. Test that a role assignment without valid_from defaults to now."

**Documentation as specification.** User stories and acceptance criteria become the constraints the AI must satisfy. "As an administrator, I can revoke a user's role by end-dating their assignment, so that their access ends immediately but their history remains auditable." The AI generates code; you verify it matches the documented behavior.

**Code reviews against physics.** Every generated file is reviewed against the primitives. Does this model have a deleted_at field? Does this role assignment have temporal validity? Does this endpoint check hierarchy before allowing role changes?

This is what separates constrained AI development from "vibe coding" gone wrong. The primitives are the physics. The prompts are the constraints. The tests are the verification. The documentation is the specification.

Part III covers this in depth: prompt contracts, schema-first generation, forbidden operations, and the development cycle that makes AI produce correct systems instead of plausible ones. For now, understand that the identity primitives aren't just concepts—they're testable, verifiable, enforceable rules that AI must follow.

---

## The Primitives

The identity primitive consists of two interlocking packages:

**django-parties** provides the party layer:
- `Person`, `Organization`, `Group` models with the Party Pattern
- Flexible `PartyRelationship` for any party-to-party connection (18 relationship types: employee, contractor, customer, owner, vendor, partner, member, spouse, guardian, parent, emergency contact, and more)
- Normalized contact tables: `Address`, `Phone`, `Email`, `PartyURL`
- Demographics model for extended person attributes
- Soft delete with restore capability
- Display name calculation and selectors for searching

**django-rbac** provides the access control layer:
- `Role` model with hierarchy levels (10-100 scale)
- `UserRole` with temporal validity (`valid_from`, `valid_to`)
- `RBACUserMixin` for adding RBAC to any User model
- Decorators (`@require_permission`, `@requires_hierarchy_level`)
- View mixins (`ModulePermissionMixin`, `HierarchyPermissionMixin`)
- `can_manage_user()` method enforcing strict hierarchy
- Effective dating via `EffectiveDatedQuerySet` (`.current()`, `.as_of()`)

These packages handle identity so you don't have to reinvent it. They encode the constraints that tutorials skip. They survive audits because they were built to.

---

## Why This Matters Later

Identity is the foundation. Every other primitive references it.

Ledger entries record which party owes money to which other party. Agreements are contracts between identified parties. Workflows track which user performed each action. Audit logs record who did what, when.

If your identity layer is wrong—if people appear multiple times, if roles can be escalated, if access history can't be reconstructed—then every downstream primitive inherits the problem.

The next chapter covers Time—when things happened versus when we recorded them. But time without identity is meaningless. "This invoice was created at 3:47 PM" means nothing if you can't say who created it.

The primitives build on each other. Identity comes first because everything else requires knowing who's involved.

---

## How to Rebuild These Primitives

The Identity packages can be rebuilt from scratch using constrained prompts:

| Package | Prompt File | Test Count |
|---------|-------------|------------|
| django-parties | `docs/prompts/django-parties.md` | 44 tests |
| django-rbac | `docs/prompts/django-rbac.md` | ~35 tests |

### Using the Prompts

```bash
# Rebuild django-parties
cat docs/prompts/django-parties.md | claude

# Request: "Implement the Person and Organization models first,
# then PartyRelationship with GenericForeignKey."
```

### Key Constraints

- **Party pattern enforced**: Person and Organization share PartyBaseMixin
- **GenericForeignKey for contact info**: Address, Phone, Email attach to any party type
- **Relationship validity**: PartyRelationship has valid_from/valid_to for temporal queries
- **Soft delete via BaseModel**: Parties are never hard-deleted

If Claude creates separate Customer and Vendor models instead of using Person with roles, that's a constraint violation.

---

## References

- Fellegi, Ivan P., and Alan B. Sunter. "A Theory for Record Linkage." *Journal of the American Statistical Association* 64, no. 328 (1969): 1183-1210.
- TDAN.com. "A Universal Person and Organization Data Model." https://tdan.com/a-universal-person-and-organization-data-model/5014
- ADRM Software. "Party Data Model." http://www.adrm.com/ba-party.shtml
- Hevo Data. "Party Data Models: A Comprehensive Guide." https://hevodata.com/learn/party-data-model/
- Landbase. "Duplicate Record Rate Statistics: 32 Key Facts Every Data Professional Should Know in 2025." https://www.landbase.com/blog/duplicate-record-rate-statistics
- Eckerson Group. "Hidden Costs of Duplicate Data." https://www.eckerson.com/articles/hidden-costs-of-duplicate-data
- Profisee. "8 Problems That Result from Data Duplication." https://profisee.com/blog/8-business-process-problems-that-result-from-data-duplication/
- CDQ. "The Hidden Costs of Duplicate Business Partner Records." https://www.cdq.com/blog/hidden-costs-duplicate-business-partner-records
- Informatica. "What Is Identity Resolution?" https://www.informatica.com/resources/articles/what-is-identity-resolution.html
- Senzing. "What Is Identity Resolution? How It Works & Why It Matters." https://senzing.com/what-is-identity-resolution-defined/
- Splink. "The Fellegi-Sunter Model." https://moj-analytical-services.github.io/splink/topic_guides/theory/fellegi_sunter.html

---

*Status: Draft*
