# Dorm System Project Context

This document is a source-grounded handoff for another AI developer continuing work on this repository. It describes the architecture that exists in the workspace, distinguishes implemented code from planned or incomplete code, and records important relationships between models, QuerySets, services, forms, views, URLs, policies, and tests.

No functionality should be inferred beyond the code and design documents described here.

## Status vocabulary

- **IMPLEMENTED**: The component exists and is wired or usable in the current repository.
- **PARTIALLY IMPLEMENTED**: The component exists, but is incomplete, inconsistent, contains known defects, or is not fully wired.
- **PLANNED**: The design documentation describes the component, but implementation is absent or inactive.
- **UNKNOWN**: The repository does not provide enough evidence to establish the behavior.

---

# 1. Project purpose

## IMPLEMENTED / PARTIALLY IMPLEMENTED

This is intended to be a Django modular monolith for university dormitory management and allocation.

The implemented foundation covers:

- Custom user identity and role data.
- Student and staff profiles.
- Academic years, programs, degrees, majors, departments, enrollments, and campus assignments.
- University and campus structure.
- Dormitory accommodation hierarchy:

```text
University
  -> Campus
    -> Building
      -> Floor
        -> Room
          -> Bed
```

- Account login and account-claim workflow.
- Domain-oriented service classes.
- Reusable QuerySets/managers.
- Policy classes for authorization decisions.

The repository's design documents describe a larger controlled allocation system involving booking requests, room assignments, roommate groups, delegates, notifications, and audit history. Those systems are not currently implemented or activated in Django.

The primary architectural goal is strong consistency for accommodation and future allocation operations. The code favors transactional services, explicit state transitions, database constraints, and separation of read-side QuerySets from write-side services.

Relevant documentation:

- [`docs/00_overview.md`](./00_overview.md)
- [`docs/01_architecture.md`](./01_architecture.md)
- [`docs/04_data_flow.md`](./04_data_flow.md)
- [`docs/05_state_machines.md`](./05_state_machines.md)
- [`docs/07_permission_model.md`](./07_permission_model.md)
- [`docs/09_edge_cases.md`](./09_edge_cases.md)

---

# 2. Complete architecture

## IMPLEMENTED

The project is structured as a Django modular monolith.

The active high-level flow is:

```text
config/settings.py
    -> active Django apps
    -> config/urls.py
        -> accounts URLs/views

accounts
    -> User
    -> authentication
    -> account claim

profiles
    -> Student and Staff
    -> academic records
    -> services and QuerySets

university
    -> University
    -> UniversityService

accommodation
    -> Campus, Building, Floor, Room, Bed, BedConfiguration
    -> accommodation QuerySets
    -> accommodation services

core
    -> timestamps
    -> Gender
    -> domain exceptions
    -> shared forms
    -> authorization policies
```

The architecture deliberately separates concerns:

```text
Models
    local persistence and model-level invariants

QuerySets/managers
    reusable database reads, filters, search, eager loading

Services
    transactional business operations and state transitions

Policies
    authorization decisions only

Forms
    input parsing and user-facing validation

Views
    HTTP/session/form orchestration
```

This separation is explicitly documented in:

- [`apps/core/forms.py`](../apps/core/forms.py), `OperationForm`
- [`apps/core/policies/base.py`](../apps/core/policies/base.py), `BasePolicy`
- The docstrings in the student, staff, and accommodation QuerySets.

## PARTIALLY IMPLEMENTED

The repository contains a number of architecture defects that should be treated as existing technical debt rather than silently corrected during unrelated work:

- Some account files contain literal `******` placeholders and are not valid Python as written.
- Several old references use `UserType` or `role`, while the current model defines `AccountType` and `account_type`.
- Account status values are inconsistently treated as uppercase model choices and lowercase strings.
- Several QuerySet and service methods contain incorrect field names or method calls.
- Active URLs expose only account flows; most domain services have no HTTP views.
- Tests are placeholders.

## PLANNED

The design documents describe future modules for:

- Bookings/allocation.
- Roommate invitations and groups.
- Delegate-assisted actions.
- Notifications.
- Audit history.

The intended dependency direction in [`docs/01_architecture.md`](./01_architecture.md) is:

```text
accounts -> all apps
profiles -> campuses, roommates, bookings
campuses -> housing, bookings
housing -> bookings
roommates -> bookings
bookings -> notifications, audit
delegates -> bookings
```

The actual repository names currently use `university` and `accommodation` rather than the conceptual `campuses` and `housing` names in that design document.

---

# 3. Django app structure

## Project package

### `config`

Path: [`config/`](../config/)

- [`config/settings.py`](../config/settings.py)
  - SQLite database at `db.sqlite3`.
  - `AUTH_USER_MODEL = "accounts.User"`.
  - Active apps listed below.
  - Custom authentication backend configured.
- [`config/urls.py`](../config/urls.py)
  - Landing page.
  - `/accounts/`.
  - `/admin/`.
- [`config/views.py`](../config/views.py)
  - `LandingPageView`.
- [`config/asgi.py`](../config/asgi.py)
- [`config/wsgi.py`](../config/wsgi.py)

### Active apps in `INSTALLED_APPS`

1. `apps.core`
2. `apps.accounts`
3. `apps.profiles`
4. `apps.university`
5. `apps.accommodation`

### Present but disabled

These are not in `INSTALLED_APPS`:

- [`apps/bookings/`](../apps/bookings/)
- [`apps/roomates/`](../apps/roomates/)
- [`admin_panel/`](../admin_panel/)

Their current models/views/tests are placeholders or scaffolding.

## `apps.core`

Path: [`apps/core/`](../apps/core/)

Responsibilities:

- Abstract timestamp model.
- Gender reference model.
- Shared domain exceptions.
- Shared form mixins.
- Authorization policy base and domain policies.

Important files:

- [`apps/core/abstract_models/timestamp_models.py`](../apps/core/abstract_models/timestamp_models.py), `TimeStampModel`
- [`apps/core/models/gender_model.py`](../apps/core/models/gender_model.py), `Gender`
- [`apps/core/exceptions.py`](../apps/core/exceptions.py)
- [`apps/core/forms.py`](../apps/core/forms.py), `StyledFormMixin`, `OperationForm`
- [`apps/core/policies/`](../apps/core/policies/)

## `apps.accounts`

Path: [`apps/accounts/`](../apps/accounts/)

Responsibilities:

- Custom user model.
- User creation manager.
- Multi-identifier authentication.
- Login/logout.
- Account claiming.
- Django admin integration.

Important files:

