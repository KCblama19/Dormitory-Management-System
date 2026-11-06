class BasePolicy:
    """
    Base class for authorization policies.

    This Policies answer one question:

        "Is this actor allowed to perform this operation?"

    This Policies do not:
    - modify database records
    - perform business operations
    - validate form data
    - handle HTTP requests
    """

    @staticmethod
    def _require_actor(actor):
        from django.core.exceptions import ImproperlyConfigured
        
        if actor is None:
            raise ImproperlyConfigured(
                "A policy check requires an actor."
            )

    @classmethod
    def is_authenticated(cls, actor):
        cls._require_actor(actor)
        return bool(
            getattr(actor, "is_authenticated", False)
        )

    @classmethod
    def is_active_account(cls, actor):
        """
        Check whether the User account is usable.

        accountStatus is the project's existing account-status field.
        """
        return (
            cls.is_authenticated(actor)
            and getattr(actor, "is_active", False)
            and getattr(actor, "accountStatus", None) == "active"
        )

    @classmethod
    def is_global_admin(cls, actor):
        return (
            cls.is_active_account(actor)
            and getattr(actor, "account_type", None) == "ADMIN"
        )

    @classmethod
    def is_student_account(cls, actor):
        return (
            cls.is_active_account(actor)
            and getattr(actor, "account_type", None) == "STUDENT"
        )

    @classmethod
    def is_staff_account(cls, actor):
        return (
            cls.is_active_account(actor)
            and getattr(actor, "account_type", None) == "STAFF"
        )

    @classmethod
    def staff_profile(cls, actor):
        """
        Return the Staff profile associated with the authenticated user.

        Returns None instead of raising because policy checks commonly need
        to answer a simple True/False question.
        """
        if not cls.is_staff_account(actor):
            return None

        return getattr(actor, "staff_profile", None)

    @classmethod
    def active_staff_profile(cls, actor):
        staff = cls.staff_profile(actor)

        if staff is None:
            return None

        if getattr(staff, "status", None) != "ACTIVE":
            return None

        return staff

    @classmethod
    def is_building_manager(cls, actor):
        staff = cls.active_staff_profile(actor)

        return (
            staff is not None
            and getattr(staff, "role", None) == "BUILDING_MANAGER"
        )

    @classmethod
    def is_building_staff(cls, actor):
        staff = cls.active_staff_profile(actor)

        return (
            staff is not None
            and getattr(staff, "role", None) == "BUILDING_STAFF"
        )

    @classmethod
    def managed_building(cls, actor):
        """
        Return the building assigned to the actor's Staff profile.
        """
        staff = cls.active_staff_profile(actor)

        if staff is None:
            return None

        return getattr(staff, "building", None)

    @classmethod
    def manages_building(cls, actor, building):
        """
        True when the actor is the Building Manager for this building.
        
        Global Admin can manage any building.
        A Building Manager can manage only their assigned building.
        Building Staff cannot manage building-level configuration
        
        There are plans to include a CAMPUS-level manager later.
        """
        if cls.is_global_admin(actor):
            return building is not None

        if not cls.is_building_manager(actor) or building is None:
            return False
        
        managed = cls.managed_building(actor)

        return (
            managed is not None
            and managed.pk == building.pk
        )    
            
    @classmethod
    def works_in_building(cls, actor, building):
        """
        True when the actor is an active staff member assigned to this
        building.

        This includes Global admin and both:
        - Building Manager
        - Building Staff
        """
        if cls.is_global_admin(actor):
            return building is not None
        
        if building is None:
            return False

        staff = cls.active_staff_profile(actor)

        if staff is None:
            return False

        assigned_building = getattr(staff, "building", None)

        return (
            assigned_building is not None
            and assigned_building.pk == building.pk
        )