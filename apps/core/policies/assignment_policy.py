from apps.core.policies.base import BasePolicy


class AssignmentPolicy(BasePolicy):
    """
    Authorization rules for the Assignment lifecycle.

    Authorization boundaries:

        Global Admin:
            System-wide Assignment authority.

        Building Manager:
            Full permitted Assignment authority within
            their assigned building.

        Building Staff:
            Permitted operational actions within their
            assigned building.

        Student:
            May perform permitted actions on their own
            Assignments.

    This policy handles authorization only.

    Lifecycle transitions, deadlines, eligibility,
    physical departure verification, and other business
    validations remain the responsibility of services.
    """

    # =========================================================
    # PRIVATE HELPERS
    # =========================================================

    @staticmethod
    def _get_assignment_building(assignment):
        """
        Resolve the Building through the Assignment hierarchy.

        Assignment
            -> Bed
                -> Room
                    -> Floor
                        -> Building

        Returns None if the required relationship is unavailable.
        """
        if assignment is None:
            return None

        bed = getattr(assignment, "bed", None)
        room = getattr(bed, "room", None)
        floor = getattr(room, "floor", None)

        return getattr(floor, "building", None)

    @staticmethod
    def _get_related_assignment(resource):
        """
        Resolve an Assignment from a related workflow record.

        Used by CheckoutRequest and AssignmentExtension
        authorization methods.
        """
        if resource is None:
            return None

        return getattr(resource, "assignment", None)

    @classmethod
    def _is_assignment_owner(cls, actor, assignment):
        """
        Check whether the actor is the student who owns
        the Assignment.

        Students cannot access another student's Assignment.
        """
        if assignment is None or not cls.is_student_account(actor):
            return False

        student = getattr(assignment, "student", None)

        if student is None:
            return False

        return (
            getattr(student, "user_id", None)
            == getattr(actor, "pk", None)
        )

    @classmethod
    def _can_operate_assignment(cls, actor, assignment):
        """
        Authorize operational Assignment actions.

        Building Manager, Building Staff, and Global Admin
        qualify within their respective scopes.
        """
        building = cls._get_assignment_building(assignment)

        return cls.works_in_building(actor, building)

    @classmethod
    def _can_manage_assignment(cls, actor, assignment):
        """
        Authorize Manager-level Assignment decisions.

        Only Building Manager and Global Admin qualify.
        """
        building = cls._get_assignment_building(assignment)

        return cls.manages_building(actor, building)

    # =========================================================
    # VIEW ASSIGNMENTS
    # =========================================================

    @classmethod
    def can_view_assignment(cls, actor, assignment):
        """
        Authorize viewing an individual Assignment.

        Students can view their own Assignments.

        Building Manager and Building Staff can view
        Assignments belonging to their building.

        Global Admin can view Assignments system-wide.
        """
        if assignment is None:
            return False

        return (
            cls.is_global_admin(actor)
            or cls._is_assignment_owner(actor, assignment)
            or cls._can_operate_assignment(actor, assignment)
        )

    # =========================================================
    # RESERVATION CANCELLATION
    # =========================================================

    @classmethod
    def can_cancel_reservation(cls, actor, assignment):
        """
        Authorize cancellation of a reservation.

        Permitted actors:

            - Student cancelling their own reservation.
            - Building Manager within their building.
            - Building Staff within their building.
            - Global Admin system-wide.

        Services must reject cancellation after check-in.
        """
        if assignment is None:
            return False

        return (
            cls.is_global_admin(actor)
            or cls._is_assignment_owner(actor, assignment)
            or cls._can_operate_assignment(actor, assignment)
        )

    # =========================================================
    # CHECK-IN
    # =========================================================

    @classmethod
    def can_check_in(cls, actor, assignment):
        """
        Authorize normal check-in.

        Permitted actors:

            - Building Manager.
            - Building Staff.
            - Global Admin.

        Students cannot check themselves in.
        """
        return cls._can_operate_assignment(
            actor,
            assignment,
        )

    @classmethod
    def can_approve_early_check_in(cls, actor, assignment):
        """
        Authorize early check-in approval.

        Building Manager, Building Staff, and Global Admin
        may approve early check-in.

        No separate early-check-in reason is required.

        The service must record the approver and perform
        approval and check-in atomically.
        """
        return cls._can_operate_assignment(
            actor,
            assignment,
        )

    # =========================================================
    # CHECKOUT REQUESTS
    # =========================================================

    @classmethod
    def can_request_checkout(cls, actor, assignment):
        """
        Authorize a student to request checkout.

        Students may only request checkout for their
        own Assignments.

        Students cannot directly release occupied beds.
        """
        return cls._is_assignment_owner(
            actor,
            assignment,
        )

    @classmethod
    def can_view_checkout_request(cls, actor, checkout_request):
        """
        Authorize viewing a CheckoutRequest.

        Students can view requests associated with their
        own Assignments.

        Staff can view requests within their building.

        Global Admin has system-wide access.
        """
        assignment = cls._get_related_assignment(
            checkout_request
        )

        return cls.can_view_assignment(
            actor,
            assignment,
        )

    @classmethod
    def can_assist_checkout_inspection(
        cls,
        actor,
        checkout_request,
    ):
        """
        Authorize physical checkout inspection assistance.

        Building Staff, Building Manager, and Global Admin
        may perform this activity within their permitted scope.

        This permission does not grant authority to resolve
        or independently approve checkout requests.
        """
        assignment = cls._get_related_assignment(
            checkout_request
        )

        return cls._can_operate_assignment(
            actor,
            assignment,
        )

    @classmethod
    def can_resolve_checkout_request(
        cls,
        actor,
        checkout_request,
    ):
        """
        Authorize checkout request resolution.

        Only Building Manager and Global Admin may:

            - Approve/confirm checkout.
            - Reject checkout.
            - Resolve checkout requests.

        Building Staff cannot independently resolve requests.
        """
        assignment = cls._get_related_assignment(
            checkout_request
        )

        return cls._can_manage_assignment(
            actor,
            assignment,
        )

    @classmethod
    def can_complete_checkout(cls, actor, assignment):
        """
        Authorize completion of an Assignment checkout.

        Only Building Manager and Global Admin may complete
        checkout after physical departure has been verified.

        Building Staff cannot independently release the bed.
        """
        return cls._can_manage_assignment(
            actor,
            assignment,
        )

    # =========================================================
    # ASSIGNMENT EXTENSIONS
    # =========================================================

    @classmethod
    def can_request_extension(cls, actor, assignment):
        """
        Authorize a student to request a reservation extension.

        Students may request an extension for their own
        Assignments.

        The service validates the Assignment status,
        existing pending requests, and requested deadline.
        """
        return cls._is_assignment_owner(
            actor,
            assignment,
        )

    @classmethod
    def can_view_extension(cls, actor, extension):
        """
        Authorize viewing an AssignmentExtension.

        Students can view their own extension requests.

        Building staff can view extension requests within
        their building.

        Global Admin has system-wide access.
        """
        assignment = cls._get_related_assignment(extension)

        return cls.can_view_assignment(
            actor,
            assignment,
        )

    @classmethod
    def can_decide_extension(cls, actor, extension):
        """
        Authorize approval or rejection of an extension.

        Only Building Manager and Global Admin may decide.

        Building Staff cannot approve or reject extensions.
        """
        assignment = cls._get_related_assignment(extension)

        return cls._can_manage_assignment(
            actor,
            assignment,
        )

    # =========================================================
    # ELIGIBILITY REVIEWS
    # =========================================================

    @classmethod
    def can_review_eligibility(cls, actor, assignment):
        """
        Authorize eligibility-review decisions.

        Only Building Manager and Global Admin may approve
        or reject an eligibility review.

        Building Staff cannot make eligibility decisions.

        Review rejection does not automatically cancel
        or terminate the Assignment.
        """
        return cls._can_manage_assignment(
            actor,
            assignment,
        )

    # =========================================================
    # ADMINISTRATIVE TERMINATION
    # =========================================================

    @classmethod
    def can_terminate_assignment(cls, actor, assignment):
        """
        Authorize administrative termination of an
        active accommodation relationship.

        Building Manager may terminate Assignments within
        their assigned building.

        Global Admin may terminate Assignments system-wide.

        Building Staff cannot independently terminate
        an active accommodation relationship.
        """
        return cls._can_manage_assignment(
            actor,
            assignment,
        )