from .base import BasePolicy


class StaffPolicy(BasePolicy):
    """
    Authorization rules for Staff records.

    Global Admin:
        - create staff
        - manage all staff
        - assign staff to buildings
        - change roles
        - transfer staff

    Building Manager:
        - create staff for their building
        - manage staff assigned to their building
        - change staff role within their authority
        - transfer staff only within the boundaries allowed by
          the service/policy

    Building Staff:
        - does NOT manage staff records
    """

    @classmethod
    def can_view_staff(cls, actor, staff=None):
        if cls.is_global_admin(actor):
            return True

        if staff is None:
            return cls.is_building_manager(actor)

        building = getattr(staff, "building", None)

        return cls.manages_building(actor, building)

    @classmethod
    def can_create_staff(cls, actor, building):
        """
        Manager can create staff assigned to their own building.
        Admin can create anywhere.
        """
        if cls.is_global_admin(actor):
            return True

        return cls.manages_building(actor, building)

    @classmethod
    def can_update_staff(cls, actor, staff):
        if cls.is_global_admin(actor):
            return True

        return cls.manages_building(
            actor,
            getattr(staff, "building", None),
        )

    @classmethod
    def can_assign_staff_to_building(cls, actor, building):
        if cls.is_global_admin(actor):
            return True

        return cls.manages_building(actor, building)

    @classmethod
    def can_change_staff_role(cls, actor, staff):
        if cls.is_global_admin(actor):
            return True

        if not cls.manages_building(
            actor,
            getattr(staff, "building", None),
        ):
            return False

        return cls.is_building_manager(actor)

    @classmethod
    def can_activate_staff(cls, actor, staff):
        return cls.can_update_staff(actor, staff)

    @classmethod
    def can_deactivate_staff(cls, actor, staff):
        return cls.can_update_staff(actor, staff)

    @classmethod
    def can_transfer_staff(cls, actor, staff, new_building):
        """
        Global Admin can transfer staff anywhere.

        A Building Manager cannot move staff into a building they do
        not manage.
        """
        if cls.is_global_admin(actor):
            return True

        if not cls.is_building_manager(actor):
            return False

        current_building = getattr(staff, "building", None)

        return (
            current_building is not None
            and new_building is not None
            and current_building.pk
            == cls.managed_building(actor).pk
            and new_building.pk
            == cls.managed_building(actor).pk
        )