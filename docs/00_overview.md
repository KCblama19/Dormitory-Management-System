# Dormitory Allocation System — Overview

## 1. System Purpose

This system is a multi-campus university dormitory allocation platform designed to replace manual housing assignment with a structured, rule-driven, approval-based workflow.

It supports:
- Newly admitted students
- Continuing students
- Transferred students
- Remote onboarding before arrival
- Campus-scoped housing allocation
- Roommate coordination and grouping
- Admin-controlled approvals and assignments
- Delegate-assisted booking (optional layer)

This is not a reservation system.
It is a controlled allocation system with strict institutional rules.

---

## 2. Core Problems Solved

The system addresses:

- Manual room assignment inefficiency
- Overbooking and capacity conflicts
- Lack of structured roommate coordination
- Poor visibility into room availability
- Difficulty enforcing campus-specific rules
- Lack of auditability in housing decisions

---

## 3. Primary Users

### 3.1 Students
Students can:
- Log in after account provisioning and claim
- View rooms in assigned campus only
- See available slots and occupants
- Send and receive roommate invitations
- Form roommate groups (pre-booking stage)
- Submit booking requests (solo or group)
- Cancel pending requests
- Confirm booking decisions

---

### 3.2 Admin / Housing Management
Admins can:
- Create and manage users
- Assign campuses to students
- Configure campuses, buildings, floors, rooms
- Generate rooms automatically
- Approve or reject bookings
- Directly assign rooms
- Enforce capacity and policy rules
- Invalidate bookings on campus changes

---

### 3.3 Delegates (Optional Role)
Delegates can:
- Assist students with booking
- Submit booking requests on behalf of students within scope

Delegates cannot:
- Approve bookings
- Override admin decisions
- Act outside assigned scope

---

## 4. Core Domain Rules

### 4.1 Campus Rule
- Students are assigned exactly one campus
- Students cannot choose campuses
- Campus changes are admin-controlled only

---

### 4.2 Eligibility Rule
A student can only book if:
- Admission is approved
- Student account is active
- Campus is assigned

---

### 4.3 Room Structure
- Rooms are the core allocation unit
- Capacity is defined at room level
- Beds are conceptual, not independent entities

Typical capacities(based on beds):
- 2 (international student dorms)
- 4–8 (standard dorms)

---

### 4.4 Gender Rule
- Rooms enforce same-gender assignment by default
- Floors or buildings may override restrictions

---

### 4.5 Booking Model
- All bookings are approval-based
- No instant assignment
- Admin retains final authority

---

### 4.6 Capacity Invariant
At all times:

- approved_occupancy + reserved_slots ≤ room_capacity

This invariant is never violated.

---

### 4.7 Campus Change Rule
If a campus changes:
- All active bookings are invalidated
- Assignments are removed
- Students must rebook

---

## 5. Core System Characteristics

- Monolithic Django backend with modular apps
- Strict transactional booking logic
- Event-driven notifications (in-app first)
- Full audit trail of all operations
- Strong consistency over eventual consistency
- Capacity-first allocation model

---

## 6. High-Level Modules

- accounts (authentication + identity)
- profiles (student/staff data)
- campuses (institution structure)
- housing (rooms, buildings, floors)
- roommates (invites + grouping)
- bookings (core allocation engine)
- delegates (on-behalf actions)
- notifications (event alerts)
- audit (system history)

---

## 7. Key System Philosophy

- Capacity is absolute, not advisory
- Booking is a controlled transaction, not a request queue
- Room allocation is the system’s source of truth
- Everything else (roommates, delegates, preferences) feeds into booking