# Dormitory Allocation System — Architecture

## 1. System Type

A Django-based modular monolith designed for:
- High-integrity allocation logic
- Strict consistency in capacity management
- Multi-role access control
- Audit-safe operations

---

## 2. Core Architecture Style

### Pattern
- Modular Monolith (not microservices)

### Reason
- Booking logic requires strong consistency
- Cross-module transactions are frequent
- Avoid distributed consistency problems early

---

## 3. Django App Structure

### Core Apps

- accounts
- profiles
- campuses
- housing
- roommates
- bookings
- delegates
- notifications
- audit

---

## 4. Dependency Rules (STRICT)

```text
accounts → all apps
profiles → campuses, roommates, bookings
campuses → housing, bookings
housing → bookings
roommates → bookings
bookings → notifications, audit
delegates → bookings
```

Rule
No circular dependencies allowed

All booking-related writes must pass through bookings app

---

## 5. Domain Architecture Layers

### 5.1 Identity Layer
**Modules**:
- accounts

**Responsible for**:
- authentication
- account activation
- role management

### 5.2 Institutional Layer
**Modules**:
- campuses
- profiles

**Responsible for**:
- campus structure
- academic assignment

### 5.3 Housing Layer
**Module**:
- housing

**Responsible for**:
- buildings
- floors
- rooms
- capacity rules

### 5.4 Social Layer
**Module**:
- roommates

**Responsible for**:
- roommate invitations
- grouping logic
- pre-booking relationships

### 5.5 Allocation Layer (CORE ENGINE)
**Module**:
- bookings

**Responsible for**:
- booking requests
- capacity reservation
- approval workflow
- assignment creation

### 5.6 Governance Layer
**Modules**:
- delegates
- audit

**Responsible for**:
- admin decisions
- delegate actions
- system enforcement

### 5.7 Notification Layer
**Module**:
- notifications 

**Responsible for**:
- event communication
- in-app notifications
- optional email/SMS integration

---

## 6. Core Data Flow Architecture

### 6.1 Booking Flow (High Level)
- Student selects room:
    - System validates eligibility
    - System checks capacity
    - System reserves slot (transactional)
- Booking created:
    - Optional occupant review triggered
    - Admin review triggered
- Final decision:
    - approved → assignment created
    - rejected → capacity released

### 6.2 Roommate Flow
- Student sends invitation:
    - System validates:
        - campus match
        - gender match 

**invitation limit**
- Invitation accepted/rejected

- Accepted members form group snapshot
- Group used at booking time only

### 6.3 Capacity Reservation Flow
Booking request received:
- System locks room row (transaction)
- Checks available capacity
    - If sufficient:
        - reserve slots
        - create booking
    - If insufficient:
        - reject immediately

---

## 7. State Machines (Core Systems)

### 7.1 Booking States
**Draft**
→ awaiting_student_confirmation
→ pending_occupant_review
→ pending_admin_review
→ approved
→ rejected
→ cancelled
→ expired
→ invalidated

### 7.2 Roommate Group States
**Forming**
→ active
→ locked
→ dissolved

### 7.3 Room Assignment States
**Pending**
→ assigned
→ invalidated

---

## 8. Concurrency Model
**Key Principle**
Booking is transactional and atomic.

**Rules**
- Room capacity is enforced inside database transactions
- Only one transaction can modify reservation state at a time
- First successful commit wins
- Conflicting requests fail immediately

**Lock Strategy**
- Row-level locking on Room
- Reservation happens before booking creation
- Prevents oversubscription

---

## 9. Capacity Model
**Room Fields**
- capacity
- approved_occupancy
- reserved_slots

**Constraint**
- approved_occupancy + reserved_slots ≤ capacity
**Behavior**
- Reservation reduces available slots immediately
- Approval finalizes occupancy
- Rejection releases reserved slots

---
## 10. System Guarantees
- No room over-allocation ever
- No double-booking under concurrency
- All booking decisions are traceable
- All actions are auditable
- No silent state mutation in roommate or booking systems

## 11. Design Philosophy
- Strong consistency over scalability shortcuts
- Transaction safety over performance shortcuts (MVP phase)
- Booking system is the single source of truth
- Everything else is supporting infrastructure