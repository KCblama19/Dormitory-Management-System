from datetime import date

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q

from apps.accounts.models import User
from apps.profiles.models.student.profile import Student
from apps.profiles.models.staff.staff_models import Staff


def find_claim_user(identifier: str) -> User | None:
    """
    Resolve a student/staff institutional identifier to its User account.

    Student IDs belong to Student.
    Staff IDs belong to Staff.
    """

    identifier = str(identifier).strip()

    if not identifier:
        return None

    student = (
        Student.objects
        .select_related("user")
        .filter(student_id=identifier)
        .first()
    )

    if student:
        return student.user

    staff = (
        Staff.objects
        .select_related("user")
        .filter(staff_id=identifier)
        .first()
    )

    if staff:
        return staff.user

    return None


def verifyUserCredentials(
    identifier: str,
    temp_password: str,
) -> User | None:
    """
    Verify the institutional identifier and temporary password.

    The identifier is resolved through the Student or Staff domain model,
    not directly through User.
    """

    user = find_claim_user(identifier)

    if user is None:
        return None

    if user.is_claimed:
        return None

    if not user.check_password(temp_password):
        return None

    if user.accountStatus != User.AccountStatus.ACTIVE:
        return None

    return user


def verifyUserDOB(
    user: User,
    date_of_birth: date,
) -> bool:
    """
    Verify the date of birth associated with the User account.
    """

    if user is None or date_of_birth is None:
        return False

    return user.date_of_birth == date_of_birth


@transaction.atomic
def updateUserPassword(
    user: User,
    new_password: str,
) -> User | None:
    """
    Complete the account claim.

    The account is marked claimed only after the new password
    has successfully been stored.
    """

    if user is None:
        return None

    user = (
        User.objects
        .select_for_update()
        .get(pk=user.pk)
    )

    if user.is_claimed:
        return None

    user.set_password(new_password)
    user.is_claimed = True

    user.save(
        update_fields=[
            "password",
            "is_claimed",
        ]
    )

    return user