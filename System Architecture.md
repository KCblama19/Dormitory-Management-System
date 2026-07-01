## **System Architecture**



\- A student may hold up to \*\*3 active roommate invitations\*\* at once, but can only be in \*\*one accepted roommate grouping\*\* at a time.



Below is the consolidated architecture document



##### **Dormitory Allocation System**



###### **Foundational Architecture Document**



###### **1. System Purpose**



This system is a multi-campus university dormitory allocation platform designed to replace manual housing assignment processes with a structured, approval-based workflow.



It supports:

\- newly admitted students

\- continuing students

\- transferred students

\- remote onboarding before arrival

\- campus-scoped room browsing and booking

\- roommate invitations and assisted matching

\- admin-controlled approvals and direct assignments

\- delegate-assisted booking support



This is \*\*not\*\* a simple room reservation tool. It is an \*\*allocation and approval system\*\* with strict institutional rules.



\## 2. Core Problems Being Solved



The system addresses these operational problems:



\- manual room allocation is inefficient and inconsistent

\- students need to plan housing before arriving physically

\- roommate coordination currently happens informally

\- capacity conflicts and overbooking are hard to manage manually

\- campus-specific restrictions are difficult to enforce by hand

\- administrators need a system that is simple enough to adopt quickly



\## 3. Primary Users



\### Students

Students can:

\- claim their pre-created account

\- log in remotely

\- complete their profile

\- view rooms only in their assigned campus

\- see current occupants and limited roommate metadata

\- send or accept roommate invitations

\- submit solo or grouped booking requests

\- confirm delegate-submitted requests

\- cancel their own pending requests



\### Admin / Building Management

Admins can:

\- create and provision users

\- assign campuses

\- manage student records

\- configure campuses, buildings, floors, and rooms

\- generate rooms automatically

\- edit room configurations manually

\- approve or reject booking requests

\- directly assign rooms

\- invalidate bookings after campus changes

\- resolve delegate conflicts

\- enforce capacity and policy rules



\### Delegates / Student Representatives

Delegates can:

\- help students find roommates

\- submit booking requests on behalf of students

\- assist students in the process



Delegates cannot:

\- approve bookings

\- override admin decisions

\- exceed their delegated scope



Delegate scope rules:

\- country representatives: only students in their country group

\- higher association officers: broader student scope



\---



\## 4. Domain Rules



\### Campus Assignment

\- Students do not choose campuses.

\- Central administration assigns the campus.

\- A student has only \*\*one active campus\*\* at a time.

\- Campus changes happen only through administration.



\### Eligibility

A student can only book if all are true:

\- admission is fully approved

\- student ID exists

\- campus has been assigned



If any of these are false, booking is blocked.



\### Room Structure

\- The system models \*\*rooms\*\*, not individual beds as first-class entities.

\- Capacity is stored at room level.

\- Bed slots exist conceptually only as the basis for room capacity.

\- Capacity examples:

&#x20; - international dorms: usually 2

&#x20; - local/student dorms: 4 to 8



\### Gender Rules

\- Same gender per room is mandatory by default.

\- Some campuses or floors may have stricter restrictions.

\- Floor-level restrictions such as female-only floors must be enforced.



\### Roommate Rules

Mandatory:

\- same campus

\- same gender



Optional preferences:

\- nationality

\- major/program

\- level (`BSc`, `Masters`, `PhD`)



\### Booking Policy

\- Booking is \*\*approval-based\*\*

\- Booking is \*\*not instant\*\*

\- Final decision belongs to admin/building management

\- Admin can directly assign rooms

\- Admin cannot exceed room capacity



\### Campus Change

If a student’s campus changes:

\- existing booking is invalidated

\- existing assignment is invalidated

\- student is notified

\- no automatic transfer is performed



\### Capacity

Capacity is a hard invariant:

\- approved occupancy + reserved pending slots must never exceed room capacity

\- admin may not override this invariant



\---



\## 5. Account and Authentication Architecture



\### Provisioning Model

There is \*\*no public registration\*\*.



Accounts are created by admin or import script.



For each account, the system sets:

\- role: student, staff, admin

\- identifier: `student\_id` or `staff\_id`

\- optional email

\- optional phone

\- internal `username = UUID`

