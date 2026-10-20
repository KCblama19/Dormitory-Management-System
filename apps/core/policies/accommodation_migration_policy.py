from apps.core.policies import base

# APPLICATION EXCEPTIONS
from apps.core.exceptions import PermissionDenied

class AccommodationMigrationPolicy(base):
    
    @staticmethod
    def can_migrate_room(
        cls, actor, room
    ):
        if cls.is_global_admin(actor):
            return None
        
        floor = getattr(room, "floor", None)
        building = getattr(floor, "building", None)
        
        return cls.manages_building(
            actor,
            building,
        )