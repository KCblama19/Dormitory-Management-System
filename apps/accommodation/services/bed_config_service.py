from django.db import transaction
from django.core.exceptions import ValidationError

from apps.accommodation.models import BedConfiguration

# POLICIES
from apps.core.policies import AccommodationPolicy

# APPLICATION EXCEPTIONS
from apps.core.exceptions import (
    PermissionDenied,
    ValidationError,
)

class BedConfigurationService:

    @staticmethod
    @transaction.atomic
    def create_configuration(
        *,
        actor,
        name,
        bed_count,
        description="",
    ):
        
        if not AccommodationPolicy.can_create_bed_configuration(
            actor,
        ):
            raise PermissionDenied(
                "You do not have permission to create "
                "bed configuration."
            )

        if bed_count < 2:
            raise ValidationError(
                "A bed configuration must contain at least two beds."
            )

        if BedConfiguration.objects.filter(
            name=name
        ).exists():
            raise ValidationError(
                f"Bed configuration '{name}' already exists."
            )

        configuration = BedConfiguration(
            name=name.strip(),
            bed_count=bed_count,
            description=description.strip(),
            is_active=True,
        )

        try:
            configuration.full_clean()
            configuration.save()
        except ValidationError as exc:
            raise ValidationError(exc.message_dict)

        return configuration

    @staticmethod
    @transaction.atomic
    def update_configuration(
        *,
        actor,
        configuration,
        name=None,
        bed_count=None,
        description=None,
    ):
        if not AccommodationPolicy.can_update_bed_configuration(
            actor,
            configuration,
        ):
            raise PermissionDenied(
                "You do not have permission to update "
                "bed configuration."
            )

        if name is not None:
            configuration.name = name.strip()

        if bed_count is not None:

            if bed_count < 2:
                raise ValidationError(
                    "A bed configuration must contain at least two beds."
                )

            configuration.bed_count = bed_count

        if description is not None:
            configuration.description = description.strip()

        try:
            configuration.full_clean()
            configuration.save()
        except ValidationError as exc:
            raise ValidationError(exc.message_dict)

        return configuration

    @staticmethod
    @transaction.atomic
    def activate_configuration(*, actor, configuration):
        
        if not AccommodationPolicy.can_activate_bed_configuration(
            actor,
            configuration,
        ):
            raise PermissionDenied(
                "You do not have permission to activate "
                "bed configuration."
            )
            
        configuration.is_active = True
        configuration.full_clean()
        configuration.save(
            update_fields=["is_active"]
        )

        return configuration

    @staticmethod
    @transaction.atomic
    def deactivate_configuration(*, actor, configuration):
        
        if not AccommodationPolicy.can_deactivate_bed_configuration(
            actor,
            configuration,
        ):
            raise PermissionDenied(
                "You do not have permission to deactivate "
                "bed configuration."
            )
        if (
            configuration.default_for_buildings.exists()
            or configuration.floor_overrides.exists()
            or configuration.room_overrides.exists()
        ):
            raise ValidationError(
                "A bed configuration currently in use cannot "
                "be deactivated."
            )

        configuration.is_active = False

        configuration.full_clean()
        configuration.save(
            update_fields=["is_active"]
        )

        return configuration