from django.db import transaction
from django.core.exceptions import ValidationError

from apps.accommodation.models import BedConfiguration


class BedConfigurationService:

    @staticmethod
    @transaction.atomic
    def create_configuration(
        *,
        name,
        bed_count,
        description="",
    ):

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
        configuration,
        name=None,
        bed_count=None,
        description=None,
    ):

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
    def activate_configuration(*, configuration):

        configuration.is_active = True
        configuration.full_clean()
        configuration.save(
            update_fields=["is_active"]
        )

        return configuration

    @staticmethod
    @transaction.atomic
    def deactivate_configuration(*, configuration):

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