\- unusable password initially

\- `is\_active = False`

\- `is\_verified = False`



\### Account Claim Flow

User claims an account by providing:

\- identifier

\- verification data such as date of birth

\- new password



System flow:

1\. find user by identifier

2\. reject if not found

3\. reject if already active

4\. verify identity data

5\. if valid:

&#x20;  - set password

&#x20;  - set `is\_active = True`

&#x20;  - set `is\_verified = True`



\### Login Flow

User logs in using:

\- student ID

\- staff ID

\- email

\- phone



System:

1\. normalizes identifier

2\. finds the user by one of the allowed identifiers

3\. rejects if account inactive

4\. validates password

5\. authenticates internally via UUID username

6\. creates session



\### Tokens

System may support activation/reset via:

\- email token

\- SMS token



\### Identity Rules

These must be unique:

\- student ID

\- staff ID

\- email

\- phone



The internal username UUID:

\- is never exposed

\- is never used as login input



\---



\## 6. High-Level Monolith Architecture



Recommended Django app structure:



\- `accounts`

\- `people` or `profiles`

\- `campuses`

\- `housing`

\- `roommates`

\- `bookings`

\- `delegates`

\- `notifications`

\- `audit`



\### App Responsibilities



`accounts`

\- authentication

\- claim account

\- login

\- password reset

\- role-aware identity lookup



`profiles`

\- student profile

\- staff profile

\- demographic and roommate-visible metadata

\- eligibility state



`campuses`

\- campus master data

\- campus configuration

\- transfer/change history



`housing`

\- buildings

\- floors

\- rooms

\- room generation

\- capacity and restriction rules



`roommates`

\- invitations

\- invitation limits

\- accepted roommate grouping

\- invitation lifecycle



`bookings`

\- booking requests

\- participant snapshots

\- room reservation logic

\- occupant review

\- admin approvals/rejections

\- direct assignments

\- cooldown handling



`delegates`

\- delegate roles and scope

\- association/country permissions

\- on-behalf actions



`notifications`

\- in-app notifications

\- optional email/SMS fanout later



`audit`

\- immutable event history

\- admin actions

\- status history



\---



\## 7. Core Entities and Recommended Models



\## 7.1 User

Purpose:

\- authentication identity



Important fields:

\- `id`

\- `username` (UUID, internal only)

\- `role`

\- `student\_id` nullable

\- `staff\_id` nullable

\- `email`

\- `phone`

\- `is\_active`

\- `is\_verified`

\- `last\_login`



Notes:

\- one of `student\_id` or `staff\_id` depending on role

\- UUID username is never user-facing



\## 7.2 StudentProfile

Purpose:

\- student-specific domain record



Important fields:

\- `user`

\- `full\_name`

\- `date\_of\_birth`

\- `gender`

\- `nationality`

\- `major`

\- `academic\_level`

\- `assigned\_campus`

\- `admission\_status`

\- `eligibility\_status`

\- `arrival\_date`

\- `country\_group` if needed for delegate scoping



\## 7.3 StaffProfile

Purpose:

\- staff/admin/delegate domain record



Important fields:

\- `user`

\- `full\_name`

\- `staff\_id`

\- `staff\_role`

\- `assigned\_campus` nullable for global admins



\## 7.4 Campus

Purpose:

\- top-level allocation boundary



Important fields:

\- `name`

\- `code`

\- `city`

\- `status`



\## 7.5 CampusConfiguration

Purpose:

\- controls generation and policy defaults



Important fields:

\- `campus`

\- `number\_of\_floors`

\- `rooms\_per\_floor`

\- `default\_room\_capacity`

\- `default\_gender\_rule`

\- `booking\_open\_at`

\- `booking\_close\_at`

\- `occupant\_review\_window\_days`

\- `delegate\_confirmation\_window\_days`

\- `admin\_review\_window\_days`



\## 7.6 Building

Purpose:

\- physical dormitory grouping



Important fields:

\- `campus`

\- `building\_code` or `building\_number`

\- `name`

\- `gender\_policy\_override`

\- `active`



\## 7.7 Floor

Purpose:

\- floor-level rules and grouping



Important fields:

\- `building`

\- `floor\_number`

\- `gender\_rule`

