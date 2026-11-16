from django.core.exceptions import FieldDoesNotExist, ImproperlyConfigured
from django.db import models
from django.db.models import (
    CharField,
    Count,
    Exists,
    IntegerField,
    OuterRef,
    Q,
    Subquery,
    Value,
)
from django.db.models.functions import Cast, Coalesce


# An Assignment represents an active accommodation commitment
# while it is RESERVED or CHECKED_IN.
#
# Keep these values aligned with the Assignment status choices.
ACTIVE_ASSIGNMENT_STATUSES = (
    "RESERVED",
    "CHECKED_IN",
)


class RoomQuerySet(models.QuerySet):
    """
    Reusable queries for Room operations.

    This queryset handles room filtering, relationship loading,
    searching, and aggregated bed-capacity metrics.

    Room capacity is derived from Bed records.

    Assignment records determine whether operational beds are
    reserved, occupied, or available for another allocation.
    """

    # ---------------------------------------------------------
    # ROOM FILTERING
    # ---------------------------------------------------------

    def for_floor(self, floor):
        """
        Return rooms belonging to a particular floor.

        Accepts either a Floor instance or its primary key.
        """
        floor_id = getattr(floor, "pk", floor)

        return self.filter(
            floor_id=floor_id,
        )

    def for_building(self, building):
        """
        Return rooms belonging to a particular building.

        Accepts either a Building instance or its primary key.
        """
        building_id = getattr(building, "pk", building)

        return self.filter(
            floor__building_id=building_id,
        )

    # ---------------------------------------------------------
    # RELATIONSHIP LOADING
    # ---------------------------------------------------------

    def with_floor(self):
        """
        Load the room's floor and its accommodation hierarchy.

        This avoids additional queries when accessing:

            room.floor
            room.building
            room.floor.building.campus
        """
        return self.select_related(
            "floor",
            "floor__building",
            "floor__building__campus",
        )

    def with_configuration(self):
        """
        Load all configuration levels used by the room.

        Configuration inheritance:

            Room override
                |
            Floor override
                |
            Building default
        """
        return self.select_related(
            "bed_configuration_override",
            "floor__bed_configuration_override",
            "floor__building__default_bed_configuration",
        )

    def with_beds(self):
        """
        Prefetch the physical beds belonging to each room.

        This is useful when displaying individual bed information
        for multiple rooms.
        """
        return self.prefetch_related(
            "beds",
        )

    # ---------------------------------------------------------
    # CAPACITY METRIC ANNOTATIONS
    # ---------------------------------------------------------

    def with_capacity_metrics(self):
        """
        Annotate each room with its accommodation capacity metrics.

        Available annotations:

            annotated_physical_capacity
            annotated_operational_capacity
            annotated_reserved_bed_count
            annotated_occupied_bed_count
            annotated_committed_bed_count
            annotated_available_bed_count

        The Room model's corresponding properties automatically
        use these annotations when they are present.

        Distinct bed counts prevent duplicate counting when a bed
        has multiple historical Assignment records.

        Available beds require a separate NOT EXISTS check because
        a bed may have historical assignments as well as an active
        assignment.

        This method expects:

            Room -> Bed:
                reverse relation: beds

            Bed -> Assignment:
                reverse relation: assignments

            Assignment:
                foreign key to Bed
                status field
        """

        # Resolve the related models through Django's model metadata.
        # This avoids importing Assignment directly and creating
        # unnecessary cross-application import dependencies.
        try:
            beds_relation = self.model._meta.get_field("beds")

            bed_model = beds_relation.related_model

            assignments_relation = bed_model._meta.get_field(
                "assignments"
            )

        except FieldDoesNotExist as exc:
            raise ImproperlyConfigured(
                "Room capacity annotations require the Bed reverse "
                "relationship 'beds' and the Assignment reverse "
                "relationship 'assignments'."
            ) from exc

        assignment_model = assignments_relation.related_model

        # Resolve the actual foreign-key field names rather than
        # assuming that the database columns use default names.
        room_fk_name = beds_relation.field.name
        bed_fk_name = assignments_relation.field.name

        bed_status_path = f"{beds_relation.name}__status"

        assignment_status_path = (
            f"{beds_relation.name}__"
            f"{assignments_relation.name}__status"
        )

        bed_pk_path = f"{beds_relation.name}__pk"

        # -----------------------------------------------------
        # PHYSICAL AND OPERATIONAL METRICS
        # -----------------------------------------------------

        physical_capacity_filter = ~Q(
            **{
                bed_status_path: "RETIRED",
            }
        )

        operational_capacity_filter = Q(
            **{
                bed_status_path: "AVAILABLE",
            }
        )

        reserved_filter = Q(
            **{
                assignment_status_path: "RESERVED",
            }
        )

        occupied_filter = Q(
            **{
                assignment_status_path: "CHECKED_IN",
            }
        )

        committed_filter = Q(
            **{
                f"{assignment_status_path}__in":
                    ACTIVE_ASSIGNMENT_STATUSES,
            }
        )

        # -----------------------------------------------------
        # AVAILABLE BED SUBQUERY
        # -----------------------------------------------------

        # Find active assignments belonging to the current Bed.
        #
        # OuterRef("pk") refers to the Bed currently being examined
        # by the available-bed subquery.
        active_assignments = assignment_model._base_manager.filter(
            **{
                f"{bed_fk_name}_id": OuterRef("pk"),
            },
            status__in=ACTIVE_ASSIGNMENT_STATUSES,
        )

        # Count operational beds that do not have an active
        # accommodation commitment.
        #
        # This is a correlated subquery so each Room receives
        # its own available-bed count.
        available_bed_count = (
            bed_model._base_manager.filter(
                **{
                    f"{room_fk_name}_id": OuterRef("pk"),
                },
                status="AVAILABLE",
            )
            .annotate(
                _has_active_assignment=Exists(
                    active_assignments
                )
            )
            .filter(
                _has_active_assignment=False,
            )
            .order_by()
            .values(room_fk_name)
            .annotate(
                total=Count("pk"),
            )
            .values("total")[:1]
        )

        # -----------------------------------------------------
        # RETURN ANNOTATED ROOM QUERYSET
        # -----------------------------------------------------

        return self.annotate(
            annotated_physical_capacity=Count(
                bed_pk_path,
                filter=physical_capacity_filter,
                distinct=True,
            ),

            annotated_operational_capacity=Count(
                bed_pk_path,
                filter=operational_capacity_filter,
                distinct=True,
            ),

            annotated_reserved_bed_count=Count(
                bed_pk_path,
                filter=reserved_filter,
                distinct=True,
            ),

            annotated_occupied_bed_count=Count(
                bed_pk_path,
                filter=occupied_filter,
                distinct=True,
            ),

            annotated_committed_bed_count=Count(
                bed_pk_path,
                filter=committed_filter,
                distinct=True,
            ),

            annotated_available_bed_count=Coalesce(
                Subquery(
                    available_bed_count,
                    output_field=IntegerField(),
                ),
                Value(0),
                output_field=IntegerField(),
            ),
        )

    # ---------------------------------------------------------
    # ROOM SEARCH
    # ---------------------------------------------------------

    def search(self, term):
        """
        Search rooms using their position or accommodation hierarchy.

        Supported search fields:

            Room position
            Floor number
            Building number
            Building code

        Casting numeric values to text allows partial searches
        without depending on the underlying field types.
        """
        term = str(term or "").strip()

        if not term:
            return self

        return self.annotate(
            _room_position_search=Cast(
                "position",
                output_field=CharField(),
            ),
            _floor_number_search=Cast(
                "floor__floor_number",
                output_field=CharField(),
            ),
            _building_number_search=Cast(
                "floor__building__building_number",
                output_field=CharField(),
            ),
            _building_code_search=Cast(
                "floor__building__code",
                output_field=CharField(),
            ),
        ).filter(
            Q(_room_position_search__icontains=term)
            | Q(_floor_number_search__icontains=term)
            | Q(_building_number_search__icontains=term)
            | Q(_building_code_search__icontains=term)
        ).distinct()