- [`apps/accounts/models.py`](../apps/accounts/models.py), `User`
- [`apps/accounts/manager.py`](../apps/accounts/manager.py), `UserManager`
- [`apps/accounts/backends/auth_backends.py`](../apps/accounts/backends/auth_backends.py), `MultiIdentifierBackend`
- [`apps/accounts/services/claim_service.py`](../apps/accounts/services/claim_service.py), `ClaimService`
- [`apps/accounts/views/views.py`](../apps/accounts/views/views.py)
- [`apps/accounts/views/claim_views.py`](../apps/accounts/views/claim_views.py)
- [`apps/accounts/urls.py`](../apps/accounts/urls.py)

## `apps.profiles`

Path: [`apps/profiles/`](../apps/profiles/)

Responsibilities:

- Student profiles.
- Staff profiles.
- Academic records.
- Student campus assignment.
- Student/staff services and QuerySets.

The app has nested model modules. [`apps/profiles/apps.py`](../apps/profiles/apps.py), `ProfilesConfig.ready()`, imports:

```python
import apps.profiles.student.models
import apps.profiles.staff.models
```

This is used to force model package imports during application startup.

## `apps.university`

Path: [`apps/university/`](../apps/university/)

Responsibilities:

- `University` model.
- `UniversityQuerySet`.
- `UniversityService`.
- `UniversityForm`.

## `apps.accommodation`

Path: [`apps/accommodation/`](../apps/accommodation/)

Responsibilities:

- University campus.
- Dormitory buildings.
- Floors.
- Rooms.
- Beds.
- Reusable bed configurations.
- Physical accommodation migration.

Important subdirectories:

- [`apps/accommodation/models/`](../apps/accommodation/models/)
- [`apps/accommodation/models/managers/`](../apps/accommodation/models/managers/)
- [`apps/accommodation/services/`](../apps/accommodation/services/)
- [`apps/accommodation/forms/`](../apps/accommodation/forms/)

---

# 4. Domain model

## Identity domain

### `User`

File: [`apps/accounts/models.py`](../apps/accounts/models.py)  
Class: `User`

Responsibility:

- Central authenticated identity.
- Stores institutional identifiers.
- Stores account type and account status.
- Stores claim-flow date of birth and claimed state.

Important fields:

```python
id = models.UUIDField(primary_key=True, default=uuid.uuid4)
username = models.CharField(..., unique=True, blank=True, null=True)
student_id = models.CharField(..., unique=True, null=True, blank=True)
staff_id = models.CharField(..., unique=True, null=True, blank=True)
email = models.EmailField(..., unique=True, null=True, blank=True)
account_type = models.CharField(choices=AccountType.choices)
accountStatus = models.CharField(choices=AccountStatus.choices)
is_claimed = models.BooleanField(default=False)
date_of_birth = models.DateField(null=True, blank=True)
```

`User.clean()` requires:

- Students to have a `student_id`.
- Staff/admin users to have either `staff_id` or email.

`User.save()` calls `full_clean()` before saving in ordinary saves.

### `Student`

File: [`apps/profiles/student/models/student_models.py`](../apps/profiles/student/models/student_models.py)  
Class: `Student`

Responsibility:

- Student personal profile.
- Admission status.
- Housing eligibility.
- Gender and nationality.
- Access to current enrollment and campus assignment.

Important properties:

- `full_name`
- `current_enrollment`
- `current_campus_assignment`
- `current_campus`
- `year_of_study`
- `study_stage`
- `can_book`

`Student.can_book()` only checks admission acceptance and housing eligibility. The model docstring states that final booking authorization must eventually include account, campus, booking-period, and allocation rules.

### `Staff`

File: [`apps/profiles/staff/models/staff_models.py`](../apps/profiles/staff/models/staff_models.py)  
Class: `Staff`

Responsibility:

- Staff-specific profile.
- Building assignment.
- Building-level staff role and status.

Roles:

- `BUILDING_MANAGER`
- `BUILDING_STAFF`

Statuses:

- `ACTIVE`
- `INACTIVE`
- `SUSPENDED`

The database constraint `unique_active_building_manager` allows only one active building manager per building.

## Academic domain

### `AcademicYear`

File: [`apps/profiles/student/models/academic_year.py`](../apps/profiles/student/models/academic_year.py)  
Class: `AcademicYear`

Stores:

- Name such as `2026/2027`.
- Start and end dates.
- Active state.
- Current-year state.

Database constraint: only one row may have `is_current=True`.

### `Department`

File: [`apps/profiles/student/models/department.py`](../apps/profiles/student/models/department.py)  
Class: `Department`

Stores a department name and unique code.

### `Major`

File: [`apps/profiles/student/models/major.py`](../apps/profiles/student/models/major.py)  
Class: `Major`

Belongs to one `Department`.

Database constraint: unique major name within a department.

### `Degree`

File: [`apps/profiles/student/models/degree.py`](../apps/profiles/student/models/degree.py)  
Class: `Degree`

Represents a qualification and academic level:

- Undergraduate: `UG`
- Postgraduate: `PG`
- Doctorate: `DOC`

### `Program`

File: [`apps/profiles/student/models/program.py`](../apps/profiles/student/models/program.py)  
Class: `Program`

Represents the actual curriculum/program a student follows.

Program types include:

- Degree.
- Language.
- Exchange.
- Visiting.
- Short-term.
- Other.

Degree programs require a degree and major. Language programs reject degree and major references.

### `StudentEnrollment`

File: [`apps/profiles/student/models/enrollment.py`](../apps/profiles/student/models/enrollment.py)  
Class: `StudentEnrollment`

Connects:

```text
Student + Program + AcademicYear
```

Tracks:

- Primary status.
- Year of study.
- Enrollment status.
- Start/end dates.
- Expected graduation date.

Only one primary active enrollment is allowed per student and academic year.

### `StudentAssignCampus`

File: [`apps/profiles/student/models/campus_assignment.py`](../apps/profiles/student/models/campus_assignment.py)  
Class: `StudentAssignCampus`

Connects:

```text
Student + Campus + AcademicYear
```

Tracks:

- Active/ended/transferred state.
- Start/end dates.
- Arrival date.
- Transfer reason.

Only one active campus assignment is allowed per student and academic year.

## Institutional and accommodation domain

### `University`

File: [`apps/university/models.py`](../apps/university/models.py)  
Class: `University`

Stores university code, name, website, and active state.

### `Campus`

File: [`apps/accommodation/models/campus/campus_model.py`](../apps/accommodation/models/campus/campus_model.py)  
Class: `Campus`

Belongs to a `University`.

Stores:

- Name/code unique within a university.
- Address.
- City/province/country.
- Active state.

### `Building`

File: [`apps/accommodation/models/building/building_model.py`](../apps/accommodation/models/building/building_model.py)  
Class: `Building`

Belongs to a `Campus`.

Stores:

- Building number/name/code.
- Student population policy.
- Gender policy.
- Maximum floor count.
- Default bed configuration.
- Active state.

### `Floor`

File: [`apps/accommodation/models/floor/floor_model.py`](../apps/accommodation/models/floor/floor_model.py)  
Class: `Floor`