\- `is\_restricted`

\- `restriction\_note`



\## 7.8 Room

Purpose:

\- assignable occupancy unit



Important fields:

\- `campus`

\- `building`

\- `floor`

\- `room\_code`

\- `room\_number`

\- `capacity`

\- `gender\_rule`

\- `status`

\- `manually\_modified`

\- `approved\_occupancy\_count`

\- `reserved\_pending\_slots`



Derived:

\- `available\_slots = capacity - approved\_occupancy\_count - reserved\_pending\_slots`



Room code rule:

\- three-digit logical room code:

&#x20; - first digit = floor

&#x20; - last two digits = room number

\- if building labeling is also needed, store separately rather than overloading the room code



\## 7.9 RoomAssignment

Purpose:

\- final approved student-to-room allocation



Important fields:

\- `student`

\- `room`

\- `campus`

\- `booking\_request` nullable if direct admin assignment

\- `status`

\- `assigned\_by`

\- `assigned\_at`

\- `invalidated\_at`

\- `invalidation\_reason`



\## 7.10 RoommateInvitation

Purpose:

\- student-to-student invitation workflow



Important fields:

\- `sender`

\- `receiver`

\- `campus`

\- `status`

\- `expires\_at`



Rules:

\- sender and receiver must be same campus

\- sender and receiver must be same gender

\- sender can have at most 3 active invitations

\- a student can accept only one active invitation path into an accepted roommate grouping



\## 7.11 RoommateGroup

Purpose:

\- stable pre-booking grouping



Important fields:

\- `campus`

\- `created\_by`

\- `status`



Statuses:

\- `forming`

\- `active`

\- `locked`

\- `dissolved`



\## 7.12 RoommateGroupMember

Purpose:

\- membership and invitation acceptance state



Important fields:

\- `group`

\- `student`

\- `membership\_status`

\- `joined\_at`



\## 7.13 BookingRequest

Purpose:

\- approval workflow for room request



Important fields:

\- `campus`

\- `room`

\- `group` nullable

\- `requested\_by\_user`

\- `submission\_mode`

\- `requested\_slot\_count`

\- `status`

\- `student\_confirmation\_required`

\- `student\_confirmed\_at`

\- `occupant\_review\_required`

\- `occupant\_review\_deadline`

\- `admin\_review\_deadline`

\- `reserved\_at`

\- `expires\_at`

\- `reapply\_blocked\_until`

\- `decision\_reason`



Submission modes:

\- `student`

\- `delegate`

\- `admin\_direct`



Statuses:

\- `draft`

\- `awaiting\_student\_confirmation`

\- `pending\_occupant\_review`

\- `pending\_admin\_review`

\- `approved`

\- `rejected`

\- `cancelled`

\- `expired`

\- `invalidated`



\## 7.14 BookingParticipant

Purpose:

\- snapshot of students attached to request at submission time



Important fields:

\- `booking\_request`

\- `student`

\- `snapshot\_name`

\- `snapshot\_gender`

\- `snapshot\_nationality`

\- `snapshot\_major`

\- `snapshot\_academic\_level`



This is important so later group/profile edits do not mutate historical bookings.



\## 7.15 OccupantReview

Purpose:

\- current occupants’ advisory response for partially occupied rooms



Important fields:

\- `booking\_request`

\- `occupant\_student`

\- `decision`

\- `comment`

\- `responded\_at`



Decision options:

\- `accept`

\- `reject`

\- `no\_response`



Important:

\- advisory only

\- never final



\## 7.16 DelegateScope

Purpose:

\- defines who a delegate may act for



Important fields:

\- `delegate\_user`

\- `scope\_type`

\- `campus`

\- `country\_group` nullable

\- `active`



Scope examples:

\- campus-wide officer

\- country representative



\## 7.17 Notification

Purpose:

\- event alerts without full chat/messaging



Important fields:

\- `recipient\_user`

\- `type`

\- `title`

\- `body`

\- `related\_object\_type`

\- `related\_object\_id`

\- `is\_read`

\- `sent\_via\_email`

\- `sent\_via\_sms`



\## 7.18 AuditLog

Purpose:

\- immutable activity history



Important fields:

\- `actor\_user`

\- `action\_type`

\- `target\_type`

