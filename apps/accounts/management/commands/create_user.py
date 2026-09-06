from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
import getpass


User = get_user_model()


class Command(BaseCommand):
    """
    Secure interactive user creation wizard.

    Supports:
    - Student creation
    - Staff creation
    - Admin creation
    """

    def handle(self, *args, **options):
        self.stdout.write("\nUser Creation Wizard\n")

        role = self.ask_role()

        if role == "student":
            self.create_student()

        elif role == "staff":
            self.create_staff()

        elif role == "admin":
            self.create_admin()

        else:
            raise CommandError("Invalid role selected")

    # --------------------------
    # ROLE SELECTION
    # --------------------------
    def ask_role(self):
        self.stdout.write("Select role:")
        self.stdout.write("1. student")
        self.stdout.write("2. staff")
        self.stdout.write("3. admin")

        choice = input("\nRole: ").strip()

        mapping = {
            "1": "student",
            "2": "staff",
            "3": "admin",
            "student": "student",
            "staff": "staff",
            "admin": "admin",
        }

        role = mapping.get(choice.lower())

        if not role:
            raise CommandError("Invalid role selection")

        return role

    # --------------------------
    # STUDENT CREATION
    # --------------------------
    def create_student(self):
        student_id = input("Student ID: ").strip()

        if not student_id:
            raise CommandError("Student ID is required")

        user = User.objects.create_student(student_id=student_id)

        self.stdout.write(self.style.SUCCESS(f"Student created: {user}"))

    # --------------------------
    # STAFF FLOW
    # --------------------------
    def create_staff(self):
        email = input("Email: ").strip()
        staff_id = input("Staff ID (optional): ").strip() or None

        if not email and not staff_id:
            raise CommandError("Staff must have email or staff_id")

        password = self.ask_password()

        user = User.objects.create_staff(
            email=email or None,
            staff_id=staff_id,
        )

        user.set_password(password)
        user.save()

        self.stdout.write(self.style.SUCCESS(f"Staff created: {user}"))

    # --------------------------
    # ADMIN FLOW
    # --------------------------
    def create_admin(self):
        email = input("Email: ").strip()
        staff_id = input("Staff ID (optional): ").strip() or None

        if not email and not staff_id:
            raise CommandError("Admin must have email or staff_id")

        password = self.ask_password()

        user = User.objects.create_superuser(
            username=email or None,
            email=email or None,
            staff_id=staff_id,
            password=password,
        )

        self.stdout.write(self.style.SUCCESS(f"Admin created: {user}"))

    # --------------------------
    # SECURE PASSWORD HANDLING
    # --------------------------
    def ask_password(self):
        password = getpass.getpass("Password: ")
        confirm = getpass.getpass("Confirm Password: ")

        if not password or not confirm:
            raise CommandError("Password cannot be empty")

        if password != confirm:
            raise CommandError("Passwords do not match")

        if len(password) < 8:
            raise CommandError("Password must be at least 8 characters")

        return password