Belongs to a `Building`.

Stores:

- Floor number.
- Maximum rooms.
- Optional gender configuration.
- Optional bed configuration override.
- Restriction note/state.
- Operational status.

### `Room`

File: [`apps/accommodation/models/room/room_model.py`](../apps/accommodation/models/room/room_model.py)  
Class: `Room`

Belongs to a `Floor`.

Stores:

- Position within the floor.
- Optional bed configuration override.

Derives:

- Room number.
- Full room code.
- Current physical capacity from beds.
- Occupancy/available beds through the future assignment relationship.

### `BedConfiguration`

File: [`apps/accommodation/models/bed/bed_configuration.py`](../apps/accommodation/models/bed/bed_configuration.py)  
Class: `BedConfiguration`

Reusable intended bed count and configuration metadata.

The effective configuration is inherited in this order:

```text
Room override
    -> Floor override
        -> Building default
```

### `Bed`

File: [`apps/accommodation/models/bed/bed_model.py`](../apps/accommodation/models/bed/bed_model.py)  
Class: `Bed`

Belongs to a `Room`.

Statuses:

- `AVAILABLE`
- `MAINTENANCE`
- `OUT_OF_SERVICE`

Bed position is unique within a room and must be at least one.

The model intentionally does not store a student directly. `is_occupied` expects an `assignments` reverse relation from a future accommodation assignment model.

---

# 5. Model relationships

## Implemented relationship graph

```text
User
├── 1:1 Student
└── 1:1 Staff

University
└── 1:N Campus
    └── 1:N Building
        ├── 1:N Staff
        └── 1:N Floor
            └── 1:N Room
                └── 1:N Bed

Building
└── N:1 default BedConfiguration

Floor
└── N:1 optional BedConfiguration override

Room
└── N:1 optional BedConfiguration override

Student
├── 1:N StudentEnrollment
│   ├── N:1 Program
│   │   ├── N:1 Degree
│   │   └── N:1 Major
│   │       └── N:1 Department
│   └── N:1 AcademicYear
└── 1:N StudentAssignCampus
    ├── N:1 Campus
    └── N:1 AcademicYear
```

## Relationship behavior

- `Student.user`: one-to-one, `CASCADE`.
- `Staff.user`: one-to-one, `PROTECT`.
- Student profile deletes cascade from its user.
- Staff profile deletion is protected.
- Accommodation hierarchy foreign keys generally use `PROTECT` to preserve institutional structure.
- Student enrollment and campus assignment delete student-owned records on student deletion.
- Academic records protect referenced programs and academic years.

## Important missing relationship

**PARTIALLY IMPLEMENTED / PLANNED:** `Bed.is_occupied` expects `bed.assignments`, but no active accommodation assignment model was found. Therefore occupancy-dependent code is not complete.

---

# 6. QuerySets and managers

## Architectural pattern

Models attach custom QuerySets with `as_manager()`:

```python
objects = SomeQuerySet.as_manager()
```

The intended division is:

- QuerySets: reusable read-side predicates, filters, searches, and eager loading.
- Services: mutations, transactions, lifecycle changes, and cross-model business rules.

QuerySets do not intentionally perform business mutations.

## Student QuerySet

File: [`apps/profiles/student/models/managers/manager.py`](../apps/profiles/student/models/managers/manager.py)  
Class: `StudentQueryset`

Methods:

- `with_user()`
- `active()`
- `admitted()`
- `eligible()`
- `ineligible()`
- `pending_eligibility()`
- `suspended()`
- `with_active_enrollment()`
- `with_active_campus()`
- `ready_for_accommodation()`
- `for_campus(campus)`
- `for_academic_year(academic_year)`
- `search(term)`

The intended readiness composition is:

```python
Student.objects.ready_for_accommodation()
```

with these conditions:

```text
active user account
accepted admission
eligible for accommodation
active enrollment
active campus assignment
```

**PARTIALLY IMPLEMENTED:** The current method contains defects, including a missing call to `with_active_campus()` and relationship names that do not match the model `related_name`s.

## Academic QuerySets

### `AcademicYearQueryset`

File: [`apps/profiles/student/models/managers/academicYearQuerySet.py`](../apps/profiles/student/models/managers/academicYearQuerySet.py)

Methods:

- `active()`
- `current()`
- `past()`
- `search(term)`

### `EnrollmentQuerySet`

File: [`apps/profiles/student/models/managers/enrollmentQuerySet.py`](../apps/profiles/student/models/managers/enrollmentQuerySet.py)

Methods:

- `active()`
- `completed()`
- `withdrawn()`
- `suspended()`
- `deferred()`
- `primary()`
- `primary_active()`
- `for_student(student)`
- `for_academic_year(academic_year)`
- `for_program(program)`

**PARTIALLY IMPLEMENTED:** `primary_active()` is written as `filter(self.active().primary())`, which is not the intended QuerySet composition. The intended form is conceptually `.active().primary()`.

### `StudentAssignCampusQuerySet`

File: [`apps/profiles/student/models/managers/campusAssignmentQuerySet.py`](../apps/profiles/student/models/managers/campusAssignmentQuerySet.py)

Methods:

- `active()`
- `ended()`
- `transferred()`
- `for_student(student)`
- `for_campus(campus)`
- `for_academic_year(academic_year)`
- `current()`

`current()` is deliberately an alias for active assignments; transition authorization remains in the service layer.

### Other academic QuerySets

- [`DegreeQuerySet`](../apps/profiles/student/models/managers/degreeQuerySet.py)
  - `active()`, `undergraduate()`, `postgraduate()`, `doctoral()`, `search()`.
- [`DepartmentQuerySet`](../apps/profiles/student/models/managers/departmentQuerySet.py)
  - `active()`, `search()`.
- [`MajorQuerySet`](../apps/profiles/student/models/managers/majorQuerySet.py)
  - `active()`, `for_department()`, `search()`.
- [`ProgramQuerySet`](../apps/profiles/student/models/managers/programQuerySet.py)
  - Program-type filters, language filters, `active()`, `search()`.

**PARTIALLY IMPLEMENTED:** `DegreeQuerySet.postgraduate()` and `.doctoral()` currently filter against `True` rather than the expected academic-level values.

## Staff QuerySet

File: [`apps/profiles/staff/models/managers/staffQuerySet.py`](../apps/profiles/staff/models/managers/staffQuerySet.py)  
Class: `StaffQuerySet`

Methods:

- `active()`
- `inactive()`
- `managers()`
- `building_staff()`
- `active_managers()`
- `active_building_staff()`
- `for_building(building)`
- `active_for_building(building)`
- `managers_for_building(building)`
- `staff_for_building(building)`
- `with_user()`
- `with_building()`
- `with_user_and_building()`
- `search(term)`

