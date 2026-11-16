from apps.core.policies.base import BasePolicy


class AllocationPolicy(BasePolicy):
    """
    Authorization rules for accommodation allocation workflows.

    Allocation strategies:

        AUTOMATIC
            Staff may initiate allocation.
            The system completes allocation automatically.

        RECOMMENDED
            Staff may prepare recommendations.
            Building Manager or Global Admin must confirm.

        MANUAL
            Staff may select a suitable bed.
            Building Manager or Global Admin must confirm.

    Authorization scope:

        Global Admin:
            System-wide allocation authority.

        Building Manager:
            Initiate, approve, and manage allocations
            within their assigned building.

        Building Staff:
            Initiate and prepare allocations within their
            assigned building, but cannot independently
            approve or finalize approval-required allocations.

    This policy controls authorization only. It does not
    validate student eligibility, bed availability, gender
    compatibility, or allocation business rules.
    """

    # =========================================================
    # PRIVATE AUTHORIZATION HELPERS
    # =========================================================

    @classmethod
    def _can_operate_in_building(cls, actor, building) -> bool:
        """
        Check whether the actor can perform operational
        allocation activities within the specified building.

        Global Admin has system-wide access.

        Building Manager and Building Staff must belong
        to the specified building through their active
        Staff profile.
        """

        if building is None:
            return False

        return (
            cls.is_global_admin(actor)
            or cls.works_in_building(actor, building)
        )

    @classmethod
    def _can_approve_in_building(cls, actor, building) -> bool:
        """
        Check whether the actor has final allocation
        approval authority within the specified building.

        Only Building Managers and Global Admins qualify.
        """

        if building is None:
            return False

        return (
            cls.is_global_admin(actor)
            or cls.manages_building(actor, building)
        )

    # =========================================================
    # VIEW ALLOCATION
    # =========================================================

    @classmethod
    def can_view_allocation_requests(
        cls,
        actor,
        building=None,
    ) -> bool:
        """
        Determine whether an actor can view allocation requests.

        Global Admin can view requests across all buildings.

        Building Manager and Building Staff can only view
        requests belonging to their assigned building.

        A building must be supplied for non-admin actors.
        """

        if cls.is_global_admin(actor):
            return True

        return cls._can_operate_in_building(
            actor,
            building,
        )

    # =========================================================
    # INITIATE ALLOCATION
    # =========================================================

    @classmethod
    def can_initiate_allocation(
        cls,
        actor,
        building,
    ) -> bool:
        """
        Authorize the initiation of an allocation request.

        Applies to both individual and group allocations.

        Building Staff, Building Manager, and Global Admin
        may initiate allocations within their permitted scope.
        """

        return cls._can_operate_in_building(
            actor,
            building,
        )

    # =========================================================
    # AUTOMATIC ALLOCATION
    # =========================================================

    @classmethod
    def can_execute_automatic_allocation(
        cls,
        actor,
        building,
    ) -> bool:
        """
        Authorize execution of automatic allocation.

        Automatic allocation does not require a separate
        Building Manager approval.

        The system identifies and allocates a suitable bed
        after an authorized actor initiates the operation.

        All mandatory allocation validations still apply.
        """

        return cls._can_operate_in_building(
            actor,
            building,
        )

    # =========================================================
    # RECOMMENDED ALLOCATION
    # =========================================================

    @classmethod
    def can_prepare_recommended_allocation(
        cls,
        actor,
        building,
    ) -> bool:
        """
        Authorize preparation of recommended allocations.

        Building Staff may generate recommendations.

        Preparing recommendations does not reserve beds
        or create Assignments.
        """

        return cls._can_operate_in_building(
            actor,
            building,
        )

    @classmethod
    def can_confirm_recommended_allocation(
        cls,
        actor,
        building,
    ) -> bool:
        """
        Authorize confirmation of recommended allocations.

        Only Building Manager or Global Admin may confirm.

        Confirmation must trigger transactional
        revalidation before Assignment creation.
        """

        return cls._can_approve_in_building(
            actor,
            building,
        )

    # =========================================================
    # MANUAL ALLOCATION
    # =========================================================

    @classmethod
    def can_prepare_manual_allocation(
        cls,
        actor,
        building,
    ) -> bool:
        """
        Authorize manual bed selection.

        Building Staff may search for and select suitable beds.

        Selection alone does not reserve a bed or create
        an Assignment.
        """

        return cls._can_operate_in_building(
            actor,
            building,
        )

    @classmethod
    def can_confirm_manual_allocation(
        cls,
        actor,
        building,
    ) -> bool:
        """
        Authorize confirmation of manual allocations.

        Only Building Manager or Global Admin may confirm.

        The selected bed must be revalidated under the
        required accommodation locks before allocation.
        """

        return cls._can_approve_in_building(
            actor,
            building,
        )

    # =========================================================
    # GENERAL ALLOCATION APPROVAL
    # =========================================================

    @classmethod
    def can_approve_allocation(
        cls,
        actor,
        building,
    ) -> bool:
        """
        General approval permission for allocation workflows.

        Use this when the service does not need to distinguish
        between recommended and manual confirmation.

        Automatic allocation must not use this permission,
        because it does not require separate approval.
        """

        return cls._can_approve_in_building(
            actor,
            building,
        )