\- `target\_id`

\- `before\_state`

\- `after\_state`

\- `timestamp`



\## 7.19 Status History Models

Recommended:

\- `BookingStatusHistory`

\- `RoomAssignmentStatusHistory`

\- `CampusTransferHistory`



These help a lot later with debugging and admin trust.



\---



\## 8. Key Workflows



\## 8.1 Account Claim

1\. Admin provisions account

2\. User submits identifier + verification data + password

3\. System verifies identity

4\. Account becomes active and verified

5\. User can log in



\## 8.2 Student Booking Eligibility

1\. User logs in

2\. System loads student profile

3\. Booking access allowed only if:

&#x20;  - admission approved

&#x20;  - student ID exists

&#x20;  - campus assigned



If not eligible:

\- room browsing may be limited or blocked

\- booking actions are blocked



\## 8.3 Room Generation

1\. Admin defines campus config

2\. Admin creates building and floor settings

3\. System generates rooms automatically

4\. Existing generated rooms are reset if explicit regeneration is requested

5\. Admin may manually edit room details afterward



\## 8.4 Roommate Invitation

1\. Student sends invitation

2\. System validates:

&#x20;  - same campus

&#x20;  - same gender

&#x20;  - sender has fewer than 3 active invitations

3\. Receiver accepts or rejects

4\. Accepted invitation contributes to one active roommate grouping

5\. Student may only finalize one accepted roommate path



\## 8.5 Solo Booking

1\. Eligible student views rooms in assigned campus

2\. Student selects room

3\. System checks:

&#x20;  - same campus

&#x20;  - gender rules

&#x20;  - enough available reservable slots

4\. System creates booking request

5\. Capacity is reserved immediately

6\. If room partially occupied:

&#x20;  - occupant review starts

&#x20;  - notification sent

7\. Admin reviews and decides

8\. If approved, assignment is created



\## 8.6 Group Booking

1\. Students form roommate group

2\. One member submits request

3\. System validates full group size fits room

4\. Request reserves required capacity immediately

5\. Admin reviews and decides

6\. If approved, assignments created for all participants



Important:

\- no partial group placement in MVP



\## 8.7 Delegate-Submitted Booking

1\. Delegate submits request for student(s)

2\. System validates delegate scope

3\. Booking is created in `awaiting\_student\_confirmation`

4\. Reserved capacity is held immediately

5\. Student must confirm within configured window

6\. If confirmed:

&#x20;  - move to occupant/admin review path

7\. If not confirmed:

&#x20;  - request expires/cancels

&#x20;  - reserved capacity released



\## 8.8 Partially Occupied Room Booking

1\. Student submits request to room with current occupants

2\. Room must still have enough reservable slots

3\. System reserves capacity immediately

4\. Current occupants receive notification

5\. Occupants review candidate metadata

6\. Occupants submit advisory response within 3 days

7\. Admin receives request and advisory input

8\. Admin makes final decision



\## 8.9 Student Cancellation

1\. Student cancels own pending request

2\. System updates status to `cancelled`

3\. Reserved capacity is released

4\. Student is blocked from reapplying to same room for 1 day



\## 8.10 Campus Change

1\. Admin changes student campus

2\. System invalidates active booking requests and assignments

3\. Reserved capacity and occupancy are recalculated

4\. Student is notified

5\. Student must rebook on new campus



\---



\## 9. Capacity and Concurrency Rules



These are the most important invariants.



\### Invariants

\- Approved occupancy cannot exceed room capacity

\- Reserved pending slots cannot push occupancy beyond room capacity

\- Final approvals cannot exceed room capacity

\- Admin cannot override capacity



\### Reservation Logic

Pending requests reserve capacity immediately.



For every room:

\- `reservable\_slots = capacity - approved\_occupancy\_count - reserved\_pending\_slots`



A booking can be created only if:

\- requested party size <= reservable slots



\### Concurrent Requests

Use transactional logic so:

\- first successful reservation wins

\- later conflicting attempts fail cleanly



\### Multiple Pending Requests

Allowed only if total reserved size does not exceed remaining capacity.



Examples:

\- room has 2 slots left

\- allowed:

&#x20; - two solo pending requests

&#x20; - one group-of-two request

\- not allowed:

