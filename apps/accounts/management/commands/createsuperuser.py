from django.contrib.auth.management.commands.createsuperuser import Command as BaseCommand


class Command(BaseCommand):
    """
    Custom createsuperuser command that forces:
    - email prompt
    - staff_id prompt
    """

    def add_arguments(self, parser):
        super().add_arguments(parser)

        parser.add_argument(
            "--staff_id",
            type=str,
            help="Optional staff ID for admin user"
        )
        
    def get_input_data(self, field, message, default=None):
        """
        This is where Django asks questions in CLI.
        We extend it to force email + staff_id.
        """

        if field.name == "email":
            email = input("Email (required for admin): ").strip()
            if not email:
                raise Exception("Email is required")
            return email

        return super().get_input_data(field, message, default)