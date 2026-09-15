from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

# Abstract Models
from apps.abstract_models.timestamp_models import TimeStampModel


class Room(TimeStampModel):
    """
    Represents a physical residential room within a dormitory floor.

    Room identity is determined by:
        Floor + room position

    The human-readable room number and full room code are derived from
    the related Floor and Building rather than stored as database fields.

    Example:
        Building 21
        Floor 12
        Room position 23

        Room number:   1223
        Full room code: 21-1223
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

    # Optional room-level accommodation configuration override.
    #
    # When this is NULL, the room inherits the Floor's configuration.
    # The Floor itself falls back to the Building's default configuration.
    #
    # This relation assumes the accommodation configuration model will be
    # defined separately as part of the Building/Floor/Bed configuration.
    bed_configuration_override = models.ForeignKey(
        "accommodation.BedConfiguration",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="room_overrides",
        verbose_name=_("bed configuration override"),
        help_text=_(
            "Optional room-level override for the number/configuration "
            "of beds. When empty, the room inherits the Floor configuration."
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

    def __str__(self):
        return self.full_code

    @property
    def building(self):
        """
        Return the Building this room belongs to through its Floor.
        """
        return self.floor.building

    @property
    def room_number(self):
        """
        Return the human-readable room number, generated from
        the floor number + room position.

        The room position is formatted using two digits
        each so that the resulting identifier remains unambiguous for
        multi-digit floor numbers.
        Floor number is not zero-padded.

        Examples:
            Floor 1 + Position 1  -> 101
            Floor 1 + Position 23 -> 123
            Floor 12 + Position 3 -> 1203
            Floor 12 + Position 23 -> 1223
        """
        return f"{self.floor.number}{self.position:02d}"

    @property
    def full_code(self):
        """
        Return the complete room code including the Building number.

        Examples:
            Building 21 / Floor 1 / Position 23
            -> 21-123

            Building 21 / Floor 12 / Position 23
            -> 21-1223
        """
        return f"{self.building.number}-{self.room_number}"

    @property
    def active_beds(self):
        """
        Return the active physical beds belonging to this room.

        Physical Bed records are the source of truth for accommodation
        capacity rather than a capacity field stored directly on Room.
        """
        return self.beds.filter(is_active=True)

    @property
    def capacity(self):
        """
        Return the room's current physical accommodation capacity.

        Capacity is determined by active Bed records.
        """
        return self.active_beds.count()

    @property
    def occupancy(self):
        """
        Return the number of currently occupied beds.

        The actual occupied state will depend on the Bed/assignment model.
        This property assumes Bed exposes an `is_occupied` state.
        """
        return self.active_beds.filter(is_occupied=True).count()

    @property
    def available_beds(self):
        """
        Return the number of currently available active beds.
        """
        return self.active_beds.filter(is_occupied=False).count()

    @property
    def effective_bed_configuration(self):
        """
        Return the accommodation configuration that applies to this room.

        Inheritance order:

            Room override
                ↓
            Floor override
                ↓
            Building default

        The exact Floor/Building implementation will determine how the
        lower-level fallback is exposed.
        """
        if self.bed_configuration_override_id:
            return self.bed_configuration_override

        return self.floor.effective_bed_configuration

    def clean(self):
        """
        Validate room-specific business rules.

        Room position must not exceed the Floor's configured maximum number
        of rooms.
        """
        super().clean()

        if not self.floor_id:
            return

        if self.position < 1:
            raise ValidationError(
                {"position": _("Room position must be at least 1.")}
            )

        if self.floor.max_rooms is not None and self.position > self.floor.max_rooms:
            raise ValidationError(
                {
                    "position": _(
                        "Room position cannot exceed the Floor's "
                        "maximum room count."
                    )
                }
            )