These QuerySets are used by [`StaffService`](../apps/profiles/staff/services/staff_service.py) and by the authentication/claim code.

**PARTIALLY IMPLEMENTED:** `with_user()` passes `None` to `select_related()`.

## Accommodation QuerySets

### `CampusQuerySet`

File: [`apps/accommodation/models/managers/campusQuerySet.py`](../apps/accommodation/models/managers/campusQuerySet.py)

- `active()`
- `inactive()`
- `for_university()`
- `search()`
- `with_university()`

### `BuildingQuerySet`

File: [`apps/accommodation/models/managers/buildingQuerySet.py`](../apps/accommodation/models/managers/buildingQuerySet.py)

- `with_campus()`
- `with_configuration()`
- `with_staff()`
- `active()`
- `inactive()`
- `for_campus()`
- Population filters.
- Gender-policy filters.
- `search()`

### `FloorQuerySet`

File: [`apps/accommodation/models/managers/floorQuerySet.py`](../apps/accommodation/models/managers/floorQuerySet.py)

- `active()`
- `inactive()`
- `maintenance()`
- `restricted()`
- `unrestricted()`
- `for_building()`
- `male()`
- `female()`
- `mixed()`
- `with_building()`
- `with_configuration()`

### `RoomQuerySet`

File: [`apps/accommodation/models/managers/roomQuerySet.py`](../apps/accommodation/models/managers/roomQuerySet.py)

- `for_floor()`
- `for_building()`
- `with_floor()`
- `with_configuration()`
- `with_beds()`
- `search()`

### `BedQuerySet`

File: [`apps/accommodation/models/managers/bedQuerySet.py`](../apps/accommodation/models/managers/bedQuerySet.py)

- `available()`
- `maintenance()`
- `out_of_service()`
- `operational()`
- `for_room()`
- `for_floor()`
- `for_building()`
- `with_room()`
- `with_hierarchy()`

### `BedConfigurationQuerySet`

File: [`apps/accommodation/models/managers/bedConfigQuerySet.py`](../apps/accommodation/models/managers/bedConfigQuerySet.py)

- `active()`
- `inactive()`
- `for_bed_count()`
- `with_bed_count_at_least()`
- `with_bed_count_at_most()`
- `search()`

---

# 7. Service layer

## Service conventions

Most services:

- Are class-based namespaces with static methods.
- Use `@transaction.atomic` for mutations.
- Validate domain conditions before mutation.
- Call `full_clean()` before saving.
- Raise domain-specific validation/conflict exceptions.
- Return the mutated model or an operation result.

Services are intended to be the write-side entry point. Views/forms should not directly implement lifecycle transitions.

## Accounts

### `ClaimService`

File: [`apps/accounts/services/claim_service.py`](../apps/accounts/services/claim_service.py)  
Class: `ClaimService`

Methods:

- `find_claim_user(identifier)`
  - Resolves through `Student.student_id` and `Staff.staff_id`.
- `verify_user_credentials(identifier, temp_password)`
  - Rejects missing, claimed, password-invalid, or non-active accounts.
- `verify_user_DOB(user, date_of_birth)`
  - Verifies the unclaimed user's date of birth.
- `update_user_password(user, new_password)`
  - Transactional.
  - Locks the user row with `select_for_update()`.
  - Sets password.
  - Marks the account claimed and active.

## Student services

### `StudentService`

File: [`apps/profiles/student/services/student_service.py`](../apps/profiles/student/services/student_service.py)  
Class: `StudentService`

Responsibilities:

- Create a student profile for a student-type user.
- Accept/reject/withdraw admission.
- Set housing eligibility.
- Activate/deactivate/suspend/restore the account.
- Query a student ready for accommodation.

### `AcademicYearService`

File: [`apps/profiles/student/services/academic_year_service.py`](../apps/profiles/student/services/academic_year_service.py)  
Class: `AcademicYearService`

Responsibilities:

- `create()`
- `activate()`
- `deactivate()`
- `set_current()`

`set_current()` clears any existing current year before setting the target current, inside a transaction.

### `EnrollmentService`

File: [`apps/profiles/student/services/enrollment_service.py`](../apps/profiles/student/services/enrollment_service.py)  
Class: `EnrollmentService`

Responsibilities:

- Create enrollment.
- Activate, complete, withdraw, suspend, or defer enrollment.
- Set primary enrollment.

The service uses QuerySet predicates such as `for_student()`, `for_academic_year()`, `active()`, `primary()`, and `primary_active()`.

### `CampusAssignmentService`

File: [`apps/profiles/student/services/campus_assignment_service.py`](../apps/profiles/student/services/campus_assignment_service.py)  
Class: `CampusAssignmentService`

Responsibilities:

- Initial student assignment.
- Campus transfer.
- Ending assignment.

Transfer locks the current assignment with `select_for_update()`, closes it, and creates the new active assignment.

## Staff services

### `StaffService`

File: [`apps/profiles/staff/services/staff_service.py`](../apps/profiles/staff/services/staff_service.py)  
Class: `StaffService`

Responsibilities:

- Create staff profile.
- Assign staff to a building.
- Change role.
- Activate/deactivate staff.
- Transfer staff.

The manager uniqueness rule is checked through `Staff.objects.managers_for_building()`, and the database also has a conditional unique constraint.

## University service

### `UniversityService`

File: [`apps/university/service.py`](../apps/university/service.py)  
Class: `UniversityService`

Responsibilities:

- Create university.
- Activate/deactivate university.

**PARTIALLY IMPLEMENTED:** The service contains an assignment typo in activation (`is_active = True,`) and the deactivate method is not declared static in the same style as the other methods.

## Accommodation services

### `CampusService`

File: [`apps/accommodation/services/campus_service.py`](../apps/accommodation/services/campus_service.py)  
Class: `CampusService`

Responsibilities:

- Create, activate, and deactivate campuses.
- Prevent campuses under inactive universities.
- Prevent deactivation while active buildings exist.

**PARTIALLY IMPLEMENTED:** Duplicate checks use `.exist()` and appear logically inverted.

### `BuildingService`

File: [`apps/accommodation/services/building_service.py`](../apps/accommodation/services/building_service.py)  
Class: `BuildingService`

Responsibilities:

- Create/update buildings.
- Activate/deactivate buildings.
- Change gender policy.
- Change student population.
- Change default bed configuration.

It prevents invalid capacity/policy changes and inactive configuration references.

### `FloorService`

File: [`apps/accommodation/services/floor_service.py`](../apps/accommodation/services/floor_service.py)  
Class: `FloorService`

Responsibilities:

- Allocate the next available floor number.
- Create/update floors.
- Activate/deactivate floors.
- Set maintenance state.
- Set/remove restrictions.
- Set/remove bed-configuration override.

**PARTIALLY IMPLEMENTED:** The file contains known defects including incorrect method names/field arguments and missing exception imports.

