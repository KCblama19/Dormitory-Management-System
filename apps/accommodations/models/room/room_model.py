from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

# Abstract Models
from apps.core.abstract_models.timestamp_models import TimeStampModel

# Manager
from apps.accommodations.models.managers.roomQuerySet import (
    ACTIVE_ASSIGNMENT_STATUSES,
    RoomQuerySet,
)


class Room(TimeStampModel):
    """
    Represents a physical residential room within a dormitory floor.

    Room identity is determined by:
        Floor + room position

    The room number and full room code are generated from the
    related Floor and Building rather than stored in the database.

    Room capacity is derived from its physical Bed records and
    their operational condition.

    Assignment records determine whether operational beds are
    reserved or occupied. Bed status alone does not determine
    whether a bed is available for another student.
    """

    floor = models.ForeignKey(
        "accommodation.Floor",
        on_delete=models.PROTECT,
        related_name="rooms",
        verbose_name=_("floor"),
        help_text=_("The floor where this room is located."),
    )

    position = models.PositiveIntegerField(
        verbose_name=_("room position"),
        help_text=_(
            "The local room position on the floor. "
            "Room positions start at 1."
        ),
    )

    # A room can override the bed configuration inherited from its floor.
    # When this is NULL, the floor's effective configuration is used.
    bed_configuration_override = models.ForeignKey(
        "accommodation.BedConfiguration",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="room_overrides",
        verbose_name=_("bed configuration override"),
        help_text=_(
            "Optional room-level override for the number and configuration "
            "of beds. When empty, the room inherits the Floor/Building "
            "configuration."
        ),
    )

    class Meta:
        ordering = ["floor", "position"]
        verbose_name = _("room")
        verbose_name_plural = _("rooms")

        constraints = [
            models.UniqueConstraint(
                fields=["floor", "position"],
                name="unique_room_position_per_floor",
            ),
            models.CheckConstraint(
                condition=Q(position__gte=1),
                name="room_position_gte_1",
            ),
        ]

    objects = RoomQuerySet.as_manager()

    def __str__(self):
        return self.full_code

    # ---------------------------------------------------------
    # ACCOMMODATION HIERARCHY
    # ---------------------------------------------------------

    @property
    def building(self):
        """
        Return the Building this room belongs to through its Floor.
        """
        return self.floor.building

    @property
    def room_number(self):
        """
        Generate the human-readable room number.

        The floor number is followed by the two-digit room position.

        Examples:
            Floor 1 + Position 1  -> 101
            Floor 1 + Position 23 -> 123
            Floor 12 + Position 3 -> 1203
            Floor 12 + Position 23 -> 1223
        """
        return f"{self.floor.floor_number}{self.position:02d}"

    @property
    def full_code(self):
        """
        Generate the complete room identifier.

        Examples:
            Building 21 / Floor 1 / Position 23 -> 21-123
            Building 21 / Floor 12 / Position 23 -> 21-1223
        """
        return f"{self.building.building_number}-{self.room_number}"

    @property
    def effective_bed_configuration(self):
        """
        Return the configuration that applies to this room.

        Configuration inheritance follows this order:

            Room override
                |
            Floor override
                |
            Building default
        """
        if self.bed_configuration_override_id:
            return self.bed_configuration_override

        return self.floor.effective_bed_configuration

    # ---------------------------------------------------------
    # PHYSICAL AND OPERATIONAL BED INVENTORY
    # ---------------------------------------------------------

    @property
    def physical_beds(self):
        """
        Return all non-retired physical beds belonging to this room.

        Maintenance and out-of-service beds remain part of the
        physical inventory because they have not been retired.
        """
        return self.beds.exclude(status="RETIRED")

    @property
    def physical_capacity(self):
        """
        Return the total physical bed capacity.

        Includes:
            AVAILABLE
            MAINTENANCE
            OUT_OF_SERVICE

        Excludes:
            RETIRED
        """
        return self._get_metric_or_count(
            "annotated_physical_capacity",
            self.physical_beds,
        )

    @property
    def operational_beds(self):
        """
        Return beds that are currently in operational condition.

        Bed.status describes physical condition, not whether a
        student has already been allocated the bed.

        A RESERVED or CHECKED_IN bed can still have AVAILABLE
        physical status.
        """
        return self.beds.filter(status="AVAILABLE")

    @property
    def operational_capacity(self):
        """
        Return the number of operational beds.

        This includes operational beds that are already reserved
        or occupied by students.
        """
        return self._get_metric_or_count(
            "annotated_operational_capacity",
            self.operational_beds,
        )

    # ---------------------------------------------------------
    # ASSIGNMENT AND OCCUPANCY METRICS
    # ---------------------------------------------------------

    @property
    def reserved_beds(self):
        """
        Return beds with an active RESERVED Assignment.

        A reserved bed has been allocated to a student, but the
        student has not completed check-in.
        """
        return self.beds.filter(
            assignments__status="RESERVED"
        ).distinct()

    @property
    def reserved_bed_count(self):
        """
        Return the number of beds currently reserved by students.
        """
        return self._get_metric_or_count(
            "annotated_reserved_bed_count",
            self.reserved_beds,
        )

    @property
    def occupied_beds(self):
        """
        Return beds with an active CHECKED_IN Assignment.

        This represents actual student occupancy, not simply
        an allocated accommodation commitment.
        """
        return self.beds.filter(
            assignments__status="CHECKED_IN"
        ).distinct()

    @property
    def occupied_bed_count(self):
        """
        Return the number of beds currently occupied by students.
        """
        return self._get_metric_or_count(
            "annotated_occupied_bed_count",
            self.occupied_beds,
        )

    @property
    def committed_beds(self):
        """
        Return beds with an active accommodation commitment.

        Both RESERVED and CHECKED_IN Assignments represent active
        commitments and prevent another student from receiving
        the same bed.
        """
        return self.beds.filter(
            assignments__status__in=ACTIVE_ASSIGNMENT_STATUSES
        ).distinct()

    @property
    def committed_bed_count(self):
        """
        Return the total number of beds with active Assignments.

        This includes reserved and occupied beds.
        """
        return self._get_metric_or_count(
            "annotated_committed_bed_count",
            self.committed_beds,
        )

    # ---------------------------------------------------------
    # AVAILABLE BED INVENTORY
    # ---------------------------------------------------------

    @property
    def available_beds(self):
        """
        Return operational beds without active Assignments.

        A bed must satisfy both conditions:

            1. Its physical status is AVAILABLE.
            2. It has no RESERVED or CHECKED_IN Assignment.

        This is a general room-level availability calculation.
        Student-specific allocation eligibility is handled by
        the accommodation allocation services.
        """
        return self.operational_beds.exclude(
            assignments__status__in=ACTIVE_ASSIGNMENT_STATUSES
        ).distinct()

    @property
    def available_bed_count(self):
        """
        Return the number of operational beds without active
        accommodation commitments.
        """
        return self._get_metric_or_count(
            "annotated_available_bed_count",
            self.available_beds,
        )

    # ---------------------------------------------------------
    # CAPACITY METRIC SUPPORT
    # ---------------------------------------------------------

    def _get_metric_or_count(self, annotation_name, queryset):
        """
        Use an existing queryset annotation when available.

        When the room was retrieved without capacity annotations,
        calculate the metric directly from its related records.

        This allows the same properties to work both for individual
        room operations and for optimized room listings.
        """
        annotated_value = getattr(self, annotation_name, None)

        if annotated_value is not None:
            return annotated_value

        return queryset.count()

    # ---------------------------------------------------------
    # MODEL VALIDATION
    # ---------------------------------------------------------

    def clean(self):
        """
        Validate room-specific business rules.

        Room positions must start at 1 and cannot exceed the
        maximum number of rooms configured for their floor.
        """
        super().clean()

        if self.position is not None and self.position < 1:
            raise ValidationError(
                {
                    "position": _(
                        "Room position must be at least 1."
                    )
                }
            )

        if not self.floor_id or self.position is None:
            return

        max_rooms = self.floor.max_rooms_per_floor

        if max_rooms is not None and self.position > max_rooms:
            raise ValidationError(
                {
                    "position": _(
                        "Room position cannot exceed the Floor's "
                        "maximum room count."
                    )
                }
            )