from apps.core.policies.base import BasePolicy


class TransferPolicy(BasePolicy):
    @classmethod
    def can_request_transfer(cls, actor, *, source, destination_building):
        source_building = source.bed.room.floor.building

        if cls.is_global_admin(actor):
            return True

        if source_building.pk != destination_building.pk:
            return False

        if cls.is_student_account(actor):
            return source.student.user_id == actor.pk

        return cls.works_in_building(actor, source_building)

    @classmethod
    def can_approve_transfer(cls, actor, *, source, destination_building):
        source_building = source.bed.room.floor.building

        return cls.is_global_admin(actor) or (
            source_building.pk == destination_building.pk
            and cls.manages_building(actor, source_building)
        )
        
    @classmethod
    def can_complete_transfer(cls, actor, *, source, destination_building):
        return cls.can_approve_transfer(
            actor,
            source=source,
            destination_building=destination_building,
        )
        
    @classmethod
    def can_request_transfer_cancellation(cls, actor, *, source, destination_building):
        return (
            cls.is_student_account(actor)
            and source.student.user_id == actor.pk
            and source.bed.room.floor.building_id == destination_building.pk
        )

    @classmethod
    def can_cancel_transfer(cls, actor, *, source, destination_building):
        if cls.is_global_admin(actor):
            return True

        source_building = source.bed.room.floor.building

        return (
            source_building.pk == destination_building.pk
            and cls.works_in_building(actor, source_building)
        )