&#x20; - three solo pending requests

&#x20; - two group-of-two requests



This preserves choice without breaking capacity rules.



\---



\## 10. Visibility Rules



Students may see:

\- room capacity

\- remaining slots

\- current occupant names

\- nationality

\- major

\- academic level



Students may not see:

\- date of birth

\- sensitive identity data

\- personal contacts unless separately permitted



This is enough for roommate decision-making without exposing sensitive information.



\---



\## 11. Permissions Model



\### Student

Can:

\- claim account

\- log in

\- manage profile fields allowed to them

\- send roommate invitations

\- accept one roommate path

\- submit requests

\- cancel own pending requests

\- view room and occupant metadata within campus



Cannot:

\- approve bookings

\- change campus

\- exceed invitation limit

\- submit requests while ineligible



\### Delegate

Can:

\- act for students within assigned scope

\- submit requests on behalf of students

\- assist matching



Cannot:

\- approve bookings

\- bypass student confirmation

\- act outside scope



\### Building Admin / Housing Admin

Can:

\- manage building/floor/room settings

\- review and decide bookings

\- directly assign rooms

\- regenerate rooms

\- invalidate requests

\- manage campus-specific restrictions



\### Central Admin

Can:

\- assign campuses

\- transfer students

\- manage all users and staff roles

\- perform cross-campus oversight



\---



\## 12. Notifications



MVP should include notifications, not full messaging.



Events:

\- booking submitted

\- occupant review needed

\- delegate request awaiting confirmation

\- booking approved

\- booking rejected

\- booking cancelled

\- booking expired

\- campus changed

\- assignment invalidated



Recipients:

\- student

\- current occupants

\- delegate

\- relevant admins



Channels:

\- in-app required

\- email optional in MVP

\- SMS later



\---



\## 13. Audit and History



Nothing should be hard-deleted in normal operations.



Use status transitions and history records instead.



Must preserve:

\- old bookings

\- old assignments

\- invitation history

\- admin decisions

\- delegate actions

\- campus changes

\- room regeneration actions

\- manual room edits



This is important for disputes and operational trust.



\---



\## 14. MVP Scope



The simplest version that still solves the real university problem is:



\- admin-provisioned accounts only

\- claim account flow

\- flexible login using identifier lookup

\- campus-assigned student model

\- eligibility enforcement

\- campus/building/floor/room configuration

\- room auto-generation

\- manual room edits

\- same-campus room browsing only

\- student metadata visibility for roommate decisions

\- roommate invitations with max 3 active invitations

\- one accepted roommate grouping at a time

\- solo booking

\- group booking

\- delegate-submitted requests with student confirmation

\- partially occupied room advisory occupant review

\- approval-based admin workflow

\- immediate pending capacity reservation

\- cancellation with 1-day same-room cooldown

\- notification system

\- audit trail

\- campus transfer invalidation flow



\### Postpone

\- algorithmic roommate matching

\- waitlists beyond reserved-capacity logic

\- full messaging/chat

\- ranking/scoring of candidates by occupants

\- complex recommendation engine

\- payment or deposit system

\- arrival check-in automation

\- public self-registration



\---



\## 15. Recommended Build Order



If we were to implement this cleanly, I would build in this order:



1\. Accounts and claim/login flows

2\. Roles and permissions

3\. Student and staff profiles

4\. Campus and eligibility model

5\. Building/floor/room configuration

6\. Room auto-generation and regeneration

7\. Basic room browsing with campus filtering

8\. Roommate invitation flow

9\. Booking request model and reservation logic

10\. Admin approval/rejection workflow

11\. Room assignment model

12\. Delegate scope and on-behalf submission

13\. Occupant review flow

14\. Notifications

15\. Audit/history hardening



That order reduces rework and keeps the domain stable as features are layered in.



\---



\## 16. Final Assessment



This system is now well-defined enough to start implementation planning. The major architectural risks have been addressed:



\- The university is the top-level boundary

\- A campus is a top-level boundary which belong to only one a university and can't belong to more than one

\- booking is approval-based

\- pending requests reserve capacity

\- roommate matching is constrained

\- delegate power is scoped

\- capacity is non-negotiable

\- account creation is institution-controlled

\- room generation supports admin usability