### `RoomService`

File: [`apps/accommodation/services/room_service.py`](../apps/accommodation/services/room_service.py)  
Class: `RoomService`

Responsibilities:

- Allocate the next available room position.
- Create/update rooms.
- Set/remove room bed configuration override.
- Prevent configuration reduction below current physical bed count.

### `BedService`

File: [`apps/accommodation/services/bed_service.py`](../apps/accommodation/services/bed_service.py)  
Class: `BedService`

Responsibilities:

- Create beds within effective configuration.
- Change bed positions.
- Set available/maintenance/out-of-service.
- Restore out-of-service beds.

An occupied bed cannot be placed out of service.

### `BedConfigurationService`

File: [`apps/accommodation/services/bed_config_service.py`](../apps/accommodation/services/bed_config_service.py)  
Class: `BedConfigurationService`

Responsibilities:

- Create/update configuration.
- Activate/deactivate configuration.

It prevents deactivation while the configuration is referenced by a building default, floor override, or room override.

### `AccommodationMigrationService`

File: [`apps/accommodation/services/acommodation_migration_service.py`](../apps/accommodation/services/acommodation_migration_service.py)  
Class: `AccommodationMigrationService`

Responsibilities:

- Inspect room configuration changes.
- Expand physical beds.
- Prepare a reduction.
- Apply a reduction.
- Reconfigure a room.

Reductions preserve records by moving excess beds to `OUT_OF_SERVICE` rather than deleting them.

---

# 8. Business rules

## Identity and account rules

Implemented or intended in code:

- No public registration flow is exposed.
- Accounts are provisioned by administrators or management commands.
- Students require a student ID.
- Staff/admin require staff ID or email.
- Account claiming requires institutional identifier, temporary password, date of birth, and a new password.
- Claimed accounts cannot be claimed again.

## Student rules

- Admission status is separate from housing eligibility.
- A student must be accepted and housing-eligible for basic accommodation readiness.
- A student may have multiple historical enrollments, but only one primary active enrollment per academic year.
- A student may have assignment history, but only one active campus assignment per academic year.

## Academic rules

- Academic-year end date must be after start date.
- Only one academic year may be current.
- Degree programs require degree and major.
- Language programs should not have degree or major.
- Enrollment end and graduation dates must follow the enrollment start date.
- Language programs normally do not use year of study.
- Non-active enrollment cannot be primary.

## Accommodation rules

- Campus must belong to an active university for creation/activation.
- Building must belong to an active campus.
- Building maximum floors must be at least one.
- Building default configuration must be active.
- Floor numbers are unique within buildings.
- Room positions are unique within floors.
- Bed positions are unique within rooms.
- Bed positions cannot exceed effective room configuration.
- Configuration inheritance is room → floor → building.
- Room/floor/building structural changes are separated from operational status changes.
- A building cannot be deactivated while it has active floors.
- A floor cannot be deactivated while available beds remain, according to the intended service rule.
- A bed cannot be placed out of service while occupied.
- Capacity reduction requires explicit excess-bed selection.
- Physical beds are not deleted during configuration reduction.

## Future allocation rules

**PLANNED:** The design documents describe:

- Campus-scoped student housing.
- Approval-based bookings.
- Capacity reservation and occupancy invariants.
- Roommate grouping.
- Campus-change invalidation of assignments/bookings.
- Auditability.

No active booking or assignment implementation was found.

---

# 9. Authentication

## Settings

File: [`config/settings.py`](../config/settings.py)

```python
AUTH_USER_MODEL = "accounts.User"

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "accounts.backends.auth_backends.MultiIdentifierBackend",
]
```

## Login

File: [`apps/accounts/forms/login_form.py`](../apps/accounts/forms/login_form.py)  
Class: `LoginForm`

Accepts:

- `identifier`
- `password`

The form passes the identifier as Django's `username` argument to `authenticate()`.

File: [`apps/accounts/views/views.py`](../apps/accounts/views/views.py)  
Class: `LogInView`

- Injects the request into the form.
- Redirects already-authenticated users to the dashboard.
- Calls `login()` after successful form authentication.

## Multi-identifier backend

File: [`apps/accounts/backends/auth_backends.py`](../apps/accounts/backends/auth_backends.py)  
Class: `MultiIdentifierBackend`

Intended supported identifiers:

- Student ID.
- Staff ID.
- Email.
- Phone number.

**PARTIALLY IMPLEMENTED:** The file contains literal placeholder syntax and also has a local variable issue in the fallback lookup. It should be treated as intended architecture, not a reliable working implementation.

## Claim flow

Routes and views are described in the URLs section below. The core implementation is `ClaimService`.

---

# 10. User roles

## Account roles

Defined in `User.AccountType`:

- `STUDENT`
- `STAFF`
- `ADMIN`

The intended system-level distinction is:

```text
ADMIN
    global/system-wide authority

STAFF
    building-scoped operational authority

STUDENT
    own profile, academic visibility, and future housing actions
```

## Staff profile roles

Defined in `Staff.Role`:

- `BUILDING_MANAGER`
- `BUILDING_STAFF`

The building manager has configuration authority over the assigned building. Building staff have operational authority but not higher-level structural configuration authority.

## Statuses

Account status:

- `ACTIVE`
- `LOCKED`
- `SUSPENDED`

Staff status:

- `ACTIVE`
- `INACTIVE`
- `SUSPENDED`

Student admission status:

- `PENDING`
- `ACCEPTED`
- `WITHDRAWN`
- `REJECTED`

Student housing eligibility:

- `PENDING`
- `ELIGIBLE`
- `INELIGIBLE`
- `SUSPENDED`

---

# 11. Authorization rules

## Policy architecture

Policies are pure authorization helpers. They should:

- Answer whether an actor may perform an operation.
- Avoid database mutation.
- Avoid form validation.
- Avoid HTTP handling.
- Avoid implementing domain operations.

This is stated in [`BasePolicy`](../apps/core/policies/base.py).

## BasePolicy

File: [`apps/core/policies/base.py`](../apps/core/policies/base.py)  
Class: `BasePolicy`

Important methods:

- `is_authenticated(actor)`
- `is_active_account(actor)`
- `is_global_admin(actor)`
- `is_student_account(actor)`
- `is_staff_account(actor)`
- `is_building_manager(actor)`
- `is_building_staff(actor)`
- `managed_building(actor)`
- `manages_building(actor, building)`
- `works_in_building(actor, building)`

## AccountPolicy

File: [`apps/core/policies/account_policy.py`](../apps/core/policies/account_policy.py)  
Class: `AccountPolicy`

Admin has system-wide user account-management authority. Claim verification itself remains in `ClaimService`.

## StudentPolicy

File: [`apps/core/policies/student_policy.py`](../apps/core/policies/student_policy.py)  
Class: `StudentPolicy`

