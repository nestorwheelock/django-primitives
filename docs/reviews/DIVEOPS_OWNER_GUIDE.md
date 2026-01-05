# DiveOps - Dive Shop Management System
## Owner's Guide

---

## What is DiveOps?

DiveOps is a comprehensive dive shop management system designed to handle the day-to-day operations of running a recreational diving business. It manages everything from customer profiles and certifications to trip scheduling, bookings, and billing.

---

## Core Concepts

### 1. Divers (Your Customers)

Every customer in your system has a **Diver Profile** that tracks:

- **Personal Information**: Name, contact details, emergency contact
- **Certifications**: What diving credentials they hold (Open Water, Advanced, Rescue, etc.)
- **Medical Status**: Whether their medical clearance is current
- **Booking History**: All past and upcoming trips

**Why this matters**: The system automatically checks if a diver is eligible for specific trips based on their certification level and medical status. No more manually checking paperwork before every trip.

---

### 2. Dive Sites

Dive sites are the locations where you take customers diving. Each site includes:

- **Name and Description**: For customer-facing materials
- **Maximum Depth**: Used to determine certification requirements
- **Location**: Geographic coordinates (for navigation/logistics)
- **Active Status**: Whether you're currently offering dives at this site

**Example**: "Blue Hole Reef" - Maximum depth 30m, requires Advanced Open Water certification

---

### 3. Excursions (Dive Trips)

An **Excursion** is a scheduled dive trip. This is the core of your daily operations:

- **Scheduled Date/Time**: When the trip departs
- **Primary Dive Site**: Main destination
- **Boat/Vessel**: Which boat is assigned (if applicable)
- **Capacity**: Maximum number of divers
- **Status**: Scheduled → In Progress → Completed (or Cancelled)

Each excursion can include **multiple dives** (e.g., a two-tank morning trip).

**Excursion Lifecycle**:
```
SCHEDULED → CHECK-IN → STARTED → COMPLETED
                ↓
            CANCELLED (if needed)
```

---

### 4. Dives (Individual Dives within an Excursion)

Each excursion contains one or more individual **Dives**:

- **Sequence Number**: First dive, second dive, etc.
- **Dive Site**: Where this specific dive takes place
- **Planned Start Time**: When the dive begins
- **Duration**: Planned dive time in minutes
- **Max Depth**: Maximum planned depth for this dive

**Example**: A "Two-Tank Morning Trip" excursion might include:
- Dive 1: Blue Hole Reef at 8:30 AM (45 min, max 25m)
- Dive 2: Coral Gardens at 10:15 AM (50 min, max 18m)

---

### 5. Bookings

A **Booking** connects a diver to an excursion:

- **Diver**: Who is booked
- **Excursion**: Which trip they're on
- **Status**: Confirmed, Checked-In, Completed, Cancelled, No-Show
- **Price**: What they paid (locked at booking time)

**Booking Lifecycle**:
```
CONFIRMED → CHECKED_IN → COMPLETED
     ↓           ↓
 CANCELLED    NO_SHOW
```

**Price Locking**: When a booking is created, the price is captured and locked. Even if you later change your pricing, existing bookings keep their original price. This protects both you and your customers.

---

### 6. Excursion Types (Product Templates)

**Excursion Types** are templates that define your product offerings:

- **Name**: "Two-Tank Morning Dive", "Night Dive", "Discover Scuba"
- **Base Price**: Starting price for this type of trip
- **Number of Dives**: How many dives are included
- **Certification Requirements**: Minimum certification needed
- **Description**: Marketing description for customers

When you create a new excursion, you can base it on an excursion type, which pre-fills the pricing and requirements.

---

### 7. Pricing System

DiveOps includes a flexible pricing system:

**Base Pricing**: Set by excursion type
- Two-Tank Morning: $120
- Night Dive: $95
- Discover Scuba: $150

**Site Price Adjustments**: Add premiums or discounts for specific dive sites
- Blue Hole (premium site): +$25
- Local Reef (standard): +$0
- Training Pool: -$20

**How it calculates**:
```
Final Price = Base Price + Site Adjustment
Example: Night Dive at Blue Hole = $95 + $25 = $120
```

---

### 8. Eligibility & Decisioning

The system automatically determines if a diver can book a specific excursion:

**Checks performed**:
1. **Certification Level**: Does the diver have the required cert for the dive depth/type?
2. **Medical Clearance**: Is their medical form current?
3. **Age Requirements**: For certain dive types (e.g., Discover Scuba minimum age)
4. **Capacity**: Is there space available on the trip?

