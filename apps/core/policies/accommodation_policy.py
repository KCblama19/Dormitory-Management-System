from .base import BasePolicy


class AccommodationPolicy(BasePolicy):
    """
    Authorization rules for the physical accommodation hierarchy.

    Hierarchy:

        University
            ↓
        Campus
            ↓
        Building
            ↓
        Floor
            ↓
        Room
            ↓
        Bed
    """

    # =========================================================
    # University
    # =========================================================

    @classmethod
    def can_view_universities(cls, actor):
        return cls.is_global_admin(actor)

    @classmethod
    def can_create_university(cls, actor):
        return cls.is_global_admin(actor)

    @classmethod
    def can_update_university(cls, actor, university):
        return (
            cls.is_global_admin(actor)
            and university is not None
        )

    @classmethod
    def can_activate_university(cls, actor, university):
        return (
            cls.is_global_admin(actor)
            and university is not None
        )

    @classmethod
    def can_deactivate_university(cls, actor, university):
        return (
            cls.is_global_admin(actor)
            and university is not None
        )

    # =========================================================
    # Campus
    # =========================================================

    @classmethod
    def can_view_campuses(cls, actor):
        return cls.is_global_admin(actor)

    @classmethod
    def can_create_campus(cls, actor):
        return cls.is_global_admin(actor)

    @classmethod
    def can_update_campus(cls, actor, campus):
        return (
            cls.is_global_admin(actor)
            and campus is not None
        )

    @classmethod
    def can_activate_campus(cls, actor, campus):
        return (
            cls.is_global_admin(actor)
            and campus is not None
        )

    @classmethod
    def can_deactivate_campus(cls, actor, campus):
        return (
            cls.is_global_admin(actor)
            and campus is not None
        )

    # =========================================================
    # Building
    # =========================================================

    @classmethod
    def can_view_building(cls, actor, building=None):
        """
        Admin can see all buildings.

        Building Manager and Building Staff can see their assigned
        building.

        Students do not receive building-management access here.
        """
        if cls.is_global_admin(actor):
            return True

        if building is None:
            return cls.is_staff_account(actor)

        return cls.works_in_building(actor, building)

    @classmethod
    def can_create_building(cls, actor):
        """
        Buildings are system-level infrastructure.

        Only Global Admin creates them.
        """
        return cls.is_global_admin(actor)

    @classmethod
    def can_update_building(cls, actor, building):
        """
        Building Manager can manage the configuration of their own
        building.

        Building Staff cannot modify the building itself.
        """
        return (
            cls.is_global_admin(actor)
            or cls.manages_building(actor, building)
        )
        
    @classmethod
    def can_activate_building(cls, actor, building):
        return cls.manages_building(actor, building)
        
    @classmethod
    def can_deactivate_building(cls, actor, building):
        return cls.manages_building(actor, building)

    @classmethod
    def can_change_building_gender_policy(cls, actor, building):
        return cls.can_update_building(actor, building)

    @classmethod
    def can_change_building_population(cls, actor, building):
        return cls.can_update_building(actor, building)

    @classmethod
    def can_change_default_bed_configuration(cls, actor, building):
        return cls.can_update_building(actor, building)

    # =========================================================
    # Floor
    # =========================================================

    @classmethod
    def can_view_floor(cls, actor, floor=None):
        if cls.is_global_admin(actor):
            return True

        if floor is None:
            return cls.is_staff_account(actor)

        building = getattr(floor, "building", None)

        return cls.works_in_building(actor, building)

    @classmethod
    def can_create_floor(cls, actor, building):
        """
        Building Manager can create floors in their building.

        Building Staff manages existing floors operationally but
        does not create new physical floors.
        """
        return (
            cls.is_global_admin(actor)
            or cls.manages_building(actor, building)
        )

    @classmethod
    def can_update_floor(cls, actor, floor):
        """
        Manager can configure floors.

        Staff can perform operational floor management, but not
        higher-level configuration changes unless explicitly exposed
        by a narrower policy below.
        """
        if floor is None:
            return False
        
        if cls.is_global_admin(actor):
            return True

        return cls.manages_building(
            actor,
            getattr(floor, "building", None),
        )

    @classmethod
    def can_manage_floor_operations(cls, actor, floor):
        """
        Operational floor management.

        Both Manager and Building Staff can perform this.
        """
        if floor is None:
            return False
        
        if cls.is_global_admin(actor):
            return True

        return cls.works_in_building(
            actor,
            getattr(floor, "building", None),
        )
        
    @classmethod
    def can_activate_floor(cls, actor, floor):
        
        return cls.manages_building(
            actor,
            getattr(floor, "building", None)
        )
    
    @classmethod
    def can_deactivate_floor(cls, actor, floor):
                
        return cls.manages_building(
            actor,
            getattr(floor, "building", None)
        )
        
    @classmethod
    def can_set_floor_maintenance(cls, actor, floor):
        
        return cls.works_in_building(
            actor, 
            getattr(floor, "building", None)
        )
        
    @classmethod 
    def can_set_floor_restriction(cls, actor, floor):
        
        return cls.works_in_building(
            actor,
            getattr(floor, "building", None)
        )
        
    @classmethod
    def can_remove_floor_restriction(cls, actor, floor):
        
        return cls.works_in_building(
            actor,
            getattr(floor, "building", None)
        )
            
    @classmethod
    def can_change_floor_gender_configuration(cls, actor, floor):
        return cls.update_floor_configuration(actor, floor)

    @classmethod
    def can_change_floor_bed_configuration(cls, actor, floor):
        return cls.update_floor_configuration(actor, floor)

    @classmethod
    def can_manage_floor_restriction(cls, actor, floor):
        return cls.update_floor_configuration(actor, floor)

    @classmethod
    def update_floor_configuration(cls, actor, floor):
        if cls.is_global_admin(actor):
            return True

        return cls.manages_building(
            actor,
            getattr(floor, "building", None),
        )

    # =========================================================
    # Room
    # =========================================================

    @classmethod
    def can_view_room(cls, actor, room=None):
        if cls.is_global_admin(actor):
            return True

        if room is None:
            return cls.is_staff_account(actor)

        floor = getattr(room, "floor", None)
        building = getattr(floor, "building", None)

        return cls.works_in_building(actor, building)

    @classmethod
    def can_create_room(cls, actor, floor):
        """
        Manager creates rooms.

        Staff manages rooms but does not alter the physical
        structure by creating rooms.
        """
        if cls.is_global_admin(actor):
            return True

        return cls.manages_building(
            actor,
            getattr(floor, "building", None),
        )

    @classmethod
    def can_update_room(cls, actor, room):
        """
        Building Manager controls room configuration.

        Building Staff has operational access.
        """
        if cls.is_global_admin(actor):
            return True

        floor = getattr(room, "floor", None)
        building = getattr(floor, "building", None)

        return cls.manages_building(actor, building)

    @classmethod
    def can_manage_room_operations(cls, actor, room):
        """
        Both Manager and Staff can manage rooms operations.
        """
        if cls.is_global_admin(actor):
            return True

        floor = getattr(room, "floor", None)
        building = getattr(floor, "building", None)

        return cls.works_in_building(actor, building)

    # =========================================================
    # Bed Configuration
    # =========================================================

    @classmethod
    def can_view_bed_configurations(cls, actor):
        return cls.is_staff_account(actor) or cls.is_global_admin(actor)

    @classmethod
    def can_create_bed_configuration(cls, actor):
        """
        Bed configurations affect accommodation capacity and are
        configuration-level operations.
        """
        return (
            cls.is_global_admin(actor)
            or cls.is_building_manager(actor)
        )

    @classmethod
    def can_update_bed_configuration(cls, actor, configuration):
        if cls.is_global_admin(actor):
            return configuration is not None

        return cls.is_building_manager(actor)

    @classmethod
    def can_activate_bed_configuration(cls, actor, configuration):
        if cls.is_global_admin(actor):
            return configuration is not None

        return cls.is_building_manager(actor)

    @classmethod
    def can_deactivate_bed_configuration(cls, actor, configuration):
        if cls.is_global_admin(actor):
            return configuration is not None

        return cls.is_building_manager(actor)

    # =========================================================
    # Bed
    # =========================================================

    @classmethod
    def can_view_bed(cls, actor, bed=None):
        if cls.is_global_admin(actor):
            return True

        if bed is None:
            return cls.is_staff_account(actor)

        room = getattr(bed, "room", None)
        floor = getattr(room, "floor", None)
        building = getattr(floor, "building", None)

        return cls.works_in_building(actor, building)

    @classmethod
    def can_create_bed(cls, actor, room):
        """
        Manager creates physical beds.

        Staff manages existing beds.
        """
        if cls.is_global_admin(actor):
            return True

        floor = getattr(room, "floor", None)
        building = getattr(floor, "building", None)

        return cls.manages_building(actor, building)

    @classmethod
    def can_update_bed(cls, actor, bed):
        if cls.is_global_admin(actor):
            return True

        room = getattr(bed, "room", None)
        floor = getattr(room, "floor", None)
        building = getattr(floor, "building", None)

        return cls.works_in_building(actor, building)

    @classmethod
    def can_change_bed_status(cls, actor, bed):
        """
        Bed status is operational management.

        Both Manager and Building Staff can manage it.
        """
        return cls.can_update_bed(actor, bed)

    @classmethod
    def can_change_bed_position(cls, actor, bed):
        """
        Changing physical bed position changes room structure.

        Manager/Admin only.
        """
        if cls.is_global_admin(actor):
            return True

        room = getattr(bed, "room", None)
        floor = getattr(room, "floor", None)
        building = getattr(floor, "building", None)

        return cls.manages_building(actor, building)
    
    @staticmethod
    def can_manage_bed_operations(
        cls, actor, bed
    ):
        """
        Use for Admin, Building Manager, and Staff
        who work in and manage a building.
        """
        if cls.is_global_admin(actor):
            return True
        
        room = getattr(bed, "room", None)
        floor = getattr(room, "floor", None)
        building = getattr(floor, "building", None)
        
        return cls.works_in_building(
            actor, building
        )