- Global admin can manage students.
- Students can view/update their own profile.
- Admission, eligibility, and student-account lifecycle operations are admin-only.
- Building staff/managers do not receive student-management scope until a future student-to-building assignment exists.

The policy explicitly refuses to infer building scope from campus assignment because campus and building are different concepts.

## StaffPolicy

File: [`apps/core/policies/staff_policy.py`](../apps/core/policies/staff_policy.py)  
Class: `StaffPolicy`

- Global admin can manage all staff.
- Building managers can manage staff in their building.
- Building staff do not manage staff records.
- Transfers by managers must remain within the manager's building.
- Role changes are restricted to managers/admins.

## AcademicPolicy

File: [`apps/core/policies/academic_policy.py`](../apps/core/policies/academic_policy.py)  
Class: `AcademicPolicy`

- Academic-year administration is admin-only.
- Enrollment and campus-assignment administration is admin-only.
- Students may view their own enrollment and campus assignment.
- Staff roles do not receive academic-record administration authority.

## AccommodationPolicy

File: [`apps/core/policies/accommodation_policy.py`](../apps/core/policies/accommodation_policy.py)  
Class: `AccommodationPolicy`

Summary:

```text
University/Campus creation:
    Admin only

Building creation:
    Admin only

Building configuration:
    Admin or building manager for that building

Floor/room structural creation:
    Admin or building manager

Floor/room/bed operational management:
    Admin, building manager, or building staff depending on operation

Bed position and physical configuration:
    Admin or building manager
```

---

# 12. Forms

## Shared form infrastructure

File: [`apps/core/forms.py`](../apps/core/forms.py)

### `StyledFormMixin`

Adds Bootstrap-compatible classes:

- `form-check-input` for checkboxes.
- `form-select` for selects.
- `form-control` for other widgets.

### `OperationForm`

Base class for action forms. It is intentionally thin and delegates mutations to services.

## Account forms

- [`LoginForm`](../apps/accounts/forms/login_form.py)
  - Identifier/password authentication.
- [`VerifyUserCredentialsForm`](../apps/accounts/forms/claim_forms.py)
  - Institutional identifier and temporary password.
- [`VerifyUserDOBForm`](../apps/accounts/forms/claim_forms.py)
  - Date of birth and minimum age check.
- [`UpdateUserPasswordForm`](../apps/accounts/forms/claim_forms.py)
  - New/confirmation password and Django password validation.
- [`UserAdminForm`](../apps/accounts/forms/admin_form.py)
  - Admin-side account creation/editing.

## Student forms

File group: [`apps/profiles/student/forms/`](../apps/profiles/student/forms/)

- `StudentForm`
- `AcceptStudentForm`
- `RejectStudentForm`
- `WithdrawStudentForm`
- `SetStudentEligibilityForm`
- `StudentAccountActionForm`
- `AcademicYearForm`
- `SetAcademicYearCurrentForm`
- `EnrollmentForm`
- `CreateEnrollmentForm`
- `EnrollmentActionForm`
- `SetPrimaryEnrollmentForm`
- `CampusAssignmentForm`
- `AssignStudentCampusForm`
- `TransferStudentCampusForm`
- `EndCampusAssignmentForm`

Forms validate input and date/status relationships. Services own state transitions.

## Staff forms

File: [`apps/profiles/staff/forms/staff_forms.py`](../apps/profiles/staff/forms/staff_forms.py)

- `StaffForm`
- `CreateStaffForm`
- `AssignStaffToBuildingForm`
- `ChangeStaffRoleForm`
- `StaffStatusForm`
- `TransferStaffForm`

## University/accommodation forms

Files:

- [`apps/university/forms.py`](../apps/university/forms.py)
- [`apps/accommodation/forms/`](../apps/accommodation/forms/)

They cover university, campus, building, floor, room, bed, bed configuration, and room reconfiguration operations.

**PARTIALLY IMPLEMENTED:** Some forms contain incorrect imports or fields that do not match the model/service implementation. For example, `UniversityForm` imports `University` from the accommodation model package.

---

# 13. Views

## Implemented account views

File: [`apps/accounts/views/views.py`](../apps/accounts/views/views.py)

### `DashBoardView`

- `TemplateView`.
- Uses `LoginRequiredMixin`.
- Template: `accounts/dashboard.html`.

### `LogInView`

- `FormView`.
- Uses `LoginForm`.
- Injects request into the form.
- Calls Django `login()`.
- Redirects to dashboard.

### `LogoutView`

- Handles POST.
- Calls Django `logout()`.
- Redirects to landing page.

File: [`apps/accounts/views/claim_views.py`](../apps/accounts/views/claim_views.py)

### `VerifyCredentialsView`

Starts claim flow and saves `claim_user_id` in session.

### `VerifyUserDOBView`

Verifies the stored user's date of birth.

### `UpdatePasswordView`

Completes claim through `ClaimService.update_user_password()` and clears session state.

## Placeholder views

The following view modules contain only placeholder functions/imports and are not exposed in `config/urls.py`:

- [`apps/profiles/views.py`](../apps/profiles/views.py)
- [`apps/university/views.py`](../apps/university/views.py)
- [`apps/accommodation/views.py`](../apps/accommodation/views.py)
- [`apps/core/views.py`](../apps/core/views.py)
- [`apps/bookings/views.py`](../apps/bookings/views.py)
- [`apps/roomates/views.py`](../apps/roomates/views.py)
- [`admin_panel/views.py`](../admin_panel/views.py)

---

# 14. URLs

## Implemented

File: [`config/urls.py`](../config/urls.py)

```text
/                       landing page
/accounts/              included account URLs
/admin/                 Django admin
```

File: [`apps/accounts/urls.py`](../apps/accounts/urls.py)

```text
/accounts/login/                    LogInView
/accounts/logout/                   LogoutView
/accounts/dashboard/                DashBoardView
/accounts/claim/                    VerifyCredentialsView
/accounts/claim/identity/           VerifyUserDOBView
/accounts/claim/update_password/    UpdatePasswordView
```

## PLANNED / NOT WIRED

There are no active URLs for:

- Student administration.
- Academic-year administration.
- Enrollment administration.
- Campus assignment administration.
- Staff management.
- University management.
- Campus/building/floor/room/bed management.
- Booking/allocation.
- Roommate workflows.

---

# 15. Validation

Validation is intended to operate at four levels.

## Model validation

Examples:

- `User.clean()`: role-specific identity requirements.
- `AcademicYear.clean()`: valid date interval.
- `Program.clean()`: degree/major requirements by program type.
- `StudentEnrollment.clean()`: date, status, and program rules.
- `StudentAssignCampus.clean()`: assignment date interval.
- `Room.clean()`: positive position and floor capacity.
- `Bed.clean()`: positive position and effective configuration limit.
- `BedConfiguration.clean()`: at least one bed.

