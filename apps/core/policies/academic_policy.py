from .base import BasePolicy


class AcademicPolicy(BasePolicy):
    """
    Authorization rules for academic records.

    Academic records are intentionally separated from accommodation
    management.
    """

    # ---------------------------------------------------------
    # Academic Years
    # ---------------------------------------------------------

    @classmethod
    def can_view_academic_years(cls, actor):
        return cls.is_global_admin(actor)

    @classmethod
    def can_create_academic_year(cls, actor):
        return cls.is_global_admin(actor)

    @classmethod
    def can_update_academic_year(cls, actor, academic_year):
        return (
            cls.is_global_admin(actor)
            and academic_year is not None
        )

    @classmethod
    def can_activate_academic_year(cls, actor, academic_year):
        return (
            cls.is_global_admin(actor)
            and academic_year is not None
        )

    @classmethod
    def can_deactivate_academic_year(cls, actor, academic_year):
        return (
            cls.is_global_admin(actor)
            and academic_year is not None
        )

    @classmethod
    def can_set_current_academic_year(cls, actor, academic_year):
        return (
            cls.is_global_admin(actor)
            and academic_year is not None
        )

    # ---------------------------------------------------------
    # Enrollment
    # ---------------------------------------------------------

    @classmethod
    def can_view_enrollment(cls, actor, enrollment=None):
        """
        Students may view their own enrollment.

        Admin can view all enrollments.

        Staff/Building Managers do not receive academic enrollment
        administration authority.
        """
        if cls.is_global_admin(actor):
            return True

        if not cls.is_student_account(actor):
            return False

        if enrollment is None:
            return True

        student = getattr(enrollment, "student", None)

        if student is None:
            return False

        return (
            getattr(student, "user_id", None)
            == getattr(actor, "pk", None)
        )

    @classmethod
    def can_create_enrollment(cls, actor):
        return cls.is_global_admin(actor)

    @classmethod
    def can_update_enrollment(cls, actor, enrollment):
        return (
            cls.is_global_admin(actor)
            and enrollment is not None
        )

    @classmethod
    def can_change_enrollment_status(cls, actor, enrollment):
        return (
            cls.is_global_admin(actor)
            and enrollment is not None
        )

    @classmethod
    def can_set_primary_enrollment(cls, actor, enrollment):
        return (
            cls.is_global_admin(actor)
            and enrollment is not None
        )

    # ---------------------------------------------------------
    # Campus Assignment
    # ---------------------------------------------------------

    @classmethod
    def can_view_campus_assignment(cls, actor, assignment=None):
        if cls.is_global_admin(actor):
            return True

        if not cls.is_student_account(actor):
            return False

        if assignment is None:
            return True

        student = getattr(assignment, "student", None)

        return (
            student is not None
            and getattr(student, "user_id", None)
            == getattr(actor, "pk", None)
        )

    @classmethod
    def can_create_campus_assignment(cls, actor):
        return cls.is_global_admin(actor)

    @classmethod
    def can_transfer_campus_assignment(cls, actor, assignment):
        return (
            cls.is_global_admin(actor)
            and assignment is not None
        )

    @classmethod
    def can_end_campus_assignment(cls, actor, assignment):
        return (
            cls.is_global_admin(actor)
            and assignment is not None
        )