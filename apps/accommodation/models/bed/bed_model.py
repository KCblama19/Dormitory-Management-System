from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils.translation import gettext_lazy as _

# Abstract Models
from apps.abstract_models.timestamp_models import TimeStampModel


class Bed(TimeStampModel):
    """
    Represents an individual physical accommodation unit within a Room.

    A Bed is the lowest-level physical accommodation entity in the
    accommodation hierarchy and is the unit that can ultimately be assigned
    to a student.

    Student assignment is intentionally NOT stored directly on this model.
    Assignments should be handled through the accommodation assignment model
    so that the system can preserve assignment history, enforce business
    rules, and prevent multiple active assignments to the same bed.
    """

    class Status(models.TextChoices):
        """
        Operational status of the physical bed.

        A bed can exist physically while being unavailable for assignment.
        """

        AVAILABLE = "AVAILABLE", _("Available")
        MAINTENANCE = "MAINTENANCE", _("Maintenance")
        OUT_OF_SERVICE = "OUT_OF_SERVICE", _("Out of service")

    room = models.ForeignKey(
        "accommodation.Room",
        on_delete=models.PROTECT,
        related_name="beds",
        verbose_name=_("room"),
        help_text=_("The room where this bed is physically located."),
    )

    position = models.PositiveIntegerField(
        verbose_name=_("bed position"),
        help_text=_(
            "The local position of this bed within the room. "
            "Bed positions start at 1."
        ),
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.AVAILABLE,
        verbose_name=_("status"),
        help_text=_(
            "The current operational status of the physical bed."
        ),
    )

    class Meta:
        ordering = ["room", "position"]
        verbose_name = _("bed")
        verbose_name_plural = _("beds")

        constraints = [
            models.UniqueConstraint(
                fields=["room", "position"],
                name="unique_bed_position_per_room",
            ),
            models.CheckConstraint(
                condition=Q(position__gte=1),
                name="bed_position_gte_1",
            ),
        ]

    def __str__(self):
        return self.code

    @property
    def building(self):
        """
        Return the Building this bed belongs to through the accommodation
        hierarchy.

        Bed → Room → Floor → Building
        """
        return self.room.floor.building

    @property
    def floor(self):
        """
        Return the Floor this bed belongs to through its Room.
        """
        return self.room.floor

    @property
    def room_number(self):
        """
        Return the derived room number for this bed.

        The Room model is responsible for generating the room number.
        """
        return self.room.room_number

    @property
    def room_code(self):
        """
        Return the complete derived room code.

        Example:

            Building 21
            Floor 12
            Room position 23

            → 21-1223
        """
        return self.room.full_code

    @property
    def code(self):
        """
        Return the human-readable bed identifier.

        The bed position is local to its Room.

        Examples:

            21-123-B01
            21-123-B02
            21-1223-B01

        The exact presentation can be changed later without changing the
        database identity of the Bed.
        """
        return f"{self.room.full_code}-B{self.position:02d}"

    @property
    def is_available(self):
        """
        Return whether the bed is operationally available.

        Availability here means that the physical bed is not blocked by
        maintenance or an out-of-service condition.

        Whether a student can actually be assigned to is taking care of
        by the accommodation assignment rules.
        """
        return self.status == self.Status.AVAILABLE

    @property
    def is_occupied(self):
        """
        Return whether this bed currently has an active student assignment.

        The actual assignment relationship is implemented by the
        accommodation assignment model.

        This property intentionally does not store an `is_occupied` field
        because occupancy is transactional state derived from assignments.
        """
        return self.assignments.filter(
            status="ACTIVE"
        ).exists()

    def clean(self):
        """
        Validate Bed-specific business rules.

        The bed position must be a positive integer and must not exceed
        the number of beds permitted by the Room's resolved configuration.
        """
        super().clean()

        if not self.room_id:
            return

        if self.position < 1:
            raise ValidationError(
                {
                    "position": _(
                        "Bed position must be at least 1."
                    )
                }
            )

        configuration = self.room.effective_bed_configuration

        if configuration is not None:
            max_beds = configuration.bed_count

            if self.position > max_beds:
                raise ValidationError(
                    {
                        "position": _(
                            "Bed position cannot exceed the number "
                            "of beds allowed by the room's effective "
                            "accommodation configuration."
                        )
                    }
                )