## Database constraints

Important constraints include:

- Unique user identifiers.
- One current academic year.
- One primary active enrollment per student/year.
- One active campus assignment per student/year.
- One active building manager per building.
- Unique campus name/code per university.
- Unique building number/code per campus.
- Unique floor number per building.
- Unique room position per floor.
- Unique bed position per room.
- Positive floor/room/bed/configuration counts.

## Form validation

Forms provide immediate user-facing validation, including:

- Date ordering.
- Minimum ages.
- Minimum bed counts.
- Positive room/floor/bed positions.
- Primary enrollment requiring active status.
- Password confirmation and Django password validators.

## Service validation

Services validate multi-record rules and state transitions, such as:

- Cannot deactivate an in-use bed configuration.
- Cannot reduce structural capacity below existing physical records.
- Cannot transfer a student without a current active assignment.
- Cannot create a second active building manager.
- Cannot activate a campus below an inactive university.

## Known validation inconsistencies

**PARTIALLY IMPLEMENTED:**

- Account status casing is inconsistent.
- `User.__str__()` and admin code use obsolete role names.
- Some QuerySets use incorrect relationship names.
- Some services catch broad exceptions or reference missing exception classes.

---

# 16. Transactions and concurrency

## Implemented transaction pattern

Most service mutations use:

```python
@staticmethod
@transaction.atomic
def operation(...):
    ...
```

This is used in:

- `ClaimService.update_user_password()`
- `AcademicYearService.create()` and `set_current()`
- `EnrollmentService` mutations.
- `CampusAssignmentService` mutations.
- `StaffService` mutations.
- `UniversityService.create_university()`.
- Accommodation services.

## Row locking

The clearest row-locking examples are:

- `ClaimService.update_user_password()`
  - Locks the `User` row with `select_for_update()`.
- `CampusAssignmentService.transfer_student()`
  - Locks the current active assignment before closing it.

`FloorService.create_floor()` intends to lock the building while allocating a floor number, but currently calls `select_for_updates()` rather than Django's `select_for_update()`.

## Intended future concurrency model

The design docs describe a future booking system with:

- Row-level locking.
- Capacity checked inside transactions.
- Reservation before booking creation.
- No over-allocation.
- First successful transaction wins.

This is **PLANNED**. No active booking model/service implementing that invariant was found.

---

# 17. Tests

## PARTIALLY IMPLEMENTED

The repository has test modules, but they currently contain only generated placeholders:

- [`apps/accounts/tests.py`](../apps/accounts/tests.py)
- [`apps/profiles/tests.py`](../apps/profiles/tests.py)
- [`apps/accommodation/tests.py`](../apps/accommodation/tests.py)
- [`apps/core/tests.py`](../apps/core/tests.py)
- [`apps/university/tests.py`](../apps/university/tests.py)
- [`apps/bookings/tests.py`](../apps/bookings/tests.py)
- [`apps/roomates/tests.py`](../apps/roomates/tests.py)
- [`admin_panel/tests.py`](../admin_panel/tests.py)

No substantive tests were found for:

- User manager creation.
- Multi-identifier authentication.
- Claim flow.
- Account status transitions.
- Policy decisions.
- QuerySet composition.
- Model constraints.
- Student services.
- Enrollment/campus assignment transitions.
- Staff manager uniqueness.
- Accommodation hierarchy services.
- Bed configuration migration.
- Transactions and concurrency.

Tests should be added before relying on the current service layer, particularly because several methods have known defects and there is no regression suite documenting intended behavior.

---

# 18. Existing implementation patterns

## Domain-oriented file organization

Models are split into nested domain packages rather than one model file:

```text
profiles/student/models/
accommodation/models/
accommodation/services/
accommodation/forms/
```

When adding code, preserve the existing package structure unless there is a clear architectural reason not to.

## Named lifecycle services

The preferred mutation style is:

```python
StudentService.accept_student(student=student)
EnrollmentService.complete_enrollment(
    enrollment=enrollment,
    end_date=end_date,
)
BedService.set_out_of_service(bed=bed)
```

Do not bypass these services with arbitrary status assignments when implementing new views or forms.

## QuerySet composition

The preferred read style is:

```python
Student.objects
    .active()
    .admitted()
    .eligible()
```

Use `select_related()` for foreign-key/one-to-one graphs and `prefetch_related()` for collections.

## Explicit effective configuration

Accommodation configuration inheritance is represented by model properties, not duplicated capacity fields:

```text
Room override
    -> Floor override
        -> Building default
```

Physical beds are the source of truth for current physical capacity.

## Domain exceptions

Use the exception classes in [`apps/core/exceptions.py`](../apps/core/exceptions.py) for service-level domain failures:

- `ValidationError`
- `ConflictError`
- `PermissionDenied`
- `NotFoundError`

Do not silently convert failures into successful-looking results.

## Policy/service separation

Policies answer whether an actor may act. Services perform the operation. Forms validate input. Views coordinate HTTP/session behavior.

---

# 19. Current implementation status

## IMPLEMENTED

- Django project configuration.
- SQLite database configuration.
- Custom `User` model declaration.
- Student/staff/profile model structure.
- Academic model structure.
- University/accommodation model structure.
- Many model-level constraints and validation methods.
- QuerySet classes across most domains.
- Service classes across student, staff, university, and accommodation domains.
- Core policy classes.
- Account URLs and account templates.
- Django admin registration for `User`.
- Account claim workflow structure.

## PARTIALLY IMPLEMENTED

- Custom user manager.
- Multi-identifier authentication.
- Login form.
- Account admin integration.
- Profile model loading.
- QuerySet correctness.
- Accommodation service correctness.
- University service correctness.
- Forms.
- Policy/runtime consistency.
- Account status lifecycle.
- Transaction locking in floor allocation.
- Occupancy-dependent bed/room properties.
- Application URL coverage.
- Test coverage.

## PLANNED

- Booking/allocation engine.
- Room assignment model.
- Roommate invitations and groups.
- Delegate role/workflows.
- Notifications.
- Audit trail.
- Booking-period rules.
- Capacity reservation workflow.
- Assignment invalidation after campus changes.

## UNKNOWN

- Whether the current SQLite database reflects the latest model code.
- Whether the project currently passes Django system checks.
- Whether migrations fully represent all nested profile/accommodation models.
- Whether the intended frontend/admin workflows have been implemented outside the inspected Python/templates.
- Whether account files containing `******` are transcription artifacts or actual repository content.

---

# 20. Important unfinished work

The following work is important before extending the system substantially.

## Immediate correctness work