**Example decision flow**:
```
Diver: John Smith (Open Water certified, medical current)
Excursion: Deep Wall Dive (requires Advanced certification)
Result: NOT ELIGIBLE - "Requires Advanced Open Water certification"
```

This prevents booking errors and keeps your operation safe and compliant.

---

## Staff Portal Features

### Dashboard
- Today's scheduled excursions
- Upcoming trips requiring attention
- Recent booking activity
- Quick statistics (bookings this week, revenue, etc.)

### Diver Management
- Search and view diver profiles
- Add/edit diver information
- View certification history
- Check booking history
- Update medical clearance status

### Excursion Management
- Create new excursions from templates
- Edit excursion details
- Add/remove dives within an excursion
- View/manage bookings for each trip
- Start and complete excursions
- Cancel trips if needed

### Booking Operations
- Create new bookings
- Check in divers
- Mark completions
- Process cancellations
- Handle no-shows

### Site Management
- Add and edit dive sites
- Set depth limits and requirements
- Configure site-specific pricing adjustments
- Activate/deactivate sites

### Product Configuration
- Create excursion types (product templates)
- Set base pricing
- Configure certification requirements
- Define dive counts per product

---

## Audit Trail

Every significant action in DiveOps is logged:

**What's tracked**:
- Who did what, when
- Excursion created/updated/cancelled/started/completed
- Bookings created/checked-in/cancelled
- Diver profile changes
- Price changes (with before/after values)

**Why this matters**:
- Accountability: Know who made changes
- Dispute resolution: See exactly what happened
- Compliance: Maintain records for insurance/liability
- Business insights: Understand operational patterns

**Example audit entries**:
```
Jan 4, 2026 09:15 AM - Sarah (Staff) - excursion_created
  "Two-Tank Morning - Blue Hole" scheduled for Jan 6

Jan 4, 2026 10:30 AM - Sarah (Staff) - booking_created
  John Smith booked for Two-Tank Morning ($120)

Jan 6, 2026 07:45 AM - Mike (Staff) - diver_checked_in
  John Smith checked in for Two-Tank Morning

Jan 6, 2026 01:30 PM - Mike (Staff) - excursion_completed
  Two-Tank Morning completed (8 divers)
```

---

## Typical Daily Workflow

### Morning Setup (Before Trips)
1. Review today's excursions on Dashboard
2. Check all bookings are confirmed
3. Review diver certifications (system handles automatically)

### Trip Check-In
1. Open the excursion
2. Check in each diver as they arrive
3. System validates eligibility automatically
4. Note any changes (late arrivals, cancellations)

### During the Trip
1. Mark excursion as "Started"
2. Log actual dive times and depths (optional)
3. Note any incidents or issues

### After the Trip
1. Mark excursion as "Completed"
2. Record completed dives for each participant
3. Review trip for billing accuracy

### End of Day
1. Review completed excursions
2. Check tomorrow's schedule
3. Follow up on any outstanding issues

---

## Key Business Benefits

### Reduced Booking Errors
The eligibility system automatically prevents:
- Unqualified divers booking advanced trips
- Overbooking beyond capacity
- Expired medical clearances slipping through

### Price Protection
- Prices locked at booking time
- Clear audit trail of any changes
- Site-specific adjustments calculated automatically

### Operational Efficiency
- Quick diver lookup and history
- One-click check-in process
- Status tracking at a glance
- Less paperwork, more diving

### Compliance & Safety
- Certification tracking
- Medical clearance monitoring
- Complete audit trail

### Business Insights
- Booking trends and patterns
- Revenue tracking
- Popular sites and trip types
- Staff activity monitoring

---

## Glossary

| Term | Definition |
|------|------------|
| **Diver** | A customer who participates in dives |
| **Excursion** | A scheduled dive trip (may include multiple dives) |
| **Dive** | A single underwater dive within an excursion |
| **Dive Site** | A location where diving takes place |
| **Booking** | A reservation connecting a diver to an excursion |
| **Excursion Type** | A template/product defining a type of trip |
| **Check-In** | The process of confirming a diver's arrival for a trip |
| **Eligibility** | Whether a diver meets requirements for a specific trip |
| **Audit Log** | A record of all actions taken in the system |
| **Price Snapshot** | The locked price captured at booking time |

---

## Support

For technical support or questions about the system, contact your system administrator.

---

*DiveOps - Making dive shop management as smooth as a perfect descent.*