1. Resolve syntax placeholders in:
   - [`apps/accounts/manager.py`](../apps/accounts/manager.py)
   - [`apps/accounts/backends/auth_backends.py`](../apps/accounts/backends/auth_backends.py)
   - [`apps/accounts/forms/login_form.py`](../apps/accounts/forms/login_form.py)
   - [`apps/accounts/management/commands/create_user.py`](../apps/accounts/management/commands/create_user.py)

2. Normalize the role vocabulary:
   - `AccountType` vs `UserType`.
   - `account_type` vs `role`.

3. Normalize account status values:
   - Use the declared `AccountStatus` choices consistently.

4. Correct QuerySet relationship names and composition:
   - Student reverse relations.
   - Enrollment `primary_active()`.
   - Staff `with_user()`.
   - Degree academic-level filters.

5. Correct service typos and missing imports:
   - `.exists()`.
   - `select_for_update()`.
   - `building.floors`.
   - `ConflictError` imports.
   - Correct model field names.

6. Add tests before changing service behavior.

## Domain completion work

1. Implement the accommodation assignment model required by `Bed.is_occupied`.
2. Decide whether occupancy is bed-based, room-based, or assignment-based and make all properties/services consistent.
3. Add views and URLs for existing services.
4. Add policy enforcement at actual HTTP/service entry points.
5. Complete migrations and verify app/model discovery.
6. Implement booking/allocation only after the physical accommodation and student readiness foundations are stable.
7. Implement roommate and delegate functionality only after booking boundaries are defined.
8. Add audit and notification behavior around state transitions if required by the product.

## Architectural caution

Do not introduce booking logic directly into `Room`, `Bed`, or student QuerySets. The design explicitly expects booking/allocation writes to be handled by a future booking service with transaction and locking guarantees.

Do not infer a student's building scope from campus assignment. The policy code explicitly distinguishes campus from building and expects a future student-to-room/bed assignment relationship.

---

# Files inspected

The architecture was derived from the following categories of files:

- Project configuration:
  - [`config/settings.py`](../config/settings.py)
  - [`config/urls.py`](../config/urls.py)
  - [`config/views.py`](../config/views.py)
  - [`manage.py`](../manage.py)
- Accounts:
  - [`apps/accounts/models.py`](../apps/accounts/models.py)
  - [`apps/accounts/manager.py`](../apps/accounts/manager.py)
  - [`apps/accounts/backends/auth_backends.py`](../apps/accounts/backends/auth_backends.py)
  - [`apps/accounts/services/`](../apps/accounts/services/)
  - [`apps/accounts/forms/`](../apps/accounts/forms/)
  - [`apps/accounts/views/`](../apps/accounts/views/)
  - [`apps/accounts/urls.py`](../apps/accounts/urls.py)
  - [`apps/accounts/admin.py`](../apps/accounts/admin.py)
- Profiles:
  - Student and staff model files under [`apps/profiles/`](../apps/profiles/)
  - QuerySets under [`apps/profiles/student/models/managers/`](../apps/profiles/student/models/managers/) and [`apps/profiles/staff/models/managers/`](../apps/profiles/staff/models/managers/)
  - Services under [`apps/profiles/student/services/`](../apps/profiles/student/services/) and [`apps/profiles/staff/services/`](../apps/profiles/staff/services/)
  - Forms under [`apps/profiles/student/forms/`](../apps/profiles/student/forms/) and [`apps/profiles/staff/forms/`](../apps/profiles/staff/forms/)
- University:
  - [`apps/university/models.py`](../apps/university/models.py)
  - [`apps/university/service.py`](../apps/university/service.py)
  - [`apps/university/forms.py`](../apps/university/forms.py)
- Accommodation:
  - Model files under [`apps/accommodation/models/`](../apps/accommodation/models/)
  - QuerySets under [`apps/accommodation/models/managers/`](../apps/accommodation/models/managers/)
  - Services under [`apps/accommodation/services/`](../apps/accommodation/services/)
  - Forms under [`apps/accommodation/forms/`](../apps/accommodation/forms/)
- Core:
  - [`apps/core/abstract_models/timestamp_models.py`](../apps/core/abstract_models/timestamp_models.py)
  - [`apps/core/models/gender_model.py`](../apps/core/models/gender_model.py)
  - [`apps/core/forms.py`](../apps/core/forms.py)
  - [`apps/core/exceptions.py`](../apps/core/exceptions.py)
  - Policy files under [`apps/core/policies/`](../apps/core/policies/)
- Tests:
  - `tests.py` files under active and inactive apps.
- Design documentation:
  - [`docs/00_overview.md`](./00_overview.md)
  - [`docs/01_architecture.md`](./01_architecture.md)
  - [`docs/04_data_flow.md`](./04_data_flow.md)
  - [`docs/05_state_machines.md`](./05_state_machines.md)
  - [`docs/07_permission_model.md`](./07_permission_model.md)
  - [`docs/09_edge_cases.md`](./09_edge_cases.md)

---

# CONTINUATION PROMPT

You are continuing development of the Django project documented in `docs/PROJECT_CONTEXT.md`.

Read that file first, then inspect the relevant source files before making any changes. Preserve the existing modular-monolith architecture:

- Models own persistence and local invariants.
- Custom QuerySets/managers own reusable read-side queries, filtering, searching, and eager loading.
- Services own transactional writes, lifecycle transitions, cross-model business rules, and conflict detection.
- Policies own authorization decisions and must not mutate data.
- Forms validate user input.
- Views coordinate HTTP/session/form behavior and should delegate mutations to services.

Do not invent functionality that is only described in the design documents. Clearly distinguish IMPLEMENTED, PARTIALLY IMPLEMENTED, PLANNED, and UNKNOWN behavior. In particular:

- `accounts`, `profiles`, `university`, `accommodation`, and `core` are the active architectural foundation.
- `bookings`, `roomates`, and `admin_panel` are present but disabled/incomplete.
- The accommodation hierarchy is `University -> Campus -> Building -> Floor -> Room -> Bed`.
- Bed occupancy depends on a future/missing assignment relationship.
- Student campus assignment must not be treated as building assignment.
- Preserve the room/floor/building bed-configuration inheritance model.
- Preserve physical bed records during capacity reductions; the existing migration service uses `OUT_OF_SERVICE` rather than deletion.
- Use the existing domain exceptions and transaction patterns.
- Do not bypass services with direct lifecycle field mutation.
- Add or update tests for behavior changes, especially service transitions, QuerySet composition, database constraints, policies, and transaction-sensitive operations.

Before editing:

1. Identify the exact files and symbols involved.
2. Check for existing QuerySets, services, policies, forms, URLs, and tests that already cover the behavior.
3. Confirm whether the requested behavior is implemented, partial, planned, or unknown.
4. Avoid unrelated cleanup.

After editing:

1. Run the smallest relevant checks/tests.
2. Report files changed, behavior changed, and validation performed.
3. Mention any pre-existing defects that block verification.
4. Do not modify application code when the request is documentation-only.

